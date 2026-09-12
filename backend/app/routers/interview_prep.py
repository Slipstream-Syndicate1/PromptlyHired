"""Persisted, explicitly generated interview roadmaps and advisory conversation."""
import copy
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.db import engine
from app.deps import CurrentUser, DbSession
from app.models import InterviewPrep, PrepMessage, Job, UserJob, Resume, JobMatch
from app.interview_prep_schemas import InterviewContext, PrepSettings, PrepPlan, ChatMessage
from app.routers.calendar import owned_event
from app.services import interview_prep as service, ai
from app.rate_limit import SlidingWindowLimiter
from app.config import settings

router = APIRouter(prefix='/api', tags=['interview preparation'])
_limiter = SlidingWindowLimiter(settings.ai_calls_per_hour, 3600)

class GenerateInput(PrepSettings):
    client_request_id: UUID
    regenerate: bool = False

class MessageInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    client_request_id: UUID

class CompletionInput(BaseModel):
    completed: bool


@contextmanager
def exclusive(key):
    # Session advisory lock spans the provider call without holding an open DB
    # transaction. Its dedicated connection is always unlocked before pooling.
    number = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], 'big', signed=True)
    with engine.connect() as conn:
        acquired = conn.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key': number})
        conn.commit()
        if not acquired:
            raise HTTPException(409, 'Preparation is already being updated. Please try again shortly.')
        try:
            yield
        finally:
            conn.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': number})
            conn.commit()


def context_for(db, user, event):
    if event.type != 'interview' or not event.starts_at or not event.job_id:
        raise HTTPException(422, 'Complete the interview time and linked job in Calendar first.')
    owner = db.scalar(select(UserJob).where(UserJob.user_id == user.id, UserJob.job_id == event.job_id))
    if owner is None:
        raise HTTPException(404, 'Job not found in your workspace.')
    job = db.get(Job, event.job_id)
    if not (job.description or '').strip():
        raise HTTPException(422, 'Add a job description before preparing for this interview.')
    resume = db.scalar(select(Resume).where(Resume.user_id == user.id, Resume.is_active.is_(True)).order_by(Resume.id.desc()))
    match = db.scalar(select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job.id, JobMatch.resume_id == resume.id)) if resume else None
    context = InterviewContext(interview_id=event.id, application_id=str(owner.id), job_id=str(job.id), status=owner.status.value if owner.status else 'interview',
        starts_at=event.starts_at, timezone=event.timezone, schedule_revision=str(event.revision),
        job_title=job.title, company=job.company.name, job_description=job.description,
        resume_text=resume.extracted_text or '' if resume else '',
        match_summary=json.dumps({'met':match.requirements_met,'missing':match.requirements_missing}) if match else '')
    fingerprint = hashlib.sha256(json.dumps({'context':context.model_dump(mode='json'), 'resume_id':resume.id if resume else None,
        'day':datetime.now(timezone.utc).astimezone(ZoneInfo(event.timezone)).date().isoformat()}, sort_keys=True).encode()).hexdigest()
    return context, fingerprint


def plan_owned(db, user, plan_id, lock=False):
    query = select(InterviewPrep).where(InterviewPrep.id == plan_id, InterviewPrep.user_id == user.id)
    if lock:
        query = query.with_for_update()
    plan = db.scalar(query.execution_options(populate_existing=True))
    if plan is None:
        raise HTTPException(404, 'Preparation plan not found.')
    return plan


def messages(db, plan_id):
    rows = db.scalars(select(PrepMessage).where(PrepMessage.plan_id == plan_id).order_by(PrepMessage.created_at, PrepMessage.id))
    return [{'id':m.id,'role':m.role,'content':m.content} for m in rows]


def plan_out(db, plan, fingerprint=None):
    return {'id':plan.id, 'outdated':fingerprint is not None and fingerprint != plan.source_fingerprint,
        'dailyMinutes':plan.settings['daily_minutes'], 'summary':plan.content['summary'],
        'hasMoreDays':plan.content['has_more_days'], 'tasks':[
            {**task,'date':day['date'],'outcome':task['expected_outcome']} for day in plan.content['days'] for task in day['tasks']],
        'messages':messages(db, plan.id)}


def call_ai(user_id, fn, *args):
    retry = _limiter.check(str(user_id))
    if retry is not None:
        raise HTTPException(429, 'Preparation request limit reached. Try again later.', headers={'Retry-After':str(retry)})
    try:
        return fn(*args)
    except ai.AIRateLimited as exc:
        raise HTTPException(429, str(exc), headers={'Retry-After':'60'}) from exc
    except ai.AIUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ai.AIError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get('/interviews/{event_id}/prep')
