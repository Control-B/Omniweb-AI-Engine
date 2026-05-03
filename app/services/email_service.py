"""Email service — transactional emails for the Omniweb platform.

Supports two backends (checked in order):
  1. Resend  — set RESEND_API_KEY (recommended, simplest)
  2. SMTP    — set SMTP_HOST + SMTP_USER + SMTP_PASSWORD

Falls back to logging-only mode when neither is configured (safe for dev).

Supported emails:
  - Welcome (post-signup)
  - Password reset
  - Team invite
  - Billing alerts
  - Weekly reports
"""
import asyncio
from html import escape
from typing import Optional
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import EmailLog
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)
settings = get_settings()


# ── Backend detection ────────────────────────────────────────────────────────

def _email_backend() -> str:
    """Return 'resend', 'smtp', or 'none'."""
    if getattr(settings, "RESEND_API_KEY", ""):
        return "resend"
    if getattr(settings, "SMTP_HOST", "") and getattr(settings, "SMTP_PORT", ""):
        return "smtp"
    return "none"


# ── Core send function ──────────────────────────────────────────────────────

async def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """Send a transactional email via the configured backend."""
    backend = _email_backend()

    if backend == "none":
        logger.info(
            f"[EMAIL-DEV] Would send email to={to} subject=\"{subject}\" "
            f"(no email provider configured — set RESEND_API_KEY or SMTP_HOST)"
        )
        return True

    try:
        if backend == "resend":
            return await _send_resend(to=to, subject=subject, html_body=html_body, text_body=text_body)
        else:
            return await _send_smtp(to=to, subject=subject, html_body=html_body, text_body=text_body)
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


# ── Resend backend ───────────────────────────────────────────────────────────

