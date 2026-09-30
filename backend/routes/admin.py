"""Admin dashboard routes — overview, users, pricing, promocodes, support."""
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.config import db
from core.deps import admin_user, mask_email, now_iso
from core.models import AdminPricingUpdate, AdminPromocode, SupportUpdate, UserSuspendRequest
from core.otp import hash_otp
from emailer import render_admin_reset_link, send_email

router = APIRouter()


@router.get("/admin/overview")
async def admin_overview(_: Dict[str, Any] = Depends(admin_user)) -> Dict[str, int]:
    return {
        "users": await db.users.count_documents({"role": {"$ne": "admin"}}),
        "suspended": await db.users.count_documents({"suspended": True}),
        "open_tickets": await db.support_tickets.count_documents({"status": "open"}),
        "open_reports": await db.reports.count_documents({"status": "open"}),
        "products": await db.products.count_documents({}),
        "contributions_pending": await db.contributions.count_documents({"status": "pending_verification"}),
    }


@router.get("/admin/users")
async def admin_users(_: Dict[str, Any] = Depends(admin_user), q: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"role": {"$ne": "admin"}}
    if q:
        query["email"] = {"$regex": re.escape(q.lower()), "$options": "i"}
    users = await db.users.find(query, {"_id": 0, "password_hash": 0, "preferences": 0}).sort("created_at", -1).to_list(200)
    return [{
        "id": u["id"], "email_masked": mask_email(u["email"]),
        "suspended": u.get("suspended", False),
        "created_at": u.get("created_at"),
        "terms_version": u.get("terms_accepted", {}).get("version"),
    } for u in users]


@router.post("/admin/users/{user_id}/suspend")
async def admin_user_suspend(user_id: str, payload: UserSuspendRequest, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    result = await db.users.update_one({"id": user_id, "role": {"$ne": "admin"}}, {"$set": {"suspended": True, "suspension_reason": payload.reason}})
    if result.matched_count == 0:
        raise HTTPException(404, "User not found")
    return {"status": "suspended"}


@router.post("/admin/users/{user_id}/reactivate")
async def admin_user_reactivate(user_id: str, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    result = await db.users.update_one({"id": user_id}, {"$set": {"suspended": False}, "$unset": {"suspension_reason": ""}})
    if result.matched_count == 0:
        raise HTTPException(404, "User not found")
    return {"status": "active"}


@router.post("/admin/users/{user_id}/send-reset")
async def admin_send_reset(user_id: str, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")
    otp = f"{random.randint(0, 999999):06d}"
    await db.password_resets.update_many(
        {"email": user["email"], "used": {"$ne": True}}, {"$set": {"used": True}},
    )
    await db.password_resets.insert_one({
        "id": str(uuid.uuid4()), "email": user["email"], "otp_hash": hash_otp(otp),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        "created_at": now_iso(), "attempts": 0, "used": False,
    })
    subject, html = render_admin_reset_link(otp, user["email"])
    await send_email(to=user["email"], subject=subject, html=html)
    return {"status": "sent"}


@router.get("/admin/pricing")
async def admin_pricing(_: Dict[str, Any] = Depends(admin_user)) -> List[Dict[str, Any]]:
    return await db.country_pricing.find({}, {"_id": 0}).sort("country", 1).to_list(100)


@router.put("/admin/pricing/{country}")
async def admin_pricing_update(country: str, payload: AdminPricingUpdate, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    doc = payload.model_dump()
    doc["country"] = country.upper()
    await db.country_pricing.replace_one({"country": country.upper()}, doc, upsert=True)
    return {"status": "updated"}


@router.get("/admin/promocodes")
async def admin_promocodes(_: Dict[str, Any] = Depends(admin_user)) -> List[Dict[str, Any]]:
    return await db.promocodes.find({}, {"_id": 0}).sort("code", 1).to_list(200)


@router.post("/admin/promocodes")
async def admin_promocode_create(payload: AdminPromocode, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    if payload.kind not in {"percent", "flat", "free_scans"}:
        raise HTTPException(400, "Invalid promocode kind")
    doc = payload.model_dump()
    doc["code"] = doc["code"].upper()
    doc["redemptions"] = 0
    doc["created_at"] = now_iso()
    try:
        await db.promocodes.insert_one(doc.copy())
    except Exception:  # noqa: BLE001
        raise HTTPException(409, "A promo code with that name already exists")
    return {"status": "created"}


@router.delete("/admin/promocodes/{code}")
async def admin_promocode_delete(code: str, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    result = await db.promocodes.update_one({"code": code.upper()}, {"$set": {"active": False}})
    if result.matched_count == 0:
        raise HTTPException(404, "Promo code not found")
    return {"status": "deactivated"}


@router.get("/admin/support")
async def admin_support(_: Dict[str, Any] = Depends(admin_user), status: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    tickets = await db.support_tickets.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    for ticket in tickets:
        if ticket.get("user_email"):
            ticket["user_email"] = mask_email(ticket["user_email"])
    return tickets


@router.put("/admin/support/{ticket_id}")
async def admin_support_update(ticket_id: str, payload: SupportUpdate, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    if payload.status not in {"open", "in_progress", "resolved", "closed"}:
        raise HTTPException(400, "Invalid status")
    result = await db.support_tickets.update_one({"id": ticket_id}, {"$set": {
        "status": payload.status, "admin_note": payload.admin_note, "updated_at": now_iso(),
    }})
    if result.matched_count == 0:
        raise HTTPException(404, "Ticket not found")
    return {"status": "updated"}


@router.get("/admin/reports")
async def admin_reports(_: Dict[str, Any] = Depends(admin_user), status: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    return await db.reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.put("/admin/reports/{report_id}")
async def admin_report_update(report_id: str, payload: SupportUpdate, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    if payload.status not in {"open", "in_progress", "resolved", "closed"}:
        raise HTTPException(400, "Invalid status")
    result = await db.reports.update_one({"id": report_id}, {"$set": {
        "status": payload.status, "admin_note": payload.admin_note, "updated_at": now_iso(),
    }})
    if result.matched_count == 0:
        raise HTTPException(404, "Report not found")
    return {"status": "updated"}


@router.get("/admin/contributions")
async def admin_contributions(_: Dict[str, Any] = Depends(admin_user), status: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    items = await db.contributions.find(query, {"_id": 0, "images": 0}).sort("created_at", -1).to_list(100)
    return items
