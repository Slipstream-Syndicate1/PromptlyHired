"""Tailored resumes built from the master resume.

The master resume is the user's own record of their career, so a version
tailored to one job may reword and reorder it but never change the facts in it.
The model therefore does not return a whole resume. It returns edits keyed to
the master's sections and entries, and `apply_tailoring` writes them onto a copy
of the master: names, schools, employers, dates and locations always come from
the master, whatever the model sends back.

Nothing here writes to the master itself. A tailored resume is a separate
GeneratedDocument, so editing it never changes the master.
"""

from __future__ import annotations

import copy
from typing import Any

from app.schemas import MasterResumeContent

# model_used on a document that is a straight copy of the master, made without AI.
MASTER_COPY = "master-copy"

MAX_SECTIONS = 12
MAX_ENTRIES = 20
MAX_BULLETS = 20
MAX_SKILL_LINES = 40
MAX_BULLET_CHARS = 600

_ENTRY_LIMITS = {"title": 300, "meta": 500, "right": 240, "subtitle": 500, "subtitle_right": 240}


def _get(source: Any, key: str, default: Any = None) -> Any:
    """Read a field from a dict or a model result alike."""
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _bullets(values: Any) -> list[str]:
    cleaned = (_text(value, MAX_BULLET_CHARS) for value in (values or []))
    return [bullet for bullet in cleaned if bullet][:MAX_BULLETS]


def normalise(data: Any) -> dict:
    """Clip a resume to the master resume limits and validate it.

    Model output is clipped rather than rejected: failing validation after the
    request has been spent would waste the user's quota for a few extra characters.
    """
    sections = []
    for section in (_get(data, "sections") or [])[:MAX_SECTIONS]:
        entries = []
        for entry in (_get(section, "entries") or [])[:MAX_ENTRIES]:
            item: dict[str, Any] = {
                key: _text(_get(entry, key), limit) for key, limit in _ENTRY_LIMITS.items()
            }
            item["bullets"] = _bullets(_get(entry, "bullets"))
            if any(item.values()):
                entries.append(item)
        heading = _text(_get(section, "heading"), 160)
        bullets = _bullets(_get(section, "bullets"))
        if heading or entries or bullets:
            sections.append({"heading": heading, "entries": entries, "bullets": bullets})

    skills = [_text(line, MAX_BULLET_CHARS) for line in (_get(data, "skills") or [])]
    result = {
        "full_name": _text(_get(data, "full_name"), 160),
        "headline": _text(_get(data, "headline"), 240),
        "contact_line": _text(_get(data, "contact_line"), 1000),
        "summary": _text(_get(data, "summary"), 4000),
        "sections": sections,
        "skills": [line for line in skills if line][:MAX_SKILL_LINES],
    }
    return MasterResumeContent.model_validate(result).model_dump()


def indexed_text(master: dict) -> str:
    """The master resume as model input, with the indexes edits must refer to."""
    lines = [f"Name: {master.get('full_name') or ''}"]
    if master.get("headline"):
        lines.append(f"Headline: {master['headline']}")
    if master.get("summary"):
        lines.append(f"Summary: {master['summary']}")

    for s_index, section in enumerate(master.get("sections") or []):
        lines.append(f"\n[section {s_index}] {section.get('heading') or ''}")
        for e_index, entry in enumerate(section.get("entries") or []):
            facts = " | ".join(
                value
                for value in (entry.get(key) for key in ("title", "meta", "subtitle", "right", "subtitle_right"))
                if value
            )
            lines.append(f"  [entry {e_index}] {facts}")
            lines.extend(f"    - {bullet}" for bullet in entry.get("bullets") or [] if bullet)
        loose = [bullet for bullet in section.get("bullets") or [] if bullet]
        if loose:
            lines.append("  [section bullets]")
            lines.extend(f"    - {bullet}" for bullet in loose)

    skills = [line for line in master.get("skills") or [] if line]
    if skills:
        lines.append("\nSkills:")
        lines.extend(f"  {line}" for line in skills)
    return "\n".join(lines)


def _pick(items: list[dict], edits: Any, index_key: str, apply) -> list[dict]:
    """Reorder `items` as the edits list them, then append any the edits left out.

    Unknown and repeated indexes are ignored, so nothing can be invented, duplicated
    or silently dropped.
    """
    used: set[int] = set()
    ordered = []
    for edit in edits or []:
        index = _get(edit, index_key)
        if not isinstance(index, int) or not 0 <= index < len(items) or index in used:
            continue
        used.add(index)
        ordered.append(apply(copy.deepcopy(items[index]), edit))
    ordered.extend(copy.deepcopy(item) for i, item in enumerate(items) if i not in used)
    return ordered


def _reword(target: dict, edit: Any) -> dict:
    """Swap in reworded bullets, only where the master already had bullets.

    Never more bullets than the master had: extra ones are where a model turns a
    skill list into accomplishments the candidate never described.
    """
    reworded = _bullets(_get(edit, "bullets"))
    if reworded and target["bullets"]:
        target["bullets"] = reworded[: len(target["bullets"])]
    return target


def _split_skill_line(line: str) -> tuple[str, list[str]]:
    label, _, rest = line.partition(":") if ":" in line else ("", "", line)
    return label.strip(), [item.strip() for item in rest.split(",") if item.strip()]


def _tailor_skills(master_skills: list[str], proposed: Any) -> list[str]:
    """Reorder and trim skill lines. Labels and items must already be in the master."""
    master_lines = [_split_skill_line(line) for line in master_skills]
    allowed = {item.lower(): item for _, items in master_lines for item in items}
    labels = {label.lower(): label for label, _ in master_lines}

    result: list[str] = []
    seen: set[str] = set()
    for line in proposed or []:
        label, items = _split_skill_line(_text(line, MAX_BULLET_CHARS))
        key = label.lower()
        if key not in labels or key in seen:
            continue
        kept = list(dict.fromkeys(allowed[item.lower()] for item in items if item.lower() in allowed))
        if not kept:
            continue
        seen.add(key)
        joined = ", ".join(kept)
        result.append(f"{labels[key]}: {joined}" if labels[key] else joined)

    if not result:
        return list(master_skills)
    # A line the model left out is kept as it was rather than dropped.
    for (label, _), line in zip(master_lines, master_skills):
        if label.lower() not in seen:
            seen.add(label.lower())
            result.append(line)
    return result[:MAX_SKILL_LINES]


def apply_tailoring(master: dict, edits: Any) -> dict:
    """A copy of the master with the model's edits applied. The master is not modified."""
    base = normalise(master)

    def tailor_section(section: dict, edit: Any) -> dict:
        section["entries"] = _pick(section["entries"], _get(edit, "entries"), "entry_index", _reword)
        return _reword(section, edit)

    base["sections"] = _pick(base["sections"], _get(edits, "sections"), "section_index", tailor_section)
    # The headline and summary are optional extras in the template: fill them only
    # when the master uses them.
    for field, limit in (("headline", 240), ("summary", 4000)):
        proposed = _text(_get(edits, field), limit)
        if base[field] and proposed:
            base[field] = proposed
    base["skills"] = _tailor_skills(base["skills"], _get(edits, "skills"))
    return MasterResumeContent.model_validate(base).model_dump()
