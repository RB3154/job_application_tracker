"""Sending emails over SMTP (used for password reset emails)."""

import logging
from email.message import EmailMessage

import aiosmtplib

from config import settings


logger = logging.getLogger(__name__)


async def send_email(to_email: str, subject: str, body: str) -> None:
    """Send a plain-text email through the SMTP server from the settings."""

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    # aiosmtplib is async, so waiting for the mail server doesn't block other requests.
    await aiosmtplib.send(
        message,
        hostname=settings.mail_server,
        port=settings.mail_port,
        username=settings.mail_username or None,
        password=settings.mail_password.get_secret_value() or None,
        start_tls=settings.mail_use_tls,
    )


async def send_password_reset_email(to_email: str, username: str, token: str) -> None:
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"

    body = f"""Hi {username},

You requested to reset your Job Application Tracker password. Use the link below to set a new password:

{reset_url}

This link will expire in {settings.reset_token_expire_minutes} minutes.

If you didn't request this, you can safely ignore this email. Your password will stay the same.

Best regards,
The Job Application Tracker Team
"""

    try:
        await send_email(to_email=to_email, subject="Reset Your Password - Job Application Tracker", body=body)
    except (aiosmtplib.SMTPException, OSError):
        # This runs after the response was sent, so the user can't be told. Log a clear message
        # (with the error details) for whoever runs the server. Never log the token: it resets the password.
        logger.exception("Could not send the password reset email for user %r", username)
