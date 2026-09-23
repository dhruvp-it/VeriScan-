"""Auth helpers, token utilities, and scan-entitlement logic."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Header, HTTPException

from core.config import JWT_SECRET, TOKEN_ALGORITHM, db


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def token_for(user_id: str) -> str:
    return jwt.encode(
        {"sub": user_id, "exp": datetime.now(timezone.utc).timestamp() + 60 * 60 * 24 * 30},
        JWT_SECRET, algorithm=TOKEN_ALGORITHM,
    )


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "***"
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        return f"{name[0]}***@{domain}"
    return f"{name[0]}{'*' * (len(name) - 2)}{name[-1]}@{domain}"


async def authenticated_user(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(authorization[7:], JWT_SECRET, algorithms=[TOKEN_ALGORITHM])
        user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    except (jwt.PyJWTError, TypeError):
        user = None
    if not user:
        raise HTTPException(401, "Session expired")
    if user.get("suspended"):
        raise HTTPException(403, "This account has been suspended. Please contact support.")
    return user


async def admin_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return user


async def consume_scan(guest_id: Optional[str], user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if user:
        entitlement = await db.entitlements.find_one({"user_id": user["id"]}, {"_id": 0})
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        if not entitlement or entitlement.get("free_month") != month:
            entitlement = {"user_id": user["id"], "free_month": month, "free_used": 0,
                           "purchased_balance": 0, "intro_used": 0, "subscribed": False}
            await db.entitlements.replace_one({"user_id": user["id"]}, entitlement, upsert=True)
        # Active paid subscription → unlimited
        if entitlement.get("subscribed"):
            return {"remaining": None, "source": "subscription"}
        # 3-month free trial → unlimited within window
        trial_expires = user.get("trial_expires_at")
        if trial_expires:
            try:
                trial_dt = datetime.fromisoformat(trial_expires)
                if trial_dt > datetime.now(timezone.utc):
                    return {"remaining": None, "source": "trial"}
            except ValueError:
                pass
        # Post-trial: purchased wallet balance
        if entitlement.get("purchased_balance", 0) > 0:
            await db.entitlements.update_one({"user_id": user["id"]}, {"$inc": {"purchased_balance": -1}})
            return {"remaining": entitlement.get("purchased_balance", 0) - 1, "source": "wallet"}
        raise HTTPException(402, "Your 3-month free trial has ended. Add credits or subscribe to continue.")
    if not guest_id:
        raise HTTPException(400, "Guest identifier required")
    guest = await db.guests.find_one({"guest_id": guest_id}, {"_id": 0})
    used = guest.get("used", 0) if guest else 0
    if used >= 3:
        raise HTTPException(401, "Your 3 guest scans are complete. Create your free account for 3 months of unlimited scans.")
    await db.guests.update_one({"guest_id": guest_id}, {"$set": {"used": used + 1}}, upsert=True)
    return {"remaining": 2 - used, "source": "guest"}