async def _send_resend(*, to: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    """Send via Resend API (https://resend.com/docs)."""
    import httpx

    payload: dict = {
        "from": settings.RESEND_FROM_EMAIL or settings.SMTP_FROM or "Omniweb AI <noreply@omniweb.ai>",
        "to": [to],
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        payload["text"] = text_body
    if settings.RESEND_REPLY_TO_EMAIL:
        payload["reply_to"] = [settings.RESEND_REPLY_TO_EMAIL]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )

    if resp.status_code >= 400:
        logger.error(f"Resend API error {resp.status_code}: {resp.text}")
        return False

    logger.info(f"Email sent via Resend to {to}: {subject}")
    return True


# ── SMTP backend ─────────────────────────────────────────────────────────────

async def _send_smtp(*, to: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    """Send via SMTP."""
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

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _smtp_send_blocking, msg, to)

    logger.info(f"Email sent via SMTP to {to}: {subject}")
    return True


def _smtp_send_blocking(msg, to: str) -> None:
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


async def send_new_lead_notification(*, to: str, lead_name: str, lead_phone: str, lead_intent: str, lead_score: float) -> bool:
    """Notify the business owner when a new lead is captured."""
    subject = f"🎯 New lead captured: {lead_name or 'Unknown'}"
    score_pct = int(lead_score * 100) if lead_score <= 1 else int(lead_score)
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
        <h1 style="font-size: 22px; margin: 0 0 8px;">New Lead Captured</h1>
        <p style="color: #666; font-size: 15px; line-height: 1.6;">
            Your AI agent just qualified a new lead.
        </p>
        <div style="background: #f8f9fa; border-radius: 12px; padding: 20px; margin: 20px 0;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 6px 0; color: #666; font-size: 14px;">Name</td><td style="padding: 6px 0; font-size: 14px; font-weight: 600;">{lead_name or '—'}</td></tr>
                <tr><td style="padding: 6px 0; color: #666; font-size: 14px;">Phone</td><td style="padding: 6px 0; font-size: 14px;">{lead_phone or '—'}</td></tr>
                <tr><td style="padding: 6px 0; color: #666; font-size: 14px;">Intent</td><td style="padding: 6px 0; font-size: 14px;">{lead_intent or '—'}</td></tr>
                <tr><td style="padding: 6px 0; color: #666; font-size: 14px;">Score</td><td style="padding: 6px 0; font-size: 14px; font-weight: 600; color: {'#10b981' if score_pct >= 70 else '#f59e0b' if score_pct >= 40 else '#6b7280'};">{score_pct}%</td></tr>
            </table>
        </div>
        <div style="text-align: center; margin: 24px 0;">
            <a href="{settings.PLATFORM_URL}/dashboard"
               style="display: inline-block; background: linear-gradient(135deg, #06b6d4, #3b82f6); color: white; padding: 12px 28px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 14px;">
                View in Dashboard
            </a>
        </div>
        <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
        <p style="color: #999; font-size: 12px; text-align: center;">
            Omniweb AI · <a href="{settings.PLATFORM_URL}" style="color: #999;">omniweb.ai</a>
        </p>
    </div>
    """
    text = f"New lead: {lead_name} ({lead_phone}) — Intent: {lead_intent}, Score: {score_pct}%"
    return await send_email(to=to, subject=subject, html_body=html, text_body=text)


async def _log_email(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    conversation_id: str | None,
    recipient: str,
    subject: str,
    email_type: str,
    ok: bool,
    error_message: str | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        EmailLog(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            recipient=recipient,
            subject=subject[:255],
            type=email_type,
            provider="resend",
            status="sent" if ok else "failed",
            error_message=error_message,
            metadata_json=metadata or {},
        )
    )
    await db.flush()


def _appointment_details_html(data: dict) -> str:
    rows = [
        ("Business", data.get("business_name")),
        ("Visitor", data.get("visitor_name")),
        ("Email", data.get("visitor_email")),
        ("Phone", data.get("visitor_phone")),
        ("Service", data.get("requested_service")),
        ("Preferred date", data.get("preferred_date")),
        ("Preferred time", data.get("preferred_time")),
        ("Source", data.get("source_url")),
        ("Notes", data.get("notes")),
    ]
    body = "".join(
        f"<tr><td style='padding:6px 12px 6px 0;color:#64748b'>{escape(label)}</td>"
        f"<td style='padding:6px 0;font-weight:600;color:#0f172a'>{escape(str(value or '—'))}</td></tr>"
        for label, value in rows
    )
    booking_url = escape(str(data.get("booking_url") or ""))
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:640px;margin:0 auto;padding:28px 20px;color:#0f172a">
      <h1 style="font-size:22px;margin:0 0 12px">{escape(str(data.get('title') or 'Appointment request'))}</h1>
      <p style="font-size:15px;line-height:1.6;color:#475569;margin:0 0 18px">{escape(str(data.get('intro') or 'Here are the appointment details.'))}</p>
      <table style="width:100%;border-collapse:collapse;background:#f8fafc;border-radius:12px;padding:14px;margin:18px 0">{body}</table>
      <p style="margin:24px 0">
        <a href="{booking_url}" style="display:inline-block;background:#6d5dfc;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px;font-weight:700">Open booking page</a>
      </p>
      <p style="font-size:12px;color:#94a3b8">Powered by Omniweb AI</p>
    </div>
    """


def _appointment_details_text(data: dict) -> str:
    lines = [
        str(data.get("title") or "Appointment request"),
        "",
        str(data.get("intro") or "Here are the appointment details."),
        "",
        f"Business: {data.get('business_name') or '—'}",
        f"Visitor: {data.get('visitor_name') or '—'}",
        f"Email: {data.get('visitor_email') or '—'}",
        f"Phone: {data.get('visitor_phone') or '—'}",
        f"Service: {data.get('requested_service') or '—'}",
        f"Preferred date: {data.get('preferred_date') or '—'}",
        f"Preferred time: {data.get('preferred_time') or '—'}",
        f"Source: {data.get('source_url') or '—'}",
        f"Notes: {data.get('notes') or '—'}",
        "",
        f"Booking page: {data.get('booking_url') or '—'}",
    ]
    return "\n".join(lines)


async def sendAppointmentRequestEmail(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    conversation_id: str | None,
    to: str,
    **data,
) -> bool:
    subject = f"Appointment request from {data.get('visitor_name') or 'a website visitor'}"
    payload = {
        **data,
        "title": "New appointment request",
        "intro": "A visitor asked your AI assistant to schedule an appointment.",
    }
    ok = await send_email(
        to=to,
        subject=subject,
        html_body=_appointment_details_html(payload),
        text_body=_appointment_details_text(payload),
    )
    await _log_email(db, tenant_id=tenant_id, conversation_id=conversation_id, recipient=to, subject=subject, email_type="appointment_request", ok=ok, metadata={"booking_url": data.get("booking_url")})
    return ok


async def sendVisitorConfirmationEmail(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    conversation_id: str | None,
    to: str,
    **data,
) -> bool:
    business = data.get("business_name") or "the team"
    subject = f"Your appointment request with {business}"
    payload = {
        **data,
        "title": "Your appointment request",
        "intro": f"Thanks for reaching out. You can choose the best available time for {business} using the booking page below.",
    }
    ok = await send_email(
        to=to,
        subject=subject,
        html_body=_appointment_details_html(payload),
        text_body=_appointment_details_text(payload),
    )
    await _log_email(db, tenant_id=tenant_id, conversation_id=conversation_id, recipient=to, subject=subject, email_type="visitor_confirmation", ok=ok, metadata={"booking_url": data.get("booking_url")})
    return ok


async def sendLeadNotificationEmail(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    conversation_id: str | None,
    to: str,
    **data,
) -> bool:
    subject = f"New lead from {data.get('visitor_name') or 'website visitor'}"
    payload = {
        **data,
        "title": "New AI assistant lead",
        "intro": "Your AI assistant captured a visitor who may need follow-up.",
    }
    ok = await send_email(
        to=to,
        subject=subject,
        html_body=_appointment_details_html(payload),
        text_body=_appointment_details_text(payload),
    )
    await _log_email(db, tenant_id=tenant_id, conversation_id=conversation_id, recipient=to, subject=subject, email_type="lead_notification", ok=ok, metadata={"source_url": data.get("source_url")})
    return ok


async def sendWidgetInstallEmail(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    conversation_id: str | None = None,
    to: str,
    business_name: str,
    widget_url: str,
) -> bool:
    subject = f"{business_name or 'Your'} Omniweb widget is installed"
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;padding:28px 20px">
      <h1 style="font-size:22px;margin:0 0 12px">Widget installed</h1>
      <p style="color:#475569;line-height:1.6">Your Omniweb AI widget is installed and ready to help visitors.</p>
      <p><a href="{escape(widget_url)}" style="display:inline-block;background:#6d5dfc;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px;font-weight:700">Open widget</a></p>
    </div>
    """
    text = f"Your Omniweb AI widget is installed: {widget_url}"
    ok = await send_email(to=to, subject=subject, html_body=html, text_body=text)
    await _log_email(db, tenant_id=tenant_id, conversation_id=conversation_id, recipient=to, subject=subject, email_type="widget_install", ok=ok, metadata={"widget_url": widget_url})
    return ok


async def send_trial_expiring_email(*, to: str, name: str, days_left: int) -> bool:
    """Warn the user their trial is about to expire."""
    subject = f"⏰ Your Omniweb trial expires in {days_left} day{'s' if days_left != 1 else ''}"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
        <h1 style="font-size: 22px; margin: 0 0 8px;">Your trial is ending soon</h1>
        <p style="color: #666; font-size: 15px; line-height: 1.6;">
            Hi {name}, your free trial expires in <strong>{days_left} day{'s' if days_left != 1 else ''}</strong>.
            Subscribe now to keep your AI agent running without interruption.
        </p>
        <div style="text-align: center; margin: 28px 0;">
            <a href="{settings.PLATFORM_URL}/dashboard"
               style="display: inline-block; background: linear-gradient(135deg, #06b6d4, #3b82f6); color: white; padding: 14px 32px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 15px;">
                Subscribe Now
            </a>
        </div>
        <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
        <p style="color: #999; font-size: 12px; text-align: center;">
            Omniweb AI · <a href="{settings.PLATFORM_URL}" style="color: #999;">omniweb.ai</a>
        </p>
    </div>
    """
    text = f"Hi {name}, your Omniweb trial expires in {days_left} days. Subscribe at {settings.PLATFORM_URL}/dashboard"
    return await send_email(to=to, subject=subject, html_body=html, text_body=text)


async def send_usage_limit_warning(*, to: str, name: str, minutes_used: int, plan_limit: int, plan: str) -> bool:
    """Warn when approaching plan minute limits (e.g., 80% usage)."""
    pct = int((minutes_used / plan_limit) * 100) if plan_limit > 0 else 100
    subject = f"⚠️ You've used {pct}% of your {plan} plan minutes"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
        <h1 style="font-size: 22px; margin: 0 0 8px;">Usage Alert</h1>
        <p style="color: #666; font-size: 15px; line-height: 1.6;">
            Hi {name}, you've used <strong>{minutes_used}</strong> of your <strong>{plan_limit}</strong> minutes
            on the <strong>{plan}</strong> plan ({pct}%).
        </p>
        <p style="color: #666; font-size: 15px;">
            Consider upgrading to avoid service interruption.
        </p>
        <div style="text-align: center; margin: 28px 0;">
            <a href="{settings.PLATFORM_URL}/dashboard"
               style="display: inline-block; background: linear-gradient(135deg, #06b6d4, #3b82f6); color: white; padding: 12px 28px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 14px;">
                Manage Plan
            </a>
        </div>
        <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
        <p style="color: #999; font-size: 12px; text-align: center;">
            Omniweb AI · <a href="{settings.PLATFORM_URL}" style="color: #999;">omniweb.ai</a>
        </p>
    </div>
    """
    text = f"Usage alert: {minutes_used}/{plan_limit} minutes used on {plan} plan ({pct}%). Manage: {settings.PLATFORM_URL}/dashboard"
    return await send_email(to=to, subject=subject, html_body=html, text_body=text)
