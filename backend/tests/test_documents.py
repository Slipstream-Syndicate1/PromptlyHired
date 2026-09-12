"""Document generation and editing."""


SAMPLE = (
    "Backend Engineer at Acme Ltd. Python, PostgreSQL and AWS. You will design "
    "APIs and own services in production. Five years of experience required."
) * 3


def _first_job(client, headers, title="Backend Engineer"):
    """Jobs are pasted, not searched.

    The URL is the dedup key, so distinct roles need distinct URLs - two pastes
    of the same link deliberately collapse onto one job.
    """
    slug = title.lower().replace(" ", "-")
    return client.post(
        "/api/jobs/from-text",
        headers=headers,
        json={"text": SAMPLE, "title": title, "company": "Acme Ltd",
              "url": f"https://example.com/jobs/{slug}"},
    ).json()


def test_generate_resume_and_cover_letter(client, with_resume, ai_stub):
    headers, _ = with_resume()
    job = _first_job(client, headers)

    resume_doc = client.post(
        f"/api/jobs/{job['id']}/documents", headers=headers, json={"kind": "resume"}
    )
    assert resume_doc.status_code == 201
    assert resume_doc.json()["kind"] == "resume"
    assert resume_doc.json()["content"]["full_name"] == "Alex Morgan"
    assert resume_doc.json()["edited_content"] is None

    letter = client.post(
        f"/api/jobs/{job['id']}/documents", headers=headers, json={"kind": "cover_letter"}
    )
    assert letter.status_code == 201
    assert letter.json()["content"]["greeting"].startswith("Dear")

    assert ai_stub["resume"] == 1 and ai_stub["cover"] == 1


def test_generation_passes_user_steering_through(client, with_resume, ai_stub):
    headers, _ = with_resume()
    job = _first_job(client, headers)
    doc = client.post(
        f"/api/jobs/{job['id']}/documents",
        headers=headers,
        json={"kind": "resume", "instructions": "emphasise my backend work"},
    ).json()
    assert doc["content"]["instructions_seen"] == "emphasise my backend work"


def test_generation_uses_the_match_when_one_exists(client, with_resume, ai_stub):
    headers, _ = with_resume()
    job = _first_job(client, headers)
    client.post(f"/api/jobs/{job['id']}/match", headers=headers)
    r = client.post(f"/api/jobs/{job['id']}/documents", headers=headers, json={"kind": "resume"})
    assert r.status_code == 201


def test_generation_requires_a_resume(client, auth, with_resume, ai_stub):
    owner, _ = with_resume()
    job = _first_job(client, owner)
    other, _, _ = auth()
    r = client.post(f"/api/jobs/{job['id']}/documents", headers=other, json={"kind": "resume"})
    assert r.status_code == 409


def test_edits_never_overwrite_the_generated_original(client, with_resume, ai_stub):
    """Keeping both is what makes "reset to generated" possible and auditable."""
    headers, _ = with_resume()
    job = _first_job(client, headers)
    doc = client.post(
        f"/api/jobs/{job['id']}/documents", headers=headers, json={"kind": "resume"}
    ).json()
    original = doc["content"]

    edited = client.patch(
        f"/api/documents/{doc['id']}",
        headers=headers,
        json={"edited_content": {"full_name": "Alex M.", "summary": "My own words"}},
    ).json()

    assert edited["edited_content"]["summary"] == "My own words"
    assert edited["content"] == original


def test_reset_discards_edits(client, with_resume, ai_stub):
    headers, _ = with_resume()
    job = _first_job(client, headers)
    doc = client.post(
        f"/api/jobs/{job['id']}/documents", headers=headers, json={"kind": "resume"}
    ).json()
    client.patch(
        f"/api/documents/{doc['id']}", headers=headers, json={"edited_content": {"x": 1}}
    )

    reset = client.post(f"/api/documents/{doc['id']}/reset", headers=headers).json()
    assert reset["edited_content"] is None
    assert reset["content"] == doc["content"]
    # Reset must not re-run generation.
    assert ai_stub["resume"] == 1


def test_documents_are_private(client, with_resume, auth, ai_stub):
    headers, _ = with_resume()
    job = _first_job(client, headers)
    doc = client.post(
        f"/api/jobs/{job['id']}/documents", headers=headers, json={"kind": "resume"}
    ).json()

    other, _, _ = auth()
    assert client.get(f"/api/documents/{doc['id']}", headers=other).status_code == 404
    assert client.patch(
        f"/api/documents/{doc['id']}", headers=other, json={"edited_content": {"x": 1}}
    ).status_code == 404


def test_delete_document(client, with_resume, ai_stub):
    headers, _ = with_resume()
    job = _first_job(client, headers)
    doc = client.post(
        f"/api/jobs/{job['id']}/documents", headers=headers, json={"kind": "resume"}
    ).json()
    assert client.delete(f"/api/documents/{doc['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/documents/{doc['id']}", headers=headers).status_code == 404
