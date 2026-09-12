"""Application tracking: what you applied to, where it stands, and what the
employer said.

Application holds only the current status. Every status change writes an
ApplicationEvent, and that history is how responses - interview invitations,
rejections, offers - are monitored over time. Communications log individual
exchanges with the employer about one application.

Everything is scoped to the signed-in user. Another user's application is a
404, never a 403, so its existence is not confirmed.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbSession
from app.models import (
    Application,
    ApplicationEvent,
    ApplicationStatus,
    Communication,
    Job,
    Resume,
)
from app.routers.jobs import _get_or_create_company
from app.schemas import (
    ApplicationCreate,
    ApplicationEventOut,
    ApplicationOut,
    ApplicationStats,
    ApplicationUpdate,
    CommunicationCreate,
    CommunicationOut,
    CommunicationUpdate,
)
from app.services.user_state import decorate_jobs

router = APIRouter(prefix="/api/applications", tags=["applications"])
communications_router = APIRouter(prefix="/api/communications", tags=["applications"])

# Jobs for applications sent elsewhere, entered by hand rather than pasted.
SOURCE_MANUAL = "manual"
# Still waiting on the employer: the stages where following up makes sense.
OPEN_STATUSES = frozenset(
    {ApplicationStatus.applied, ApplicationStatus.online_assessment, ApplicationStatus.interview}
)
# With no next-action date set, an open application this quiet needs a nudge.
FOLLOW_UP_AFTER_DAYS = 14

DUPLICATE_DETAIL = "You're already tracking an application for this job."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found(what: str = "Application") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found.")


def _load(db, user, application_id: int) -> Application:
    row = db.scalar(
        select(Application)
        .options(selectinload(Application.job).selectinload(Job.company))
        .where(Application.id == application_id, Application.user_id == user.id)
    )
    if row is None:
        raise _not_found()
    return row


def _check_resume(db, user, resume_id: int | None) -> None:
    if resume_id is None:
        return
    owned = db.scalar(select(Resume.id).where(Resume.id == resume_id, Resume.user_id == user.id))
    if owned is None:
        raise _not_found("Resume")


def _needs_follow_up(
    current: ApplicationStatus, next_action_date: date | None, days_quiet: int, today: date
) -> bool:
    if current not in OPEN_STATUSES:
        return False
    if next_action_date is not None:
        return next_action_date <= today
    return days_quiet >= FOLLOW_UP_AFTER_DAYS


def _days_since(moment: datetime, now: datetime) -> int:
    return max(0, (now - moment).days)


def _to_out(db, user, rows: list[Application]) -> list[ApplicationOut]:
    if not rows:
        return []
    jobs = decorate_jobs(db, user, [row.job for row in rows])
    counts = dict(
        db.execute(
            select(Communication.application_id, func.count())
            .where(Communication.application_id.in_([row.id for row in rows]))
            .group_by(Communication.application_id)
        ).all()
    )
    now = _now()
    out = []
    for row, job in zip(rows, jobs):
        days = _days_since(row.status_updated_at, now)
        out.append(
            ApplicationOut(
                id=row.id,
                job=job,
                status=row.status,
                applied_date=row.applied_date,
                status_updated_at=row.status_updated_at,
                notes=row.notes,
                next_action=row.next_action,
                next_action_date=row.next_action_date,
                resume_id=row.resume_id,
                created_at=row.created_at,
                updated_at=row.updated_at,
                days_since_update=days,
                needs_follow_up=_needs_follow_up(row.status, row.next_action_date, days, now.date()),
                communications_count=counts.get(row.id, 0),
            )
        )
    return out


def application_for_job(db, user, job_id: int) -> ApplicationOut | None:
    """The user's application for one job, shown on the job detail view."""
    row = db.scalar(
        select(Application)
        .options(selectinload(Application.job).selectinload(Job.company))
        .where(Application.user_id == user.id, Application.job_id == job_id)
    )
    return _to_out(db, user, [row])[0] if row else None


# --- Applications -----------------------------------------------------------


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    user: CurrentUser,
    db: DbSession,
    status_filter: ApplicationStatus | None = Query(default=None, alias="status"),
) -> list[ApplicationOut]:
    query = (
        select(Application)
        .options(selectinload(Application.job).selectinload(Job.company))
        .where(Application.user_id == user.id)
        .order_by(Application.status_updated_at.desc(), Application.id.desc())
    )
    if status_filter is not None:
        query = query.where(Application.status == status_filter)
    return _to_out(db, user, list(db.scalars(query)))


