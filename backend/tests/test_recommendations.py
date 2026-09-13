"""Job recommendations from resume skills.

The with_resume fixture gives the user skills Python, FastAPI, PostgreSQL and
AWS, job titles Backend Engineer and Senior Backend Engineer, and the location
London, UK. Both job sources are stubbed; nothing calls Adzuna or Himalayas.
"""

import uuid
from datetime import date, timedelta

import pytest

from app.models import JobType
from app.services import job_feed, job_sources, recommendations
from app.services.job_sources import NormalizedJob


@pytest.fixture(autouse=True)
def _fresh_cache():
    job_feed.clear_cache()
    yield
    job_feed.clear_cache()


def _job(source, title, description, company=None, days_ago=0):
    return NormalizedJob(
        source_api=source,
        external_id=f"{source}-{uuid.uuid4().hex}",
        title=title,
        company_name=company or f"Company {uuid.uuid4().hex[:6]}",
        company_logo_url=None,
        location="Calgary, Alberta" if source == job_sources.ADZUNA else "Remote (Canada)",
        salary_range=None,
        url=f"https://example.com/jobs/{uuid.uuid4().hex}",
        posted_date=date.today() - timedelta(days=days_ago),
        description=description,
        job_type=JobType.full_time,
        source_publisher="Adzuna" if source == job_sources.ADZUNA else "Himalayas",
    )


@pytest.fixture
def sources(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "adzuna_app_id", "test-id")
    monkeypatch.setattr(settings, "adzuna_app_key", "test-key")
    state = {
        job_sources.ADZUNA: [],
        job_sources.HIMALAYAS: [],
        "calls": {job_sources.ADZUNA: [], job_sources.HIMALAYAS: []},
    }

    def stub(name):
        def search(**kwargs):
            state["calls"][name].append(kwargs)
            return state[name]

        return search

    monkeypatch.setattr(job_sources, "search_adzuna", stub(job_sources.ADZUNA))
    monkeypatch.setattr(job_sources, "search_himalayas", stub(job_sources.HIMALAYAS))
    return state


