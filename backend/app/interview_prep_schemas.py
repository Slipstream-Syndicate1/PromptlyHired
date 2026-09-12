"""Preparation contracts; interview context must come from an authorized adapter."""
from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

InterviewType = Literal['technical', 'behavioral', 'not_sure']


class PrepSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    interview_type: InterviewType = 'not_sure'
    daily_minutes: int = Field(strict=True, ge=15, le=480)
    same_day_minutes: int | None = Field(default=None, strict=True, ge=1, le=480)


class InterviewContext(BaseModel):
    """Server-only snapshot, never an HTTP request body or proof of ownership."""
    interview_id: str
    application_id: str
    job_id: str
    status: str
    starts_at: AwareDatetime
    timezone: str
    schedule_revision: str
    job_title: str
    company: str
    job_description: str = Field(min_length=1)
    resume_text: str = ''
    match_summary: str = ''


class PrepSlot(BaseModel):
    date: date
    minutes: int = Field(ge=1, le=480)


class GeneratedTask(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    category: Literal['technical', 'behavioral']
    priority: Literal['high', 'medium', 'low']
    minutes: int = Field(strict=True, ge=1, le=480)
    instructions: str = Field(min_length=1, max_length=1200)
    expected_outcome: str = Field(min_length=1, max_length=500)
    job_requirement: str = Field(min_length=1, max_length=500)


class GeneratedDay(BaseModel):
    date: date
    tasks: list[GeneratedTask] = Field(min_length=1, max_length=8)


class GeneratedPlan(BaseModel):
    summary: str = Field(min_length=1, max_length=1500)
    days: list[GeneratedDay] = Field(min_length=1, max_length=14)


class PrepTask(GeneratedTask):
    id: str
    completed: bool = False


class PrepDay(BaseModel):
    date: date
    minutes_budget: int
    tasks: list[PrepTask]


class PrepPlan(BaseModel):
    summary: str
    days: list[PrepDay]
    personalization_notice: str | None
    has_more_days: bool


class ChatMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=4000)


class PrepChatAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)