def get_prep(event_id: str, user: CurrentUser, db: DbSession):
    event = owned_event(db, user, event_id)
    context, fingerprint = context_for(db, user, event)
    plan = db.scalar(select(InterviewPrep).where(InterviewPrep.event_id == event_id, InterviewPrep.user_id == user.id).order_by(InterviewPrep.created_at.desc(), InterviewPrep.id.desc()))
    return {'context':{'id':event.id,'title':context.job_title,'company':context.company,'startsAt':context.starts_at,
        'timezone':context.timezone,'interviewType':plan.settings['interview_type'] if plan else 'not_sure','hasResume':bool(context.resume_text)},
        'plan':plan_out(db, plan, fingerprint) if plan else None}


@router.post('/interviews/{event_id}/prep')
def generate(event_id: str, payload: GenerateInput, user: CurrentUser, db: DbSession):
    with exclusive(f'prep:{user.id}:{event_id}'):
        event = owned_event(db, user, event_id)
        context, fingerprint = context_for(db, user, event)
        request_id = str(payload.client_request_id)
        existing = db.scalar(select(InterviewPrep).where(InterviewPrep.user_id == user.id, InterviewPrep.request_id == request_id))
        opts = payload.model_dump(exclude={'client_request_id','regenerate'})
        if existing:
            if existing.event_id != event_id or existing.settings != opts:
                raise HTTPException(409, 'This request ID was already used for different preparation settings.')
            return plan_out(db, existing, fingerprint)
        latest = db.scalar(select(InterviewPrep).where(InterviewPrep.event_id == event_id, InterviewPrep.user_id == user.id).order_by(InterviewPrep.created_at.desc(), InterviewPrep.id.desc()))
        if latest and not payload.regenerate:
            return plan_out(db, latest, fingerprint)
        user_id = user.id
        db.commit()
        result = call_ai(user_id, service.generate_plan, context, PrepSettings(**opts))
        db.expire_all()
        event = owned_event(db, user, event_id, lock=True)
        _, current = context_for(db, user, event)
        if current != fingerprint:
            raise HTTPException(409, 'The interview or resume changed while preparing. Please try again.')
        plan = InterviewPrep(id=str(uuid4()), event_id=event_id, user_id=user.id, request_id=request_id,
            source_fingerprint=fingerprint, settings=opts, content=result.model_dump(mode='json'))
        db.add(plan)
        db.commit()
        return plan_out(db, plan, fingerprint)


@router.patch('/interview-prep/{plan_id}/tasks/{task_id}')
def complete(plan_id: str, task_id: str, payload: CompletionInput, user: CurrentUser, db: DbSession):
    plan = plan_owned(db, user, plan_id, lock=True)
    content = copy.deepcopy(plan.content)
    for day in content['days']:
        for task in day['tasks']:
            if task['id'] == task_id:
                task['completed'] = payload.completed
                plan.content = content
                db.commit()
                return {'completed':payload.completed}
    raise HTTPException(404, 'Preparation task not found.')


@router.get('/interview-prep/{plan_id}/messages')
def get_messages(plan_id: str, user: CurrentUser, db: DbSession):
    plan_owned(db, user, plan_id)
    return messages(db, plan_id)


@router.post('/interview-prep/{plan_id}/messages')
def ask(plan_id: str, payload: MessageInput, user: CurrentUser, db: DbSession):
    with exclusive(f'chat:{user.id}:{plan_id}'):
        plan = plan_owned(db, user, plan_id)
        request_id = str(payload.client_request_id)
        existing = db.scalar(select(PrepMessage).where(PrepMessage.plan_id == plan_id, PrepMessage.request_id == request_id, PrepMessage.role == 'assistant'))
        if existing:
            question = db.scalar(select(PrepMessage).where(PrepMessage.plan_id == plan_id, PrepMessage.request_id == request_id, PrepMessage.role == 'user'))
            if question.content != payload.message:
                raise HTTPException(409, 'This request ID was already used for another question.')
            return {'id':existing.id,'role':existing.role,'content':existing.content}
        context, _ = context_for(db, user, owned_event(db, user, plan.event_id))
        history = [ChatMessage(role=m['role'],content=m['content']) for m in messages(db, plan_id)[-10:]]
        snapshot = PrepPlan.model_validate(plan.content)
        user_id = user.id
        db.commit()
        answer = call_ai(user_id, service.answer_question, context, snapshot, payload.message, history)
        plan_owned(db, user, plan_id, lock=True)
        now = datetime.now(timezone.utc)
        question = PrepMessage(id=str(uuid4()),plan_id=plan_id,request_id=request_id,role='user',content=payload.message,created_at=now)
        from datetime import timedelta
        reply = PrepMessage(id=str(uuid4()),plan_id=plan_id,request_id=request_id,role='assistant',content=answer.answer,created_at=now+timedelta(microseconds=1))
        db.add_all([question,reply])
        db.commit()
        return {'id':reply.id,'role':reply.role,'content':reply.content}
