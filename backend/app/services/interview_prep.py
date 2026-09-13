"""Interview preparation plans.

The model's answer is clipped to the saved shape rather than rejected: the
request has already been spent, and a few characters over a limit is not worth
making the user spend another one.
"""

from __future__ import annotations

from typing import Any

from app.schemas import InterviewPrepContent

MAX_FOCUS_AREAS = 6
MAX_QUESTIONS = 8
MAX_ACTIONS = 8
MAX_ASKS = 6
MAX_WATCH_OUTS = 5


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _lines(values: Any, limit: int, chars: int = 500) -> list[str]:
    cleaned = (_text(value, chars) for value in (values or []))
    return [line for line in cleaned if line][:limit]


def _get(source: Any, key: str) -> Any:
    return source.get(key) if isinstance(source, dict) else getattr(source, key, None)


def normalise(roadmap: Any) -> dict:
    """Clip a generated roadmap to the stored limits and validate it."""
    # Blanks are dropped before the cap, so one empty entry does not cost a usable one.
    focus_areas = []
    for area in _get(roadmap, "focus_areas") or []:
        topic = _text(_get(area, "topic"), 200)
        actions = _lines(_get(area, "actions"), MAX_ACTIONS)
        if topic or actions:
            focus_areas.append(
                {"topic": topic, "why": _text(_get(area, "why"), 1000), "actions": actions}
            )
    focus_areas = focus_areas[:MAX_FOCUS_AREAS]

    questions = []
    for item in _get(roadmap, "likely_questions") or []:
        question = _text(_get(item, "question"), 500)
        if question:
            questions.append(
                {"question": question, "how_to_answer": _text(_get(item, "how_to_answer"), 1500)}
            )
    questions = questions[:MAX_QUESTIONS]

    content = {
        "summary": _text(_get(roadmap, "summary"), 2000),
        "focus_areas": focus_areas,
        "likely_questions": questions,
        "questions_to_ask": _lines(_get(roadmap, "questions_to_ask"), MAX_ASKS),
        "watch_outs": _lines(_get(roadmap, "watch_outs"), MAX_WATCH_OUTS),
    }
    return InterviewPrepContent.model_validate(content).model_dump()


def is_empty(content: dict) -> bool:
    """A plan with nothing in it is worse than none: the caller should not save it."""
    return not any(
        content.get(key) for key in ("summary", "focus_areas", "likely_questions", "questions_to_ask")
    )
