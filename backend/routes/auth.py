"""Auth, registration, and legal-document routes."""
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from fastapi import APIRouter, Header, HTTPException
from pymongo import ReturnDocument

from core.config import PREFERENCES, db
from core.deps import now_iso, token_for
from core.models import (
    AuthRequest, LoginRequest, PasswordResetComplete, PasswordResetStart,
)
from core.otp import check_otp, hash_otp
from core.settings import trial_days_for_signup
from emailer import render_otp_email, send_email
from legal_content import (
    EFFECTIVE_DATE, PRIVACY_POLICY, PRIVACY_VERSION, TERMS_OF_SERVICE, TERMS_VERSION,
)

router = APIRouter()

# Brute-force protection for /auth/login — account-scoped lockout.
MAX_LOGIN_FAILS = 5
LOCK_MINUTES = 15
# Constant-time dummy so unknown emails still incur a bcrypt cost (no user enumeration by timing).
DUMMY_HASH = bcrypt.hashpw(b"unusable-dummy-password", bcrypt.gensalt()).decode()


async def _record_login_failure(email: str, now: datetime) -> None:
    doc = await db.auth_throttle.find_one_and_update(
        {"_id": email},
        {"$inc": {"failures": 1}, "$set": {"last_failure": now.isoformat()}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    if (doc or {}).get("failures", 0) >= MAX_LOGIN_FAILS:
        await db.auth_throttle.update_one(
            {"_id": email},
            {"$set": {"locked_until": (now + timedelta(minutes=LOCK_MINUTES)).isoformat(),
                      "failures": 0}},
        )


@router.get("/")
async def root() -> Dict[str, str]:
    return {"message": "VeriScan API is ready"}


@router.get("/legal/terms")
async def legal_terms() -> Dict[str, Any]:
    return {"version": TERMS_VERSION, "effective": EFFECTIVE_DATE, "content": TERMS_OF_SERVICE}


@router.get("/legal/privacy")
async def legal_privacy() -> Dict[str, Any]:
    return {"version": PRIVACY_VERSION, "effective": EFFECTIVE_DATE, "content": PRIVACY_POLICY}


@router.post("/auth/register")
async def register(payload: AuthRequest, x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if payload.accepted_terms_version != TERMS_VERSION or payload.accepted_privacy_version != PRIVACY_VERSION:
        raise HTTPException(400, "Please accept the current Terms & Privacy Policy to continue.")
    email = payload.email.strip().lower()
    if await db.users.find_one({"email": email}, {"_id": 0}):
        raise HTTPException(409, "An account with this email already exists")
    preferences = PREFERENCES.copy()
    if x_guest_id:
        guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0})
        if guest and guest.get("preferences"):
            preferences = guest["preferences"]
    trial_days = await trial_days_for_signup()
    user = {
        "id": str(uuid.uuid4()), "email": email,
        "password_hash": bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode(),
        "preferences": preferences, "role": "user",
        "suspended": False,
        "terms_accepted": {"version": TERMS_VERSION, "at": now_iso()},
        "privacy_accepted": {"version": PRIVACY_VERSION, "at": now_iso()},
        "trial_expires_at": (datetime.now(timezone.utc) + timedelta(days=trial_days)).isoformat(),
        "created_at": now_iso(),
    }
    await db.users.insert_one(user.copy())
    await db.entitlements.insert_one({
        "user_id": user["id"], "free_month": datetime.now(timezone.utc).strftime("%Y-%m"),
        "free_used": 0, "purchased_balance": 0, "intro_used": 0, "subscribed": False,
    })
    if x_guest_id:
        await db.history.update_many({"user_id": f"guest:{x_guest_id}"}, {"$set": {"user_id": user["id"]}})
    return {"token": token_for(user["id"]), "user": {"id": user["id"], "email": email, "preferences": user["preferences"], "role": "user"}}


@router.post("/auth/login")
async def login(payload: LoginRequest) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    email = payload.email.strip().lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    throttle = await db.auth_throttle.find_one({"_id": email})
    locked = False
    if throttle and throttle.get("locked_until"):
        try:
            locked = datetime.fromisoformat(throttle["locked_until"]) > now
        except ValueError:
            locked = False
    # Always run bcrypt (dummy hash for unknown users) to equalize timing.
    password_ok = bcrypt.checkpw(
        payload.password.encode(),
        (user["password_hash"] if user else DUMMY_HASH).encode(),
    )
    if not user or locked or not password_ok:
        await _record_login_failure(email, now)
        raise HTTPException(401, "Email or password is incorrect")
    if user.get("suspended"):
        raise HTTPException(403, "This account has been suspended. Please contact support.")
    await db.auth_throttle.delete_one({"_id": email})
    return {"token": token_for(user["id"]), "user": {
        "id": user["id"], "email": user["email"], "preferences": user.get("preferences", PREFERENCES),
        "role": user.get("role", "user"),
    }}


@router.post("/auth/forgot-password")
async def forgot_password(payload: PasswordResetStart) -> Dict[str, str]:
    email = payload.email.strip().lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    # Always respond with the same message to avoid enumeration
    if user and not user.get("suspended"):
        otp = f"{random.randint(0, 999999):06d}"
        # Invalidate any earlier unused codes for this account.
        await db.password_resets.update_many(
            {"email": email, "used": {"$ne": True}}, {"$set": {"used": True}},
        )
        await db.password_resets.insert_one({
            "id": str(uuid.uuid4()), "email": email, "otp_hash": hash_otp(otp),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "created_at": now_iso(), "attempts": 0, "used": False,
        })
        subject, html = render_otp_email(otp)
        await send_email(to=email, subject=subject, html=html)
    return {"status": "sent"}


@router.post("/auth/reset-password")
async def reset_password(payload: PasswordResetComplete) -> Dict[str, str]:
    email = payload.email.strip().lower()
    # Atomically grab the newest active code and count this attempt (max 5).
    record = await db.password_resets.find_one_and_update(
        {"email": email, "used": {"$ne": True}, "attempts": {"$lt": 5}},
        {"$inc": {"attempts": 1}},
        sort=[("created_at", -1)],
        return_document=ReturnDocument.AFTER,
    )
    if not record:
        raise HTTPException(400, "That reset code doesn't match. Try again or request a new one.")
    if datetime.fromisoformat(record["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(400, "This reset code has expired. Please request a new one.")
    if not check_otp(payload.otp, record.get("otp_hash", "")):
        raise HTTPException(400, "That reset code doesn't match. Try again or request a new one.")
    new_hash = bcrypt.hashpw(payload.new_password.encode(), bcrypt.gensalt()).decode()
    await db.users.update_one({"email": email}, {"$set": {"password_hash": new_hash}})
    await db.password_resets.delete_many({"email": email})
    # Clear any login lockout so the user can sign in immediately.
    await db.auth_throttle.delete_one({"_id": email})
    return {"status": "ok"}
