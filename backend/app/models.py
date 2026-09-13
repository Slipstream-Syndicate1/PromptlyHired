from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobType(str, enum.Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    remote = "remote"


class DocumentKind(str, enum.Enum):
    resume = "resume"
    cover_letter = "cover_letter"


class ApplicationStatus(str, enum.Enum):
    """Where an application stands. Ordered roughly by how far it progressed.

    A job only becomes an Application once actually applied to - shortlisting
    before that is SavedJob.
    """

    applied = "applied"
    online_assessment = "online_assessment"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"


class CommunicationKind(str, enum.Enum):
    email = "email"
    call = "call"
    meeting = "meeting"
    message = "message"
    other = "other"


class CommunicationDirection(str, enum.Enum):
    received = "received"
    sent = "sent"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    profile_picture_url: Mapped[str | None] = mapped_column(String(1024))
    # Job recommendations: where to search. Overrides the resume location when set.
    preferred_location: Mapped[str | None] = mapped_column(String(120))
    include_remote: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    resumes: Mapped[list[Resume]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    saved_jobs: Mapped[list[SavedJob]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Resume(Base):
    """The uploaded source document.

    Extracted text is stored alongside the file so match scoring and generation
    never re-download or re-parse the original on every call.

    Uploading a new resume deactivates the previous one rather than replacing
    it: generated documents reference the resume they were built from, and that
    provenance has to survive.
    """

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="resumes")
    skill_profile: Mapped[SkillProfile | None] = relationship(
        back_populates="resume", uselist=False, cascade="all, delete-orphan"
    )


class SkillProfile(Base):
    """AI-derived skillset, one per Resume. Drives the automatic job search.

    Derived once per resume, never per search. The user can edit it - extraction
    is a starting point, not an authority on someone's own career.
    """

    __tablename__ = "skill_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    skills: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    job_titles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    domains: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    locations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    seniority: Mapped[str | None] = mapped_column(String(60))
    years_experience: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(60))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    edited_by_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    resume: Mapped[Resume] = relationship(back_populates="skill_profile")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Lowercased/trimmed name, so the same employer arriving from different
    # listings collapses onto one Company row.
    normalized_name: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    logo_url: Mapped[str | None] = mapped_column(String(1024))
    short_description: Mapped[str | None] = mapped_column(Text)

    jobs: Mapped[list[Job]] = relationship(back_populates="company")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source_api", "external_id", name="uq_job_source_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    salary_range: Mapped[str | None] = mapped_column(String(120))
    url: Mapped[str | None] = mapped_column(String(2048))
    posted_date: Mapped[date | None] = mapped_column(Date, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    job_type: Mapped[JobType | None] = mapped_column(Enum(JobType, name="job_type"))
    source_api: Mapped[str] = mapped_column(String(50), nullable=False)
    # JSearch search-v2 ids are ~400-character opaque blobs.
    external_id: Mapped[str] = mapped_column(String(768), nullable=False)
    # The board the listing lives on, used to label the outbound Apply link.
    source_publisher: Mapped[str | None] = mapped_column(String(120))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    company: Mapped[Company] = relationship(back_populates="jobs")


class UserJob(Base):
    """Records that this user added this job to their workspace.

    Job rows are shared and deduplicated - two users pasting the same link get
    the same Job - so ownership cannot live on Job itself. Without this, a
    freshly pasted job would not appear on the user's Jobs page until they
    happened to save or analyse it.

    Distinct from SavedJob, which is a deliberate shortlist. Everything you
    paste lands here; only what you star lands there.
    """

    __tablename__ = "user_jobs"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_user_job"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    job: Mapped[Job] = relationship()


class SavedJob(Base):
    """Shortlist. Job-level, no AI cost, no side effects."""

    __tablename__ = "saved_jobs"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_saved_user_job"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="saved_jobs")
    job: Mapped[Job] = relationship()


class JobMatch(Base):
    """AI match analysis, computed when a card is opened and cached forever after.

    Keyed by resume as well as job: a new resume produces a new analysis, and
    the old one survives for comparison. Recomputation is only ever
    user-initiated, because every analysis costs a real API call.
    """

    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "resume_id", name="uq_match_user_job_resume"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    match_percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    requirements_met: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    requirements_missing: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(60))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped[Job] = relationship()
    resume: Mapped[Resume] = relationship()


class GeneratedDocument(Base):
    """A tailored resume or cover letter.

    `content` is what the model produced and is never overwritten;
    `edited_content` holds the user's revisions. Keeping both means "reset to
    generated" always works, and makes it auditable what the AI actually wrote
    versus what the user changed.
    """

    __tablename__ = "generated_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[DocumentKind] = mapped_column(
        Enum(DocumentKind, name="document_kind"), nullable=False
    )
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    edited_content: Mapped[dict | None] = mapped_column(JSONB)
    model_used: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=utcnow, nullable=False
    )

    job: Mapped[Job] = relationship()
    resume: Mapped[Resume] = relationship()


class Application(Base):
    """A job the user has actually applied to, and where it stands now.

    Only the current status lives here. The path it took - and so every
    response from the employer - is in ApplicationEvent.
    """

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_application_user_job"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Which CV was sent. SET NULL, not CASCADE: deleting an old resume must not
    # erase the record that you applied.
    resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"),
        default=ApplicationStatus.applied,
        index=True,
        nullable=False,
    )
    applied_date: Mapped[date] = mapped_column(Date, nullable=False)
    status_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    # The next thing to do and when - drives follow-up reminders and lets the
    # calendar show application dates from the server instead of localStorage.
    next_action: Mapped[str | None] = mapped_column(String(255))
    next_action_date: Mapped[date | None] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=utcnow, nullable=False
    )

    job: Mapped[Job] = relationship()
    resume: Mapped[Resume | None] = relationship()
    events: Mapped[list[ApplicationEvent]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationEvent.changed_at",
    )
    communications: Mapped[list[Communication]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="Communication.occurred_at.desc()",
    )


class ApplicationEvent(Base):
    """One status change: the history of an application.

    Application holds only the current status, which cannot answer "when did
    they invite me to interview" or "how long until I heard back". Recording
    each transition is what makes response tracking real.
    """

    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Null only for the event that created the application.
    from_status: Mapped[ApplicationStatus | None] = mapped_column(
        Enum(ApplicationStatus, name="application_status")
    )
    to_status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)

    application: Mapped[Application] = relationship(back_populates="events")


class Communication(Base):
    """A logged exchange with an employer about one application."""

    __tablename__ = "communications"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[CommunicationKind] = mapped_column(
        Enum(CommunicationKind, name="communication_kind"), nullable=False
    )
    direction: Mapped[CommunicationDirection] = mapped_column(
        Enum(CommunicationDirection, name="communication_direction"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    contact_name: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str | None] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    application: Mapped[Application] = relationship(back_populates="communications")


class RefreshToken(Base):
    """Hashed, rotating refresh tokens - lets a session be revoked server-side."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PasswordResetToken(Base):
    """A one-time password reset link.

    Stored only as a SHA-256 hash, like refresh tokens, so a database leak
    cannot be used to reset anyone's password. Single use and short-lived.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set when the link is used, or when a newer link replaces it.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
