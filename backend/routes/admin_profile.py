"""Admin self-service — email/phone change with OTP verification.

Email change requires two OTPs: one delivered to the current admin email and
one delivered to the new email; both must be entered in the same session.

Phone change requires a single OTP delivered to the admin's current email
(no SMS gateway is configured yet — see PRD roadmap). Admin phone number is
stored on the user document under `phone_number` and `phone_verified_at`.
"""
import random
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core.config import db
from core.deps import admin_user, now_iso
from emailer import (
    render_admin_email_change_otp, render_admin_phone_change_otp, send_email,
)

router = APIRouter()

OTP_TTL_MINUTES = 15


class AdminChangeEmailStart(BaseModel):
    new_email: EmailStr
    password: str = Field(min_length=6)


class AdminChangeEmailConfirm(BaseModel):
    session_id: str
    current_otp: str = Field(min_length=6, max_length=6)
    new_otp: str = Field(min_length=6, max_length=6)


class AdminChangePhoneStart(BaseModel):
    new_phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=6)


class AdminChangePhoneConfirm(BaseModel):
    session_id: str
    otp: str = Field(min_length=6, max_length=6)


def _otp() -> str:
    return f"{random.randint(0, 999999):06d}"


def _sid() -> str:
    return secrets.token_urlsafe(24)


async def _require_password(admin: Dict[str, Any], password: str) -> None:
    hash_ = admin.get("password_hash", "")
    if not hash_ or not bcrypt.checkpw(password.encode(), hash_.encode()):
        raise HTTPException(401, "Current password is incorrect")


@router.get("/admin/profile")
async def admin_profile(admin: Dict[str, Any] = Depends(admin_user)) -> Dict[str, Any]:
    return {
        "id": admin["id"],
        "email": admin["email"],
        "phone_number": admin.get("phone_number"),
        "phone_verified_at": admin.get("phone_verified_at"),
        "role": admin.get("role"),
        "created_at": admin.get("created_at"),
        "terms_accepted": admin.get("terms_accepted"),
        "privacy_accepted": admin.get("privacy_accepted"),
    }


@router.post("/admin/profile/change-email/start")
async def admin_change_email_start(payload: AdminChangeEmailStart, admin: Dict[str, Any] = Depends(admin_user)) -> Dict[str, Any]:
    await _require_password(admin, payload.password)
    new_email = payload.new_email.strip().lower()
    if new_email == admin["email"].lower():
        raise HTTPException(400, "This is already your admin email")
    if await db.users.find_one({"email": new_email}, {"_id": 0, "id": 1}):
        raise HTTPException(409, "Another account already uses that email")
    session_id = _sid()
    current_code = _otp()
    new_code = _otp()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()
    await db.admin_change_sessions.insert_one({
        "session_id": session_id, "admin_id": admin["id"], "kind": "email",
        "current_otp": current_code, "new_otp": new_code,
        "new_email": new_email, "expires_at": expires, "used": False,
        "created_at": now_iso(),
    })
    subject_cur, html_cur = render_admin_email_change_otp(current_code, is_current=True)
    subject_new, html_new = render_admin_email_change_otp(new_code, is_current=False)
    await send_email(to=admin["email"], subject=subject_cur, html=html_cur)
    await send_email(to=new_email, subject=subject_new, html=html_new)
    return {"session_id": session_id, "expires_at": expires,
            "sent_to_current": True, "sent_to_new": True}


@router.post("/admin/profile/change-email/confirm")
async def admin_change_email_confirm(payload: AdminChangeEmailConfirm, admin: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    session = await db.admin_change_sessions.find_one(
        {"session_id": payload.session_id, "admin_id": admin["id"], "kind": "email"},
        {"_id": 0},
    )
    if not session or session.get("used"):
        raise HTTPException(400, "Invalid or expired session")
    if datetime.fromisoformat(session["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(400, "This verification code has expired. Please request a new one.")
    if payload.current_otp != session["current_otp"] or payload.new_otp != session["new_otp"]:
        raise HTTPException(400, "One or both codes are incorrect")
    await db.users.update_one({"id": admin["id"]}, {"$set": {"email": session["new_email"]}})
    await db.admin_change_sessions.update_one({"session_id": payload.session_id}, {"$set": {"used": True}})
    return {"status": "email_updated", "new_email": session["new_email"]}


@router.post("/admin/profile/change-phone/start")
async def admin_change_phone_start(payload: AdminChangePhoneStart, admin: Dict[str, Any] = Depends(admin_user)) -> Dict[str, Any]:
    await _require_password(admin, payload.password)
    # Normalise: strip spaces and dashes, keep leading +
    phone = payload.new_phone.strip().replace(" ", "").replace("-", "")
    if not phone.replace("+", "").isdigit():
        raise HTTPException(400, "Phone number must contain only digits (with an optional leading +)")
    if phone == admin.get("phone_number"):
        raise HTTPException(400, "That phone number is already saved")
    session_id = _sid()
    otp = _otp()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()
    await db.admin_change_sessions.insert_one({
        "session_id": session_id, "admin_id": admin["id"], "kind": "phone",
        "otp": otp, "new_phone": phone, "expires_at": expires, "used": False,
        "created_at": now_iso(),
    })
    subject, html = render_admin_phone_change_otp(otp, phone[-4:] if len(phone) >= 4 else phone)
    await send_email(to=admin["email"], subject=subject, html=html)
    return {"session_id": session_id, "expires_at": expires, "delivery": "email",
            "delivery_notice": "OTP delivered to your admin email. SMS delivery will be added when an SMS gateway (Twilio / MSG91) is configured."}


@router.post("/admin/profile/change-phone/confirm")
async def admin_change_phone_confirm(payload: AdminChangePhoneConfirm, admin: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    session = await db.admin_change_sessions.find_one(
        {"session_id": payload.session_id, "admin_id": admin["id"], "kind": "phone"},
        {"_id": 0},
    )
    if not session or session.get("used"):
        raise HTTPException(400, "Invalid or expired session")
    if datetime.fromisoformat(session["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(400, "This verification code has expired. Please request a new one.")
    if payload.otp != session["otp"]:
        raise HTTPException(400, "That code is incorrect")
    await db.users.update_one(
        {"id": admin["id"]},
        {"$set": {"phone_number": session["new_phone"], "phone_verified_at": now_iso()}},
    )
    await db.admin_change_sessions.update_one({"session_id": payload.session_id}, {"$set": {"used": True}})
    return {"status": "phone_updated", "new_phone": session["new_phone"]}


@router.post("/admin/analytics/report/send-now")
async def admin_send_monthly_report_now(admin: Dict[str, Any] = Depends(admin_user)) -> Dict[str, Any]:
    """Manual trigger — sends the previous month's analytics email to every admin."""
    from scheduler import _send_monthly_reports
    _ = admin
    sent = await _send_monthly_reports(force=True)
    return {"sent": sent}
