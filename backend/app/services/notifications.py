from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.models import Application, Job, User
from app.services import email as email_service


def _normalise_preferences(raw: object) -> dict:
    payload = raw if isinstance(raw, dict) else {}
    categories = payload.get("categories") or []
    offsets = payload.get("reminder_offsets_hours") or [24]
    allowed = {
        "interview_coming_up",
        "offer_deadline_coming_up",
        "application_deadline_coming_up",
        "coffee_chat_event_coming_up",
        "networking_event_coming_up",
    }
    clean_categories = [str(item) for item in categories if str(item) in allowed]
    clean_offsets: list[int] = []
    seen: set[int] = set()
    for value in offsets:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            continue
        if numeric <= 0 or numeric in seen:
            continue
        seen.add(numeric)
        clean_offsets.append(numeric)
    return {
        "email_enabled": bool(payload.get("email_enabled")),
        "categories": list(dict.fromkeys(clean_categories)),
        "reminder_offsets_hours": sorted(clean_offsets) or [24],
    }


def _category_for_application(application: Application) -> str | None:
    if application.status.value == "interview":
        return "interview_coming_up"
    if application.status.value == "offer":
        return "offer_deadline_coming_up"
    if application.next_action_date is not None:
        return "application_deadline_coming_up"
    return None


def _reminder_time_for(application: Application, offset_hours: int) -> datetime | None:
    if application.next_action_date is None:
        return None
    base = datetime.combine(
        application.next_action_date, datetime.min.time(), tzinfo=timezone.utc
    )
    return base - timedelta(hours=offset_hours)


def _body_for(application: Application, category: str, offset_hours: int, user: User) -> str:
    company = application.job.company.name if application.job and application.job.company else "the company"
    title = application.job.title if application.job else "your application"
    action = application.next_action or "your next action"
    due = application.next_action_date.isoformat() if application.next_action_date else "soon"
    return (
        f"Hi {user.name},\n\n"
        f"This is a reminder for {title} at {company}.\n"
        f"Category: {category.replace('_', ' ')}\n"
        f"Next action: {action}\n"
        f"Due: {due}\n"
        f"Reminder sent {offset_hours} hours before the deadline.\n\n"
        "This email was sent by PromptlyHired."
    )


def send_upcoming_reminders(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    sent_count = 0
    with SessionLocal() as session:
        users = session.scalars(select(User)).all()
        for user in users:
            prefs = _normalise_preferences(user.notification_preferences)
            if not prefs["email_enabled"] or not prefs["categories"]:
                continue
            applications = session.scalars(
                select(Application)
                .options(selectinload(Application.job).selectinload(Job.company))
                .where(Application.user_id == user.id)
            ).all()
            for application in applications:
                category = _category_for_application(application)
                if category is None or category not in set(prefs["categories"]):
                    continue
                for offset_hours in prefs["reminder_offsets_hours"]:
                    reminder_time = _reminder_time_for(application, offset_hours)
                    if reminder_time is None:
                        continue
                    if reminder_time <= now and reminder_time > now - timedelta(minutes=30):
                        subject = (
                            f"Reminder: {application.job.title} {category.replace('_', ' ')}"
                            if application.job
                            else f"Reminder: {category.replace('_', ' ')}"
                        )
                        if email_service.send_email(
                            user.email,
                            subject,
                            _body_for(application, category, offset_hours, user),
                        ):
                            sent_count += 1
    return sent_count