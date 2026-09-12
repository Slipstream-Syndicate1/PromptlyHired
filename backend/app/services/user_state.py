"""Attach per-user state to job cards in one batch, not per row.

Includes the cached match score. Reading it is a database join; it is NEVER
computed here. A card shows a percentage only once the user has explicitly
asked for an analysis of that job, and the figures shown are those of their
currently active resume.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, GeneratedDocument, Job, JobMatch, Resume, SavedJob, User, UserJob
from app.schemas import CompanyOut, JobOut


def decorate_jobs(db: Session, user: User, jobs: Iterable[Job]) -> list[JobOut]:
    jobs = list(jobs)
    if not jobs:
        return []

    job_ids = {j.id for j in jobs}
    company_ids = {j.company_id for j in jobs}

    saved_ids = set(
        db.scalars(
            select(SavedJob.job_id).where(
                SavedJob.user_id == user.id, SavedJob.job_id.in_(job_ids)
            )
        )
    )
    # Scoped to the active resume: a match computed against an old CV should
    # not be shown as if it described the current one.
    active = db.scalar(
        select(Resume.id)
        .where(Resume.user_id == user.id, Resume.is_active.is_(True))
        .order_by(Resume.uploaded_at.desc())
    )
    matches = {}
    if active is not None:
        matches = {
            m.job_id: m
            for m in db.scalars(
                select(JobMatch).where(
                    JobMatch.user_id == user.id,
                    JobMatch.job_id.in_(job_ids),
                    JobMatch.resume_id == active,
                )
            )
        }
    documented_ids = set(
        db.scalars(
            select(GeneratedDocument.job_id).where(
                GeneratedDocument.user_id == user.id,
                GeneratedDocument.job_id.in_(job_ids),
            )
        )
    )
    tracking = {
        uj.job_id: uj
        for uj in db.scalars(
            select(UserJob).where(UserJob.user_id == user.id, UserJob.job_id.in_(job_ids))
        )
    }

    companies = {
        c.id: c for c in db.scalars(select(Company).where(Company.id.in_(company_ids)))
    }

    return [
        JobOut(
            id=job.id,
            title=job.title,
            company=CompanyOut.model_validate(companies[job.company_id]),
            location=job.location,
            salary_range=job.salary_range,
            url=job.url,
            posted_date=job.posted_date,
            description=job.description,
            job_type=job.job_type,
            source_api=job.source_api,
            source_publisher=job.source_publisher,
            is_saved=job.id in saved_ids,
            has_match=job.id in matches,
            has_documents=job.id in documented_ids,
            match_percentage=(
                matches[job.id].match_percentage if job.id in matches else None
            ),
            requirements_met_count=(
                len(matches[job.id].requirements_met) if job.id in matches else None
            ),
            requirements_missing_count=(
                len(matches[job.id].requirements_missing) if job.id in matches else None
            ),
            status=tracking[job.id].status if job.id in tracking else None,
            applied_at=tracking[job.id].applied_at if job.id in tracking else None,
            status_updated_at=(
                tracking[job.id].status_updated_at if job.id in tracking else None
            ),
            next_event_at=tracking[job.id].next_event_at if job.id in tracking else None,
            next_event_type=(
                tracking[job.id].next_event_type if job.id in tracking else None
            ),
            next_event_note=(
                tracking[job.id].next_event_note if job.id in tracking else None
            ),
        )
        for job in jobs
    ]
