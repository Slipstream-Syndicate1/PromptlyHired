"""Forgot password: reset links, single use, expiry, and no account enumeration."""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

# What the auth fixture signs every test user up with.
OLD_PASSWORD = "correct horse battery"
NEW_PASSWORD = "a brand new passphrase"


@pytest.fixture
def outbox(monkeypatch):
    """Capture reset emails instead of sending them."""
    from app.services import email as email_service

    sent = []

    def fake_send(to, subject, text_body, html_body=None):
        sent.append({"to": to, "subject": subject, "body": text_body})
        return True

    monkeypatch.setattr(email_service, "send_email", fake_send)
    return sent


def _link_from(message):
    return next(word for word in message["body"].split() if "/reset-password?token=" in word)


def _token_from(message):
    return parse_qs(urlparse(_link_from(message)).query)["token"][0]


def _request_reset(client, email):
    return client.post("/api/auth/forgot-password", json={"email": email})


def _reset(client, token, password=NEW_PASSWORD):
    return client.post("/api/auth/reset-password", json={"token": token, "password": password})


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# --- Requesting a link -----------------------------------------------------------


def test_unknown_email_gets_the_same_answer(client, auth, outbox):
    """Otherwise the form would reveal which emails have accounts."""
    _, email, _ = auth()

    known = _request_reset(client, email)
    unknown = _request_reset(client, "nobody-registered@example.com")

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [m["to"] for m in outbox] == [email]


def test_link_points_at_the_frontend_and_email_is_case_insensitive(client, auth, outbox):
    from app.config import settings

    _, email, _ = auth()
    _request_reset(client, email.upper())

    assert len(outbox) == 1
    expected = f"{settings.app_base_url.rstrip('/')}/reset-password?token="
    assert _link_from(outbox[0]).startswith(expected)


def test_forgot_password_is_rate_limited(client, outbox):
    statuses = [
        _request_reset(client, f"nobody-{i}@example.com").status_code for i in range(6)
    ]
    assert statuses[:5] == [202] * 5
    assert statuses[5] == 429


# --- Using a link ----------------------------------------------------------------


def test_reset_changes_the_password_and_signs_in(client, auth, outbox):
    _, email, _ = auth()
    _request_reset(client, email)

    reset = _reset(client, _token_from(outbox[0]))
    assert reset.status_code == 200
    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {reset.json()['access_token']}"}
    )
    assert me.json()["email"] == email

    assert _login(client, email, OLD_PASSWORD).status_code == 401
    assert _login(client, email, NEW_PASSWORD).status_code == 200


def test_link_works_only_once(client, auth, outbox):
    _, email, _ = auth()
    _request_reset(client, email)
    token = _token_from(outbox[0])

    assert _reset(client, token).status_code == 200
    again = _reset(client, token, password="yet another passphrase")
    assert again.status_code == 400
    assert _login(client, email, NEW_PASSWORD).status_code == 200


def test_expired_link_is_refused(client, auth, outbox, db):
    from app.models import PasswordResetToken
    from app.security import hash_refresh_token

    _, email, _ = auth()
    _request_reset(client, email)
    token = _token_from(outbox[0])

    row = db.query(PasswordResetToken).filter_by(token_hash=hash_refresh_token(token)).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    assert _reset(client, token).status_code == 400
    assert _login(client, email, OLD_PASSWORD).status_code == 200


def test_only_the_newest_link_works(client, auth, outbox):
    _, email, _ = auth()
    _request_reset(client, email)
    _request_reset(client, email)
    older, newer = _token_from(outbox[0]), _token_from(outbox[1])

    assert _reset(client, older).status_code == 400
    assert _reset(client, newer).status_code == 200


def test_reset_signs_out_existing_sessions(client, auth, outbox):
    _, email, tokens = auth()
    _request_reset(client, email)
    _reset(client, _token_from(outbox[0]))

    stale = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert stale.status_code == 401


def test_only_the_hash_is_stored(client, auth, outbox, db):
    from app.models import PasswordResetToken

    _, email, _ = auth()
    _request_reset(client, email)
    token = _token_from(outbox[0])

    stored = [row.token_hash for row in db.query(PasswordResetToken).all()]
    assert token not in stored


def test_bad_input_is_rejected(client, outbox):
    assert _reset(client, "x" * 40).status_code == 400
    assert _reset(client, "short").status_code == 422
    assert _reset(client, "x" * 40, password="short").status_code == 422
    assert _reset(client, "x" * 40, password="p" * 73).status_code == 422


# --- Delivery ------------------------------------------------------------------


def test_production_never_logs_the_reset_link(monkeypatch, caplog):
    """With no SMTP in production, the link must not land in the logs."""
    import logging

    from app.config import settings
    from app.services import email as email_service

    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "smtp_host", "")

    with caplog.at_level(logging.DEBUG):
        sent = email_service.send_email(
            "person@example.com", "Reset", "https://x/reset-password?token=live-secret-123"
        )

    assert sent is False
    assert "live-secret-123" not in caplog.text
    assert "person@example.com" not in caplog.text


def test_development_prints_the_link_when_smtp_is_unset(monkeypatch, caplog):
    import logging

    from app.config import settings
    from app.services import email as email_service

    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "smtp_host", "")

    with caplog.at_level(logging.DEBUG):
        email_service.send_email("dev@example.com", "Reset", "token=visible-in-dev")

    assert "visible-in-dev" in caplog.text
