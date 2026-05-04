#!/usr/bin/env python3
"""Send a real test email through the same code path the assistant uses.

Usage (run inside the API container so it sees your real env vars):
    python scripts/test_email_send.py you@yourpersonal.com
    python scripts/test_email_send.py you@yourpersonal.com --from "Acme <hello@acme.test>"

What it does:
  1. Reports which email backend is active (resend / smtp / none).
  2. Reports whether the platform RESEND_FROM_EMAIL domain is verified.
  3. If --from is given, also reports whether THAT tenant sender is verified.
  4. Sends a tiny test email using the EXACT same send_email function the
     assistant uses. Prints success/failure and the Resend HTTP response so
     you can see the real reason a send fails.
  5. Exits non-zero on failure so you can use it in deploy smoke tests.

This script never prints API keys.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Make the package importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import email_service  # noqa: E402


async def _run(target: str, sender: str | None) -> int:
    backend = email_service._email_backend()
    print(f"[1/4] Email backend detected: {backend}")
    if backend == "none":
        print(
            "      ✗ No email backend is configured on this container.\n"
            "        Set RESEND_API_KEY (preferred) or SMTP_HOST/SMTP_USER/SMTP_PASSWORD\n"
            "        on the API service and redeploy."
        )
        return 2

    platform_from = (
        getattr(email_service.settings, "RESEND_FROM_EMAIL", "")
        or getattr(email_service.settings, "SMTP_FROM", "")
        or ""
    )
    platform_status = await email_service.resend_sender_identity_status(platform_from or None)
    print(
        f"[2/4] Platform sender: {platform_status.get('sender') or '(unset)'}\n"
        f"      domain={platform_status.get('domain') or '(none)'}"
        f" status={platform_status.get('status')}"
        f" verified={platform_status.get('verified')}"
    )
    if backend == "resend" and not platform_status.get("verified") and not sender:
        print(
            "      ✗ The platform sender domain is not verified in Resend.\n"
            "        Resend will reject every send. Verify the domain at\n"
            "        https://resend.com/domains and update RESEND_FROM_EMAIL."
        )
        return 3

    if sender:
        tenant_status = await email_service.resend_sender_identity_status(sender)
        print(
            f"[3/4] Tenant sender override: {tenant_status.get('sender')}\n"
            f"      domain={tenant_status.get('domain')}"
            f" status={tenant_status.get('status')}"
            f" verified={tenant_status.get('verified')}"
        )
    else:
        print("[3/4] No tenant --from override; using platform sender.")

    print(f"[4/4] Sending test email to {target} ...")
    ok = await email_service.send_email(
        to=target,
        subject="Omniweb AI test email",
        html_body=(
            "<h2>Omniweb AI test email</h2>"
            "<p>This is a smoke-test email sent from your API container "
            "through the exact same Resend code path used by the AI assistant.</p>"
            "<p>If you received this, transactional email is working. "
            "If not, check the API logs for a Resend error message and your "
            "spam folder.</p>"
        ),
        text_body=(
            "Omniweb AI test email\n\n"
            "This is a smoke-test email sent from your API container through "
            "the exact same Resend code path used by the AI assistant. If you "
            "received this, transactional email is working. If not, check the "
            "API logs and your spam folder."
        ),
        from_email=sender,
    )
    if ok:
        print(
            "      ✓ send_email() returned True.\n"
            "        - If Resend was active, that means HTTP 2xx from api.resend.com/emails.\n"
            "        - Check your INBOX *and* SPAM folder for the test email.\n"
            "        - If nothing arrives in either, the platform domain DKIM/SPF\n"
            "          records may not be live yet (DNS can take up to an hour)."
        )
        return 0

    print(
        "      ✗ send_email() returned False.\n"
        "        Look in the API logs for a line containing 'Resend API error'.\n"
        "        That line includes the exact HTTP status and JSON error body\n"
        "        from Resend (most common: domain not verified, or invalid From)."
    )
    return 4


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a test transactional email via the configured backend.")
    parser.add_argument("to", help="Destination email address (your personal inbox).")
    parser.add_argument(
        "--from",
        dest="sender",
        default=None,
        help="Optional tenant sender override (e.g. 'Acme <hello@acme.test>').",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args.to, args.sender))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
