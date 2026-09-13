"""Job recommendations from the skills in a resume.

Searches the same free sources as the job feed, using the job titles the resume
suggests, then ranks what comes back by how many of the candidate's skills each
job mentions. That ranking is free and instant. The page then asks for an AI
match score on the top few, which is cached like any other match.

Every search goes through job_feed.search, so the shared cache stops repeated
visits from spending the Adzuna quota.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import Application, Job, Resume, SkillProfile, User
from app.services import job_feed, job_sources

# Each title is one search per source, so this caps the quota a refresh can use.
MAX_TITLES = 2
MAX_RESULTS = 20
# Skills past this many rarely change the ranking; they only add noise.
MAX_SKILLS = 15
# A title sharing at least two thirds of the words of a resume job title is
# plainly one of the target roles, even when its advert names none of the skills.
STRONG_TITLE_MATCH = 2.0
# Remote-board adverts run to thousands of characters while local ones arrive as
# short snippets, so description-only mentions stop counting past this many -
# otherwise long adverts would always outrank local jobs on length alone.
DESCRIPTION_MATCH_CAP = 4
# Local jobs come from the location search the user asked for.
LOCAL_BONUS = 2.0

# A skill must stand alone: "Java" must not match "JavaScript", and "C" must not
# match every word containing a c.
_BEFORE = r"(?<![A-Za-z0-9+#])"
_AFTER = r"(?![A-Za-z0-9+#])"
# One-letter skills (C, R) must also not be joined to punctuation that makes them
# part of something else: R&D, C-suite, U.S., A/B, the R's. A full stop after is
# fine when it ends a sentence ("Python, SQL and R.").
_SINGLE_BEFORE = r"(?<![A-Za-z0-9+#&./'-])"
_SINGLE_AFTER = r"(?![A-Za-z0-9+#&/'-]|\.\w)"

# Words that narrow a job title to a level or a term. Student resumes almost
# always suggest titles like "Software Developer Intern", which local job boards
# rarely list, so a search that finds too few local jobs is repeated for the
# same role without them.
_LEVEL_WORDS = re.compile(
    r"\b(intern(ship)?|co-?op|junior|jr|senior|sr|student|new grad(uate)?|entry[ -]level"
    r"|lead|principal|staff|trainee|i{1,3}|iv|summer|fall|winter|spring|20\d\d)\b",
    re.IGNORECASE,
)
MIN_LOCAL_RESULTS = 5

NO_RESUME_NOTICE = "Upload your resume to get job recommendations based on your skills."
NO_TITLES_NOTICE = (
    "Add a job title or a few skills to your skill profile on the Profile page to get "
    "recommendations."
)


@dataclass
class Recommendation:
    job: Job
    matched_skills: list[str]
    relevance: int
    score: float


@dataclass
class Recommendations:
    items: list[Recommendation] = field(default_factory=list)
    searched_titles: list[str] = field(default_factory=list)
    location: str | None = None
    include_remote: bool = True
    sources: list[str] = field(default_factory=list)
    notice: str | None = None


def _skill_pattern(skill: str) -> re.Pattern[str]:
    if len(skill) == 1:
        return re.compile(_SINGLE_BEFORE + re.escape(skill) + _SINGLE_AFTER)
    # Two-letter skills such as Go match only in their exact case, or "go" would
    # match half the sentences in every advert.
    flags = 0 if len(skill) <= 2 else re.IGNORECASE
    return re.compile(_BEFORE + re.escape(skill) + _AFTER, flags)


def match_skills(skills: list[str], title: str | None, description: str | None) -> tuple[list[str], float]:
    """The skills a job mentions, and a score in which a title mention counts double.

    Description-only mentions add at most DESCRIPTION_MATCH_CAP to the score.
    """
    matched: list[str] = []
    title_hits = description_hits = 0
    for skill in skills:
        pattern = _skill_pattern(skill)
        if pattern.search(title or ""):
            matched.append(skill)
            title_hits += 1
        elif pattern.search(description or ""):
            matched.append(skill)
            description_hits += 1
    return matched, 2.0 * title_hits + min(description_hits, DESCRIPTION_MATCH_CAP)


def relevance(matched_count: int, skill_count: int) -> int:
    """0-100: the share of a realistic number of skills a job mentions.

    Measured against at most ten skills, so a long skill list does not make every
    job look like a poor fit.
    """
    expected = max(3, min(skill_count, 10))
    return min(100, round(100 * matched_count / expected))


def broaden_title(title: str) -> str:
    """The role without level or term words: "Software Developer Intern" -> "Software Developer"."""
    without_levels = _LEVEL_WORDS.sub(" ", title)
    return " ".join(re.sub(r"[^A-Za-z0-9+#./ ]", " ", without_levels).split())


def _words(text: str | None) -> set[str]:
    return set(re.findall(r"[a-z]+", (text or "").lower()))


def title_bonus(job_title: str | None, target_titles: list[str]) -> float:
    """Up to 3 points for sharing words with a job title from the resume."""
    words = _words(job_title)
    best = 0.0
    for target in target_titles:
        wanted = {word for word in _words(target) if len(word) > 2}
        if wanted:
            best = max(best, 3 * len(words & wanted) / len(wanted))
    return best


def _active_profile(db, user: User) -> SkillProfile | None:
    resume = db.scalar(
        select(Resume)
        .options(selectinload(Resume.skill_profile))
        .where(Resume.user_id == user.id, Resume.is_active.is_(True))
        .order_by(Resume.uploaded_at.desc())
    )
    return resume.skill_profile if resume is not None else None


def recommend(db, user: User) -> Recommendations:
    profile = _active_profile(db, user)
    if profile is None:
        return Recommendations(include_remote=user.include_remote, notice=NO_RESUME_NOTICE)

    skills = [skill for skill in (profile.skills or []) if skill][:MAX_SKILLS]
    titles = [title for title in (profile.job_titles or []) if title][:MAX_TITLES]
    if not titles and skills:
        # No suggested titles: search for the strongest skills instead.
        titles = [" ".join(skills[:2])]
    location = user.preferred_location or next(
        (place for place in (profile.locations or []) if place), None
    )

    result = Recommendations(
        searched_titles=titles, location=location, include_remote=user.include_remote
    )
    if not titles:
        result.notice = NO_TITLES_NOTICE
        return result

    job_ids: list[int] = []
    searched = {title.lower() for title in titles}

    def search_for(query: str) -> list[int]:
        found = job_feed.search(
            db,
            job_feed.FeedQuery(
                # Lowercased like the feed, so both share cache entries.
                q=query.lower(),
                location=location.lower() if location else None,
                job_type=None,
                remote_only=False,
                posted_within_days=None,
                page=1,
            ),
        )
        job_ids.extend(job_id for job_id in found.job_ids if job_id not in job_ids)
        result.sources.extend(s for s in found.sources if s not in result.sources)
        if found.notice and result.notice is None:
            result.notice = found.notice
        return found.job_ids

    for title in titles:
        found_ids = search_for(title)
        if not settings.adzuna_enabled:
            continue  # Only Adzuna searches locally; broadening cannot help without it.
        local = (
            db.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.id.in_(found_ids), Job.source_api == job_sources.ADZUNA)
            )
            if found_ids
            else 0
        )
        broader = broaden_title(title)
        if local < MIN_LOCAL_RESULTS and broader and broader.lower() not in searched:
            searched.add(broader.lower())
            search_for(broader)

    applied = set(db.scalars(select(Application.job_id).where(Application.user_id == user.id)))
    ranked: list[Recommendation] = []
    for job in job_feed.load_jobs(db, job_ids):
        if job.id in applied:
            continue
        if not user.include_remote and job.source_api == job_sources.HIMALAYAS:
            continue
        matched, score = match_skills(skills, job.title, job.description)
        bonus = title_bonus(job.title, titles)
        # Short adverts often list no skills at all, so a job that is plainly one
        # of the resume roles stays in even without a skill mention.
        if not matched and bonus < STRONG_TITLE_MATCH:
            continue
        ranked.append(
            Recommendation(
                job=job,
                matched_skills=matched,
                relevance=relevance(len(matched), len(skills)),
                score=score
                + bonus
                + (LOCAL_BONUS if location and job.source_api == job_sources.ADZUNA else 0.0),
            )
        )

    # Best skill fit first; newer postings break ties.
    ranked.sort(key=lambda item: (item.score, item.job.posted_date or date.min), reverse=True)
    result.items = ranked[:MAX_RESULTS]
    return result
