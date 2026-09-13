"""Tailored resumes made from the master resume.

The master resume is permanent and edited on Profile. A resume for one job is a
copy of it with quick edits: the AI may reword and reorder, but names, schools,
employers, dates and locations always come from the master, and editing a job's
copy never changes the master.
"""

import copy

from app.services import ai, tailored_resume
from tests.conftest import SAMPLE_RESUME

MASTER = {
    "full_name": "Alex Morgan",
    "headline": "",
    "contact_line": "780-555-0100 | alex@example.com | linkedin.com/in/alex | github.com/alex",
    "summary": "",
    "sections": [
        {
            "heading": "Education",
            "bullets": [],
            "entries": [{
                "title": "University of Alberta", "meta": "", "right": "Edmonton, AB",
                "subtitle": "BSc Computing Science", "subtitle_right": "Sept. 2021 - Apr. 2025",
                "bullets": [],
            }],
        },
        {
            "heading": "Experience",
            "bullets": [],
            "entries": [
                {
                    "title": "Software Developer Intern", "meta": "", "right": "May 2024 - Aug. 2024",
                    "subtitle": "Acme Ltd", "subtitle_right": "Edmonton, AB",
                    "bullets": ["Built REST APIs in Python", "Wrote tests"],
                },
                {
                    "title": "IT Assistant", "meta": "", "right": "Sept. 2022 - Apr. 2023",
                    "subtitle": "City Library", "subtitle_right": "Edmonton, AB",
                    "bullets": ["Fixed laptops"],
                },
            ],
        },
        {
            "heading": "Projects",
            "bullets": [],
            "entries": [{
                "title": "Job Tracker", "meta": "React, FastAPI", "right": "2025",
                "subtitle": "", "subtitle_right": "", "bullets": ["Shipped a PWA"],
            }],
        },
    ],
    "skills": ["Languages: Python, JavaScript, SQL", "Frameworks: React, FastAPI"],
}

REORDER_EXPERIENCE_FIRST = {
    "headline": "Backend developer",
    "summary": "",
    "sections": [
        {
            "section_index": 1,
            "entries": [
                {"entry_index": 1, "bullets": ["Supported 40 staff laptops"]},
                {"entry_index": 0, "bullets": ["Designed Python REST APIs for payments"]},
            ],
            "bullets": [],
        },
    ],
    "skills": ["Frameworks: FastAPI, React", "Languages: Python, Rust", "Hacking: Everything"],
}


def _entry_facts(section):
    keys = ("title", "meta", "right", "subtitle", "subtitle_right")
    return [tuple(entry[k] for k in keys) for entry in section["entries"]]


# --- Applying the AI's edits ---------------------------------------------


def test_edits_reorder_and_reword_but_facts_come_from_the_master():
    result = tailored_resume.apply_tailoring(MASTER, REORDER_EXPERIENCE_FIRST)

    assert [s["heading"] for s in result["sections"]] == ["Experience", "Education", "Projects"]
    experience = result["sections"][0]
    assert [e["title"] for e in experience["entries"]] == ["IT Assistant", "Software Developer Intern"]
    assert experience["entries"][1]["bullets"] == ["Designed Python REST APIs for payments"]
    # Every entry keeps its master dates, employer and location.
    assert sorted(_entry_facts(experience)) == sorted(_entry_facts(MASTER["sections"][1]))
    assert result["full_name"] == MASTER["full_name"]
    assert result["contact_line"] == MASTER["contact_line"]


def test_the_master_itself_is_never_modified():
    before = copy.deepcopy(MASTER)
    tailored_resume.apply_tailoring(MASTER, REORDER_EXPERIENCE_FIRST)
    assert MASTER == before


def test_unknown_and_repeated_indexes_cannot_invent_duplicate_or_drop_anything():
    edits = {
        "headline": "", "summary": "", "skills": [],
        "sections": [
            {"section_index": 9, "entries": [], "bullets": []},
            {"section_index": 1, "bullets": [], "entries": [
                {"entry_index": 0, "bullets": ["First"]},
                {"entry_index": 0, "bullets": ["Duplicate"]},
                {"entry_index": 5, "bullets": ["Invented"]},
            ]},
            {"section_index": 1, "entries": [], "bullets": []},
        ],
    }
    result = tailored_resume.apply_tailoring(MASTER, edits)

    assert len(result["sections"]) == 3
    experience = result["sections"][0]
    assert len(experience["entries"]) == 2
    assert experience["entries"][0]["bullets"] == ["First"]
    assert "Invented" not in str(result) and "Duplicate" not in str(result)


