"""The job feed: search the free sources, store what comes back, cache it.

Adzuna allows 2,500 calls a month, about 80 a day. If every page load reached
the API, a handful of users would exhaust it, so identical searches are served
from an in-process cache for FEED_CACHE_MINUTES. The cache holds job ids, not
jobs: results are re-read from the database and decorated per user, so saved
state and match scores are always current.

Fetched jobs become ordinary Job rows, so saving, match analysis, documents and
application tracking work on them with no special cases.

A source that fails never takes the feed down. If every source fails, the
fallback is jobs already stored from earlier searches, with a notice saying so.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import Company, Job, JobType
from app.services import job_sources

logger = logging.getLogger(__name__)

FEED_SOURCES = (job_sources.ADZUNA, job_sources.HIMALAYAS)
MAX_CACHE_ENTRIES = 256

FALLBACK_NOTICE = (
    "Live job search is unavailable right now, so these are jobs found in earlier searches."
)
UNAVAILABLE_NOTICE = "Live job search is unavailable right now. Try again in a few minutes."


@dataclass(frozen=True, slots=True)
class FeedQuery:
    q: str | None
    location: str | None
    job_type: JobType | None
    remote_only: bool
    posted_within_days: int | None
    page: int


@dataclass(slots=True)
class FeedResult:
    job_ids: list[int]
    has_more: bool
    sources: list[str] = field(default_factory=list)
    notice: str | None = None


_cache: dict[FeedQuery, tuple[float, FeedResult]] = {}
_cache_lock = threading.Lock()
# One writer at a time, so two identical searches cannot race to insert the
# same job or company.
_store_lock = threading.Lock()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _cached(query: FeedQuery) -> FeedResult | None:
    ttl = settings.feed_cache_minutes * 60
    with _cache_lock:
        hit = _cache.get(query)
        if hit is not None and time.monotonic() - hit[0] < ttl:
            return hit[1]
    return None


def _remember(query: FeedQuery, result: FeedResult) -> None:
    if settings.feed_cache_minutes <= 0:
        return
    with _cache_lock:
        if query not in _cache and len(_cache) >= MAX_CACHE_ENTRIES:
            oldest = min(_cache, key=lambda key: _cache[key][0])
            del _cache[oldest]
        _cache[query] = (time.monotonic(), result)


def _fetch(query: FeedQuery) -> tuple[list[job_sources.NormalizedJob], bool, list[str]]:
    """Query the sources in parallel. Returns (jobs, has_more, sources_that_answered)."""
    calls = {}
    # Every Himalayas listing is remote, so remote-only needs Himalayas alone.
    if not query.remote_only and settings.adzuna_enabled:
        calls[job_sources.ADZUNA] = lambda: job_sources.search_adzuna(
            q=query.q,
            location=query.location,
            job_type=query.job_type,
            posted_within_days=query.posted_within_days,
            page=query.page,
        )
    calls[job_sources.HIMALAYAS] = lambda: job_sources.search_himalayas(
        q=query.q, job_type=query.job_type, page=query.page
    )

    groups: list[list[job_sources.NormalizedJob]] = []
    answered: list[str] = []
    has_more = False
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = {name: pool.submit(call) for name, call in calls.items()}
        # Adzuna first, so it wins cross-source duplicates.
        for name, future in futures.items():
            try:
                jobs = future.result()
            except job_sources.SourceError as exc:
                logger.warning("Job source %s failed: %s", name, exc)
                continue
            except Exception:
                logger.exception("Job source %s failed unexpectedly", name)
                continue
            answered.append(name)
            has_more = has_more or len(jobs) >= job_sources.HAS_MORE_THRESHOLD
            groups.append(jobs)

    jobs = job_sources.merge(*groups)
    if query.posted_within_days:
        # Adzuna filters by date itself; Himalayas has no such parameter.
        cutoff = date.today() - timedelta(days=query.posted_within_days)
        jobs = [job for job in jobs if job.posted_date is not None and job.posted_date >= cutoff]
    return jobs, has_more, answered


def _store(db: Session, found: list[job_sources.NormalizedJob]) -> list[int]:
    """Upsert fetched jobs as ordinary Job rows. Returns their ids in feed order."""
    # Imported here: the jobs router imports this module. Shared with pasting so
    # the same employer collapses onto one Company row whichever way it arrived.
    from app.routers.jobs import _get_or_create_company

    with _store_lock:
        for attempt in (1, 2):
            try:
                ids: list[int] = []
                seen: set[tuple[str, str]] = set()
                for item in found:
                    identity = (item.source_api, item.external_id)
                    if identity in seen:
                        continue
                    seen.add(identity)

                    company = _get_or_create_company(db, item.company_name)
                    if item.company_logo_url and not company.logo_url:
                        company.logo_url = item.company_logo_url

                    job = db.scalar(
                        select(Job).where(
                            Job.source_api == item.source_api,
                            Job.external_id == item.external_id,
                        )
                    )
                    if job is None:
                        job = Job(source_api=item.source_api, external_id=item.external_id)
                        db.add(job)
                    # Refreshed every fetch, in case the listing was edited.
                    job.company_id = company.id
                    job.title = item.title
                    job.location = item.location
                    job.salary_range = item.salary_range
                    job.url = item.url
                    job.posted_date = item.posted_date
                    job.description = item.description
                    job.job_type = item.job_type
                    job.source_publisher = item.source_publisher
                    db.flush()
                    ids.append(job.id)
                db.commit()
                return ids
            except IntegrityError:
                # Another worker (e.g. a paste) created the same company or job.
                db.rollback()
                if attempt == 2:
                    raise
    return []


def _stored(db: Session, query: FeedQuery) -> list[int]:
    """Matching jobs kept from earlier searches, for when every source is down."""
    statement = (
        select(Job.id)
        .join(Company, Company.id == Job.company_id)
        .where(Job.source_api.in_(FEED_SOURCES))
    )
    if query.q:
        statement = statement.where(
            or_(
                Job.title.icontains(query.q, autoescape=True),
                Company.name.icontains(query.q, autoescape=True),
            )
        )
    if query.location and not query.remote_only:
        statement = statement.where(Job.location.icontains(query.location, autoescape=True))
    if query.remote_only:
        statement = statement.where(Job.source_api == job_sources.HIMALAYAS)
    if query.job_type is not None:
        statement = statement.where(Job.job_type == query.job_type)
    if query.posted_within_days:
        statement = statement.where(
            Job.posted_date >= date.today() - timedelta(days=query.posted_within_days)
        )
    statement = (
        statement.order_by(Job.posted_date.desc().nulls_last(), Job.id.desc())
        .offset((query.page - 1) * job_sources.PAGE_SIZE)
        .limit(job_sources.PAGE_SIZE)
    )
    return list(db.scalars(statement))


def search(db: Session, query: FeedQuery) -> FeedResult:
    hit = _cached(query)
    if hit is not None:
        return hit

    found, has_more, answered = _fetch(query)
    if not answered:
        ids = _stored(db, query)
        # Not cached, so the next request tries the live sources again.
        return FeedResult(
            job_ids=ids,
            has_more=len(ids) >= job_sources.PAGE_SIZE,
            sources=[],
            notice=FALLBACK_NOTICE if ids else UNAVAILABLE_NOTICE,
        )

    result = FeedResult(job_ids=_store(db, found), has_more=has_more, sources=answered)
    _remember(query, result)
    return result


def load_jobs(db: Session, ids: list[int]) -> list[Job]:
    """Jobs in the given order, skipping any deleted since they were cached."""
    if not ids:
        return []
    rows = db.scalars(select(Job).options(selectinload(Job.company)).where(Job.id.in_(ids)))
    by_id = {job.id: job for job in rows}
    return [by_id[job_id] for job_id in ids if job_id in by_id]
