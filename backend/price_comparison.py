"""Live e-commerce price comparison (hybrid).

Tier 1 (always on): retailer search deep-links, category-routed. Zero API keys
required and always works — opens the retailer's search page for the product.

Tier 2 (optional): live prices via the QuickCommerce API (Amazon / Flipkart /
Nykaa) and Apify actors (Tata 1mg / HealthKart) when API keys are configured
in .env. Results are cached in MongoDB for 15 minutes to conserve provider
credits and absorb provider outages.
"""
import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)

QUICKCOMMERCE_API_KEY = os.environ.get("QUICKCOMMERCE_API_KEY", "")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
APIFY_1MG_ACTOR = os.environ.get("APIFY_1MG_ACTOR", "matrix-crawl/1mg-scraper")
APIFY_HEALTHKART_ACTOR = os.environ.get("APIFY_HEALTHKART_ACTOR", "")
QC_BASE = "https://api.quickcommerceapi.com"
CACHE_TTL_SECONDS = 15 * 60

RETAILERS: List[Dict[str, Any]] = [
    {"id": "amazon", "name": "Amazon India", "icon": "cart-outline", "color": "#FF9900",
     "categories": ["food", "personal_care", "supplement"],
     "search": "https://www.amazon.in/s?k={q}", "live": "quickcommerce", "qc_platform": "Amazon"},
    {"id": "flipkart", "name": "Flipkart", "icon": "storefront-outline", "color": "#2874F0",
     "categories": ["food", "personal_care", "supplement"],
     "search": "https://www.flipkart.com/search?q={q}", "live": "quickcommerce", "qc_platform": "Flipkart"},
    {"id": "blinkit", "name": "Blinkit", "icon": "flash-outline", "color": "#E0A800",
     "categories": ["food", "personal_care"],
     "search": "https://blinkit.com/s/?q={q}", "live": None},
    {"id": "zepto", "name": "Zepto", "icon": "bicycle-outline", "color": "#5B21B6",
     "categories": ["food", "personal_care"],
     "search": "https://www.zeptonow.com/search?query={q}", "live": None},
    {"id": "nykaa", "name": "Nykaa", "icon": "color-palette-outline", "color": "#FC2779",
     "categories": ["personal_care"],
     "search": "https://www.nykaa.com/search/result/?q={q}", "live": "quickcommerce", "qc_platform": "Nykaa"},
    {"id": "1mg", "name": "Tata 1mg", "icon": "medkit-outline", "color": "#FF6F61",
     "categories": ["supplement"],
     "search": "https://www.1mg.com/search/all?name={q}", "live": "apify"},
    {"id": "healthkart", "name": "HealthKart", "icon": "fitness-outline", "color": "#00A896",
     "categories": ["supplement"],
     "search": "https://www.healthkart.com/search?text={q}", "live": "apify"},
]


def deep_links(name: str, brand: str, category: str) -> List[Dict[str, Any]]:
    """Category-routed retailer search links — always available."""
    query = quote_plus(" ".join(part for part in (brand, name) if part).strip())
    links: List[Dict[str, Any]] = []
    for retailer in RETAILERS:
        if category in retailer["categories"]:
            links.append({
                "id": retailer["id"], "name": retailer["name"], "icon": retailer["icon"],
                "color": retailer["color"], "url": retailer["search"].format(q=query),
            })
    return links


def _to_number(*values: Any) -> Optional[float]:
    for value in values:
        if value is None:
            continue
        try:
            return float(str(value).replace(",", "").replace("₹", "").replace("Rs.", "").strip())
        except (TypeError, ValueError):
            continue
    return None


