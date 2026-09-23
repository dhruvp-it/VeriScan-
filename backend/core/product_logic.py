"""Product lookup, badge detection, OCR extraction, and watchlist alerts."""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from emergentintegrations.llm.chat import ImageContent, LlmChat, UserMessage

from core.config import EMERGENT_LLM_KEY, db
from core.deps import now_iso
from emailer import render_watchlist_alert, send_email
from ingredients_db import build_public_product, overall_score, parse_ingredients

logger = logging.getLogger(__name__)


def _nutrition_from_off(nutriments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(nutriments, dict) or not nutriments:
        return None
    def num(key: str) -> Optional[float]:
        value = nutriments.get(f"{key}_100g")
        try:
            return round(float(value), 2) if value is not None else None
        except (TypeError, ValueError):
            return None
    out = {
        "energy_kcal": num("energy-kcal") or num("energy"),
        "protein_g": num("proteins"), "carbohydrates_g": num("carbohydrates"),
        "sugars_g": num("sugars"), "fat_g": num("fat"),
        "saturated_fat_g": num("saturated-fat"), "fiber_g": num("fiber"), "salt_g": num("salt"),
    }
    return out if any(v is not None for v in out.values()) else None


def _dietary_type_from_off(product: Dict[str, Any]) -> str:
    labels = " ".join([str(product.get("labels", "")), str(product.get("labels_tags", "")),
                       str(product.get("categories", ""))]).lower()
    if "vegan" in labels:
        return "vegan"
    if "vegetarian" in labels:
        return "vegetarian"
    if any(word in labels for word in ("meat", "chicken", "beef", "pork", "fish")):
        return "non_vegetarian"
    return "not_applicable"


# Regulatory badge detection
BADGE_MATCHERS: List[Dict[str, Any]] = [
    {"id": "fssai", "label": "FSSAI Approved", "region": "IN", "keywords": ["fssai"]},
    {"id": "green_dot", "label": "Vegetarian (Green Dot)", "region": "IN", "keywords": ["green dot", "green-dot", "vegetarian"]},
    {"id": "brown_triangle", "label": "Non-Vegetarian (Brown Triangle)", "region": "IN", "keywords": ["brown triangle", "brown-triangle", "non-vegetarian", "non-veg"]},
    {"id": "fda", "label": "US FDA Registered", "region": "US", "keywords": ["fda", "u.s. food and drug", "us food and drug"]},
    {"id": "usda_organic", "label": "USDA Organic", "region": "US", "keywords": ["usda organic", "usda-organic"]},
    {"id": "eu_bio", "label": "EU Organic Bio", "region": "EU", "keywords": ["eu-organic", "eu organic", "european-organic", "bio-europeen"]},
    {"id": "peta", "label": "PETA Cruelty-Free", "region": "GLOBAL", "keywords": ["peta", "cruelty-free"]},
    {"id": "leaping_bunny", "label": "Leaping Bunny", "region": "GLOBAL", "keywords": ["leaping-bunny", "leaping bunny"]},
    {"id": "vegan_society", "label": "Vegan Society", "region": "GLOBAL", "keywords": ["vegan-society", "vegan society", "vegan.svg"]},
    {"id": "trustified", "label": "Trustified", "region": "GLOBAL", "keywords": ["trustified"]},
    {"id": "informed_sport", "label": "Informed Sport", "region": "GLOBAL", "keywords": ["informed-sport", "informed sport", "informed choice"]},
    {"id": "kosher", "label": "Kosher", "region": "GLOBAL", "keywords": ["kosher"]},
    {"id": "halal", "label": "Halal", "region": "GLOBAL", "keywords": ["halal"]},
    {"id": "gluten_free", "label": "Gluten-Free Certified", "region": "GLOBAL", "keywords": ["gluten-free", "gluten free"]},
    {"id": "non_gmo", "label": "Non-GMO Project", "region": "GLOBAL", "keywords": ["non-gmo", "non gmo"]},
]


def detect_badges(product: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return regulatory / certification badges detected from labels + any manual admin overrides."""
    haystack = " ".join([
        str(product.get("labels", "")), str(product.get("labels_tags", "")),
        str(product.get("certifications", "")), str(product.get("ingredients_text", "")),
        str(product.get("origin_country", "")).lower(),
    ]).lower()
    if isinstance(product.get("labels"), list):
        haystack += " " + " ".join(str(x).lower() for x in product["labels"])
    detected: List[Dict[str, str]] = []
    seen: set[str] = set()
    for matcher in BADGE_MATCHERS:
        if any(kw in haystack for kw in matcher["keywords"]):
            if matcher["id"] not in seen:
                detected.append({"id": matcher["id"], "label": matcher["label"], "region": matcher["region"]})
                seen.add(matcher["id"])
    # Green Dot / Brown Triangle inferred from dietary_type for Indian products if not explicit
    origin = str(product.get("origin_country", "")).lower()
    dietary = str(product.get("dietary_type", "")).lower()
    if "india" in origin:
        if dietary in ("vegan", "vegetarian") and "green_dot" not in seen:
            detected.append({"id": "green_dot", "label": "Vegetarian (Green Dot)", "region": "IN"})
        elif dietary == "non_vegetarian" and "brown_triangle" not in seen:
            detected.append({"id": "brown_triangle", "label": "Non-Vegetarian (Brown Triangle)", "region": "IN"})
    # Manual admin override: product.badges_override overrides detection completely
    if isinstance(product.get("badges_override"), list) and product["badges_override"]:
        return product["badges_override"]
    # Manual admin additions
    if isinstance(product.get("badges_extra"), list):
        for extra in product["badges_extra"]:
            if isinstance(extra, dict) and extra.get("id") and extra.get("label"):
                if extra["id"] not in seen:
                    detected.append({"id": extra["id"], "label": extra["label"], "region": extra.get("region", "GLOBAL")})
                    seen.add(extra["id"])
    return detected


def remote_lookup(barcode: str) -> Optional[Dict[str, Any]]:
    endpoints = [
        ("https://world.openfoodfacts.org/api/v2/product/", "food"),
        ("https://world.openbeautyfacts.org/api/v2/product/", "personal_care"),
    ]
    for endpoint, category in endpoints:
        try:
            response = requests.get(f"{endpoint}{barcode}.json", timeout=6,
                                    headers={"User-Agent": "VeriScan/1.0 (support@veriscan.app)"})
            data = response.json()
            if data.get("status") != 1:
                continue
            product = data.get("product", {})
            ingredients_text = product.get("ingredients_text_en") or product.get("ingredients_text") or ""
            labels_tags = product.get("labels_tags", []) or []
            image = product.get("image_front_url") or product.get("image_url")
            record = {
                "id": f"online-{barcode}", "barcode": barcode,
                "name": product.get("product_name") or product.get("generic_name") or "Scanned product",
                "brand": (product.get("brands") or "Public registry").split(",")[0].strip(),
                "category": category,
                "description": product.get("generic_name") or "Details sourced from the public product registry.",
                "dietary_type": _dietary_type_from_off(product),
                "origin_country": (product.get("countries") or "Global").split(",")[0].strip(),
                "manufactured_in": (product.get("manufacturing_places") or product.get("countries") or "Registry listing").split(",")[0].strip(),
                "first_detected_year": datetime.now(timezone.utc).year,
                "price_tier": "affordable", "target_age_group": "Adults",
                "primary_region": (product.get("countries") or "Global").split(",")[0].strip(),
                "serving_size": product.get("serving_size") or product.get("quantity") or "See label",
                "price_inr": 0, "image_url": image,
                "labels": [tag.replace("en:", "").replace("-", " ") for tag in labels_tags[:6]],
                "ingredients_text": ingredients_text,
                "nutrition_per_100g": _nutrition_from_off(product.get("nutriments", {})),
                "retailers": [],
            }
            record["ingredients"] = parse_ingredients(ingredients_text)
            return record
        except (requests.RequestException, ValueError, TypeError) as exc:
            logger.info("Remote lookup failed for %s: %s", endpoint, exc)
            continue
    return None


async def alternatives_for(product: Dict[str, Any], preferences: Dict[str, List[str]], limit: int = 3) -> List[Dict[str, Any]]:
    threshold = product.get("overall_health_score", 60)
    cursor = db.products.find(
        {"category": product.get("category"), "barcode": {"$ne": product.get("barcode")}},
        {"_id": 0},
    ).limit(30)
    candidates = []
    async for candidate in cursor:
        scored = build_public_product(candidate, preferences)
        if scored["overall_health_score"] > threshold:
            candidates.append(scored)
    candidates.sort(key=lambda item: (item["overall_health_score"], item["personal_match"]), reverse=True)
    return candidates[:limit]


async def maybe_notify_watchlist(new_product: Dict[str, Any]) -> None:
    """When a new product is added, alert any user watching a similar-category
    product with a lower safety score."""
    barcodes = await db.watchlist.distinct("barcode")
    if not barcodes:
        return
    for barcode in barcodes:
        watched = await db.products.find_one({"barcode": barcode}, {"_id": 0})
        if not watched:
            continue
        if watched.get("category") != new_product.get("category"):
            continue
        old_score = overall_score(watched.get("ingredients", []))
        new_score = overall_score(new_product.get("ingredients", []))
        if new_score <= old_score + 5:
            continue
        watchers = db.watchlist.find({"barcode": barcode}, {"_id": 0})
        async for entry in watchers:
            user = await db.users.find_one({"id": entry["user_id"]}, {"_id": 0})
            if not user or user.get("suspended"):
                continue
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "user_id": user["id"],
                "kind": "watchlist_alt",
                "title": f"A cleaner {new_product.get('category', 'product').replace('_', ' ')} landed",
                "body": f"{new_product['name']} scores {int(new_score)}/100 — better than your saved {watched['name']}.",
                "product_barcode": new_product.get("barcode"),
                "read": False, "created_at": now_iso(),
            })
            subject, html = render_watchlist_alert(watched["name"], new_product["name"], int(new_score))
            await send_email(to=user["email"], subject=subject, html=html)


async def extract_product_from_images(images_base64: List[str]) -> Dict[str, Any]:
    """Send up to 5 label images to Claude and parse structured JSON."""
    limited = images_base64[:5]
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"veriscan-ocr-{uuid.uuid4()}",
        system_message=(
            "You extract product-label data from mobile phone photos of packaged food, "
            "supplements and personal-care products. Read the label text carefully. "
            "Return ONLY minified JSON with the schema: {\"ingredients_text\": string (comma separated as printed), "
            "\"nutrition_per_100g\": {\"energy_kcal\": number|null, \"protein_g\": number|null, "
            "\"carbohydrates_g\": number|null, \"sugars_g\": number|null, \"fat_g\": number|null, "
            "\"saturated_fat_g\": number|null, \"fiber_g\": number|null, \"salt_g\": number|null}, "
            "\"dietary_type\": one of 'vegan'|'vegetarian'|'non_vegetarian'|'not_applicable', "
            "\"certifications\": string[]}. If a field can't be read, return null (or empty)."
        ),
    ).with_model("anthropic", "claude-sonnet-4-6")
    contents = [ImageContent(image_base64=img) for img in limited if img]
    message = UserMessage(
        text="Extract the label data from these product photos and return JSON only.",
        file_contents=contents,
    )
    full = ""
    from emergentintegrations.llm.chat import StreamDone, TextDelta
    async for event in chat.stream_message(message):
        if isinstance(event, TextDelta):
            full += event.content
        elif isinstance(event, StreamDone):
            break
    # Robustly extract the first JSON object
    import re as _re
    match = _re.search(r"\{[\s\S]*\}", full)
    if not match:
        raise RuntimeError("Model returned no JSON")
    return json.loads(match.group(0))