def test_entries_without_bullets_do_not_gain_any_and_empty_rewrites_keep_the_original():
    edits = {
        "headline": "", "summary": "", "skills": [],
        "sections": [
            {"section_index": 0, "bullets": ["Top student"], "entries": [
                {"entry_index": 0, "bullets": ["Made up award"]},
            ]},
            {"section_index": 1, "bullets": [], "entries": [{"entry_index": 0, "bullets": ["", "  "]}]},
        ],
    }
    result = tailored_resume.apply_tailoring(MASTER, edits)

    education = result["sections"][0]
    assert education["bullets"] == [] and education["entries"][0]["bullets"] == []
    assert result["sections"][1]["entries"][0]["bullets"] == ["Built REST APIs in Python", "Wrote tests"]


def test_an_entry_never_gets_more_bullets_than_the_master_gave_it():
    """Extra bullets are how a skills list turns into claimed accomplishments."""
    edits = {"sections": [{"section_index": 1, "bullets": [], "entries": [
        {"entry_index": 1, "bullets": ["Fixed laptops", "Deployed AWS infrastructure", "Led a Docker migration"]},
    ]}]}
    result = tailored_resume.apply_tailoring(MASTER, edits)
    it_assistant = result["sections"][0]["entries"][0]
    assert it_assistant["title"] == "IT Assistant"
    assert it_assistant["bullets"] == ["Fixed laptops"]


def test_headline_and_summary_are_only_filled_when_the_master_uses_them():
    assert tailored_resume.apply_tailoring(MASTER, REORDER_EXPERIENCE_FIRST)["headline"] == ""

    with_headline = {**MASTER, "headline": "Developer"}
    assert tailored_resume.apply_tailoring(with_headline, REORDER_EXPERIENCE_FIRST)["headline"] == "Backend developer"


def test_skills_can_be_reordered_and_trimmed_but_never_added():
    result = tailored_resume.apply_tailoring(MASTER, REORDER_EXPERIENCE_FIRST)
    assert result["skills"] == ["Frameworks: FastAPI, React", "Languages: Python"]


def test_a_skill_line_left_out_is_kept_and_nonsense_falls_back_to_the_master():
    kept = tailored_resume.apply_tailoring(MASTER, {"sections": [], "skills": ["Frameworks: React"]})
    assert kept["skills"] == ["Frameworks: React", "Languages: Python, JavaScript, SQL"]

    nonsense = tailored_resume.apply_tailoring(MASTER, {"sections": [], "skills": ["Hacking: Rust"]})
    assert nonsense["skills"] == MASTER["skills"]


def test_normalise_clips_model_output_to_the_master_limits():
    messy = {
        "full_name": "A" * 500,
        "sections": [
            {"heading": "Experience", "bullets": [], "entries": [
                {"title": "T" * 1000, "bullets": ["x"] * 50} for _ in range(30)
            ]},
            {"heading": "", "bullets": ["", " "], "entries": []},
        ],
        "skills": ["Languages: Python", ""],
    }
    result = tailored_resume.normalise(messy)

    assert len(result["full_name"]) == 160
    assert len(result["sections"]) == 1, "empty sections are dropped"
    entries = result["sections"][0]["entries"]
    assert len(entries) == 20 and len(entries[0]["title"]) == 300 and len(entries[0]["bullets"]) == 20
    assert result["skills"] == ["Languages: Python"]


def test_indexed_text_numbers_sections_and_entries():
    text = tailored_resume.indexed_text(MASTER)
    assert "[section 1] Experience" in text
    assert "[entry 1] IT Assistant | City Library | Sept. 2022 - Apr. 2023 | Edmonton, AB" in text
    assert "Languages: Python, JavaScript, SQL" in text


# --- Prompt safety ---------------------------------------------------------


def _capture(monkeypatch, result):
    captured = {}

    def fake_generate(label, *, system, prompt, schema, thinking=None):
        captured.update(system=system, prompt=prompt, schema=schema)
        return result

    monkeypatch.setattr(ai, "_generate", fake_generate)
    return captured


def test_tailoring_fences_the_advert_after_the_master_and_forbids_invention(monkeypatch):
    captured = _capture(monkeypatch, ai.MasterTailoring(headline="", summary="", sections=[], skills=[]))
    ai.tailor_master_resume("MY MASTER RESUME", "Engineer", "Acme", "advert body")

    prompt = captured["prompt"]
    assert prompt.index("MY MASTER RESUME") < prompt.index(ai.UNTRUSTED_OPEN)
    assert "advert body" in prompt
    assert "invent" in captured["system"].lower()
    assert captured["schema"] is ai.MasterTailoring


def test_structuring_a_cv_forbids_invention(monkeypatch):
    captured = _capture(monkeypatch, None)
    ai.structure_resume("MY CV")
    assert "invent" in captured["system"].lower()
    assert "MY CV" in captured["prompt"]


# --- API -----------------------------------------------------------------


def _job(client, headers):
    return client.post(
        "/api/jobs/from-text",
        headers=headers,
        json={"text": "Backend Engineer at Acme Ltd. Python and AWS. " * 5,
              "title": "Backend Engineer", "company": "Acme Ltd",
              "url": "https://example.com/jobs/tailored"},
    ).json()


