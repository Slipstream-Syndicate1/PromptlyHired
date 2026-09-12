"""The doctor must be honest: report real failures, never a false green."""

from app import doctor
from app.config import Settings


def test_database_and_migrations_pass_against_the_test_db(database):
    assert doctor.check_database()[0] == "PASS"
    assert doctor.check_migrations()[0] == "PASS"


def test_missing_ai_key_is_a_hard_failure_in_production(monkeypatch):
    """AI is the product now - a deployment without a key is broken, not degraded."""
    prod = Settings(
        env="production", jwt_secret="x" * 48,
        cors_origins=["https://a.netlify.app"], app_base_url="https://a.netlify.app",
    )
    monkeypatch.setattr(doctor, "settings", prod)
    status, name, detail = doctor.check_ai()
    assert status == "FAIL"
    assert "GEMINI_API_KEY" in detail



def test_missing_ai_key_is_only_a_skip_in_development(monkeypatch):
    monkeypatch.setattr(doctor, "settings", Settings(env="development"))
    assert doctor.check_ai()[0] == "SKIP"



def test_local_media_is_a_hard_failure_in_production(monkeypatch):
    prod = Settings(
        env="production", jwt_secret="x" * 48,
        cors_origins=["https://a.netlify.app"], app_base_url="https://a.netlify.app",
    )
    monkeypatch.setattr(doctor, "settings", prod)
    status, _, detail = doctor.check_media_storage()
    assert status == "FAIL"
    assert "WIPED" in detail



def test_production_url_misconfiguration_is_reported(monkeypatch):
    monkeypatch.setattr(
        doctor, "settings",
        Settings(env="production", jwt_secret="change-me-in-production"),
    )
    assert doctor.check_frontend_urls()[0] == "FAIL"


# --- Job feed ------------------------------------------------------------------


def _stub_sources(monkeypatch, himalayas=None, adzuna=None):
    from app.services import job_sources

    def respond(result):
        def search(**kwargs):
            if isinstance(result, Exception):
                raise result
            return result or []

        return search

    monkeypatch.setattr(job_sources, "search_himalayas", respond(himalayas))
    monkeypatch.setattr(job_sources, "search_adzuna", respond(adzuna))


def test_job_feed_without_adzuna_keys_is_a_skip(monkeypatch):
    monkeypatch.setattr(doctor, "settings", Settings(env="development", adzuna_app_id=""))
    _stub_sources(monkeypatch, himalayas=[object()] * 3)
    status, _, detail = doctor.check_job_feed()
    assert status == "SKIP"
    assert "3 jobs" in detail and "ADZUNA" in detail


def test_job_feed_passes_when_both_sources_answer(monkeypatch):
    monkeypatch.setattr(
        doctor, "settings",
        Settings(env="development", adzuna_app_id="id", adzuna_app_key="key"),
    )
    _stub_sources(monkeypatch, himalayas=[object()] * 2, adzuna=[object()] * 5)
    status, _, detail = doctor.check_job_feed()
    assert status == "PASS"
    assert "Adzuna returned 5" in detail


def test_rejected_adzuna_key_is_a_failure(monkeypatch):
    from app.services.job_sources import SourceError

    monkeypatch.setattr(
        doctor, "settings",
        Settings(env="development", adzuna_app_id="id", adzuna_app_key="wrong"),
    )
    _stub_sources(monkeypatch, himalayas=[object()],
                  adzuna=SourceError("Adzuna rejected the credentials"))
    status, _, detail = doctor.check_job_feed()
    assert status == "FAIL"
    assert "rejected the credentials" in detail


def test_unreachable_himalayas_is_a_failure(monkeypatch):
    from app.services.job_sources import SourceError

    monkeypatch.setattr(doctor, "settings", Settings(env="development"))
    _stub_sources(monkeypatch, himalayas=SourceError("Himalayas could not be reached"))
    assert doctor.check_job_feed()[0] == "FAIL"


# --- Email ---------------------------------------------------------------------


class _FakeSMTP:
    """Stands in for smtplib.SMTP. The check must log in but never send."""

    sent = False

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        import smtplib

        if password != "right-app-password":
            raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")

    def send_message(self, message):
        _FakeSMTP.sent = True


def _email_settings(password):
    return Settings(
        env="development",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="sender@example.com",
        smtp_password=password,
        smtp_from="PromptlyHired <sender@example.com>",
    )


def test_email_unset_is_a_skip_in_development(monkeypatch):
    monkeypatch.setattr(doctor, "settings", Settings(env="development", smtp_host=""))
    assert doctor.check_email()[0] == "SKIP"


def test_email_unset_is_a_failure_in_production(monkeypatch):
    prod = Settings(
        env="production", jwt_secret="x" * 48, smtp_host="",
        cors_origins=["https://a.netlify.app"], app_base_url="https://a.netlify.app",
    )
    monkeypatch.setattr(doctor, "settings", prod)
    status, _, detail = doctor.check_email()
    assert status == "FAIL"
    assert "SMTP_HOST" in detail


def test_email_login_passes_without_sending(monkeypatch):
    import smtplib

    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(doctor, "settings", _email_settings("right-app-password"))
    _FakeSMTP.sent = False
    status, _, detail = doctor.check_email()
    assert status == "PASS"
    assert "sender@example.com" in detail
    assert _FakeSMTP.sent is False


def test_rejected_email_login_explains_app_passwords(monkeypatch):
    import smtplib

    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(doctor, "settings", _email_settings("normal-gmail-password"))
    status, _, detail = doctor.check_email()
    assert status == "FAIL"
    assert "App Password" in detail
    assert "normal-gmail-password" not in detail


def test_a_host_without_a_login_is_never_a_pass(monkeypatch):
    """A host alone once reported green while nothing could actually be sent."""
    monkeypatch.setattr(
        doctor, "settings",
        Settings(env="development", smtp_host="smtp.gmail.com", smtp_user="", smtp_password=""),
    )
    status, _, detail = doctor.check_email()
    assert status == "SKIP"
    assert "SMTP_USER" in detail
