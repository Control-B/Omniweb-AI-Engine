"""Email service — transactional emails for the Omniweb platform.

Provides a pluggable email backend. In production, set EMAIL_PROVIDER to
"smtp" and configure SMTP_* env vars. Falls back to logging-only mode
when no provider is configured (safe for dev).

Supported emails:
  - Welcome (post-signup)
    - Password reset
    - Team invite
  - Billing alerts
  - Weekly reports
"""
import asyncio
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """Send a transactional email.

    Returns True if sent (or logged in dev mode), False on error.
    Uses SMTP if configured, otherwise logs the email for dev visibility.
    """
    if not _is_email_configured():
        logger.info(
            f"[EMAIL-DEV] Would send email to={to} subject=\"{subject}\" "
            f"(no email provider configured — set SMTP_HOST to enable)"
        )
        return True

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM or f"noreply@{settings.SMTP_HOST}"
        msg["To"] = to

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Run blocking SMTP in a thread
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _smtp_send, msg, to)

        logger.info(f"Email sent to {to}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


def _smtp_send(msg, to: str) -> None:
    """Blocking SMTP send — called in executor."""
    import smtplib

    host = settings.SMTP_HOST
    port = int(settings.SMTP_PORT)
    user = settings.SMTP_USER
    password = settings.SMTP_PASSWORD

    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=10)
    else:
        server = smtplib.SMTP(host, port, timeout=10)
        server.starttls()

    if user and password:
        server.login(user, password)

    server.sendmail(msg["From"], [to], msg.as_string())
    server.quit()


def _is_email_configured() -> bool:
    """Check if SMTP credentials are set."""
    return bool(getattr(settings, "SMTP_HOST", "") and getattr(settings, "SMTP_PORT", ""))


# ── Email Templates ──────────────────────────────────────────────────────────

async def send_welcome_email(*, to: str, name: str) -> bool:
    """Send a welcome email after signup."""
    subject = "Welcome to Omniweb AI 🚀"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <div style="display: inline-block; background: #6366f1; border-radius: 12px; padding: 12px;">
                <span style="color: white; font-size: 24px;">⚡</span>
            </div>
        </div>
        <h1 style="font-size: 22px; margin: 0 0 8px;">Welcome, {name}!</h1>
        <p style="color: #666; font-size: 15px; line-height: 1.6;">
            Your Omniweb AI account is ready. Here's what you can do next:
        </p>
        <ul style="color: #666; font-size: 14px; line-height: 1.8; padding-left: 20px;">
            <li><strong>Configure your AI agent</strong> — set your greeting, business hours, and services</li>
            <li><strong>Buy a phone number</strong> — get a local or toll-free number for your agent</li>
            <li><strong>Set up automations</strong> — auto-send follow-up SMS after calls</li>
            <li><strong>Add your knowledge base</strong> — upload docs so your agent knows your business</li>
        </ul>
        <div style="text-align: center; margin: 28px 0;">
            <a href="{settings.PLATFORM_URL}/dashboard"
               style="display: inline-block; background: #6366f1; color: white; padding: 12px 28px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 14px;">
                Open Dashboard →
            </a>
        </div>
        <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
        <p style="color: #999; font-size: 12px; text-align: center;">
            Omniweb AI · <a href="{settings.PLATFORM_URL}" style="color: #999;">omniweb.ai</a>
        </p>
    </div>
    """
    text = f"Welcome to Omniweb AI, {name}! Open your dashboard: {settings.PLATFORM_URL}/dashboard"
    return await send_email(to=to, subject=subject, html_body=html, text_body=text)


async def send_password_reset_email(*, to: str, name: str, reset_url: str) -> bool:
    """Send a password reset link email."""
    subject = "Reset your Omniweb password"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
        <h1 style="font-size: 22px; margin: 0 0 8px;">Password Reset</h1>
        <p style="color: #666; font-size: 15px; line-height: 1.6;">
            Hi {name}, we received a request to reset your password. Click the button below to choose a new one.
        </p>
        <div style="text-align: center; margin: 28px 0;">
            <a href="{reset_url}"
               style="display: inline-block; background: #6366f1; color: white; padding: 12px 28px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 14px;">
                Reset Password
            </a>
        </div>
        <p style="color: #999; font-size: 13px;">
            This link expires in 1 hour. If you didn't request this, you can safely ignore this email.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
        <p style="color: #999; font-size: 12px; text-align: center;">
            Omniweb AI · <a href="{settings.PLATFORM_URL}" style="color: #999;">omniweb.ai</a>
        </p>
    </div>
    """
    text = f"Reset your Omniweb password: {reset_url} (expires in 1 hour)"
    return await send_email(to=to, subject=subject, html_body=html, text_body=text)


async def send_team_invite_email(*, to: str, name: str, invited_by: str, accept_url: str) -> bool:
    """Send an admin/team invitation email."""
    subject = "You're invited to Omniweb AI Admin"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
        <h1 style="font-size: 22px; margin: 0 0 8px;">You're invited</h1>
        <p style="color: #666; font-size: 15px; line-height: 1.6;">
            Hi {name}, {invited_by} invited you to join the Omniweb AI admin workspace.
        </p>
        <div style="text-align: center; margin: 28px 0;">
            <a href="{accept_url}"
               style="display: inline-block; background: #6366f1; color: white; padding: 12px 28px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 14px;">
                Accept Invite
            </a>
        </div>
        <p style="color: #999; font-size: 13px;">
            This invite expires in 72 hours. You'll set your password on the next screen.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
        <p style="color: #999; font-size: 12px; text-align: center;">
            Omniweb AI · <a href="{settings.PLATFORM_URL}" style="color: #999;">omniweb.ai</a>
        </p>
    </div>
    """
    text = f"{invited_by} invited you to join Omniweb AI Admin. Accept here: {accept_url}"
    return await send_email(to=to, subject=subject, html_body=html, text_body=text)