def _save_master(client, headers, resume_id, master=MASTER):
    r = client.put(f"/api/resumes/{resume_id}/master", headers=headers, json={"master_content": master})
    assert r.status_code == 200, r.text
    return r.json()


def test_create_resume_tailors_the_saved_master(client, with_resume, ai_stub):
    headers, resume = with_resume()
    _save_master(client, headers, resume["id"])
    job = _job(client, headers)
    ai_stub["tailoring"] = REORDER_EXPERIENCE_FIRST

    doc = client.post(f"/api/jobs/{job['id']}/documents", headers=headers, json={"kind": "resume"})
    assert doc.status_code == 201, doc.text
    content = doc.json()["content"]

    assert ai_stub.get("tailor") == 1 and ai_stub["resume"] == 0
    assert "[section 1] Experience" in ai_stub["master_text"]
    assert content["full_name"] == "Alex Morgan"
    assert content["sections"][0]["heading"] == "Experience"
    assert sorted(_entry_facts(content["sections"][0])) == sorted(_entry_facts(MASTER["sections"][1]))


def test_cover_letters_still_come_from_the_cover_letter_call(client, with_resume, ai_stub):
    headers, resume = with_resume()
    _save_master(client, headers, resume["id"])
    job = _job(client, headers)
    r = client.post(f"/api/jobs/{job['id']}/documents", headers=headers, json={"kind": "cover_letter"})
    assert r.status_code == 201
    assert ai_stub["cover"] == 1 and ai_stub.get("tailor", 0) == 0


def test_without_a_master_the_resume_comes_from_the_cv_in_the_same_layout(client, with_resume, ai_stub):
    headers, _ = with_resume()
    job = _job(client, headers)
    content = client.post(
        f"/api/jobs/{job['id']}/documents", headers=headers, json={"kind": "resume"}
    ).json()["content"]
    assert ai_stub["resume"] == 1
    assert content["sections"][0]["entries"] == []
    assert content["sections"][0]["bullets"] == ["Built services"]


def test_start_from_master_is_an_exact_copy_without_ai(client, with_resume, ai_stub):
    headers, resume = with_resume()
    saved = _save_master(client, headers, resume["id"])["master_content"]
    job = _job(client, headers)

    r = client.post(f"/api/jobs/{job['id']}/documents/from-master", headers=headers)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["kind"] == "resume"
    assert doc["content"] == saved
    assert doc["model_used"] == tailored_resume.MASTER_COPY
    assert ai_stub["resume"] == 0 and ai_stub.get("tailor", 0) == 0


def test_start_from_master_needs_a_saved_master(client, with_resume):
    headers, _ = with_resume()
    job = _job(client, headers)
    r = client.post(f"/api/jobs/{job['id']}/documents/from-master", headers=headers)
    assert r.status_code == 422
    assert "Profile" in r.json()["detail"]


def test_start_from_master_unknown_job(client, with_resume):
    headers, resume = with_resume()
    _save_master(client, headers, resume["id"])
    assert client.post("/api/jobs/999999/documents/from-master", headers=headers).status_code == 404


def test_editing_a_jobs_copy_never_changes_the_master(client, with_resume, ai_stub):
    headers, resume = with_resume()
    _save_master(client, headers, resume["id"])
    job = _job(client, headers)
    doc = client.post(f"/api/jobs/{job['id']}/documents/from-master", headers=headers).json()

    edited = {**doc["content"], "full_name": "Someone Else", "sections": []}
    assert client.patch(
        f"/api/documents/{doc['id']}", headers=headers, json={"edited_content": edited}
    ).status_code == 200

    master = client.get("/api/resumes/active", headers=headers).json()["master_content"]
    assert master["full_name"] == "Alex Morgan"
    assert len(master["sections"]) == 3


def test_uploading_a_new_cv_keeps_the_master(client, with_resume, ai_stub):
    headers, resume = with_resume()
    _save_master(client, headers, resume["id"])

    second = client.post(
        "/api/resumes",
        headers=headers,
        files={"file": ("cv2.txt", SAMPLE_RESUME.encode(), "text/plain")},
    ).json()
    assert second["id"] != resume["id"]
    assert second["master_content"]["full_name"] == "Alex Morgan"


def test_draft_from_the_uploaded_cv_is_returned_but_not_saved(client, with_resume, ai_stub):
    headers, resume = with_resume()
    r = client.post(f"/api/resumes/{resume['id']}/master/draft", headers=headers)
    assert r.status_code == 200, r.text
    draft = r.json()

    assert ai_stub["structure"] == 1
    assert draft["full_name"] == "Alex Morgan"
    assert draft["sections"][0]["entries"][0]["subtitle"] == "Acme Ltd"
    assert client.get("/api/resumes/active", headers=headers).json()["master_content"] is None


def test_cannot_draft_from_another_users_cv(client, with_resume, auth):
    _, resume = with_resume()
    other, _, _ = auth()
    assert client.post(f"/api/resumes/{resume['id']}/master/draft", headers=other).status_code == 404
