"""Application tracking, response history and the communications log."""

from datetime import date, timedelta


def _apply(client, headers, **body):
    response = client.post("/api/applications", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _transitions(client, headers, application_id):
    events = client.get(f"/api/applications/{application_id}/events", headers=headers).json()
    return [(e["from_status"], e["to_status"]) for e in events], events


# --- Creating ---------------------------------------------------------------


def test_track_a_pasted_job(client, with_resume, with_job):
    headers, _ = with_resume()
    job = with_job(headers)

    app = _apply(client, headers, job_id=job["id"])

    assert app["status"] == "applied"
    assert app["job"]["id"] == job["id"]
    assert app["applied_date"] == date.today().isoformat()
    # Records which CV went out, defaulting to the active one.
    assert app["resume_id"] is not None
    assert _transitions(client, headers, app["id"])[0] == [(None, "applied")]


def test_manual_entry_for_a_job_applied_to_elsewhere(client, auth):
    headers, _, _ = auth()

    app = _apply(
        client,
        headers,
        company="Globex",
        position="Data Analyst",
        url="https://globex.example/jobs/1",
        status="interview",
        applied_date="2026-08-01",
    )

    assert app["job"]["company"]["name"] == "Globex"
    assert app["job"]["title"] == "Data Analyst"
    assert app["job"]["source_api"] == "manual"
    assert app["job"]["url"] == "https://globex.example/jobs/1"
    assert app["status"] == "interview"
    assert app["applied_date"] == "2026-08-01"
    assert app["resume_id"] is None


def test_needs_a_job_or_a_manual_company_and_position(client, auth):
    headers, _, _ = auth()

    def post(body):
        return client.post("/api/applications", json=body, headers=headers).status_code

    assert post({}) == 422
    assert post({"company": "Globex"}) == 422
    assert post({"position": "Analyst"}) == 422
    assert post({"job_id": 999_999, "company": "Globex", "position": "Analyst"}) == 422


def test_link_must_be_http(client, auth):
    """The link becomes an href; javascript: would run on click."""
    headers, _, _ = auth()
    body = {"company": "Globex", "position": "Analyst", "url": "javascript:alert(1)"}
    assert client.post("/api/applications", json=body, headers=headers).status_code == 422


def test_unknown_job_and_resume_are_404(client, auth):
    headers, _, _ = auth()
    missing_job = client.post("/api/applications", json={"job_id": 999_999}, headers=headers)
    assert missing_job.status_code == 404
    body = {"company": "Globex", "position": "Analyst", "resume_id": 999_999}
    assert client.post("/api/applications", json=body, headers=headers).status_code == 404


def test_one_application_per_job(client, with_resume, with_job):
    headers, _ = with_resume()
    job = with_job(headers)
    _apply(client, headers, job_id=job["id"])

    again = client.post("/api/applications", json={"job_id": job["id"]}, headers=headers)
    assert again.status_code == 409


# --- Privacy ----------------------------------------------------------------


def test_applications_are_private(client, auth):
    owner, _, _ = auth()
    other, _, _ = auth()
    app = _apply(client, owner, company="Initech", position="Engineer")
    base = f"/api/applications/{app['id']}"

    assert client.get("/api/applications", headers=other).json() == []
    assert client.get(base, headers=other).status_code == 404
    assert client.patch(base, json={"status": "offer"}, headers=other).status_code == 404
    assert client.get(f"{base}/events", headers=other).status_code == 404
    assert client.get(f"{base}/communications", headers=other).status_code == 404
    comm = {"kind": "email", "direction": "sent"}
    assert client.post(f"{base}/communications", json=comm, headers=other).status_code == 404
    assert client.delete(base, headers=other).status_code == 404

    # Untouched for the owner.
    assert client.get(base, headers=owner).json()["status"] == "applied"


def test_communications_are_private(client, auth):
    owner, _, _ = auth()
    other, _, _ = auth()
    app = _apply(client, owner, company="Initech", position="Engineer")
    comm = client.post(
        f"/api/applications/{app['id']}/communications",
        json={"kind": "email", "direction": "sent"},
        headers=owner,
    ).json()

    url = f"/api/communications/{comm['id']}"
    assert client.patch(url, json={"summary": "x"}, headers=other).status_code == 404
    assert client.delete(url, headers=other).status_code == 404


# --- Stages and responses -----------------------------------------------------


def test_status_changes_record_the_response_history(client, auth):
    headers, _, _ = auth()
    app = _apply(client, headers, company="Hooli", position="SRE")
    base = f"/api/applications/{app['id']}"

    moved = client.patch(
        base, json={"status": "interview", "note": "Invited to interview by email"}, headers=headers
    )
    assert moved.status_code == 200
    assert moved.json()["status"] == "interview"

    client.patch(base, json={"status": "offer"}, headers=headers)
    # Not a status change, so not a response event.
    client.patch(base, json={"notes": "Negotiating salary"}, headers=headers)

    transitions, events = _transitions(client, headers, app["id"])
    assert transitions == [(None, "applied"), ("applied", "interview"), ("interview", "offer")]
    assert events[1]["note"] == "Invited to interview by email"
    assert client.get(base, headers=headers).json()["notes"] == "Negotiating salary"


def test_setting_the_same_status_records_nothing(client, auth):
    headers, _, _ = auth()
    app = _apply(client, headers, company="Hooli", position="SRE")

    client.patch(f"/api/applications/{app['id']}", json={"status": "applied"}, headers=headers)
    assert _transitions(client, headers, app["id"])[0] == [(None, "applied")]


def test_a_note_needs_a_status_change(client, auth):
    headers, _, _ = auth()
    app = _apply(client, headers, company="Hooli", position="SRE")
    base = f"/api/applications/{app['id']}"

    assert client.patch(base, json={"note": "Recruiter replied"}, headers=headers).status_code == 422
    body = {"status": "applied", "note": "Still waiting"}
    assert client.patch(base, json=body, headers=headers).status_code == 422


def test_required_fields_cannot_be_cleared(client, auth):
    headers, _, _ = auth()
    app = _apply(client, headers, company="Hooli", position="SRE")
    base = f"/api/applications/{app['id']}"

    assert client.patch(base, json={"status": None}, headers=headers).status_code == 422
    assert client.patch(base, json={"applied_date": None}, headers=headers).status_code == 422
    # Optional ones can.
    cleared = client.patch(base, json={"next_action_date": None}, headers=headers)
    assert cleared.status_code == 200


def test_filter_by_stage(client, auth):
    headers, _, _ = auth()
    _apply(client, headers, company="A", position="One")
    _apply(client, headers, company="B", position="Two", status="interview")
    _apply(client, headers, company="C", position="Three", status="rejected")

    interviews = client.get("/api/applications?status=interview", headers=headers).json()
    assert [a["job"]["company"]["name"] for a in interviews] == ["B"]
    assert len(client.get("/api/applications", headers=headers).json()) == 3
    assert client.get("/api/applications?status=bogus", headers=headers).status_code == 422


# --- Dashboard figures and follow-ups -------------------------------------------


def test_stats_for_dashboard_cards(client, auth):
    headers, _, _ = auth()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    _apply(client, headers, company="A", position="1")
    overdue = _apply(
        client,
        headers,
        company="B",
        position="2",
        status="interview",
        next_action="Send thank-you note",
        next_action_date=yesterday,
    )
    _apply(client, headers, company="C", position="3", status="offer")
    _apply(client, headers, company="D", position="4", status="rejected")
    _apply(client, headers, company="E", position="5", status="withdrawn")

    stats = client.get("/api/applications/stats", headers=headers).json()
    assert stats["total"] == 5
    assert stats["by_status"] == {
        "applied": 1,
        "online_assessment": 0,
        "interview": 1,
        "offer": 1,
        "rejected": 1,
        "withdrawn": 1,
    }
    assert stats["active"] == 2
    assert stats["offers"] == 1
    # Only B: past its next-action date. A was applied to today.
    assert stats["needs_follow_up"] == 1
    # 3 of the 4 not withdrawn got past "applied".
    assert stats["response_rate_pct"] == 75

    assert overdue["needs_follow_up"] is True


def test_stats_with_no_applications(client, auth):
    headers, _, _ = auth()
    stats = client.get("/api/applications/stats", headers=headers).json()
    assert stats["total"] == 0
    assert stats["response_rate_pct"] is None


def test_closed_applications_never_need_follow_up(client, auth):
    headers, _, _ = auth()
    long_ago = (date.today() - timedelta(days=30)).isoformat()
    app = _apply(
        client, headers, company="A", position="1", status="rejected", next_action_date=long_ago
    )
    assert app["needs_follow_up"] is False


# --- Communications log -------------------------------------------------------


def test_communications_log(client, auth):
    headers, _, _ = auth()
    app = _apply(client, headers, company="Umbrella", position="Analyst")
    base = f"/api/applications/{app['id']}/communications"

    sent = client.post(
        base,
        json={
            "kind": "email",
            "direction": "sent",
            "subject": "Following up",
            "occurred_at": "2026-09-01T10:00:00Z",
        },
        headers=headers,
    )
    assert sent.status_code == 201
    call = client.post(
        base,
        json={
            "kind": "call",
            "direction": "received",
            "contact_name": "Jane Recruiter",
            "summary": "Phone screen booked",
            "occurred_at": "2026-09-03T15:30:00Z",
        },
        headers=headers,
    ).json()

    logged = client.get(base, headers=headers).json()
    # Newest first.
    assert [c["kind"] for c in logged] == ["call", "email"]
    detail = client.get(f"/api/applications/{app['id']}", headers=headers).json()
    assert detail["communications_count"] == 2

    edited = client.patch(
        f"/api/communications/{call['id']}",
        json={"summary": "Phone screen moved to Friday"},
        headers=headers,
    ).json()
    assert edited["summary"] == "Phone screen moved to Friday"
    assert edited["contact_name"] == "Jane Recruiter"

    assert client.delete(f"/api/communications/{call['id']}", headers=headers).status_code == 204
    assert len(client.get(base, headers=headers).json()) == 1


def test_communication_defaults_to_now_and_validates(client, auth):
    headers, _, _ = auth()
    app = _apply(client, headers, company="Umbrella", position="Analyst")
    base = f"/api/applications/{app['id']}/communications"

    logged = client.post(base, json={"kind": "message", "direction": "received"}, headers=headers)
    assert logged.status_code == 201
    assert logged.json()["occurred_at"] is not None

    bad_kind = {"kind": "fax", "direction": "sent"}
    assert client.post(base, json=bad_kind, headers=headers).status_code == 422
    assert client.post(base, json={"kind": "email"}, headers=headers).status_code == 422
    comm_id = logged.json()["id"]
    cleared = client.patch(f"/api/communications/{comm_id}", json={"kind": None}, headers=headers)
    assert cleared.status_code == 422


# --- Deletion -----------------------------------------------------------------


def test_deleting_an_application_removes_its_history(client, auth, db):
    from app.models import ApplicationEvent, Communication

    headers, _, _ = auth()
    app = _apply(client, headers, company="Umbrella", position="Analyst")
    base = f"/api/applications/{app['id']}"
    client.patch(base, json={"status": "interview"}, headers=headers)
    comm = {"kind": "email", "direction": "sent"}
    client.post(f"{base}/communications", json=comm, headers=headers)

    assert client.delete(base, headers=headers).status_code == 204
    assert client.get(base, headers=headers).status_code == 404
    assert db.query(ApplicationEvent).filter_by(application_id=app["id"]).count() == 0
    assert db.query(Communication).filter_by(application_id=app["id"]).count() == 0


def test_deleting_a_resume_keeps_the_application(client, with_resume, with_job, db):
    """The record that you applied must outlive the CV you sent."""
    from app.models import Resume

    headers, _ = with_resume()
    job = with_job(headers)
    app = _apply(client, headers, job_id=job["id"])

    db.delete(db.get(Resume, app["resume_id"]))
    db.commit()

    after = client.get(f"/api/applications/{app['id']}", headers=headers)
    assert after.status_code == 200
    assert after.json()["resume_id"] is None
    assert after.json()["status"] == "applied"
