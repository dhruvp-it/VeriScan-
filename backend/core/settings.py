"""Global app settings — launch offer eligibility window and free duration.

The launch offer grants every new signup a long free period (default 1 year)
while the eligibility window is open. The window defaults to 3 months from
launch and can be toggled / extended by an admin from the console.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from core.config import db

LAUNCH_OFFER_KEY = "launch_offer"
DEFAULT_FREE_DAYS = 365          # every new signup gets a full year free
DEFAULT_ELIGIBILITY_DAYS = 90    # offer stays open for 3 months after launch
FALLBACK_TRIAL_DAYS = 90         # normal trial once the launch offer closes


async def get_launch_offer() -> Dict[str, Any]:
    """Return the launch-offer settings doc, seeding sensible defaults once."""
    doc = await db.app_settings.find_one({"key": LAUNCH_OFFER_KEY}, {"_id": 0})
    if not doc:
        now = datetime.now(timezone.utc)
        doc = {
            "key": LAUNCH_OFFER_KEY,
            "active": True,
            "launched_at": now.isoformat(),
            "eligibility_ends_at": (now + timedelta(days=DEFAULT_ELIGIBILITY_DAYS)).isoformat(),
            "free_days": DEFAULT_FREE_DAYS,
        }
        await db.app_settings.update_one(
            {"key": LAUNCH_OFFER_KEY}, {"$setOnInsert": doc}, upsert=True,
        )
    return doc


def offer_is_live(offer: Dict[str, Any]) -> bool:
    """True when the offer is toggled on and the window has not lapsed."""
    if not offer.get("active"):
        return False
    try:
        return datetime.fromisoformat(offer["eligibility_ends_at"]) > datetime.now(timezone.utc)
    except (ValueError, KeyError, TypeError):
        return False


async def trial_days_for_signup() -> int:
    """Free-trial length for a brand new signup, honoring the launch offer."""
    offer = await get_launch_offer()
    if offer_is_live(offer):
        return int(offer.get("free_days", DEFAULT_FREE_DAYS))
    return FALLBACK_TRIAL_DAYS