def _normalize(raw: Dict[str, Any], retailer_name: str) -> Optional[Dict[str, Any]]:
    """Map provider-specific JSON onto the common product shape. Never invent a price."""
    title = raw.get("name") or raw.get("title") or raw.get("product_name")
    url = raw.get("deeplink") or raw.get("url") or raw.get("product_url") or raw.get("link")
    if not title or not url:
        return None
    image = raw.get("image") or raw.get("image_url") or raw.get("thumbnail")
    if not image and isinstance(raw.get("images"), list) and raw["images"]:
        image = raw["images"][0]
    return {
        "retailer": retailer_name, "title": str(title)[:140], "url": str(url),
        "price_inr": _to_number(raw.get("offer_price"), raw.get("price"), raw.get("selling_price"), raw.get("sale_price")),
        "mrp_inr": _to_number(raw.get("mrp"), raw.get("list_price"), raw.get("original_price")),
        "image": image, "rating": _to_number(raw.get("rating"), raw.get("stars")),
        "available": raw.get("available", raw.get("inStock", raw.get("in_stock"))),
    }


async def _quickcommerce(query: str, platform: str) -> List[Dict[str, Any]]:
    if not QUICKCOMMERCE_API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                f"{QC_BASE}/v1/search",
                params={"q": query, "platform": platform},
                headers={"X-API-Key": QUICKCOMMERCE_API_KEY},
            )
            response.raise_for_status()
            body = response.json()
        rows = (body.get("data") or {}).get("products") or body.get("products") or []
        return [p for raw in rows[:8] if isinstance(raw, dict) and (p := _normalize(raw, platform))]
    except Exception as exc:  # noqa: BLE001 — provider must never break the app
        logger.info("QuickCommerce search failed for %s: %s", platform, exc)
        return []


async def _apify(query: str, actor: str, retailer_name: str) -> List[Dict[str, Any]]:
    if not APIFY_TOKEN or not actor:
        return []
    try:
        endpoint = f"https://api.apify.com/v2/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items"
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                endpoint, params={"token": APIFY_TOKEN},
                json={"searchQueries": [query], "maxItems": 8},
            )
            response.raise_for_status()
            rows = response.json()
        return [p for raw in rows[:8] if isinstance(raw, dict) and (p := _normalize(raw, retailer_name))]
    except Exception as exc:  # noqa: BLE001
        logger.info("Apify search failed for %s: %s", retailer_name, exc)
        return []


async def live_prices(query: str, category: str) -> List[Dict[str, Any]]:
    """Query every live-capable retailer relevant to the category, concurrently."""
    tasks = []
    for retailer in RETAILERS:
        if category not in retailer["categories"] or not retailer.get("live"):
            continue
        if retailer["live"] == "quickcommerce":
            tasks.append(_quickcommerce(query, retailer["qc_platform"]))
        elif retailer["live"] == "apify":
            actor = APIFY_1MG_ACTOR if retailer["id"] == "1mg" else APIFY_HEALTHKART_ACTOR
            tasks.append(_apify(query, actor, retailer["name"]))
    if not tasks:
        return []
    results = await asyncio.gather(*tasks, return_exceptions=True)
    products = [p for group in results if isinstance(group, list) for p in group]
    priced = [p for p in products if p.get("price_inr") is not None]
    return priced or products


async def compare_for(product: Dict[str, Any], db: Any) -> Dict[str, Any]:
    """Build the hybrid comparison payload for a product record."""
    name = str(product.get("name") or "").strip()
    brand = str(product.get("brand") or "").strip()
    category = str(product.get("category") or "food")
    query = " ".join(part for part in (brand, name) if part).strip() or name
    links = deep_links(name, brand, category)
    live_enabled = bool(QUICKCOMMERCE_API_KEY or APIFY_TOKEN)
    products: List[Dict[str, Any]] = []
    if live_enabled and query:
        cache_key = f"{category}:{query.lower()}"
        cached = await db.price_cache.find_one({"cache_key": cache_key}, {"_id": 0})
        if cached and time.time() - cached.get("fetched_at", 0) < CACHE_TTL_SECONDS:
            products = cached.get("products", [])
        else:
            products = await live_prices(query, category)
            await db.price_cache.update_one(
                {"cache_key": cache_key},
                {"$set": {"cache_key": cache_key, "products": products, "fetched_at": time.time()}},
                upsert=True,
            )
    return {
        "query": query, "live_enabled": live_enabled, "fetched_at": time.time(),
        "products": products, "deep_links": links,
    }