# Declared before /{application_id} so "stats" is never parsed as an id.
@router.get("/stats", response_model=ApplicationStats)
def application_stats(user: CurrentUser, db: DbSession) -> ApplicationStats:
    rows = db.execute(
        select(Application.status, Application.next_action_date, Application.status_updated_at)
        .where(Application.user_id == user.id)
    ).all()

    by_status = {s.value: 0 for s in ApplicationStatus}
    now = _now()
    follow_ups = 0
    for current, next_action_date, status_updated_at in rows:
        by_status[current.value] += 1
        days = _days_since(status_updated_at, now)
        follow_ups += _needs_follow_up(current, next_action_date, days, now.date())

    total = len(rows)
    considered = total - by_status[ApplicationStatus.withdrawn.value]
    heard_back = considered - by_status[ApplicationStatus.applied.value]
    return ApplicationStats(
        total=total,
        by_status=by_status,
        active=sum(by_status[s.value] for s in OPEN_STATUSES),
        offers=by_status[ApplicationStatus.offer.value],
        needs_follow_up=follow_ups,
        response_rate_pct=round(100 * heard_back / considered) if considered else None,
    )


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate, user: CurrentUser, db: DbSession
) -> ApplicationOut:
    # Validate everything before writing, so a bad resume_id never leaves an
    # orphaned manual job behind.
    _check_resume(db, user, payload.resume_id)

    if payload.job_id is not None:
        job = db.get(Job, payload.job_id)
        if job is None:
            raise _not_found("Job")
        already = db.scalar(
            select(Application.id).where(
                Application.user_id == user.id, Application.job_id == job.id
            )
        )
        if already is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_DETAIL)
    else:
        company = _get_or_create_company(db, payload.company)
        job = Job(
            company_id=company.id,
            title=payload.position[:500],
            location=payload.location,
            url=payload.url,
            source_api=SOURCE_MANUAL,
            # Manual entries have no natural identity to deduplicate on.
            external_id=uuid.uuid4().hex,
        )
        db.add(job)
        db.flush()

    resume_id = payload.resume_id
    if resume_id is None:
        # Record the CV that was current when the application went out.
        resume_id = db.scalar(
            select(Resume.id).where(Resume.user_id == user.id, Resume.is_active.is_(True))
        )

    row = Application(
        user_id=user.id,
        job_id=job.id,
        resume_id=resume_id,
        status=payload.status,
        applied_date=payload.applied_date or date.today(),
        notes=payload.notes,
        next_action=payload.next_action,
        next_action_date=payload.next_action_date,
    )
    row.events.append(ApplicationEvent(from_status=None, to_status=payload.status))
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Two requests racing past the duplicate check.
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_DETAIL)

    return _to_out(db, user, [_load(db, user, row.id)])[0]


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(application_id: int, user: CurrentUser, db: DbSession) -> ApplicationOut:
    return _to_out(db, user, [_load(db, user, application_id)])[0]


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: int, payload: ApplicationUpdate, user: CurrentUser, db: DbSession
) -> ApplicationOut:
    row = _load(db, user, application_id)
    data = payload.model_dump(exclude_unset=True)
    note = data.pop("note", None)
    new_status = data.pop("status", None)
    changed = new_status is not None and new_status != row.status

    if note and not changed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "A note records what changed the status. To log a message without "
                "a status change, add a communication."
            ),
        )
    if "resume_id" in data:
        _check_resume(db, user, data["resume_id"])

    for field, value in data.items():
        setattr(row, field, value)

    if changed:
        row.events.append(
            ApplicationEvent(from_status=row.status, to_status=new_status, note=note)
        )
        row.status = new_status
        row.status_updated_at = _now()

    db.commit()
    return _to_out(db, user, [_load(db, user, row.id)])[0]


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: int, user: CurrentUser, db: DbSession) -> Response:
    db.delete(_load(db, user, application_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{application_id}/events", response_model=list[ApplicationEventOut])
def list_events(
    application_id: int, user: CurrentUser, db: DbSession
) -> list[ApplicationEvent]:
    row = _load(db, user, application_id)
    return list(
        db.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == row.id)
            .order_by(ApplicationEvent.changed_at, ApplicationEvent.id)
        )
    )


# --- Communications ---------------------------------------------------------


@router.get("/{application_id}/communications", response_model=list[CommunicationOut])
def list_communications(
    application_id: int, user: CurrentUser, db: DbSession
) -> list[Communication]:
    row = _load(db, user, application_id)
    return list(
        db.scalars(
            select(Communication)
            .where(Communication.application_id == row.id)
            .order_by(Communication.occurred_at.desc(), Communication.id.desc())
        )
    )


@router.post(
    "/{application_id}/communications",
    response_model=CommunicationOut,
    status_code=status.HTTP_201_CREATED,
)
def add_communication(
    application_id: int, payload: CommunicationCreate, user: CurrentUser, db: DbSession
) -> Communication:
    row = _load(db, user, application_id)
    communication = Communication(
        application_id=row.id,
        kind=payload.kind,
        direction=payload.direction,
        occurred_at=payload.occurred_at or _now(),
        contact_name=payload.contact_name,
        subject=payload.subject,
        summary=payload.summary,
    )
    db.add(communication)
    db.commit()
    db.refresh(communication)
    return communication


def _load_communication(db, user, communication_id: int) -> Communication:
    communication = db.scalar(
        select(Communication)
        .join(Communication.application)
        .where(Communication.id == communication_id, Application.user_id == user.id)
    )
    if communication is None:
        raise _not_found("Communication")
    return communication


@communications_router.patch("/{communication_id}", response_model=CommunicationOut)
def update_communication(
    communication_id: int, payload: CommunicationUpdate, user: CurrentUser, db: DbSession
) -> Communication:
    communication = _load_communication(db, user, communication_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(communication, field, value)
    db.commit()
    db.refresh(communication)
    return communication


@communications_router.delete("/{communication_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_communication(communication_id: int, user: CurrentUser, db: DbSession) -> Response:
    db.delete(_load_communication(db, user, communication_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