def _recommended(client, headers):
    response = client.get("/api/jobs/recommended", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- What gets searched ------------------------------------------------------------


def test_without_a_resume_it_asks_for_one(client, auth, sources):
    headers, _, _ = auth()
    data = _recommended(client, headers)
    assert data["jobs"] == []
    assert "Upload your resume" in data["notice"]
    assert sources["calls"][job_sources.ADZUNA] == []


def test_searches_the_resume_job_titles_and_location(client, with_resume, sources):
    headers, _ = with_resume()
    data = _recommended(client, headers)

    assert data["searched_titles"] == ["Backend Engineer", "Senior Backend Engineer"]
    assert data["location"] == "London, UK"
    calls = sources["calls"][job_sources.ADZUNA]
    assert [c["q"] for c in calls] == ["backend engineer", "senior backend engineer"]
    assert {c["location"] for c in calls} == {"london, uk"}


def test_preferred_location_overrides_the_resume(client, with_resume, sources):
    headers, _ = with_resume()
    profile = client.patch("/api/profile", json={"preferred_location": " Calgary, AB "}, headers=headers)
    assert profile.json()["preferred_location"] == "Calgary, AB"

    _recommended(client, headers)
    assert sources["calls"][job_sources.ADZUNA][-1]["location"] == "calgary, ab"

    # Clearing it goes back to the resume location.
    client.patch("/api/profile", json={"preferred_location": None}, headers=headers)
    data = _recommended(client, headers)
    assert data["location"] == "London, UK"


def test_a_title_with_few_local_jobs_is_searched_without_its_level(client, with_resume, sources, monkeypatch):
    """Local boards rarely list "Intern" titles, so the role is searched without it."""
    headers, resume = with_resume()
    client.patch(
        f"/api/resumes/{resume['id']}/skill-profile",
        json={"job_titles": ["Software Developer Intern"]},
        headers=headers,
    )
    local_job = _job(job_sources.ADZUNA, "Software Developer", "Python and AWS.")
    queries = []

    def adzuna(**kwargs):
        queries.append(kwargs["q"])
        return [] if "intern" in kwargs["q"] else [local_job]

    monkeypatch.setattr(job_sources, "search_adzuna", adzuna)
    data = _recommended(client, headers)

    assert queries == ["software developer intern", "software developer"]
    assert [j["job"]["title"] for j in data["jobs"]] == ["Software Developer"]
    # The page still says what the resume asked for.
    assert data["searched_titles"] == ["Software Developer Intern"]


def test_no_broader_search_when_local_results_are_plenty(client, with_resume, sources):
    headers, resume = with_resume()
    client.patch(
        f"/api/resumes/{resume['id']}/skill-profile",
        json={"job_titles": ["Software Developer Intern"]},
        headers=headers,
    )
    sources[job_sources.ADZUNA] = [
        _job(job_sources.ADZUNA, f"Software Developer Intern {i}", "Python.")
        for i in range(recommendations.MIN_LOCAL_RESULTS)
    ]
    _recommended(client, headers)
    assert [c["q"] for c in sources["calls"][job_sources.ADZUNA]] == ["software developer intern"]


def test_repeat_visits_use_the_cache(client, with_resume, sources):
    headers, _ = with_resume()
    _recommended(client, headers)
    after_first = len(sources["calls"][job_sources.ADZUNA])
    _recommended(client, headers)
    assert len(sources["calls"][job_sources.ADZUNA]) == after_first == 2


# --- Ranking -------------------------------------------------------------------------


def test_ranks_by_skills_and_says_why(client, with_resume, sources):
    headers, _ = with_resume()
    strong = _job(job_sources.ADZUNA, "Python Backend Engineer",
                  "Build APIs with FastAPI and PostgreSQL on AWS.")
    medium = _job(job_sources.ADZUNA, "Data Engineer", "Pipelines written in Python.")
    unrelated = _job(job_sources.ADZUNA, "Line Cook", "Prepare food in a busy kitchen.")
    sources[job_sources.ADZUNA] = [unrelated, medium, strong]

    jobs = _recommended(client, headers)["jobs"]

    assert [j["job"]["title"] for j in jobs] == ["Python Backend Engineer", "Data Engineer"]
    assert set(jobs[0]["matched_skills"]) == {"Python", "FastAPI", "PostgreSQL", "AWS"}
    assert jobs[0]["relevance"] == 100
    assert jobs[1]["matched_skills"] == ["Python"]
    assert jobs[0]["relevance"] > jobs[1]["relevance"]


def test_a_target_role_stays_in_even_without_skill_mentions(client, with_resume, sources):
    """Short adverts often name no skills; the role itself is still a fit."""
    headers, _ = with_resume()
    sources[job_sources.ADZUNA] = [
        _job(job_sources.ADZUNA, "Backend Engineer II", "Join our growing team."),
        _job(job_sources.ADZUNA, "Office Manager", "Join our growing team."),
    ]
    jobs = _recommended(client, headers)["jobs"]
    assert [j["job"]["title"] for j in jobs] == ["Backend Engineer II"]
    assert jobs[0]["matched_skills"] == []
    assert jobs[0]["relevance"] == 0


def test_local_jobs_are_not_buried_by_long_remote_adverts(client, with_resume, sources):
    """Local snippets name few skills; a long remote advert must not win on length."""
    headers, _ = with_resume()
    sources[job_sources.ADZUNA] = [_job(job_sources.ADZUNA, "Backend Engineer", "Join our team.")]
    sources[job_sources.HIMALAYAS] = [
        _job(job_sources.HIMALAYAS, "Remote Developer",
             "Python, FastAPI, PostgreSQL and AWS. " * 50)
    ]
    titles = [j["job"]["title"] for j in _recommended(client, headers)["jobs"]]
    assert titles == ["Backend Engineer", "Remote Developer"]


def test_the_same_job_from_two_title_searches_appears_once(client, with_resume, sources):
    headers, _ = with_resume()
    sources[job_sources.ADZUNA] = [_job(job_sources.ADZUNA, "Backend Engineer", "Python and AWS.")]
    jobs = _recommended(client, headers)["jobs"]
    assert len(jobs) == 1


def test_remote_jobs_can_be_left_out(client, with_resume, sources):
    headers, _ = with_resume()
    sources[job_sources.ADZUNA] = [_job(job_sources.ADZUNA, "Backend Engineer", "Python.")]
    sources[job_sources.HIMALAYAS] = [_job(job_sources.HIMALAYAS, "Remote Python Developer", "Python and AWS.")]

    assert len(_recommended(client, headers)["jobs"]) == 2

    client.patch("/api/profile", json={"include_remote": False}, headers=headers)
    data = _recommended(client, headers)
    assert data["include_remote"] is False
    assert [j["job"]["source_publisher"] for j in data["jobs"]] == ["Adzuna"]


def test_jobs_already_applied_to_are_left_out(client, with_resume, sources):
    headers, _ = with_resume()
    sources[job_sources.ADZUNA] = [
        _job(job_sources.ADZUNA, "Backend Engineer", "Python and AWS."),
        _job(job_sources.ADZUNA, "Platform Engineer", "Python and PostgreSQL."),
    ]
    first = _recommended(client, headers)["jobs"][0]["job"]
    assert client.post("/api/applications", json={"job_id": first["id"]}, headers=headers).status_code == 201

    remaining = [j["job"]["id"] for j in _recommended(client, headers)["jobs"]]
    assert first["id"] not in remaining
    assert len(remaining) == 1


def test_recommended_jobs_carry_the_usual_per_user_state(client, with_resume, sources):
    headers, _ = with_resume()
    sources[job_sources.ADZUNA] = [_job(job_sources.ADZUNA, "Backend Engineer", "Python and AWS.")]
    job = _recommended(client, headers)["jobs"][0]["job"]

    client.post(f"/api/saved/{job['id']}", headers=headers)
    again = _recommended(client, headers)["jobs"][0]["job"]
    assert again["is_saved"] is True
    assert again["match_percentage"] is None  # no AI call happens here


# --- Skill matching ----------------------------------------------------------------------


def test_short_and_symbol_skills_match_whole_words_only():
    matched, _ = recommendations.match_skills(
        ["Go", "C++", "SQL", "R", "Java"],
        "Go Developer",
        "C++ and SQL. We are going to Google. Some JavaScript. Rust.",
    )
    assert matched == ["Go", "C++", "SQL"]


def test_one_letter_skills_ignore_abbreviations():
    """R&D and C-suite are not the R and C languages."""
    skills = ["R", "C"]
    assert recommendations.match_skills(skills, "Analyst", "Join our R&D team and C-suite reporting.")[0] == []
    assert recommendations.match_skills(skills, "Analyst", "Based in the U.S. with A/B tests.")[0] == []
    assert recommendations.match_skills(skills, "Analyst", "You know Python, SQL and R.")[0] == ["R"]
    assert recommendations.match_skills(skills, "Analyst", "Systems work in C, plus R (tidyverse).")[0] == ["R", "C"]


def test_a_title_mention_counts_double():
    assert recommendations.match_skills(["Python"], "Python Developer", "")[1] == 2
    assert recommendations.match_skills(["Python"], "Developer", "Python daily")[1] == 1


def test_description_mentions_are_capped():
    skills = ["Python", "SQL", "Java", "Git", "Docker", "AWS"]
    description = "Python SQL Java Git Docker AWS"
    matched, score = recommendations.match_skills(skills, "Developer", description)
    assert len(matched) == 6
    assert score == recommendations.DESCRIPTION_MATCH_CAP
    # Title mentions are not capped.
    assert recommendations.match_skills(skills, "Python SQL Java Developer", "")[1] == 6


def test_broaden_title_drops_level_and_term_words():
    assert recommendations.broaden_title("Software Developer Intern") == "Software Developer"
    assert recommendations.broaden_title("Senior Backend Engineer II") == "Backend Engineer"
    assert recommendations.broaden_title("Data Analyst Co-op (Summer 2026)") == "Data Analyst"
    assert recommendations.broaden_title("C++ Developer") == "C++ Developer"
    assert recommendations.broaden_title("Intern") == ""


def test_relevance_is_measured_against_a_realistic_skill_count():
    assert recommendations.relevance(5, 40) == 50  # capped at ten expected skills
    assert recommendations.relevance(3, 3) == 100
    assert recommendations.relevance(0, 8) == 0
