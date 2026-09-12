"""Free job sources: Adzuna and Himalayas.

Pure module: calls the APIs and normalises what comes back. No database access;
storing and caching are job_feed.py.

Everything these APIs return is untrusted third-party data. Descriptions arrive
as HTML and are reduced to plain text. Links are kept only if they are http(s),
because the Apply button renders them as an href, and logos only if https.

Terms we follow:
  * Adzuna allows publishing its listings. Free keys get 25 calls a minute,
    250 a day and 2,500 a month.
  * Himalayas asks for a link back to its listing and to be named as the
    source; the Apply button does both ("Apply on Himalayas").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.models import JobType
from app.schemas import clean_text
from app.services.job_url import page_text

logger = logging.getLogger(__name__)

ADZUNA = "adzuna"
HIMALAYAS = "himalayas"

PAGE_SIZE = 20
# A source returning at least this many results probably has another page.
HAS_MORE_THRESHOLD = 15
MAX_DESCRIPTION_CHARS = 20_000
TIMEOUT = httpx.Timeout(15.0, connect=8.0)
USER_AGENT = "PromptlyHired/1.0 (+https://github.com/Slipstream-Syndicate1/PromptlyHired)"

ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
HIMALAYAS_URL = "https://himalayas.app/jobs/api/search"


class SourceError(RuntimeError):
    """A job source failed. The feed carries on with the other source.

    Messages are written here, never taken from the underlying exception:
    httpx errors include the request URL, and Adzuna's carries the API key.
    """


@dataclass(slots=True)
class NormalizedJob:
    source_api: str
    external_id: str
    title: str
    company_name: str
    company_logo_url: str | None
    location: str | None
    salary_range: str | None
    url: str | None
    posted_date: date | None
    description: str | None
    job_type: JobType | None
    source_publisher: str


# --- Shared helpers -----------------------------------------------------------


def _safe_url(value: object, *, https_only: bool = False) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    allowed = {"https"} if https_only else {"http", "https"}
    if parsed.scheme.lower() not in allowed or not parsed.netloc:
        return None
    return value[:2048]


def _text(value: object, limit: int) -> str | None:
    """HTML or plain text from a source, reduced to clean plain text."""
    if not isinstance(value, str) or not value.strip():
        return None
    return clean_text(page_text(value, limit=limit))


def _int(value: object) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _get_json(url: str, params: dict[str, str], name: str) -> dict:
    try:
        with httpx.Client(
            timeout=TIMEOUT, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        ) as client:
            response = client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise SourceError(f"{name} could not be reached") from exc

    if response.status_code == 429:
        raise SourceError(f"{name} rate limit reached")
    if response.status_code >= 400:
        # Status only: the URL would leak Adzuna's key into the logs.
        logger.warning("%s returned HTTP %s", name, response.status_code)
        raise SourceError(f"{name} returned an error")
    try:
        data = response.json()
    except ValueError as exc:
        raise SourceError(f"{name} returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise SourceError(f"{name} returned an unexpected response")
    return data


# --- Adzuna -------------------------------------------------------------------

_ADZUNA_CURRENCY = {
    "ca": "$", "us": "$", "au": "$", "nz": "$", "sg": "$",
    "gb": "£", "in": "₹",
    "de": "€", "fr": "€", "nl": "€", "it": "€", "es": "€", "at": "€", "be": "€",
}


def _adzuna_salary(item: dict) -> str | None:
    lo, hi = _int(item.get("salary_min")), _int(item.get("salary_max"))
    if lo is None and hi is None:
        return None
    symbol = _ADZUNA_CURRENCY.get(settings.job_country, "")
    if lo is not None and hi is not None and lo != hi:
        text = f"{symbol}{lo:,} - {symbol}{hi:,}"
    else:
        text = f"{symbol}{(lo if lo is not None else hi):,}"
    # Adzuna estimates some salaries; label those rather than pass a guess off as fact.
    if str(item.get("salary_is_predicted", "0")).lower() in {"1", "true"}:
        text += " (est.)"
    return text[:120]


def _adzuna_job_type(item: dict) -> JobType | None:
    contract_time = str(item.get("contract_time") or "").lower()
    contract_type = str(item.get("contract_type") or "").lower()
    if contract_time == "part_time":
        return JobType.part_time
    if contract_type == "contract":
        return JobType.contract
    if contract_time == "full_time":
        return JobType.full_time
    return None


def _adzuna_posted(item: dict) -> date | None:
    raw = item.get("created")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def normalize_adzuna(item: dict) -> NormalizedJob | None:
    external_id = item.get("id")
    title = _text(item.get("title"), 500)
    company = _text((item.get("company") or {}).get("display_name"), 255)
    if not external_id or not title or not company:
        return None
    location = _text((item.get("location") or {}).get("display_name"), 255)
    return NormalizedJob(
        source_api=ADZUNA,
        external_id=str(external_id)[:768],
        title=title,
        company_name=company,
        company_logo_url=None,
        location=location,
        salary_range=_adzuna_salary(item),
        url=_safe_url(item.get("redirect_url")),
        posted_date=_adzuna_posted(item),
        # A truncated snippet: Adzuna does not return full descriptions.
        description=_text(item.get("description"), MAX_DESCRIPTION_CHARS),
        job_type=_adzuna_job_type(item),
        source_publisher="Adzuna",
    )


def search_adzuna(
    *,
    q: str | None,
    location: str | None,
    job_type: JobType | None,
    posted_within_days: int | None,
    page: int,
) -> list[NormalizedJob]:
    if not settings.adzuna_enabled:
        return []
    params = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "results_per_page": str(PAGE_SIZE),
        "sort_by": "date",
        "content-type": "application/json",
    }
    if q:
        params["what"] = q
    if location:
        params["where"] = location
    if posted_within_days:
        params["max_days_old"] = str(posted_within_days)
    if job_type is JobType.full_time:
        params["full_time"] = "1"
    elif job_type is JobType.part_time:
        params["part_time"] = "1"
    elif job_type is JobType.contract:
        params["contract"] = "1"

    url = ADZUNA_URL.format(country=settings.job_country, page=max(1, page))
    data = _get_json(url, params, "Adzuna")
    items = data.get("results") or []
    return [job for job in (normalize_adzuna(i) for i in items if isinstance(i, dict)) if job]


# --- Himalayas ----------------------------------------------------------------

_COUNTRY_NAMES = {
    "ca": "Canada", "us": "United States", "gb": "United Kingdom", "au": "Australia",
    "nz": "New Zealand", "ie": "Ireland", "in": "India", "de": "Germany",
    "fr": "France", "nl": "Netherlands", "es": "Spain", "it": "Italy", "sg": "Singapore",
}
_HIMALAYAS_EMPLOYMENT = {
    JobType.full_time: "Full Time",
    JobType.part_time: "Part Time",
    JobType.contract: "Contractor",
}
_CURRENCY_SYMBOLS = {"USD": "$", "CAD": "CA$", "AUD": "A$", "EUR": "€", "GBP": "£", "INR": "₹"}
_SALARY_PERIODS = {"hourly": "/hr", "hour": "/hr", "monthly": "/mo", "month": "/mo",
                   "yearly": "/yr", "annual": "/yr", "annually": "/yr", "year": "/yr"}


def _himalayas_job_type(value: object) -> JobType | None:
    kind = str(value or "").lower()
    if "part" in kind:
        return JobType.part_time
    if any(word in kind for word in ("contract", "temporary", "freelance")):
        return JobType.contract
    if "full" in kind:
        return JobType.full_time
    return None


def _himalayas_salary(item: dict) -> str | None:
    lo, hi = _int(item.get("minSalary")), _int(item.get("maxSalary"))
    if not lo and not hi:
        return None
    currency = str(item.get("currency") or "").upper()[:3]
    symbol = _CURRENCY_SYMBOLS.get(currency, f"{currency} " if currency else "")
    if lo and hi and lo != hi:
        text = f"{symbol}{lo:,} - {symbol}{hi:,}"
    else:
        text = f"{symbol}{(lo or hi):,}"
    text += _SALARY_PERIODS.get(str(item.get("salaryPeriod") or "").lower(), "")
    return text[:120]


def _himalayas_location(item: dict) -> str:
    places = [p for p in item.get("locationRestrictions") or [] if isinstance(p, str) and p.strip()]
    if not places:
        return "Remote (worldwide)"
    shown = ", ".join(places[:3])
    extra = len(places) - 3
    return f"Remote ({shown}{f' +{extra} more' if extra > 0 else ''})"[:255]


def _himalayas_posted(item: dict) -> date | None:
    stamp = _int(item.get("pubDate"))
    if stamp is None:
        return None
    try:
        return datetime.fromtimestamp(stamp, tz=timezone.utc).date()
    except (OverflowError, OSError, ValueError):
        return None


def normalize_himalayas(item: dict) -> NormalizedJob | None:
    external_id = item.get("guid") or item.get("applicationLink")
    title = _text(item.get("title"), 500)
    company = _text(item.get("companyName"), 255)
    if not external_id or not title or not company:
        return None
    return NormalizedJob(
        source_api=HIMALAYAS,
        external_id=str(external_id)[:768],
        title=title,
        company_name=company,
        company_logo_url=_safe_url(item.get("companyLogo"), https_only=True),
        location=_himalayas_location(item),
        salary_range=_himalayas_salary(item),
        # Linking to the Himalayas listing is one of its terms of use.
        url=_safe_url(item.get("applicationLink")) or _safe_url(item.get("guid")),
        posted_date=_himalayas_posted(item),
        description=_text(item.get("description"), MAX_DESCRIPTION_CHARS)
        or _text(item.get("excerpt"), MAX_DESCRIPTION_CHARS),
        job_type=_himalayas_job_type(item.get("employmentType")),
        source_publisher="Himalayas",
    )


def search_himalayas(*, q: str | None, job_type: JobType | None, page: int) -> list[NormalizedJob]:
    params = {"sort": "recent", "page": str(max(1, page))}
    if q:
        params["q"] = q
    country = _COUNTRY_NAMES.get(settings.job_country)
    if country:
        params["country"] = country
    if job_type in _HIMALAYAS_EMPLOYMENT:
        params["employment_type"] = _HIMALAYAS_EMPLOYMENT[job_type]

    data = _get_json(HIMALAYAS_URL, params, "Himalayas")
    items = data.get("jobs") or []
    return [job for job in (normalize_himalayas(i) for i in items if isinstance(i, dict)) if job]


# --- Merging ------------------------------------------------------------------


def merge(*groups: list[NormalizedJob]) -> list[NormalizedJob]:
    """Combine sources, drop cross-source duplicates, newest first.

    The same vacancy has a different id in each source, so identity is title
    plus employer. Earlier groups win a duplicate.
    """
    seen: set[tuple[str, str]] = set()
    out: list[NormalizedJob] = []
    for group in groups:
        for job in group:
            key = (" ".join(job.title.lower().split()), " ".join(job.company_name.lower().split()))
            if key in seen:
                continue
            seen.add(key)
            out.append(job)
    # Stable sort, so equal dates keep source order; undated listings go last.
    out.sort(key=lambda job: job.posted_date or date.min, reverse=True)
    return out
