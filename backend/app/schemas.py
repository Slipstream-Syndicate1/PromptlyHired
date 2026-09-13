"""Pydantic request/response models.

Every endpoint validates at this boundary - client-side validation is never
trusted. Free-text fields are length-capped and stripped of control characters
before they reach the database.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import (
    ApplicationStatus,
    CommunicationDirection,
    CommunicationKind,
    DocumentKind,
    JobType,
)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value: str | None) -> str | None:
    """Strip control characters and surrounding whitespace.

    Rendering safety itself comes from React escaping by default; this keeps
    junk out of the stored data rather than trying to be an HTML sanitiser.
    """
    if value is None:
        return None
    cleaned = _CONTROL_CHARS.sub("", value).strip()
    return cleaned or None


def clean_list(values: list[str] | None, max_items: int = 60, max_len: int = 120) -> list[str]:
    """Normalise an AI- or user-supplied string list.

    Deduplicates case-insensitively while preserving order, so an extraction
    returning both "Python" and "python" yields one entry.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in (values or [])[: max_items * 3]:
        cleaned = clean_text(str(raw))
        if not cleaned:
            continue
        cleaned = cleaned[:max_len]
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if len(out) >= max_items:
            break
    return out


# --- Auth ---------------------------------------------------------------


class UserCreate(BaseModel):
    email: EmailStr
    # 72 bytes is bcrypt's hard limit - reject rather than silently truncate.
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        cleaned = clean_text(v)
        if not cleaned:
            raise ValueError("name must not be blank")
        return cleaned


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    # Same bounds as sign-up: 72 bytes is the bcrypt limit.
    password: str = Field(min_length=8, max_length=72)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


# --- Profile ------------------------------------------------------------


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    profile_picture_url: str | None = None
    preferred_location: str | None = None
    include_remote: bool = True
    created_at: datetime


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    profile_picture_url: str | None = Field(default=None, max_length=1024)
    # Blank or null clears it, so recommendations use the resume location again.
    preferred_location: str | None = Field(default=None, max_length=120)
    include_remote: bool | None = None

    @field_validator("name", "profile_picture_url", "preferred_location")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        return clean_text(v)


# --- Resume & skill profile ---------------------------------------------


class SkillProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    skills: list[str]
    job_titles: list[str]
    domains: list[str]
    locations: list[str]
    seniority: str | None = None
    years_experience: float | None = None
    summary: str | None = None
    edited_by_user: bool = False
    generated_at: datetime


