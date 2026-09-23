"""Watchlist, notifications, support tickets, and product reports."""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header

from core.config import PREFERENCES, db
from core.deps import authenticated_user, now_iso
from core.models import ReportRequest, SupportRequest
from ingredients_db import build_public_product

router = APIRouter()


@router.get("/watchlist")
async def watchlist(authorization: Optional[str] = Header(default=None)) -> List[Dict[str, Any]]:
    user = await authenticated_user(authorization)
    items = await db.watchlist.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    hydrated = []
    for item in items:
        product = await db.products.find_one({"barcode": item["barcode"]}, {"_id": 0})
        if product:
            hydrated.append({"barcode": item["barcode"], "added_at": item["added_at"],
                             "product": build_public_product(product, user.get("preferences", PREFERENCES))})
    return hydrated


@router.post("/watchlist/{barcode}")
async def watchlist_add(barcode: str, authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    user = await authenticated_user(authorization)
    await db.watchlist.update_one(
        {"user_id": user["id"], "barcode": barcode},
        {"$setOnInsert": {"user_id": user["id"], "barcode": barcode, "added_at": now_iso()}},
        upsert=True,
    )
    return {"status": "saved"}


@router.delete("/watchlist/{barcode}")
async def watchlist_remove(barcode: str, authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    user = await authenticated_user(authorization)
    await db.watchlist.delete_one({"user_id": user["id"], "barcode": barcode})
    return {"status": "removed"}


@router.get("/notifications")
async def notifications(authorization: Optional[str] = Header(default=None)) -> List[Dict[str, Any]]:
    user = await authenticated_user(authorization)
    return await db.notifications.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)


@router.post("/notifications/{notification_id}/read")
async def notification_read(notification_id: str, authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    user = await authenticated_user(authorization)
    await db.notifications.update_one({"id": notification_id, "user_id": user["id"]}, {"$set": {"read": True}})
    return {"status": "ok"}


@router.post("/support")
async def submit_support(payload: SupportRequest, authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization) if authorization else None
    ticket = {
        "id": str(uuid.uuid4()), "user_id": (user or {}).get("id"),
        "user_email": (user or {}).get("email"),
        "guest_id": x_guest_id if not user else None,
        "subject": payload.subject, "message": payload.message,
        "category": payload.category, "status": "open",
        "admin_note": None, "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.support_tickets.insert_one(ticket.copy())
    return {"id": ticket["id"], "status": "open", "created_at": ticket["created_at"]}


@router.get("/support/mine")
async def my_tickets(authorization: Optional[str] = Header(default=None)) -> List[Dict[str, Any]]:
    user = await authenticated_user(authorization)
    return await db.support_tickets.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)


@router.post("/reports")
async def submit_report(payload: ReportRequest, authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization) if authorization else None
    item = {
        "id": str(uuid.uuid4()), "barcode": payload.barcode, "reason": payload.reason,
        "reporter_user_id": (user or {}).get("id"),
        "reporter_guest_id": x_guest_id if not user else None,
        "status": "open", "admin_note": None,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.reports.insert_one(item.copy())
    return {"id": item["id"], "status": "open"}
