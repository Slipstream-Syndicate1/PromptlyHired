"""Tailored resume / cover letter generation, editing, and the History view."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.deps import CurrentUser, DbSession
from app.models import Application, DocumentKind, GeneratedDocument, Job, JobMatch
from app.rate_limit import ai_rate_limit
from app.routers.jobs import require_description
from app.routers.resumes import require_active_resume
from app.schemas import (
    DocumentGenerateRequest,
    DocumentUpdate,
    GeneratedDocumentOut,
    HistoryEntryOut,
)
from app.services import ai, tailored_resume
from app.services.user_state import decorate_jobs

router = APIRouter(prefix="/api", tags=["documents"])


def _resume_source_text(resume) -> str:
    """Turn the editable master resume into model input without changing its schema."""
    master = resume.master_content
    if not master:
        return resume.extracted_text or ""

    lines: list[str] = []
    for key in ("full_name", "headline", "contact_line", "summary"):
        value = str(master.get(key) or "").strip()
        if value:
            lines.append(value)
    for section in master.get("sections") or []:
        heading = str(section.get("heading") or "").strip()
        if heading:
            lines.append(f"\n{heading}")
        for entry in section.get("entries") or []:
            left = " | ".join(
                str(entry.get(key) or "").strip()
                for key in ("title", "meta")
                if str(entry.get(key) or "").strip()
            )
            right = str(entry.get("right") or "").strip()
            if left or right:
                lines.append(" - ".join(part for part in (left, right) if part))
            subtitle = str(entry.get("subtitle") or "").strip()
            subtitle_right = str(entry.get("subtitle_right") or "").strip()
            if subtitle or subtitle_right:
                lines.append(" - ".join(part for part in (subtitle, subtitle_right) if part))
            for bullet in entry.get("bullets") or []:
                bullet = str(bullet).strip()
                if bullet:
                    lines.append(f"- {bullet}")
        for bullet in section.get("bullets") or []:
            bullet = str(bullet).strip()
            if bullet:
                lines.append(f"- {bullet}")
    skills = [str(skill).strip() for skill in master.get("skills") or [] if str(skill).strip()]
    if skills:
        lines.append("\nTechnical Skills")
        lines.extend(skills)
    return "\n".join(lines).strip() or (resume.extracted_text or "")


def _match_summary(match: JobMatch | None) -> str:
    if match is None:
        return ""
    met = ", ".join(match.requirements_met[:10])
    missing = ", ".join(match.requirements_missing[:10])
    return f"Already satisfied: {met or 'none identified'}\nGaps: {missing or 'none identified'}"


@router.post(
    "/jobs/{job_id}/documents",
    response_model=GeneratedDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ai_rate_limit)],
)
def generate_document(
    job_id: int, payload: DocumentGenerateRequest, user: CurrentUser, db: DbSession
) -> GeneratedDocument:
    """Generate a tailored document. Always creates a draft, never sends anything."""
    job = db.scalar(select(Job).options(selectinload(Job.company)).where(Job.id == job_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    require_description(job)

    resume = require_active_resume(db, user)
    match = db.scalar(
        select(JobMatch).where(
            JobMatch.user_id == user.id,
            JobMatch.job_id == job_id,
            JobMatch.resume_id == resume.id,
        )
    )

    job_args = (job.title, job.company.name, job.description or "", _match_summary(match), payload.instructions)
    master = resume.master_content if payload.kind is DocumentKind.resume else None
    try:
        if master:
            # Quick edits to a copy of the master: facts stay exactly as the user saved them.
            edits = ai.tailor_master_resume(tailored_resume.indexed_text(master), *job_args)
            content = tailored_resume.apply_tailoring(master, edits)
        elif payload.kind is DocumentKind.resume:
            result = ai.generate_resume(_resume_source_text(resume), *job_args)
            content = tailored_resume.normalise(result.model_dump())
        else:
            content = ai.generate_cover_letter(_resume_source_text(resume), *job_args).model_dump()
    except ai.AIUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ai.AIRateLimited as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except ai.AIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    document = GeneratedDocument(
        user_id=user.id,
        job_id=job_id,
        resume_id=resume.id,
        kind=payload.kind,
        content=content,
        model_used=ai.last_model_used(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.post(
    "/jobs/{job_id}/documents/from-master",
    response_model=GeneratedDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def copy_master_resume(job_id: int, user: CurrentUser, db: DbSession) -> GeneratedDocument:
    """Start this job's resume as an exact copy of the master resume.

    No AI and no quota. The copy is a separate document, so editing it for this
    job never changes the master. Works for hand-logged jobs too, since it needs
    no advert.
    """
    if db.get(Job, job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    resume = require_active_resume(db, user)
    if not resume.master_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Save your master resume on the Profile page first.",
        )

    document = GeneratedDocument(
        user_id=user.id,
        job_id=job_id,
        resume_id=resume.id,
        kind=DocumentKind.resume,
        content=tailored_resume.normalise(resume.master_content),
        model_used=tailored_resume.MASTER_COPY,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/documents/{document_id}", response_model=GeneratedDocumentOut)
def get_document(document_id: int, user: CurrentUser, db: DbSession) -> GeneratedDocument:
    document = db.scalar(
        select(GeneratedDocument).where(
            GeneratedDocument.id == document_id, GeneratedDocument.user_id == user.id
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


@router.patch("/documents/{document_id}", response_model=GeneratedDocumentOut)
def update_document(
    document_id: int, payload: DocumentUpdate, user: CurrentUser, db: DbSession
) -> GeneratedDocument:
    """Save the user's edits.

    Writes to `edited_content` only - the original AI output is never
    overwritten, so "reset to generated" always works.
    """
    document = db.scalar(
        select(GeneratedDocument).where(
            GeneratedDocument.id == document_id, GeneratedDocument.user_id == user.id
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    document.edited_content = payload.edited_content
    db.commit()
    db.refresh(document)
    return document


@router.post("/documents/{document_id}/reset", response_model=GeneratedDocumentOut)
def reset_document(document_id: int, user: CurrentUser, db: DbSession) -> GeneratedDocument:
    """Discard edits and fall back to the generated original. Costs nothing."""
    document = db.scalar(
        select(GeneratedDocument).where(
            GeneratedDocument.id == document_id, GeneratedDocument.user_id == user.id
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    document.edited_content = None
    db.commit()
    db.refresh(document)
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, user: CurrentUser, db: DbSession) -> Response:
    document = db.scalar(
        select(GeneratedDocument).where(
            GeneratedDocument.id == document_id, GeneratedDocument.user_id == user.id
        )
    )
    if document is not None:
        db.delete(document)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/history", response_model=list[HistoryEntryOut])
def history(user: CurrentUser, db: DbSession) -> list[HistoryEntryOut]:
    """The record of work done, most recent first.

    A job is logged here once the user applied to it, generated a resume or
    cover letter for it, or both. Nothing is stored for History itself: it is
    derived from Application and GeneratedDocument, so it can never drift from
    the board or the job page.
    """
    # Imported here rather than at the top: applications imports this module.
    from app.routers.applications import _to_out as applications_out

    documents = list(
        db.scalars(
            select(GeneratedDocument)
            .options(
                selectinload(GeneratedDocument.job).selectinload(Job.company)
            )
            .where(GeneratedDocument.user_id == user.id)
            .order_by(GeneratedDocument.created_at.desc())
        )
    )
    applications = list(
        db.scalars(
            select(Application)
            .options(selectinload(Application.job).selectinload(Job.company))
            .where(Application.user_id == user.id)
        )
    )
    if not documents and not applications:
        return []

    grouped: dict[int, list[GeneratedDocument]] = {}
    for document in documents:
        grouped.setdefault(document.job_id, []).append(document)

    tracked = {
        out.job.id: out for out in applications_out(db, user, applications)
    }

    jobs = {d.job.id: d.job for d in documents} | {a.job.id: a.job for a in applications}
    decorated = {j.id: out for j, out in zip(jobs.values(), decorate_jobs(db, user, jobs.values()))}

    entries = []
    for job_id in jobs:
        docs = grouped.get(job_id, [])
        application = tracked.get(job_id)
        last_generated = max((d.created_at for d in docs), default=None)
        # An applied job with no documents is still history: it is work done.
        moments = [m for m in (last_generated, application.status_updated_at if application else None) if m]
        entries.append(
            HistoryEntryOut(
                job=decorated[job_id],
                documents=[GeneratedDocumentOut.model_validate(d) for d in docs],
                application=application,
                last_generated_at=last_generated,
                last_activity_at=max(moments),
            )
        )
    entries.sort(key=lambda e: e.last_activity_at, reverse=True)
    return entries
