"""Profile preferences and entitlement routes."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header

from core.config import PREFERENCES, db
from core.deps import authenticated_user
from core.models import ProfileRequest
from legal_content import PRIVACY_VERSION, TERMS_VERSION

router = APIRouter()


class TermsAccept(ProfileRequest):
    pass


@router.post("/profile/accept-terms")
async def accept_terms(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Marks the current user as having accepted the current Terms and Privacy
    Policy versions. Required for subscription checkout."""
    from datetime import datetime, timezone
    user = await authenticated_user(authorization)
    now = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "terms_accepted": {"version": TERMS_VERSION, "at": now},
            "privacy_accepted": {"version": PRIVACY_VERSION, "at": now},
        }},
    )
    return {"status": "accepted", "terms_version": TERMS_VERSION, "privacy_version": PRIVACY_VERSION}


@router.get("/profile/terms-status")
async def terms_status(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if not authorization:
        return {"registered": False, "up_to_date": True,
                "terms_version": TERMS_VERSION, "privacy_version": PRIVACY_VERSION}
    user = await authenticated_user(authorization)
    ta = user.get("terms_accepted", {}) or {}
    pa = user.get("privacy_accepted", {}) or {}
    return {
        "registered": True,
        "up_to_date": ta.get("version") == TERMS_VERSION and pa.get("version") == PRIVACY_VERSION,
        "accepted_terms_version": ta.get("version"),
        "accepted_privacy_version": pa.get("version"),
        "terms_version": TERMS_VERSION, "privacy_version": PRIVACY_VERSION,
    }


@router.get("/profile")
async def get_profile(authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if authorization:
        user = await authenticated_user(authorization)
        return {"email": user["email"], "preferences": user.get("preferences", PREFERENCES),
                "registered": True, "role": user.get("role", "user")}
    if x_guest_id:
        guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) or {}
        return {"email": None, "preferences": guest.get("preferences", PREFERENCES), "registered": False, "role": "guest"}
    return {"email": None, "preferences": PREFERENCES, "registered": False, "role": "guest"}


@router.put("/profile")
async def save_profile(payload: ProfileRequest, authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    preferences = payload.model_dump()
    if authorization:
        user = await authenticated_user(authorization)
        await db.users.update_one({"id": user["id"]}, {"$set": {"preferences": preferences}})
    elif x_guest_id:
        await db.guests.update_one({"guest_id": x_guest_id}, {"$set": {"preferences": preferences}}, upsert=True)
    return preferences


@router.get("/entitlements")
async def entitlements(authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if authorization:
        user = await authenticated_user(authorization)
        item = await db.entitlements.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        trial_days = 0
        trial_active = False
        if user.get("trial_expires_at"):
            try:
                expires = datetime.fromisoformat(user["trial_expires_at"])
                delta = expires - datetime.now(timezone.utc)
                if delta.total_seconds() > 0:
                    trial_active = True
                    trial_days = int(delta.total_seconds() // 86400)
            except ValueError:
                pass
        return {
            "registered": True, "role": user.get("role", "user"),
            "free_remaining": 0,
            "wallet": item.get("purchased_balance", 0),
            "subscribed": item.get("subscribed", False),
            "trial_active": trial_active, "trial_days_remaining": trial_days,
            "email": user["email"],
        }
    guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) if x_guest_id else None
    return {"registered": False, "role": "guest",
            "free_remaining": max(0, 3 - (guest or {}).get("used", 0)),
            "wallet": 0, "subscribed": False,
            "trial_active": False, "trial_days_remaining": 0, "email": None}
