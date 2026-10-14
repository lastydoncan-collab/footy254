"""
FOOTY254 Email Service

Sends transactional email (password reset) over SMTP when SMTP_* settings are
configured. When they are not, the message is logged instead of sent, so local
development works without mail credentials while production (with SMTP_HOST
set) delivers for real.

Port 465 uses implicit TLS; any other port uses STARTTLS.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not is_configured():
        if settings.IS_PRODUCTION:
            # Never write a live password-reset link into production logs.
            logger.error(
                "SMTP is not configured; email NOT sent. To=%s Subject=%s",
                to_email,
                subject,
            )
        else:
            logger.warning(
                "SMTP not configured; email NOT sent. To=%s Subject=%s\n%s",
                to_email,
                subject,
                body,
            )
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.FROM_EMAIL
    message["To"] = to_email
    message.set_content(body)

    context = ssl.create_default_context()

    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=15,
                context=context,
            )
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)

        with server:
            if settings.SMTP_PORT != 465:
                server.starttls(context=context)

            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)

        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    body = (
        "We received a request to reset your FOOTY254 password.\n\n"
        f"Reset it here (valid for {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes): "
        f"{reset_link}\n\n"
        "If you didn't request this, you can safely ignore this email - "
        "your password will not change."
    )

    return send_email(to_email, "Reset your FOOTY254 password", body)


def send_login_alert_email(to_email: str, device: str, ip_address: str | None) -> bool:
    """Tell the owner about a new sign-in (only if they left login alerts on)."""

    return send_email(
        to_email,
        "New sign-in to your FOOTY254 account",
        "We noticed a new sign-in to your FOOTY254 account.\n\n"
        f"Device: {device}\n"
        f"IP address: {ip_address or 'unknown'}\n\n"
        "If this was you, no action is needed. If not, sign in, change your "
        "password and choose 'Log out other devices' under Security.\n",
    )
