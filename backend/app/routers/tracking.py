"""The Tracking page: Wishlist, then a kanban of Applied / Interview / Offer /
Rejected.

This app never applies on a user's behalf - it prepares them for an
application they submit on the original posting. So a job only reaches a
status column once the user tells it they applied, and every later move
(Interview, Offer, Rejected) is the user reporting what happened, not
something derived.

Status lives on UserJob rather than a separate table: it is inherently a
per-user fact about a job, exactly like `added_at` and `SavedJob` already are.

Wishlist is not a new concept: it is the existing Saved feature (SavedJob),
filtered to jobs that don't have a status yet. Reusing it rather than adding
a second "interested in this job" mechanism means the Saved page and the
Wishlist column are always looking at the same data.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbSession
from app.models import Job, SavedJob, UserJob, utcnow
from app.schemas import ApplicationStatusUpdate, JobOut, NextEventUpdate
from app.services.user_state import decorate_jobs

router = APIRouter(prefix="/api/tracking", tags=["tracking"])


def _load_user_job(db, user, job_id: int) -> UserJob:
    user_job = db.scalar(
        select(UserJob).where(UserJob.user_id == user.id, UserJob.job_id == job_id)
    )
    if user_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return user_job


def _decorated(db, user, job_id: int) -> JobOut:
    job = db.scalar(select(Job).options(selectinload(Job.company)).where(Job.id == job_id))
    return decorate_jobs(db, user, [job])[0]


@router.get("", response_model=list[JobOut])
def list_tracked(user: CurrentUser, db: DbSession) -> list[JobOut]:
    """Every job with a status, plus every saved-but-not-yet-applied job.

    The board sorts client-side (by recency, applied date, company, or
    title), so no ordering is imposed here - it would only be discarded.
    """
    tracked_ids = set(
        db.scalars(
            select(UserJob.job_id).where(
                UserJob.user_id == user.id, UserJob.status.is_not(None)
            )
        )
    )
    saved_ids = set(db.scalars(select(SavedJob.job_id).where(SavedJob.user_id == user.id)))
    job_ids = tracked_ids | saved_ids
    if not job_ids:
        return []

    jobs = list(
        db.scalars(
            select(Job).options(selectinload(Job.company)).where(Job.id.in_(job_ids))
        )
    )
    return decorate_jobs(db, user, jobs)


@router.patch("/{job_id}", response_model=JobOut)
def set_status(
    job_id: int, payload: ApplicationStatusUpdate, user: CurrentUser, db: DbSession
) -> JobOut:
    """Move a job to a stage, or clear it (`status: null`) to stop tracking it.

    The job must already be in the user's workspace - Tracking is a state on
    top of a job they added, not a second way to add one.
    """
    user_job = _load_user_job(db, user, job_id)

    if payload.status is None:
        user_job.status = None
        user_job.applied_at = None
        user_job.status_updated_at = None
    else:
        # The first status ever set is the application date; later moves
        # (Interview, Offer, Rejected) must not overwrite it.
        if user_job.applied_at is None:
            user_job.applied_at = utcnow()
        user_job.status = payload.status
        user_job.status_updated_at = utcnow()
    db.commit()

    return _decorated(db, user, job_id)


@router.patch("/{job_id}/event", response_model=JobOut)
def set_event(
    job_id: int, payload: NextEventUpdate, user: CurrentUser, db: DbSession
) -> JobOut:
    """Set or clear the next thing coming up for this job - an interview, a
    deadline, or a reminder. Independent of `status`: you can flag a deadline
    before you've even applied, or after Offer.
    """
    user_job = _load_user_job(db, user, job_id)

    user_job.next_event_at = payload.next_event_at
    # A cleared date means no event at all - don't leave an orphaned type/note.
    user_job.next_event_type = payload.next_event_type if payload.next_event_at else None
    user_job.next_event_note = payload.next_event_note if payload.next_event_at else None
    db.commit()

    return _decorated(db, user, job_id)
