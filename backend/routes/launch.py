"""Launch offer routes — public status + admin controls to extend/toggle."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import db
from core.deps import admin_user
from core.settings import LAUNCH_OFFER_KEY, get_launch_offer, offer_is_live

router = APIRouter()


class LaunchOfferUpdate(BaseModel):
    active: Optional[bool] = None
    eligibility_ends_at: Optional[str] = None
    free_days: Optional[int] = None


@router.get("/launch-offer")
async def launch_offer_public() -> Dict[str, Any]:
    """Public — powers the welcome message and home banner."""
    offer = await get_launch_offer()
    return {
        "active": offer_is_live(offer),
        "launched_at": offer.get("launched_at"),
        "eligibility_ends_at": offer.get("eligibility_ends_at"),
        "free_days": int(offer.get("free_days", 365)),
    }


@router.get("/admin/launch-offer")
async def launch_offer_admin(_: Dict[str, Any] = Depends(admin_user)) -> Dict[str, Any]:
    offer = await get_launch_offer()
    return {
        "active": offer.get("active", False),
        "live": offer_is_live(offer),
        "launched_at": offer.get("launched_at"),
        "eligibility_ends_at": offer.get("eligibility_ends_at"),
        "free_days": int(offer.get("free_days", 365)),
    }


@router.put("/admin/launch-offer")
async def update_launch_offer(
    payload: LaunchOfferUpdate, _: Dict[str, Any] = Depends(admin_user),
) -> Dict[str, Any]:
    await get_launch_offer()  # ensure the doc exists before updating
    updates: Dict[str, Any] = {}
    if payload.active is not None:
        updates["active"] = payload.active
    if payload.eligibility_ends_at is not None:
        updates["eligibility_ends_at"] = payload.eligibility_ends_at
    if payload.free_days is not None:
        if payload.free_days < 1 or payload.free_days > 3650:
            raise HTTPException(400, "Free duration must be between 1 and 3650 days.")
        updates["free_days"] = int(payload.free_days)
    if updates:
        await db.app_settings.update_one({"key": LAUNCH_OFFER_KEY}, {"$set": updates})
    offer = await get_launch_offer()
    return {
        "active": offer.get("active", False),
        "live": offer_is_live(offer),
        "launched_at": offer.get("launched_at"),
        "eligibility_ends_at": offer.get("eligibility_ends_at"),
        "free_days": int(offer.get("free_days", 365)),
    }
