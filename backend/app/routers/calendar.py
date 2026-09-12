"""Account-owned calendar records used by interview preparation."""
from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import CalendarEvent, UserJob

router = APIRouter(prefix='/api/calendar', tags=['calendar'])

class EventInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID | None = None
    title: str = Field(min_length=1, max_length=250)
    date: date
    time: str | None = Field(default='', pattern=r'^([01]\d|2[0-3]):[0-5]\d$|^$')
    type: Literal['deadline', 'interview', 'offer', 'other']
    notes: str = Field(default='', max_length=500)
    job_id: int | None = None
    timezone: str = Field(max_length=100)


def owned_event(db, user, event_id, *, lock=False):
    query = select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.user_id == user.id)
    if lock:
        query = query.with_for_update()
    event = db.scalar(query.execution_options(populate_existing=True))
    if event is None:
        raise HTTPException(404, 'Calendar event not found.')
    return event


def validated(db, user, data):
    if not data.title.strip():
        raise HTTPException(422, 'Enter an event name.')
    if data.job_id is not None and db.scalar(select(UserJob.id).where(UserJob.user_id == user.id, UserJob.job_id == data.job_id)) is None:
        raise HTTPException(404, 'Job not found in your workspace.')
    try:
        zone = ZoneInfo(data.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, 'Choose a valid timezone.') from None
    starts_at = None
    if data.time:
        local = datetime.fromisoformat(f'{data.date.isoformat()}T{data.time}').replace(tzinfo=zone)
        starts_at = local.astimezone(timezone.utc)
        if starts_at.astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
            raise HTTPException(422, 'This time does not exist due to daylight saving time. Choose another time.')
        if local.replace(fold=1).utcoffset() != local.utcoffset():
            raise HTTPException(422, 'This time occurs twice due to daylight saving time. Choose an unambiguous time.')
    values = data.model_dump(exclude={'id'})
    values.update(title=data.title.strip(), time=data.time or '', starts_at=starts_at)
    return values


def event_out(event):
    return {name: getattr(event, name) for name in ('id','title','date','time','type','notes','job_id','timezone','starts_at','revision')}


@router.get('')
def list_events(user: CurrentUser, db: DbSession):
    return [event_out(e) for e in db.scalars(select(CalendarEvent).where(CalendarEvent.user_id == user.id).order_by(CalendarEvent.date, CalendarEvent.time))]


@router.post('', status_code=201)
def create_event(payload: EventInput, user: CurrentUser, db: DbSession):
    if payload.id:
        existing = db.get(CalendarEvent, str(payload.id))
        if existing:
            if existing.user_id != user.id:
                raise HTTPException(409, 'This browser event has already been imported by another account.')
            return event_out(existing)
    values = validated(db, user, payload)
    event = CalendarEvent(id=str(payload.id or uuid4()), user_id=user.id, revision=1, **values)
    db.add(event)
    db.commit()
    return event_out(event)


@router.patch('/{event_id}')
def update_event(event_id: str, payload: dict, user: CurrentUser, db: DbSession):
    from pydantic import ValidationError
    event = owned_event(db, user, event_id, lock=True)
    if 'id' in payload or set(payload) - set(EventInput.model_fields):
        raise HTTPException(422, 'Unsupported event field.')
    current = {k: getattr(event, k) for k in EventInput.model_fields if k != 'id'}
    try:
        parsed = EventInput.model_validate({**current, **payload})
    except ValidationError:
        raise HTTPException(422, 'Enter valid calendar event details.') from None
    values = validated(db, user, parsed)
    for key, value in values.items():
        setattr(event, key, value)
    event.revision += 1
    db.commit()
    return event_out(event)


@router.delete('/{event_id}', status_code=204)
def delete_event(event_id: str, user: CurrentUser, db: DbSession):
    db.delete(owned_event(db, user, event_id, lock=True))
    db.commit()
    return Response(status_code=204)
