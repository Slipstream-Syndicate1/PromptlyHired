"""The Tracking board: Wishlist, then Applied / Interview / Offer / Rejected.

A job only shows up here once it is saved or the user tells the app they
applied - the app never applies on anyone's behalf, so nothing here is
inferred.
"""


def test_tracking_is_empty_until_saved_or_marked_applied(client, auth, with_job):
    headers, _, _ = auth()
    with_job(headers)
    assert client.get("/api/tracking", headers=headers).json() == []


# --- Wishlist (reuses the existing Saved feature) --------------------------


def test_saving_a_job_adds_it_to_the_wishlist(client, auth, with_job):
    headers, _, _ = auth()
    job = with_job(headers)
    client.post(f"/api/saved/{job['id']}", headers=headers)

    board = client.get("/api/tracking", headers=headers).json()
    assert len(board) == 1
    assert board[0]["id"] == job["id"]
    assert board[0]["status"] is None
    assert board[0]["is_saved"] is True


def test_a_saved_job_moves_off_the_wishlist_once_applied(client, auth, with_job):
    headers, _, _ = auth()
    job = with_job(headers)
    client.post(f"/api/saved/{job['id']}", headers=headers)

    client.patch(f"/api/tracking/{job['id']}", headers=headers, json={"status": "applied"})

    board = client.get("/api/tracking", headers=headers).json()
    assert len(board) == 1, "still on the board, just no longer in the Wishlist bucket"
    assert board[0]["status"] == "applied"
    assert board[0]["is_saved"] is True


def test_unsaving_removes_a_wishlist_only_job_from_the_board(client, auth, with_job):
    headers, _, _ = auth()
    job = with_job(headers)
    client.post(f"/api/saved/{job['id']}", headers=headers)

    client.delete(f"/api/saved/{job['id']}", headers=headers)

    assert client.get("/api/tracking", headers=headers).json() == []


def test_marking_applied_adds_it_to_the_board(client, auth, with_job):
    headers, _, _ = auth()
    job = with_job(headers)

    r = client.patch(
        f"/api/tracking/{job['id']}", headers=headers, json={"status": "applied"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "applied"
    assert body["applied_at"] is not None
    assert body["status_updated_at"] is not None

    board = client.get("/api/tracking", headers=headers).json()
    assert [j["id"] for j in board] == [job["id"]]


def test_moving_stages_keeps_the_original_applied_at(client, auth, with_job):
    headers, _, _ = auth()
    job = with_job(headers)

    first = client.patch(
        f"/api/tracking/{job['id']}", headers=headers, json={"status": "applied"}
    ).json()

    moved = client.patch(
        f"/api/tracking/{job['id']}", headers=headers, json={"status": "interview"}
    ).json()

    assert moved["status"] == "interview"
    assert moved["applied_at"] == first["applied_at"]
    assert moved["status_updated_at"] >= first["status_updated_at"]


def test_clearing_status_removes_it_from_the_board(client, auth, with_job):
    headers, _, _ = auth()
    job = with_job(headers)
    client.patch(f"/api/tracking/{job['id']}", headers=headers, json={"status": "applied"})

    cleared = client.patch(
        f"/api/tracking/{job['id']}", headers=headers, json={"status": None}
    ).json()
    assert cleared["status"] is None
    assert cleared["applied_at"] is None

    assert client.get("/api/tracking", headers=headers).json() == []


def test_status_requires_the_job_to_already_be_in_the_workspace(client, auth):
    headers, _, _ = auth()
    r = client.patch("/api/tracking/999999", headers=headers, json={"status": "applied"})
    assert r.status_code == 404


def test_tracking_is_per_user(client, auth, with_job):
    owner, _, _ = auth()
    job = with_job(owner)
    client.patch(f"/api/tracking/{job['id']}", headers=owner, json={"status": "applied"})

    other, _, _ = auth()
    assert client.get("/api/tracking", headers=other).json() == []
    # The other user never added this job, so they cannot move its status either.
    r = client.patch(f"/api/tracking/{job['id']}", headers=other, json={"status": "offer"})
    assert r.status_code == 404


def test_tracking_requires_auth(client):
    assert client.get("/api/tracking").status_code == 401
    assert client.patch("/api/tracking/1", json={"status": "applied"}).status_code == 401


def test_rejects_an_invalid_status(client, auth, with_job):
    headers, _, _ = auth()
    job = with_job(headers)
    r = client.patch(
        f"/api/tracking/{job['id']}", headers=headers, json={"status": "ghosted"}
    )
    assert r.status_code == 422


# --- Next event (interview / deadline / reminder) --------------------------


def test_setting_an_event_is_independent_of_status(client, auth, with_job):
    """You can flag a deadline before you've even applied."""
    headers, _, _ = auth()
    job = with_job(headers)

    r = client.patch(
        f"/api/tracking/{job['id']}/event",
        headers=headers,
        json={
            "next_event_at": "2026-10-01T09:00:00Z",
            "next_event_type": "deadline",
            "next_event_note": "Submit before end of day",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] is None
    assert body["next_event_type"] == "deadline"
    assert body["next_event_note"] == "Submit before end of day"
    assert body["next_event_at"].startswith("2026-10-01")


def test_opens_event_type_for_wishlist_jobs_not_yet_open(client, auth, with_job):
    """A Wishlist job (saved, no status) can track when applications open."""
    headers, _, _ = auth()
    job = with_job(headers)
    client.post(f"/api/saved/{job['id']}", headers=headers)

    r = client.patch(
        f"/api/tracking/{job['id']}/event",
        headers=headers,
        json={"next_event_at": "2026-11-01T09:00:00Z", "next_event_type": "opens"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] is None
    assert body["next_event_type"] == "opens"


def test_clearing_the_event_wipes_type_and_note_too(client, auth, with_job):
    headers, _, _ = auth()
    job = with_job(headers)
    client.patch(
        f"/api/tracking/{job['id']}/event",
        headers=headers,
        json={"next_event_at": "2026-10-01T09:00:00Z", "next_event_type": "interview"},
    )

    cleared = client.patch(
        f"/api/tracking/{job['id']}/event", headers=headers, json={"next_event_at": None}
    ).json()
    assert cleared["next_event_at"] is None
    assert cleared["next_event_type"] is None
    assert cleared["next_event_note"] is None


def test_event_requires_the_job_to_already_be_in_the_workspace(client, auth):
    headers, _, _ = auth()
    r = client.patch(
        "/api/tracking/999999/event",
        headers=headers,
        json={"next_event_at": "2026-10-01T09:00:00Z", "next_event_type": "other"},
    )
    assert r.status_code == 404


def test_event_is_per_user(client, auth, with_job):
    owner, _, _ = auth()
    job = with_job(owner)

    other, _, _ = auth()
    r = client.patch(
        f"/api/tracking/{job['id']}/event",
        headers=other,
        json={"next_event_at": "2026-10-01T09:00:00Z", "next_event_type": "other"},
    )
    assert r.status_code == 404


def test_event_requires_auth(client):
    assert client.patch("/api/tracking/1/event", json={"next_event_at": None}).status_code == 401


def test_rejects_an_invalid_event_type(client, auth, with_job):
    headers, _, _ = auth()
    job = with_job(headers)
    r = client.patch(
        f"/api/tracking/{job['id']}/event",
        headers=headers,
        json={"next_event_at": "2026-10-01T09:00:00Z", "next_event_type": "ghosted"},
    )
    assert r.status_code == 422