class SkillProfileUpdate(BaseModel):
    """The user's own corrections. Extraction is a starting point, not truth."""

    skills: list[str] | None = None
    job_titles: list[str] | None = None
    domains: list[str] | None = None
    locations: list[str] | None = None
    seniority: str | None = Field(default=None, max_length=60)
    years_experience: float | None = Field(default=None, ge=0, le=80)
    summary: str | None = Field(default=None, max_length=4000)

    @field_validator("skills", "job_titles", "domains", "locations")
    @classmethod
    def _clean_lists(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else clean_list(v)

    @field_validator("seniority", "summary")
    @classmethod
    def _clean_strings(cls, v: str | None) -> str | None:
        return clean_text(v)


class ResumeEntryContent(BaseModel):
    """Optional structured entry used by the classic one-page resume template.

    Existing generated resumes can keep using ``heading`` + ``bullets`` only;
    these fields simply let the master resume preserve two-column metadata such
    as dates and locations without encoding layout into a bullet string.
    """

    title: str = Field(default="", max_length=300)
    meta: str = Field(default="", max_length=500)
    right: str = Field(default="", max_length=240)
    subtitle: str = Field(default="", max_length=500)
    subtitle_right: str = Field(default="", max_length=240)
    bullets: list[str] = Field(default_factory=list, max_length=20)


class ResumeSectionContent(BaseModel):
    heading: str = Field(default="", max_length=160)
    bullets: list[str] = Field(default_factory=list, max_length=20)
    entries: list[ResumeEntryContent] = Field(default_factory=list, max_length=20)


class MasterResumeContent(BaseModel):
    """Canonical editable resume shape shared with tailored resume documents."""

    full_name: str = Field(default="", max_length=160)
    headline: str = Field(default="", max_length=240)
    contact_line: str = Field(default="", max_length=1000)
    summary: str = Field(default="", max_length=4000)
    sections: list[ResumeSectionContent] = Field(default_factory=list, max_length=12)
    skills: list[str] = Field(default_factory=list, max_length=40)


class MasterResumeUpdate(BaseModel):
    master_content: MasterResumeContent


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_url: str
    original_filename: str
    content_type: str
    is_active: bool
    uploaded_at: datetime
    master_content: MasterResumeContent | None = None
    skill_profile: SkillProfileOut | None = None


# --- Companies & jobs ----------------------------------------------------


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    logo_url: str | None = None
    short_description: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: CompanyOut
    location: str | None = None
    salary_range: str | None = None
    url: str | None = None
    posted_date: date | None = None
    description: str | None = None
    job_type: JobType | None = None
    source_api: str
    # Names the destination of the outbound Apply link ("Apply on LinkedIn").
    source_publisher: str | None = None

    # Per-user state attached by the router. The match figures are read from
    # the cached JobMatch row - showing them costs a database join, never an
    # API call. They are null until the user asks for an analysis.
    is_saved: bool = False
    has_match: bool = False
    has_documents: bool = False
    match_percentage: int | None = None
    requirements_met_count: int | None = None
    requirements_missing_count: int | None = None


class SavedJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job: JobOut
    saved_at: datetime


class JobFeedOut(BaseModel):
    jobs: list[JobOut]
    page: int
    has_more: bool
    # Which sources answered this search. Empty means the live search failed.
    sources: list[str]
    notice: str | None = None


class RecommendedJobOut(BaseModel):
    job: JobOut
    # The resume skills this job mentions - shown as the reason it is recommended.
    matched_skills: list[str]
    # 0-100: how many of the top resume skills the job mentions. Not an AI score.
    relevance: int


class RecommendationsOut(BaseModel):
    jobs: list[RecommendedJobOut]
    searched_titles: list[str]
    location: str | None = None
    include_remote: bool = True
    sources: list[str]
    notice: str | None = None


# --- Match analysis ------------------------------------------------------


class JobMatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    resume_id: int
    match_percentage: int
    requirements_met: list[str]
    requirements_missing: list[str]
    rationale: str | None = None
    generated_at: datetime


class JobDetailOut(BaseModel):
    job: JobOut
    match: JobMatchOut | None = None
    documents: list[GeneratedDocumentOut] = Field(default_factory=list)
    # The user's tracked application for this job, if any.
    application: ApplicationOut | None = None


# --- Generated documents -------------------------------------------------


class GeneratedDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    resume_id: int
    kind: DocumentKind
    content: dict
    edited_content: dict | None = None
    # "master-copy" for a straight copy of the master resume, otherwise the AI model.
    model_used: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentGenerateRequest(BaseModel):
    kind: DocumentKind
    # Optional user steering, e.g. "emphasise my backend work".
    instructions: str | None = Field(default=None, max_length=1000)

    @field_validator("instructions")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        return clean_text(v)


class DocumentUpdate(BaseModel):
    """The user's edits. Never overwrites the original AI output."""

    edited_content: dict


class HistoryEntryOut(BaseModel):
    """One job in the record of work done.

    A job earns an entry by being applied to, by having documents generated for
    it, or both - so applying without generating anything is still logged.
    """

    job: JobOut
    documents: list[GeneratedDocumentOut] = Field(default_factory=list)
    # The tracked application, when there is one. Its stage is shown on the entry.
    application: "ApplicationOut | None" = None
    # Null for a job that was applied to but never had documents generated.
    last_generated_at: datetime | None = None
    # The most recent of the two, which is what History is ordered by.
    last_activity_at: datetime


# --- Applications ---------------------------------------------------------

_HTTP_URL = re.compile(r"^https?://", re.IGNORECASE)


def _http_url(value: str | None) -> str | None:
    """Only http(s). The link is rendered as the Apply button's href, so a
    javascript: URL stored here would run in the browser of whoever clicks it."""
    value = clean_text(value)
    if value is not None and not _HTTP_URL.match(value):
        raise ValueError("Link must start with http:// or https://")
    return value


class ApplicationCreate(BaseModel):
    """Track an application: either for a job already in the app (job_id), or a
    manual entry (company + position) for one applied to elsewhere."""

    job_id: int | None = None
    company: str | None = Field(default=None, max_length=200)
    position: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, max_length=2048)
    location: str | None = Field(default=None, max_length=255)

    status: ApplicationStatus = ApplicationStatus.applied
    applied_date: date | None = None
    notes: str | None = Field(default=None, max_length=10_000)
    next_action: str | None = Field(default=None, max_length=255)
    next_action_date: date | None = None
    resume_id: int | None = None

    @field_validator("company", "position", "location", "notes", "next_action")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        return clean_text(v)

    @field_validator("url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return _http_url(v)

    @model_validator(mode="after")
    def _job_or_manual(self) -> ApplicationCreate:
        manual = self.company is not None or self.position is not None
        if self.job_id is not None and manual:
            raise ValueError("Give either job_id or company and position, not both.")
        if self.job_id is None and not (self.company and self.position):
            raise ValueError("Give job_id, or company and position for a manual entry.")
        return self


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    # What caused a status change, e.g. "Invited to interview by email".
    # Stored on the ApplicationEvent, so it only makes sense with a change.
    note: str | None = Field(default=None, max_length=2000)
    applied_date: date | None = None
    notes: str | None = Field(default=None, max_length=10_000)
    next_action: str | None = Field(default=None, max_length=255)
    next_action_date: date | None = None
    resume_id: int | None = None

    @field_validator("note", "notes", "next_action")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        return clean_text(v)

    @model_validator(mode="after")
    def _required_fields_stay_set(self) -> ApplicationUpdate:
        for name in ("status", "applied_date"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared.")
        return self


class ApplicationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: ApplicationStatus | None = None
    to_status: ApplicationStatus
    changed_at: datetime
    note: str | None = None


class ApplicationOut(BaseModel):
    id: int
    job: JobOut
    status: ApplicationStatus
    applied_date: date
    status_updated_at: datetime
    notes: str | None = None
    next_action: str | None = None
    next_action_date: date | None = None
    resume_id: int | None = None
    created_at: datetime
    updated_at: datetime

    days_since_update: int = 0
    # Still waiting on the employer and either past its next-action date or
    # quiet for too long. Drives follow-up reminders.
    needs_follow_up: bool = False
    communications_count: int = 0


class ApplicationStats(BaseModel):
    """Figures for the Dashboard cards, computed in one query."""

    total: int
    by_status: dict[str, int]
    active: int
    offers: int
    needs_follow_up: int
    # Share of applications (excluding withdrawn) that got past "applied".
    # Null when there is nothing to divide by, rather than a misleading 0%.
    response_rate_pct: int | None = None


class CommunicationCreate(BaseModel):
    kind: CommunicationKind
    direction: CommunicationDirection
    # Defaults to now, for logging something as it happens.
    occurred_at: datetime | None = None
    contact_name: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=300)
    summary: str | None = Field(default=None, max_length=10_000)

    @field_validator("contact_name", "subject", "summary")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        return clean_text(v)


class CommunicationUpdate(BaseModel):
    kind: CommunicationKind | None = None
    direction: CommunicationDirection | None = None
    occurred_at: datetime | None = None
    contact_name: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=300)
    summary: str | None = Field(default=None, max_length=10_000)

    @field_validator("contact_name", "subject", "summary")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        return clean_text(v)

    @model_validator(mode="after")
    def _required_fields_stay_set(self) -> CommunicationUpdate:
        for name in ("kind", "direction", "occurred_at"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared.")
        return self


class CommunicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    kind: CommunicationKind
    direction: CommunicationDirection
    occurred_at: datetime
    contact_name: str | None = None
    subject: str | None = None
    summary: str | None = None
    created_at: datetime


# --- Interview preparation -----------------------------------------------


class PrepFocusOut(BaseModel):
    topic: str = Field(default="", max_length=200)
    why: str = Field(default="", max_length=1000)
    actions: list[str] = Field(default_factory=list, max_length=8)


class PrepQuestionOut(BaseModel):
    question: str = Field(default="", max_length=500)
    how_to_answer: str = Field(default="", max_length=1500)


class InterviewPrepContent(BaseModel):
    """The saved plan. Caps keep one odd model response from filling the page."""

    summary: str = Field(default="", max_length=2000)
    focus_areas: list[PrepFocusOut] = Field(default_factory=list, max_length=6)
    likely_questions: list[PrepQuestionOut] = Field(default_factory=list, max_length=8)
    questions_to_ask: list[str] = Field(default_factory=list, max_length=6)
    watch_outs: list[str] = Field(default_factory=list, max_length=5)


class InterviewPrepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    content: InterviewPrepContent
    model_used: str | None = None
    generated_at: datetime


# JobDetailOut refers to GeneratedDocumentOut and ApplicationOut, both defined
# after it. Rebuilt once, here, where every name it needs exists.
JobDetailOut.model_rebuild()
HistoryEntryOut.model_rebuild()
