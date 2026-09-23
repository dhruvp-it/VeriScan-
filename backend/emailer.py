"""Emergent-managed Resend integration with guardrails."""
import ipaddress
import logging
import os
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "VeriScan")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = (
    "reply with your password", "reply with the code", "send your password", "cvv",
    "send us your password", "enter your password below", "confirm your card number",
    "your full card number", "seed phrase", "recovery phrase", "verify your card",
    "social security number", "confirm your bank details",
)
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for phrase in _CRED_ASK:
        if phrase in body:
            raise ValueError(f"Email asks the recipient for credentials: {phrase!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for match in _HOSTISH.finditer(text):
            if not _same_site(match.group(1).lower(), real):
                raise ValueError(f"Anchor text {match.group(1)!r} ≠ real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str, reply_to: str | None = None) -> str | None:
    _assert_safe_email(subject, html)
    if not EMAIL_KEY:
        logger.warning("EMERGENT_EMAIL_KEY not set — skipping email send to %s", to)
        return None
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if reply_to or EMAIL_REPLY_TO:
        payload["contact_email"] = reply_to or EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{EMAIL_BASE_URL}/api/v1/email/send",
                headers={"X-Email-Key": EMAIL_KEY},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as exc:
        logger.error("Email send failed: %s %s", exc.response.status_code, exc.response.text)
        # Never crash caller — email is a side-effect.
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("Email send error: %s", exc)
        return None


def render_otp_email(otp: str, purpose: str = "reset your password") -> tuple[str, str]:
    subject = f"Your {EMAIL_FROM_NAME} verification code"
    html = (
        f'<table role="presentation" width="100%" style="max-width:520px;margin:0 auto;'
        f'font-family:Arial,Helvetica,sans-serif;background:#fdfcfa;padding:24px">'
        f'<tr><td>'
        f'<h2 style="margin:0 0 12px 0;color:#1a1c19">{escape(EMAIL_FROM_NAME)}</h2>'
        f'<p style="color:#2c302d;font-size:15px;line-height:22px">'
        f'Use the code below to {escape(purpose)}. It expires in 10 minutes.</p>'
        f'<p style="font-size:32px;letter-spacing:6px;font-weight:800;color:#2e7d32;'
        f'padding:16px 24px;background:#e8f5e9;border-radius:12px;text-align:center;margin:24px 0">'
        f'{escape(otp)}</p>'
        f'<p style="color:#707873;font-size:13px;line-height:20px">'
        f'If you didn&apos;t request this, you can safely ignore the email. We never ask for your '
        f'password by email.</p>'
        f'<p style="color:#a0a4a2;font-size:12px;margin-top:32px">'
        f'Sent by {escape(EMAIL_FROM_NAME)}.</p>'
        f'</td></tr></table>'
    )
    return subject, html


def render_watchlist_alert(product_name: str, alt_name: str, alt_score: int) -> tuple[str, str]:
    subject = f"A cleaner alternative to {product_name} is on {EMAIL_FROM_NAME}"
    html = (
        f'<table role="presentation" width="100%" style="max-width:520px;margin:0 auto;'
        f'font-family:Arial,Helvetica,sans-serif;background:#fdfcfa;padding:24px">'
        f'<tr><td>'
        f'<h2 style="margin:0 0 12px 0;color:#1a1c19">{escape(EMAIL_FROM_NAME)}</h2>'
        f'<p style="color:#2c302d;font-size:15px;line-height:22px">'
        f'Good news — a cleaner alternative to <strong>{escape(product_name)}</strong> just entered our registry.</p>'
        f'<p style="color:#2c302d;font-size:16px;line-height:22px;padding:14px 18px;background:#e8f5e9;'
        f'border-radius:12px"><strong>{escape(alt_name)}</strong> — safety score '
        f'<strong>{alt_score}/100</strong>.</p>'
        f'<p style="color:#707873;font-size:13px;line-height:20px">'
        f'Open the {escape(EMAIL_FROM_NAME)} app to see full ingredients, nutrition, and buying options.</p>'
        f'<p style="color:#a0a4a2;font-size:12px;margin-top:32px">'
        f'Sent by {escape(EMAIL_FROM_NAME)}.</p>'
        f'</td></tr></table>'
    )
    return subject, html


def render_admin_reset_link(reset_code: str, subject_email: str) -> tuple[str, str]:
    subject = f"Password reset requested for your {EMAIL_FROM_NAME} account"
    html = (
        f'<table role="presentation" width="100%" style="max-width:520px;margin:0 auto;'
        f'font-family:Arial,Helvetica,sans-serif;background:#fdfcfa;padding:24px">'
        f'<tr><td>'
        f'<h2 style="margin:0 0 12px 0;color:#1a1c19">{escape(EMAIL_FROM_NAME)}</h2>'
        f'<p style="color:#2c302d;font-size:15px;line-height:22px">'
        f'A password reset was initiated for {escape(subject_email)} by our support team. '
        f'Use the code below within 30 minutes to set a new password. If you didn&apos;t request this, '
        f'contact us right away.</p>'
        f'<p style="font-size:32px;letter-spacing:6px;font-weight:800;color:#2e7d32;'
        f'padding:16px 24px;background:#e8f5e9;border-radius:12px;text-align:center;margin:24px 0">'
        f'{escape(reset_code)}</p>'
        f'<p style="color:#a0a4a2;font-size:12px;margin-top:32px">Sent by {escape(EMAIL_FROM_NAME)}.</p>'
        f'</td></tr></table>'
    )
    return subject, html


def render_trial_reminder(days_left: int) -> tuple[str, str]:
    subject = f"Your {EMAIL_FROM_NAME} free trial ends in {days_left} days"
    html = (
        f'<table role="presentation" width="100%" style="max-width:540px;margin:0 auto;'
        f'font-family:Arial,Helvetica,sans-serif;background:#fdfcfa;padding:24px">'
        f'<tr><td>'
        f'<h2 style="margin:0 0 12px 0;color:#1a1c19">{escape(EMAIL_FROM_NAME)}</h2>'
        f'<p style="color:#2c302d;font-size:16px;line-height:24px">'
        f'Just a friendly heads-up — your <strong>3-month free trial</strong> ends in '
        f'<strong>{days_left} days</strong>.</p>'
        f'<p style="color:#2c302d;font-size:15px;line-height:22px">'
        f'You&apos;ve been using unlimited barcode scans, personalised match scoring, regulatory '
        f'badges and watchlist alerts. To keep everything going without a break, pick a subscription '
        f'or top up scan credits before your trial expires.</p>'
        f'<p style="color:#2c302d;font-size:14px;line-height:22px;padding:14px 18px;background:#e8f5e9;'
        f'border-radius:12px">'
        f'💡 <strong>Launch pricing</strong> is still active — the monthly plan is at 60% off the '
        f'regular price. Open the app and tap <em>Profile → View launch plans</em>.</p>'
        f'<p style="color:#707873;font-size:13px;line-height:20px">'
        f'Prefer not to subscribe? No problem — you can add pay-per-scan credits any time. '
        f'All purchases are final and non-refundable per our Terms.</p>'
        f'<p style="color:#a0a4a2;font-size:12px;margin-top:32px">Sent by {escape(EMAIL_FROM_NAME)}.</p>'
        f'</td></tr></table>'
    )
    return subject, html


def render_admin_monthly_report(period: str, totals: dict, top_products: list, top_retailers: list) -> tuple[str, str]:
    subject = f"{EMAIL_FROM_NAME} — Monthly analytics report · {period}"
    products_html = "".join(
        f'<tr><td style="padding:6px 0;color:#2c302d;font-size:13px">{escape(p.get("name") or "Unknown")}'
        f'</td><td style="padding:6px 0;color:#2e7d32;font-size:13px;font-weight:800;text-align:right">{p.get("count",0)}</td></tr>'
        for p in top_products[:10]
    ) or '<tr><td style="color:#707873;font-size:13px">No scans this period.</td></tr>'
    retailers_html = "".join(
        f'<tr><td style="padding:6px 0;color:#2c302d;font-size:13px">{escape(r.get("retailer_id") or "Unknown")}'
        f'</td><td style="padding:6px 0;color:#2e7d32;font-size:13px;font-weight:800;text-align:right">{r.get("count",0)}</td></tr>'
        for r in top_retailers[:10]
    ) or '<tr><td style="color:#707873;font-size:13px">No retailer taps this period.</td></tr>'
    html = (
        f'<table role="presentation" width="100%" style="max-width:640px;margin:0 auto;'
        f'font-family:Arial,Helvetica,sans-serif;background:#fdfcfa;padding:24px">'
        f'<tr><td>'
        f'<h2 style="margin:0 0 8px 0;color:#1a1c19">{escape(EMAIL_FROM_NAME)} — Monthly report</h2>'
        f'<p style="color:#707873;font-size:13px;margin:0 0 20px 0">Period: {escape(period)} · '
        f'Anonymous counters (no personal data included).</p>'
        f'<table role="presentation" width="100%" style="margin:0 0 20px 0">'
        f'<tr>'
        f'<td style="padding:12px 14px;background:#e8f5e9;border-radius:10px 0 0 10px;color:#1a1c19">'
        f'<div style="font-size:11px;font-weight:800;letter-spacing:0.5px;color:#2e7d32">SCANS</div>'
        f'<div style="font-size:22px;font-weight:800;margin-top:4px">{totals.get("scan",0):,}</div></td>'
        f'<td style="padding:12px 14px;background:#e8f5e9;color:#1a1c19">'
        f'<div style="font-size:11px;font-weight:800;letter-spacing:0.5px;color:#2e7d32">RETAILER TAPS</div>'
        f'<div style="font-size:22px;font-weight:800;margin-top:4px">{totals.get("retailer_click",0):,}</div></td>'
        f'<td style="padding:12px 14px;background:#e8f5e9;border-radius:0 10px 10px 0;color:#1a1c19">'
        f'<div style="font-size:11px;font-weight:800;letter-spacing:0.5px;color:#2e7d32">CONTRIBUTIONS</div>'
        f'<div style="font-size:22px;font-weight:800;margin-top:4px">{totals.get("contribute",0):,}</div></td>'
        f'</tr></table>'
        f'<h3 style="color:#1a1c19;font-size:15px;margin:20px 0 8px 0">Top scanned products</h3>'
        f'<table role="presentation" width="100%" style="border-collapse:collapse">{products_html}</table>'
        f'<h3 style="color:#1a1c19;font-size:15px;margin:24px 0 8px 0">Retailer tap breakdown</h3>'
        f'<table role="presentation" width="100%" style="border-collapse:collapse">{retailers_html}</table>'
        f'<p style="color:#707873;font-size:13px;margin-top:24px">'
        f'Full CSV export available in the admin dashboard under Analytics.</p>'
        f'<p style="color:#a0a4a2;font-size:12px;margin-top:24px">Sent by {escape(EMAIL_FROM_NAME)}.</p>'
        f'</td></tr></table>'
    )
    return subject, html


def render_admin_email_change_otp(otp: str, is_current: bool) -> tuple[str, str]:
    role = "your current admin email" if is_current else "the new admin email you requested"
    subject = f"{EMAIL_FROM_NAME} admin — email change verification"
    html = (
        f'<table role="presentation" width="100%" style="max-width:520px;margin:0 auto;'
        f'font-family:Arial,Helvetica,sans-serif;background:#fdfcfa;padding:24px">'
        f'<tr><td>'
        f'<h2 style="margin:0 0 12px 0;color:#1a1c19">{escape(EMAIL_FROM_NAME)}</h2>'
        f'<p style="color:#2c302d;font-size:15px;line-height:22px">'
        f'You&apos;re updating {escape(role)}. Enter the code below in the admin panel within '
        f'15 minutes to confirm. If you didn&apos;t initiate this, ignore this email and change '
        f'your password immediately.</p>'
        f'<p style="font-size:30px;letter-spacing:6px;font-weight:800;color:#2e7d32;'
        f'padding:14px 22px;background:#e8f5e9;border-radius:12px;text-align:center;margin:20px 0">'
        f'{escape(otp)}</p>'
        f'<p style="color:#a0a4a2;font-size:12px;margin-top:24px">Sent by {escape(EMAIL_FROM_NAME)}.</p>'
        f'</td></tr></table>'
    )
    return subject, html


def render_admin_phone_change_otp(otp: str, phone_last4: str) -> tuple[str, str]:
    subject = f"{EMAIL_FROM_NAME} admin — phone change verification"
    html = (
        f'<table role="presentation" width="100%" style="max-width:520px;margin:0 auto;'
        f'font-family:Arial,Helvetica,sans-serif;background:#fdfcfa;padding:24px">'
        f'<tr><td>'
        f'<h2 style="margin:0 0 12px 0;color:#1a1c19">{escape(EMAIL_FROM_NAME)}</h2>'
        f'<p style="color:#2c302d;font-size:15px;line-height:22px">'
        f'You&apos;re updating your admin phone number to one ending in <strong>{escape(phone_last4)}</strong>. '
        f'Enter the code below in the admin panel within 15 minutes to confirm.</p>'
        f'<p style="font-size:30px;letter-spacing:6px;font-weight:800;color:#2e7d32;'
        f'padding:14px 22px;background:#e8f5e9;border-radius:12px;text-align:center;margin:20px 0">'
        f'{escape(otp)}</p>'
        f'<p style="color:#a0a4a2;font-size:12px;margin-top:24px">Sent by {escape(EMAIL_FROM_NAME)}.</p>'
        f'</td></tr></table>'
    )
    return subject, html
