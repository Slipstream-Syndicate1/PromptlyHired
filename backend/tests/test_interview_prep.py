"""Interview preparation: one saved plan per application, once it reaches interview.

The plan costs a free-tier AI request, so it is written only when the user asks,
saved, and reused until they ask for a new one.
"""

from app.services import ai, interview_prep

SAMPLE = (
    "Backend Engineer at Acme Ltd. Python, PostgreSQL and AWS. You will design APIs "
    "and own services in production. Five years of experience required."
) * 3


def _job(client, headers, slug="interview"):
    return client.post(
        "/api/jobs/from-text",
        headers=headers,
        json={"text": SAMPLE, "title": "Backend Engineer", "company": "Acme Ltd",
              "url": f"https://example.com/jobs/{slug}"},
    ).json()


def _application(client, headers, status="applied", slug="interview"):
    job = _job(client, headers, slug)
    return client.post(
        "/api/applications", headers=headers, json={"job_id": job["id"], "status": status}
    ).json()


def _to_interview(client, headers, application):
    r = client.patch(
        f"/api/applications/{application['id']}", headers=headers, json={"status": "interview"}
    )
    assert r.status_code == 200, r.text
    return r.json()


# --- The plan itself --------------------------------------------------------


def test_planning_needs_the_interview_stage(client, with_resume, ai_stub):
    headers, _ = with_resume()
    application = _application(client, headers)

    r = client.post(f"/api/applications/{application['id']}/interview-prep", headers=headers)
    assert r.status_code == 422
    assert "Interview" in r.json()["detail"]
    assert ai_stub.get("interview", 0) == 0, "no quota spent before there is an interview"


def test_plan_is_written_once_then_reused(client, with_resume, ai_stub):
    headers, _ = with_resume()
    application = _to_interview(client, headers, _application(client, headers))

    created = client.post(f"/api/applications/{application['id']}/interview-prep", headers=headers)
    assert created.status_code == 200, created.text
    content = created.json()["content"]
    assert "Backend Engineer" in content["summary"]
    assert content["focus_areas"][0]["actions"] == ["Re-read your payments project"]
    assert content["likely_questions"][0]["question"].startswith("Tell us")
    assert content["questions_to_ask"] and content["watch_outs"]
    assert ai_stub["interview"] == 1

    # Asking again returns the saved plan rather than spending another request.
    again = client.post(f"/api/applications/{application['id']}/interview-prep", headers=headers)
    assert again.status_code == 200
    assert again.json()["id"] == created.json()["id"]
    assert ai_stub["interview"] == 1


def test_reading_the_saved_plan_is_free(client, with_resume, ai_stub):
    headers, _ = with_resume()
    application = _to_interview(client, headers, _application(client, headers))

    assert client.get(
        f"/api/applications/{application['id']}/interview-prep", headers=headers
    ).json() is None

    client.post(f"/api/applications/{application['id']}/interview-prep", headers=headers)
    saved = client.get(f"/api/applications/{application['id']}/interview-prep", headers=headers)
    assert saved.status_code == 200
    assert saved.json()["content"]["summary"]
    assert ai_stub["interview"] == 1


def test_writing_it_again_replaces_the_plan(client, with_resume, ai_stub):
    headers, _ = with_resume()
    application = _to_interview(client, headers, _application(client, headers))
    first = client.post(
        f"/api/applications/{application['id']}/interview-prep", headers=headers
    ).json()

    ai_stub["roadmap"] = {
        "summary": "A second plan.",
        "focus_areas": [], "likely_questions": [],
        "questions_to_ask": ["Who would I report to?"], "watch_outs": [],
    }
    again = client.post(
        f"/api/applications/{application['id']}/interview-prep?refresh=true", headers=headers
    ).json()

    assert ai_stub["interview"] == 2
    assert again["id"] == first["id"], "one plan per application, replaced not duplicated"
    assert again["content"]["summary"] == "A second plan."


def test_no_quota_spent_on_a_hand_logged_job(client, with_resume, ai_stub):
    """Applications logged by hand have no advert, so there is nothing to work from."""
    headers, _ = with_resume()
    application = client.post(
        "/api/applications",
        headers=headers,
        json={"company": "Someone Else Ltd", "position": "Backend Engineer"},
    ).json()
    _to_interview(client, headers, application)

    r = client.post(f"/api/applications/{application['id']}/interview-prep", headers=headers)
    assert r.status_code == 422
    assert ai_stub.get("interview", 0) == 0


def test_another_users_plan_is_a_404(client, with_resume, auth, ai_stub):
    headers, _ = with_resume()
    application = _to_interview(client, headers, _application(client, headers))
    client.post(f"/api/applications/{application['id']}/interview-prep", headers=headers)

    other, _, _ = auth()
    assert client.get(
        f"/api/applications/{application['id']}/interview-prep", headers=other
    ).status_code == 404
    assert client.post(
        f"/api/applications/{application['id']}/interview-prep", headers=other
    ).status_code == 404


def test_stopping_tracking_removes_the_plan(client, with_resume, ai_stub):
    headers, _ = with_resume()
    application = _to_interview(client, headers, _application(client, headers))
    client.post(f"/api/applications/{application['id']}/interview-prep", headers=headers)

    assert client.delete(f"/api/applications/{application['id']}", headers=headers).status_code == 204
    assert client.get(
        f"/api/applications/{application['id']}/interview-prep", headers=headers
    ).status_code == 404


# --- Model output -----------------------------------------------------------


def test_output_is_clipped_to_the_saved_shape():
    content = interview_prep.normalise({
        "summary": "S" * 5000,
        "focus_areas": [{"topic": f"T{i}", "why": "w", "actions": ["a"] * 20} for i in range(12)],
        "likely_questions": [{"question": "", "how_to_answer": "dropped"}]
        + [{"question": f"Q{i}", "how_to_answer": "a"} for i in range(12)],
        "questions_to_ask": ["ask"] * 12 + ["", "  "],
        "watch_outs": ["gap"] * 12,
    })

    assert len(content["summary"]) == 2000
    assert len(content["focus_areas"]) == 6
    assert len(content["focus_areas"][0]["actions"]) == 8
    assert len(content["likely_questions"]) == 8
    assert all(item["question"] for item in content["likely_questions"]), "blank questions dropped"
    assert len(content["questions_to_ask"]) == 6 and len(content["watch_outs"]) == 5


def test_an_empty_plan_is_recognised():
    assert interview_prep.is_empty(interview_prep.normalise({}))
    assert not interview_prep.is_empty(interview_prep.normalise({"summary": "Something"}))


def test_prompt_fences_the_advert_and_forbids_inventing_experience(monkeypatch):
    captured = {}

    def fake_generate(label, *, system, prompt, schema, thinking=None):
        captured.update(system=system, prompt=prompt, schema=schema)
        return None

    monkeypatch.setattr(ai, "_generate", fake_generate)
    ai.interview_roadmap("MY RESUME", "Engineer", "Acme", "advert body")

    assert captured["prompt"].index("MY RESUME") < captured["prompt"].index(ai.UNTRUSTED_OPEN)
    assert "advert body" in captured["prompt"]
    assert "invent" in captured["system"].lower()
    assert "predict" in captured["system"].lower(), "never forecasts the hiring decision"
    assert captured["schema"] is ai.InterviewRoadmap
