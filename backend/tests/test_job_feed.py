"""The job feed: free sources, caching, filters, failure handling and safety.

Both sources are stubbed. The suite never calls Adzuna or Himalayas.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from app.models import JobType
from app.services import job_feed, job_sources
from app.services.job_sources import NormalizedJob, SourceError


@pytest.fixture(autouse=True)
def _fresh_cache():
    job_feed.clear_cache()
    yield
    job_feed.clear_cache()


def _job(source, title, company, days_ago=0, **overrides):
    fields = {
        "source_api": source,
        "external_id": f"{source}-{uuid.uuid4().hex}",
        "title": title,
        "company_name": company,
        "company_logo_url": None,
        "location": "Calgary, Alberta" if source == job_sources.ADZUNA else "Remote (Canada)",
        "salary_range": None,
        "url": f"https://example.com/jobs/{uuid.uuid4().hex}",
        "posted_date": date.today() - timedelta(days=days_ago),
        "description": "We are hiring a thoughtful engineer. " * 10,
        "job_type": JobType.full_time,
        "source_publisher": "Adzuna" if source == job_sources.ADZUNA else "Himalayas",
    }
    fields.update(overrides)
    return NormalizedJob(**fields)


@pytest.fixture
def sources(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "adzuna_app_id", "test-id")
    monkeypatch.setattr(settings, "adzuna_app_key", "test-key")
    state = {
        job_sources.ADZUNA: [],
        job_sources.HIMALAYAS: [],
        "calls": {job_sources.ADZUNA: [], job_sources.HIMALAYAS: []},
        "failing": set(),
    }

    def stub(name):
        def search(**kwargs):
            state["calls"][name].append(kwargs)
            if name in state["failing"]:
                raise SourceError(f"{name} returned an error")
            return state[name]

        return search

    monkeypatch.setattr(job_sources, "search_adzuna", stub(job_sources.ADZUNA))
    monkeypatch.setattr(job_sources, "search_himalayas", stub(job_sources.HIMALAYAS))
    return state


def _feed(client, headers, **params):
    response = client.get("/api/jobs/feed", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _calls(sources, name):
    return len(sources["calls"][name])


# --- Showing jobs -------------------------------------------------------------


def test_feed_requires_sign_in(client):
    assert client.get("/api/jobs/feed").status_code == 401


def test_feed_merges_both_sources_newest_first(client, auth, sources):
    headers, _, _ = auth()
    tag = uuid.uuid4().hex[:8]
    sources[job_sources.ADZUNA] = [_job(job_sources.ADZUNA, f"Analyst {tag}", "Acme", days_ago=3)]
    sources[job_sources.HIMALAYAS] = [_job(job_sources.HIMALAYAS, f"Engineer {tag}", "Hooli", days_ago=1)]

    feed = _feed(client, headers)

    assert [j["title"] for j in feed["jobs"]] == [f"Engineer {tag}", f"Analyst {tag}"]
    assert [j["source_publisher"] for j in feed["jobs"]] == ["Himalayas", "Adzuna"]
    assert feed["sources"] == ["adzuna", "himalayas"]
    assert feed["notice"] is None


def test_cross_source_duplicates_are_dropped(client, auth, sources):
    headers, _, _ = auth()
    title = f"Designer {uuid.uuid4().hex[:8]}"
    sources[job_sources.ADZUNA] = [_job(job_sources.ADZUNA, title, "Globex")]
    sources[job_sources.HIMALAYAS] = [_job(job_sources.HIMALAYAS, title.upper(), "globex")]

    jobs = _feed(client, headers)["jobs"]

    assert len(jobs) == 1
    assert jobs[0]["source_publisher"] == "Adzuna"


def test_feed_jobs_work_like_any_other_job(client, auth, sources):
    """Stored as ordinary rows, so saving and the job page just work."""
    headers, _, _ = auth()
    title = f"Nurse {uuid.uuid4().hex[:8]}"
    sources[job_sources.HIMALAYAS] = [_job(job_sources.HIMALAYAS, title, "Initech")]
    job = _feed(client, headers)["jobs"][0]

    assert client.post(f"/api/saved/{job['id']}", headers=headers).status_code == 201
    detail = client.get(f"/api/jobs/{job['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["job"]["title"] == title
    assert _feed(client, headers)["jobs"][0]["is_saved"] is True


# --- Search, filters and caching -------------------------------------------------


def test_filters_reach_the_sources(client, auth, sources):
    headers, _, _ = auth()
    _feed(
        client, headers,
        q="Nurse", location="Calgary", job_type="part_time", posted_within_days=7, page=2,
    )

    assert sources["calls"][job_sources.ADZUNA] == [
        {"q": "nurse", "location": "calgary", "job_type": JobType.part_time,
         "posted_within_days": 7, "page": 2}
    ]
    assert sources["calls"][job_sources.HIMALAYAS] == [
        {"q": "nurse", "job_type": JobType.part_time, "page": 2}
    ]


def test_identical_searches_are_cached(client, auth, sources):
    """Adzuna allows about 80 calls a day, so repeats must not reach it."""
    headers, _, _ = auth()
    _feed(client, headers, q="python")
    _feed(client, headers, q="python")
    _feed(client, headers, q="Python")  # same search, different case
    assert _calls(sources, job_sources.ADZUNA) == 1
    assert _calls(sources, job_sources.HIMALAYAS) == 1

    _feed(client, headers, q="golang")
    assert _calls(sources, job_sources.ADZUNA) == 2


def test_cache_is_shared_between_users(client, auth, sources):
    first, _, _ = auth()
    second, _, _ = auth()
    _feed(client, first, q="welder")
    _feed(client, second, q="welder")
    assert _calls(sources, job_sources.ADZUNA) == 1


def test_remote_only_uses_himalayas_alone(client, auth, sources):
    headers, _, _ = auth()
    _feed(client, headers, remote_only="true")
    _feed(client, headers, job_type="remote", q="ops")
    assert _calls(sources, job_sources.ADZUNA) == 0
    assert _calls(sources, job_sources.HIMALAYAS) == 2


def test_feed_runs_on_himalayas_without_adzuna_keys(client, auth, sources, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "adzuna_app_key", "")
    headers, _, _ = auth()
    feed = _feed(client, headers)
    assert _calls(sources, job_sources.ADZUNA) == 0
    assert feed["sources"] == ["himalayas"]


def test_posted_within_drops_older_listings(client, auth, sources):
    headers, _, _ = auth()
    tag = uuid.uuid4().hex[:8]
    sources[job_sources.HIMALAYAS] = [
        _job(job_sources.HIMALAYAS, f"Fresh {tag}", "A", days_ago=2),
        _job(job_sources.HIMALAYAS, f"Stale {tag}", "B", days_ago=40),
        _job(job_sources.HIMALAYAS, f"Undated {tag}", "C", posted_date=None),
    ]
    titles = [j["title"] for j in _feed(client, headers, posted_within_days=7)["jobs"]]
    assert titles == [f"Fresh {tag}"]


def test_has_more_when_a_source_returns_a_full_page(client, auth, sources):
    headers, _, _ = auth()
    sources[job_sources.HIMALAYAS] = [
        _job(job_sources.HIMALAYAS, f"Role {i} {uuid.uuid4().hex[:6]}", f"Co {i}")
        for i in range(job_sources.HAS_MORE_THRESHOLD)
    ]
    assert _feed(client, headers)["has_more"] is True
    sources[job_sources.HIMALAYAS] = sources[job_sources.HIMALAYAS][:3]
    assert _feed(client, headers, q="fewer")["has_more"] is False


def test_bad_parameters_are_rejected(client, auth, sources):
    headers, _, _ = auth()
    for params in ({"page": 0}, {"page": 21}, {"posted_within_days": 0},
                   {"posted_within_days": 91}, {"q": "x" * 201}, {"job_type": "bogus"}):
        assert client.get("/api/jobs/feed", params=params, headers=headers).status_code == 422


# --- Failure handling -------------------------------------------------------------


def test_one_failing_source_does_not_break_the_feed(client, auth, sources):
    headers, _, _ = auth()
    title = f"Chef {uuid.uuid4().hex[:8]}"
    sources[job_sources.HIMALAYAS] = [_job(job_sources.HIMALAYAS, title, "Umbrella")]
    sources["failing"] = {job_sources.ADZUNA}

    feed = _feed(client, headers)

    assert [j["title"] for j in feed["jobs"]] == [title]
    assert feed["sources"] == ["himalayas"]
    assert feed["notice"] is None


def test_stored_jobs_are_served_when_every_source_fails(client, auth, sources):
    headers, _, _ = auth()
    tag = uuid.uuid4().hex[:10]
    sources[job_sources.HIMALAYAS] = [_job(job_sources.HIMALAYAS, f"Pilot {tag}", "Oceanic")]
    _feed(client, headers, q=tag)

    job_feed.clear_cache()
    sources["failing"] = {job_sources.ADZUNA, job_sources.HIMALAYAS}
    feed = _feed(client, headers, q=tag)

    assert [j["title"] for j in feed["jobs"]] == [f"Pilot {tag}"]
    assert feed["sources"] == []
    assert "earlier searches" in feed["notice"]

    # A failed search is not cached, so recovery is picked up straight away.
    sources["failing"] = set()
    before = _calls(sources, job_sources.HIMALAYAS)
    _feed(client, headers, q=tag)
    assert _calls(sources, job_sources.HIMALAYAS) == before + 1


def test_nothing_stored_and_every_source_down(client, auth, sources):
    headers, _, _ = auth()
    sources["failing"] = {job_sources.ADZUNA, job_sources.HIMALAYAS}
    feed = _feed(client, headers, q=f"nothing-{uuid.uuid4().hex}")
    assert feed["jobs"] == []
    assert "unavailable" in feed["notice"]


def test_refetching_updates_the_same_row(client, auth, sources, db):
    from app.models import Job

    headers, _, _ = auth()
    listing = _job(job_sources.HIMALAYAS, f"Old title {uuid.uuid4().hex[:6]}", "Wayne")
    sources[job_sources.HIMALAYAS] = [listing]
    first = _feed(client, headers)["jobs"][0]

    job_feed.clear_cache()
    listing.title = "New title"
    second = _feed(client, headers)["jobs"][0]

    assert second["id"] == first["id"]
    assert second["title"] == "New title"
    assert db.query(Job).filter_by(external_id=listing.external_id).count() == 1


# --- Untrusted source data ---------------------------------------------------------


def test_adzuna_listing_is_cleaned(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "job_country", "ca")
    job = job_sources.normalize_adzuna({
        "id": 4242,
        "title": "<strong>Python</strong> Developer",
        "company": {"display_name": "Acme"},
        "location": {"display_name": "Calgary, Alberta"},
        "description": "<p>Build <b>APIs</b></p><script>alert(1)</script>",
        "redirect_url": "javascript:alert(1)",
        "created": "2026-09-10T12:00:00Z",
        "salary_min": 80000,
        "salary_max": 100000,
        "salary_is_predicted": "1",
        "contract_time": "full_time",
    })

    assert job.title == "Python Developer"
    assert job.url is None  # never rendered as an href
    assert "<" not in job.description
    assert job.salary_range == "$80,000 - $100,000 (est.)"
    assert job.job_type is JobType.full_time
    assert job.posted_date == date(2026, 9, 10)
    assert (job.source_api, job.external_id, job.source_publisher) == ("adzuna", "4242", "Adzuna")


def test_incomplete_listings_are_skipped():
    assert job_sources.normalize_adzuna({"id": 1, "title": "No company"}) is None
    assert job_sources.normalize_himalayas({"title": "No id", "companyName": "X"}) is None


def test_himalayas_listing_is_cleaned():
    stamp = 1789237546
    job = job_sources.normalize_himalayas({
        "guid": "https://himalayas.app/companies/x/jobs/backend",
        "applicationLink": "https://himalayas.app/companies/x/jobs/backend",
        "title": "Backend Engineer",
        "companyName": "X Corp",
        "companyLogo": "http://insecure.example/logo.png",
        "employmentType": "Contractor",
        "minSalary": 30,
        "maxSalary": 90,
        "currency": "USD",
        "salaryPeriod": "hourly",
        "locationRestrictions": ["Canada", "United States", "Mexico", "Brazil"],
        "description": "<p>Hello <em>there</em></p>",
        "pubDate": stamp,
    })

    assert job.location == "Remote (Canada, United States, Mexico +1 more)"
    assert job.company_logo_url is None  # logos must be https
    assert job.job_type is JobType.contract
    assert job.salary_range == "$30 - $90/hr"
    assert job.url == "https://himalayas.app/companies/x/jobs/backend"
    assert "<" not in job.description
    assert job.posted_date == datetime.fromtimestamp(stamp, tz=timezone.utc).date()
    assert job.source_publisher == "Himalayas"

    worldwide = job_sources.normalize_himalayas({
        "guid": "g", "title": "T", "companyName": "C", "locationRestrictions": [],
    })
    assert worldwide.location == "Remote (worldwide)"


def test_source_errors_never_expose_the_api_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "adzuna_app_id", "id")
    monkeypatch.setattr(settings, "adzuna_app_key", "super-secret-key")

    def boom(self, url, params=None, **kwargs):
        raise httpx.ConnectError(f"failed {url}?app_key={params['app_key']}")

    monkeypatch.setattr(httpx.Client, "get", boom)
    with pytest.raises(SourceError) as excinfo:
        job_sources.search_adzuna(q="x", location=None, job_type=None,
                                  posted_within_days=None, page=1)
    assert "super-secret-key" not in str(excinfo.value)


def test_country_must_be_a_two_letter_code():
    from pydantic import ValidationError

    from app.config import Settings

    assert Settings(job_country=" CA ").job_country == "ca"
    with pytest.raises(ValidationError):
        Settings(job_country="Canada")
