"""Product lookup, alternatives, history, contributions, and price comparison."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException

from core.config import PREFERENCES, db
from core.deps import authenticated_user, consume_scan, now_iso
from core.models import ContributionRequest
from core.product_logic import (
    alternatives_for, detect_badges, extract_product_from_images,
    maybe_notify_watchlist, remote_lookup,
)
from ingredients_db import build_public_product, parse_ingredients
from price_comparison import compare_for
from routes.analytics import record as record_analytics

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/products/lookup")
async def lookup_product(
    barcode: str,
    authorization: Optional[str] = Header(default=None),
    x_guest_id: Optional[str] = Header(default=None),
    x_country: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user = await authenticated_user(authorization) if authorization else None
    product = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    if not product:
        product = remote_lookup(barcode)
        if product:
            await db.products.update_one({"barcode": barcode}, {"$set": product}, upsert=True)
            await maybe_notify_watchlist(product)
    if not product:
        raise HTTPException(404, detail={"message": "Product not found", "barcode": barcode})
    # Countries other than IN are free for now (admin can enable pricing later
    # via the country_pricing collection). Any country whose row has any positive
    # price still charges scans.
    country = (x_country or "IN").upper()
    pricing = await db.country_pricing.find_one({"country": country}, {"_id": 0})
    country_priced = bool(pricing and (pricing.get("scan_intro", 0) > 0 or pricing.get("monthly", 0) > 0))
    if country != "IN" and not country_priced:
        consumed = {"remaining": None, "source": "region_free"}
    else:
        consumed = await consume_scan(x_guest_id, user)
    if user:
        preferences = user.get("preferences", PREFERENCES)
    elif x_guest_id:
        guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) or {}
        preferences = guest.get("preferences", PREFERENCES)
    else:
        preferences = PREFERENCES
    result = build_public_product(product, preferences)
    result["badges"] = detect_badges(product)
    result["scan"] = consumed
    history_user = user["id"] if user else f"guest:{x_guest_id}"
    await db.history.insert_one({"id": str(uuid.uuid4()), "user_id": history_user,
                                  "product": result, "scanned_at": now_iso()})
    # Anonymous analytics — no user id / email / device id is stored
    await record_analytics("scan", barcode=barcode, category=result.get("category"), country=country)
    return result


@router.get("/products/alternatives")
async def product_alternatives(barcode: str, authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> List[Dict[str, Any]]:
    product = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    if not product:
        return []
    if authorization:
        user = await authenticated_user(authorization)
        preferences = user.get("preferences", PREFERENCES)
    elif x_guest_id:
        guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) or {}
        preferences = guest.get("preferences", PREFERENCES)
    else:
        preferences = PREFERENCES
    scored_product = build_public_product(product, preferences)
    alternatives = await alternatives_for(scored_product, preferences)
    for alt in alternatives:
        # rebuild badge list per alternative
        raw = await db.products.find_one({"barcode": alt["barcode"]}, {"_id": 0})
        if raw:
            alt["badges"] = detect_badges(raw)
    return alternatives


@router.get("/products/compare")
async def product_compare(barcode: str) -> Dict[str, Any]:
    """Hybrid price comparison: live prices when provider keys are configured,
    plus category-routed retailer search deep-links that always work."""
    product = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Product not found")
    return await compare_for(product, db)


@router.get("/history")
async def history(authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> List[Dict[str, Any]]:
    user = await authenticated_user(authorization) if authorization else None
    owner = user["id"] if user else f"guest:{x_guest_id}"
    return await db.history.find({"user_id": owner}, {"_id": 0}).sort("scanned_at", -1).to_list(30)


@router.post("/contributions")
async def contribution(payload: ContributionRequest, authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Free — no scan deducted. Runs OCR on submitted photos, builds a fully-
    scored product, saves it as `user_contributed` (pending admin verification)
    so the contributor sees an immediate ingredient report."""
    from core.config import EMERGENT_LLM_KEY

    user = await authenticated_user(authorization) if authorization else None
    parsed_ingredients: List[Dict[str, Any]] = []
    ingredients_text = ""
    nutrition: Optional[Dict[str, Any]] = None
    dietary_type = "not_applicable"
    certifications: List[str] = []
    ocr_error: Optional[str] = None
    if payload.images and EMERGENT_LLM_KEY:
        try:
            structured = await extract_product_from_images(payload.images)
            ingredients_text = structured.get("ingredients_text", "") or ""
            parsed_ingredients = parse_ingredients(ingredients_text)
            nutrition = structured.get("nutrition_per_100g") or None
            dietary_type = structured.get("dietary_type") or "not_applicable"
            if isinstance(structured.get("certifications"), list):
                certifications = [str(c) for c in structured["certifications"] if c]
        except Exception as exc:  # noqa: BLE001
            logger.error("OCR extraction failed: %s", exc)
            ocr_error = str(exc)
    contribution_id = str(uuid.uuid4())
    submitted_by = (user or {}).get("id", f"guest:{x_guest_id}")

    # Save the contribution record (audit + admin queue)
    contribution_doc = {
        "id": contribution_id, "barcode": payload.barcode,
        "product_name": payload.product_name, "brand": payload.brand,
        "notes": payload.notes, "images": payload.images,
        "extracted": {
            "ingredients_text": ingredients_text, "ingredients": parsed_ingredients,
            "nutrition_per_100g": nutrition, "dietary_type": dietary_type,
            "certifications": certifications,
        },
        "status": "pending_verification",
        "submitted_by": submitted_by, "created_at": now_iso(),
    }
    await db.contributions.insert_one(contribution_doc.copy())

    # Build a fully-analysed product record right away — no scan deducted
    product_doc = {
        "id": f"community-{payload.barcode}", "barcode": payload.barcode,
        "name": (payload.product_name or "Community-added product").strip(),
        "brand": (payload.brand or "Community").strip(),
        "category": "food", "description": payload.notes or "Added by a community contributor. Pending verification.",
        "dietary_type": dietary_type,
        "origin_country": "Unknown", "manufactured_in": "Unknown",
        "first_detected_year": datetime.now(timezone.utc).year,
        "price_tier": "affordable", "target_age_group": "Adults",
        "primary_region": "Global", "serving_size": "See label",
        "price_inr": 0, "image_url": None,
        "labels": certifications,
        "certifications": certifications,
        "ingredients_text": ingredients_text,
        "ingredients": parsed_ingredients,
        "nutrition_per_100g": nutrition,
        "retailers": [],
        "source": "community", "contribution_id": contribution_id,
        "status": "pending_verification",
    }
    # Only save if we actually extracted ingredients (otherwise it's a stub)
    if parsed_ingredients:
        await db.products.update_one({"barcode": payload.barcode}, {"$setOnInsert": product_doc}, upsert=True)

    # Return the analyzed product to the client
    preferences = (user or {}).get("preferences", PREFERENCES)
    if not user and x_guest_id:
        guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) or {}
        preferences = guest.get("preferences", PREFERENCES)
    analyzed = build_public_product(product_doc, preferences) if parsed_ingredients else None
    if analyzed:
        analyzed["badges"] = detect_badges(product_doc)
        analyzed["scan"] = {"remaining": None, "source": "first_time_free"}
        # Record in history so it shows up on the History tab
        await db.history.insert_one({"id": str(uuid.uuid4()), "user_id": submitted_by,
                                      "product": analyzed, "scanned_at": now_iso()})
    return {
        "contribution_id": contribution_id, "status": "pending_verification",
        "product": analyzed, "ocr_error": ocr_error,
    }
