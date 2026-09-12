"""Email delivery, used for password reset links.

With no SMTP host configured, development logs the message instead of sending
it, so no mail server is needed locally. Production never logs the body: it
contains a live reset link, and anyone who can read the logs could use it.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    if not settings.email_enabled:
        if settings.is_production:
            # No recipient either: an email address is personal data.
            logger.error("SMTP is not fully configured - could not send %r", subject)
        else:
            logger.warning(
                "SMTP not configured - printing instead of sending.\nTo: %s\nSubject: %s\n\n%s",
                to,
                subject,
                text_body,
            )
        return False

    message = EmailMessage()
    # An empty SMTP_FROM in the environment overrides the default with "".
    message["From"] = settings.smtp_from or settings.smtp_user
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        with server:
            if settings.smtp_port != 465:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send %r", subject)
        return False

    logger.info("Sent %r", subject)
    return True
