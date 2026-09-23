"""VeriScan FastAPI backend — auth, products, admin, watchlist, support, OCR."""
import base64
import hashlib
import hmac
import json
import logging
import os
import random
import secrets
import string
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
import razorpay
import requests
import stripe
from dotenv import load_dotenv
from emergentintegrations.llm.chat import ImageContent, LlmChat, UserMessage
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from emailer import (
    render_admin_reset_link, render_otp_email, render_watchlist_alert, send_email,
)
from ingredients_db import (
    build_public_product, overall_score, parse_ingredients, personalized_match,
)
from legal_content import (
    EFFECTIVE_DATE, PRIVACY_POLICY, PRIVACY_VERSION, TERMS_OF_SERVICE, TERMS_VERSION,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
JWT_SECRET = os.environ.get("JWT_SECRET", "veriscan-local-development-secret")
TOKEN_ALGORITHM = "HS256"
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
ADMIN_SEED_EMAIL = os.environ.get("ADMIN_SEED_EMAIL", "admin@veriscan.app").strip().lower()
ADMIN_SEED_PASSWORD = os.environ.get("ADMIN_SEED_PASSWORD", "changeme-strong")

app = FastAPI(title="VeriScan API")
api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

PREFERENCES: Dict[str, List[str]] = {"dietary": [], "targets": [], "sensitivities": []}

DEFAULT_COUNTRY_PRICING = [
    # Base rates in INR; other currencies use approximate PPP multipliers
    {"country": "IN", "currency": "INR", "symbol": "₹",
     "scan_intro": 5, "scan_standard": 15, "monthly": 72, "yearly": 450,
     "monthly_regular": 180, "yearly_regular": 1500, "provider": "razorpay"},
    {"country": "US", "currency": "USD", "symbol": "$",
     "scan_intro": 0.15, "scan_standard": 0.45, "monthly": 1.99, "yearly": 12.99,
     "monthly_regular": 4.99, "yearly_regular": 39.99, "provider": "stripe"},
    {"country": "CA", "currency": "CAD", "symbol": "CA$",
     "scan_intro": 0.19, "scan_standard": 0.59, "monthly": 2.49, "yearly": 16.99,
     "monthly_regular": 5.99, "yearly_regular": 49.99, "provider": "stripe"},
    {"country": "EU", "currency": "EUR", "symbol": "€",
     "scan_intro": 0.15, "scan_standard": 0.45, "monthly": 1.99, "yearly": 12.99,
     "monthly_regular": 4.49, "yearly_regular": 34.99, "provider": "stripe"},
    {"country": "GB", "currency": "GBP", "symbol": "£",
     "scan_intro": 0.12, "scan_standard": 0.39, "monthly": 1.79, "yearly": 10.99,
     "monthly_regular": 3.99, "yearly_regular": 29.99, "provider": "stripe"},
    {"country": "AE", "currency": "AED", "symbol": "د.إ",
     "scan_intro": 0.60, "scan_standard": 1.80, "monthly": 7.99, "yearly": 49.99,
     "monthly_regular": 19.99, "yearly_regular": 149.99, "provider": "stripe"},
    {"country": "AU", "currency": "AUD", "symbol": "A$",
     "scan_intro": 0.22, "scan_standard": 0.69, "monthly": 2.99, "yearly": 18.99,
     "monthly_regular": 6.99, "yearly_regular": 54.99, "provider": "stripe"},
    {"country": "NZ", "currency": "NZD", "symbol": "NZ$",
     "scan_intro": 0.25, "scan_standard": 0.79, "monthly": 3.49, "yearly": 21.99,
     "monthly_regular": 7.99, "yearly_regular": 59.99, "provider": "stripe"},
]

SEEDED_PRODUCTS = [
    {
        "id": "seed-oats-001", "barcode": "8901030895001", "name": "Organic Rolled Oats",
        "brand": "Harvest Table", "category": "food",
        "description": "Whole grain oats for a simple, nourishing breakfast.",
        "dietary_type": "vegan", "origin_country": "India", "manufactured_in": "Pune, India",
        "first_detected_year": 2024, "price_tier": "affordable", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "500 g", "price_inr": 249, "image_url": None,
        "nutrition_per_100g": {"energy_kcal": 379, "protein_g": 13.2, "carbohydrates_g": 67.7, "sugars_g": 1.0,
                                "fat_g": 6.5, "saturated_fat_g": 1.1, "fiber_g": 10.1, "salt_g": 0.02},
        "ingredients_text": "Whole grain rolled oats, Vitamin E (tocopherol).",
        "labels": ["vegan", "whole grain"],
        "retailers": [
            {"name": "Nature's Basket", "price": 249, "url": "https://www.naturesbasket.co.in/"},
            {"name": "BigBasket", "price": 239, "url": "https://www.bigbasket.com/"},
        ],
    },
    {
        "id": "seed-cleanser-001", "barcode": "8906087771204", "name": "Calm Barrier Cleanser",
        "brand": "Moss & Mineral", "category": "personal_care",
        "description": "A fragrance-free daily cleanser designed for sensitive skin.",
        "dietary_type": "not_applicable", "origin_country": "India", "manufactured_in": "Bengaluru, India",
        "first_detected_year": 2023, "price_tier": "premium", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "150 ml", "price_inr": 695, "image_url": None,
        "nutrition_per_100g": None,
        "ingredients_text": "Aqua, Glycerin, Sodium Laureth Sulfate, Panthenol, Phenoxyethanol, Fragrance.",
        "labels": [],
        "retailers": [
            {"name": "Nykaa", "price": 695, "url": "https://www.nykaa.com/"},
            {"name": "Tata 1mg", "price": 679, "url": "https://www.1mg.com/"},
        ],
    },
    {
        "id": "seed-protein-001", "barcode": "8908001234567", "name": "Plant Protein Vanilla",
        "brand": "Good Ground", "category": "supplement",
        "description": "Pea and brown rice protein with a lightly sweet vanilla finish.",
        "dietary_type": "vegan", "origin_country": "India", "manufactured_in": "Hyderabad, India",
        "first_detected_year": 2024, "price_tier": "high", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "500 g", "price_inr": 1299, "image_url": None,
        "nutrition_per_100g": {"energy_kcal": 380, "protein_g": 78.0, "carbohydrates_g": 5.0, "sugars_g": 1.5,
                                "fat_g": 4.0, "saturated_fat_g": 1.0, "fiber_g": 4.0, "salt_g": 0.3},
        "ingredients_text": "Pea protein isolate, Brown rice protein, Natural vanilla flavor, Stevia extract, Xanthan gum.",
        "labels": ["vegan", "gluten-free"],
        "retailers": [
            {"name": "Amazon India", "price": 1299, "url": "https://www.amazon.in/"},
            {"name": "HealthKart", "price": 1199, "url": "https://www.healthkart.com/"},
        ],
    },
    {
        "id": "seed-oats-002", "barcode": "8901030895002", "name": "Steel-Cut Whole Oats",
        "brand": "Field & Grain", "category": "food",
        "description": "Minimally-processed steel-cut oats with a nutty bite.",
        "dietary_type": "vegan", "origin_country": "India", "manufactured_in": "Pune, India",
        "first_detected_year": 2025, "price_tier": "affordable", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "500 g", "price_inr": 289, "image_url": None,
        "nutrition_per_100g": {"energy_kcal": 375, "protein_g": 14.0, "carbohydrates_g": 62.0, "sugars_g": 0.6,
                                "fat_g": 6.0, "saturated_fat_g": 1.0, "fiber_g": 12.0, "salt_g": 0.01},
        "ingredients_text": "Organic whole grain steel-cut oats.",
        "labels": ["organic", "vegan", "whole grain"],
        "retailers": [{"name": "BigBasket", "price": 289, "url": "https://www.bigbasket.com/"}],
    },
]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class AuthRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    accepted_terms_version: Optional[str] = None
    accepted_privacy_version: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileRequest(BaseModel):
    dietary: List[str] = []
    targets: List[str] = []
    sensitivities: List[str] = []


class ContributionRequest(BaseModel):
    barcode: str
    product_name: Optional[str] = None
    brand: Optional[str] = None
    notes: Optional[str] = None
    images: List[str] = []


class ScanPurchase(BaseModel):
    quantity: int = Field(ge=1, le=100)
    tier: str


class SubscriptionPurchase(BaseModel):
    plan: str
    country: Optional[str] = None


class SupportRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=140)
    message: str = Field(min_length=5, max_length=4000)
    category: str = Field(default="general")


class ReportRequest(BaseModel):
    barcode: str
    reason: str = Field(min_length=5, max_length=1000)


class PasswordResetStart(BaseModel):
    email: str


class PasswordResetComplete(BaseModel):
    email: str
    otp: str
    new_password: str = Field(min_length=6)


class AdminPricingUpdate(BaseModel):
    country: str
    currency: str
    symbol: str
    scan_intro: float
    scan_standard: float
    monthly: float
    yearly: float
    monthly_regular: float
    yearly_regular: float
    provider: str


class AdminPromocode(BaseModel):
    code: str = Field(min_length=3, max_length=32)
    kind: str  # 'percent' | 'flat' | 'free_scans'
    value: float
    max_redemptions: int = 100
    countries: List[str] = []
    expires_at: Optional[str] = None
    active: bool = True


class SupportUpdate(BaseModel):
    status: str  # 'open' | 'in_progress' | 'resolved' | 'closed'
    admin_note: Optional[str] = None


class UserSuspendRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=280)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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
        if entitlement.get("subscribed"):
            return {"remaining": None, "source": "subscription"}
        if entitlement.get("free_used", 0) < 5:
            await db.entitlements.update_one({"user_id": user["id"]}, {"$inc": {"free_used": 1}})
            return {"remaining": 4 - entitlement.get("free_used", 0), "source": "monthly_free"}
        if entitlement.get("purchased_balance", 0) > 0:
            await db.entitlements.update_one({"user_id": user["id"]}, {"$inc": {"purchased_balance": -1}})
            return {"remaining": entitlement.get("purchased_balance", 0) - 1, "source": "wallet"}
        raise HTTPException(402, "Monthly scans are used. Add credits or subscribe to continue.")
    if not guest_id:
        raise HTTPException(400, "Guest identifier required")
    guest = await db.guests.find_one({"guest_id": guest_id}, {"_id": 0})
    used = guest.get("used", 0) if guest else 0
    if used >= 3:
        raise HTTPException(401, "Your 3 guest scans are complete. Create your free account to keep scanning.")
    await db.guests.update_one({"guest_id": guest_id}, {"$set": {"used": used + 1}}, upsert=True)
    return {"remaining": 2 - used, "source": "guest"}


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


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@api_router.get("/")
async def root() -> Dict[str, str]:
    return {"message": "VeriScan API is ready"}


@api_router.get("/legal/terms")
async def legal_terms() -> Dict[str, Any]:
    return {"version": TERMS_VERSION, "effective": EFFECTIVE_DATE, "content": TERMS_OF_SERVICE}


@api_router.get("/legal/privacy")
async def legal_privacy() -> Dict[str, Any]:
    return {"version": PRIVACY_VERSION, "effective": EFFECTIVE_DATE, "content": PRIVACY_POLICY}


@api_router.post("/auth/register")
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
    user = {
        "id": str(uuid.uuid4()), "email": email,
        "password_hash": bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode(),
        "preferences": preferences, "role": "user",
        "suspended": False,
        "terms_accepted": {"version": TERMS_VERSION, "at": now_iso()},
        "privacy_accepted": {"version": PRIVACY_VERSION, "at": now_iso()},
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


@api_router.post("/auth/login")
async def login(payload: LoginRequest) -> Dict[str, Any]:
    user = await db.users.find_one({"email": payload.email.strip().lower()}, {"_id": 0})
    if not user or not bcrypt.checkpw(payload.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Email or password is incorrect")
    if user.get("suspended"):
        raise HTTPException(403, "This account has been suspended. Please contact support.")
    return {"token": token_for(user["id"]), "user": {
        "id": user["id"], "email": user["email"], "preferences": user.get("preferences", PREFERENCES),
        "role": user.get("role", "user"),
    }}


@api_router.post("/auth/forgot-password")
async def forgot_password(payload: PasswordResetStart) -> Dict[str, str]:
    email = payload.email.strip().lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    # Always respond with the same message to avoid enumeration
    if user and not user.get("suspended"):
        otp = f"{random.randint(0, 999999):06d}"
        await db.password_resets.insert_one({
            "email": email, "otp": otp,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "created_at": now_iso(),
        })
        subject, html = render_otp_email(otp)
        await send_email(to=email, subject=subject, html=html)
    return {"status": "sent"}


@api_router.post("/auth/reset-password")
async def reset_password(payload: PasswordResetComplete) -> Dict[str, str]:
    email = payload.email.strip().lower()
    record = await db.password_resets.find_one(
        {"email": email, "otp": payload.otp}, {"_id": 0}, sort=[("created_at", -1)],
    )
    if not record:
        raise HTTPException(400, "That reset code doesn't match. Try again or request a new one.")
    if datetime.fromisoformat(record["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(400, "This reset code has expired. Please request a new one.")
    new_hash = bcrypt.hashpw(payload.new_password.encode(), bcrypt.gensalt()).decode()
    await db.users.update_one({"email": email}, {"$set": {"password_hash": new_hash}})
    await db.password_resets.delete_many({"email": email})
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Profile & Entitlements
# ---------------------------------------------------------------------------
@api_router.get("/profile")
async def get_profile(authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if authorization:
        user = await authenticated_user(authorization)
        return {"email": user["email"], "preferences": user.get("preferences", PREFERENCES),
                "registered": True, "role": user.get("role", "user")}
    if x_guest_id:
        guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) or {}
        return {"email": None, "preferences": guest.get("preferences", PREFERENCES), "registered": False, "role": "guest"}
    return {"email": None, "preferences": PREFERENCES, "registered": False, "role": "guest"}


@api_router.put("/profile")
async def save_profile(payload: ProfileRequest, authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    preferences = payload.model_dump()
    if authorization:
        user = await authenticated_user(authorization)
        await db.users.update_one({"id": user["id"]}, {"$set": {"preferences": preferences}})
    elif x_guest_id:
        await db.guests.update_one({"guest_id": x_guest_id}, {"$set": {"preferences": preferences}}, upsert=True)
    return preferences


@api_router.get("/entitlements")
async def entitlements(authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if authorization:
        user = await authenticated_user(authorization)
        item = await db.entitlements.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        return {
            "registered": True, "role": user.get("role", "user"),
            "free_remaining": max(0, 5 - item.get("free_used", 0)),
            "wallet": item.get("purchased_balance", 0),
            "subscribed": item.get("subscribed", False), "email": user["email"],
        }
    guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) if x_guest_id else None
    return {"registered": False, "role": "guest",
            "free_remaining": max(0, 3 - (guest or {}).get("used", 0)),
            "wallet": 0, "subscribed": False, "email": None}


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
@api_router.get("/products/lookup")
async def lookup_product(
    barcode: str,
    authorization: Optional[str] = Header(default=None),
    x_guest_id: Optional[str] = Header(default=None),
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
    consumed = await consume_scan(x_guest_id, user)
    if user:
        preferences = user.get("preferences", PREFERENCES)
    elif x_guest_id:
        guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) or {}
        preferences = guest.get("preferences", PREFERENCES)
    else:
        preferences = PREFERENCES
    result = build_public_product(product, preferences)
    result["scan"] = consumed
    history_user = user["id"] if user else f"guest:{x_guest_id}"
    await db.history.insert_one({"id": str(uuid.uuid4()), "user_id": history_user,
                                  "product": result, "scanned_at": now_iso()})
    return result


@api_router.get("/products/alternatives")
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
    return await alternatives_for(scored_product, preferences)


@api_router.get("/history")
async def history(authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> List[Dict[str, Any]]:
    user = await authenticated_user(authorization) if authorization else None
    owner = user["id"] if user else f"guest:{x_guest_id}"
    return await db.history.find({"user_id": owner}, {"_id": 0}).sort("scanned_at", -1).to_list(30)


@api_router.post("/contributions")
async def contribution(payload: ContributionRequest, authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization) if authorization else None
    parsed_ingredients: List[Dict[str, Any]] = []
    ingredients_text = ""
    nutrition: Optional[Dict[str, Any]] = None
    dietary_type = "not_applicable"
    ocr_error: Optional[str] = None
    if payload.images and EMERGENT_LLM_KEY:
        try:
            structured = await extract_product_from_images(payload.images)
            ingredients_text = structured.get("ingredients_text", "")
            parsed_ingredients = parse_ingredients(ingredients_text)
            nutrition = structured.get("nutrition_per_100g") or None
            dietary_type = structured.get("dietary_type") or "not_applicable"
        except Exception as exc:  # noqa: BLE001
            logger.error("OCR extraction failed: %s", exc)
            ocr_error = str(exc)
    item = {
        "id": str(uuid.uuid4()), "barcode": payload.barcode,
        "product_name": payload.product_name, "brand": payload.brand,
        "notes": payload.notes, "images": payload.images,
        "extracted": {
            "ingredients_text": ingredients_text, "ingredients": parsed_ingredients,
            "nutrition_per_100g": nutrition, "dietary_type": dietary_type,
        },
        "status": "pending_verification",
        "submitted_by": (user or {}).get("id", f"guest:{x_guest_id}"),
        "created_at": now_iso(),
    }
    await db.contributions.insert_one(item.copy())
    response = {key: value for key, value in item.items() if key != "images"}
    if ocr_error:
        response["ocr_error"] = ocr_error
    return response


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


# ---------------------------------------------------------------------------
# Watchlist & notifications
# ---------------------------------------------------------------------------
@api_router.get("/watchlist")
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


@api_router.post("/watchlist/{barcode}")
async def watchlist_add(barcode: str, authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    user = await authenticated_user(authorization)
    await db.watchlist.update_one(
        {"user_id": user["id"], "barcode": barcode},
        {"$setOnInsert": {"user_id": user["id"], "barcode": barcode, "added_at": now_iso()}},
        upsert=True,
    )
    return {"status": "saved"}


@api_router.delete("/watchlist/{barcode}")
async def watchlist_remove(barcode: str, authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    user = await authenticated_user(authorization)
    await db.watchlist.delete_one({"user_id": user["id"], "barcode": barcode})
    return {"status": "removed"}


@api_router.get("/notifications")
async def notifications(authorization: Optional[str] = Header(default=None)) -> List[Dict[str, Any]]:
    user = await authenticated_user(authorization)
    return await db.notifications.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)


@api_router.post("/notifications/{notification_id}/read")
async def notification_read(notification_id: str, authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    user = await authenticated_user(authorization)
    await db.notifications.update_one({"id": notification_id, "user_id": user["id"]}, {"$set": {"read": True}})
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Support tickets & reports
# ---------------------------------------------------------------------------
@api_router.post("/support")
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


@api_router.get("/support/mine")
async def my_tickets(authorization: Optional[str] = Header(default=None)) -> List[Dict[str, Any]]:
    user = await authenticated_user(authorization)
    return await db.support_tickets.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)


@api_router.post("/reports")
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


# ---------------------------------------------------------------------------
# Pricing (public)
# ---------------------------------------------------------------------------
@api_router.get("/plans")
async def plans(country: Optional[str] = None) -> Dict[str, Any]:
    country = (country or "IN").upper()
    pricing_doc = await db.country_pricing.find_one({"country": country}, {"_id": 0})
    if not pricing_doc:
        pricing_doc = await db.country_pricing.find_one({"country": "IN"}, {"_id": 0})
    pricing_doc = pricing_doc or DEFAULT_COUNTRY_PRICING[0]
    return {
        "launch_promo": True,
        "country": pricing_doc["country"], "currency": pricing_doc["currency"], "symbol": pricing_doc["symbol"],
        "provider": pricing_doc["provider"],
        "scan_intro": {"price": pricing_doc["scan_intro"], "label": "First 20 purchased scans"},
        "scan_standard": {"price": pricing_doc["scan_standard"], "label": "After introductory credits"},
        "subscriptions": [
            {"id": "monthly", "price": pricing_doc["monthly"], "regular_price": pricing_doc["monthly_regular"], "period": "month"},
            {"id": "yearly", "price": pricing_doc["yearly"], "regular_price": pricing_doc["yearly_regular"], "period": "year"},
        ],
    }


@api_router.get("/promocodes/{code}")
async def promocode_lookup(code: str, country: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    promo = await db.promocodes.find_one({"code": code.upper(), "active": True}, {"_id": 0})
    if not promo:
        raise HTTPException(404, "That promo code isn't valid.")
    if promo.get("expires_at") and datetime.fromisoformat(promo["expires_at"]) < now:
        raise HTTPException(410, "That promo code has expired.")
    if promo.get("redemptions", 0) >= promo.get("max_redemptions", 100):
        raise HTTPException(410, "That promo code is fully redeemed.")
    if country and promo.get("countries") and country.upper() not in promo["countries"]:
        raise HTTPException(400, "That promo code isn't available in your region.")
    return promo


# ---------------------------------------------------------------------------
# Payments — Razorpay (IN/INR) + Stripe checkout stub (non-IN)
# ---------------------------------------------------------------------------
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
rp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)) if (RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET) else None


class RazorpayOrderIn(BaseModel):
    credits: int = Field(ge=1, le=100)
    tier: str = Field(pattern="^(intro|standard)$")


class RazorpayVerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


async def india_price_paise(field: str) -> int:
    row = await db.country_pricing.find_one({"country": "IN"}, {"_id": 0, field: 1})
    value = (row or {}).get(field)
    if not isinstance(value, (int, float)):
        raise HTTPException(409, "India price is not configured")
    # Convert rupees to paise
    return int(round(float(value) * 100))


async def credit_if_new(order: Dict[str, Any], payment_id: str) -> None:
    result = await db.payment_orders.update_one(
        {"razorpay_order_id": order["razorpay_order_id"], "credited": {"$ne": True}},
        {"$set": {"credited": True, "status": "paid", "razorpay_payment_id": payment_id}},
    )
    if result.modified_count:
        await db.entitlements.update_one(
            {"user_id": order["user_id"]},
            {"$inc": {"purchased_balance": order["credits"]}}, upsert=True,
        )


@api_router.post("/payments/razorpay/order")
async def razorpay_order(payload: RazorpayOrderIn, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization)
    if not rp_client:
        raise HTTPException(503, "Razorpay is not configured")
    field = "scan_intro" if payload.tier == "intro" else "scan_standard"
    unit_paise = await india_price_paise(field)
    amount_paise = unit_paise * payload.credits
    order = await __import__("asyncio").to_thread(rp_client.order.create, data={
        "amount": amount_paise, "currency": "INR",
        "receipt": "scan_" + uuid.uuid4().hex[:30],
        "notes": {"user_id": user["id"], "kind": "scan_credits", "credits": str(payload.credits), "tier": payload.tier},
    })
    await db.payment_orders.insert_one({
        "razorpay_order_id": order["id"], "user_id": user["id"], "kind": "scan_credits",
        "credits": payload.credits, "amount_paise": amount_paise,
        "status": "created", "credited": False, "created_at": time.time(),
    })
    return {
        "key_id": RAZORPAY_KEY_ID, "order_id": order["id"],
        "amount": amount_paise, "currency": "INR",
        "description": f"{payload.credits} VeriScan credit{'s' if payload.credits > 1 else ''}",
    }


@api_router.post("/payments/razorpay/verify")
async def razorpay_verify(payload: RazorpayVerifyIn, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization)
    if not rp_client:
        raise HTTPException(503, "Razorpay is not configured")
    order = await db.payment_orders.find_one({"razorpay_order_id": payload.razorpay_order_id, "user_id": user["id"]}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    try:
        rp_client.utility.verify_payment_signature({
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "razorpay_signature": payload.razorpay_signature,
        })
    except Exception:
        raise HTTPException(400, "Invalid payment signature")
    await credit_if_new(order, payload.razorpay_payment_id)
    return {"ok": True, "credits": order["credits"]}


@api_router.get("/payments/razorpay/checkout/{order_id}", response_class=HTMLResponse)
async def razorpay_checkout_page(order_id: str) -> str:
    """Hosted checkout page rendered inside the mobile WebView or web browser.
    Uses callback_url + redirect:true so we stay out of the popup flow."""
    order = await db.payment_orders.find_one({"razorpay_order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    order_json = json.dumps({
        "key_id": RAZORPAY_KEY_ID, "amount": order["amount_paise"], "currency": "INR",
        "order_id": order["razorpay_order_id"],
        "description": f"{order['credits']} VeriScan credits",
    })
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VeriScan checkout</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #fdfcfa; color: #1a1c19;
        display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
  .card {{ text-align: center; padding: 28px; }}
  .spinner {{ width: 36px; height: 36px; border-radius: 50%; border: 4px solid #e8f5e9;
             border-top-color: #2e7d32; animation: spin 0.9s linear infinite; margin: 0 auto 16px; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
<div class="card">
  <div class="spinner"></div>
  <p>Opening secure Razorpay checkout…</p>
</div>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
const order = {order_json};
const callbackUrl = "{"/api/payments/razorpay/callback"}";
const rzp = new Razorpay({{
  key: order.key_id,
  amount: order.amount,
  currency: order.currency,
  name: "VeriScan",
  description: order.description,
  order_id: order.order_id,
  callback_url: callbackUrl,
  redirect: true,
  theme: {{ color: "#2e7d32" }},
  modal: {{ ondismiss: () => {{ window.location.href = "/api/payments/razorpay/cancelled"; }} }},
}});
rzp.open();
</script>
</body>
</html>"""


@api_router.get("/payments/razorpay/cancelled", response_class=HTMLResponse)
async def razorpay_cancelled() -> str:
    return """<!doctype html><html><body style="font-family:system-ui;text-align:center;padding:40px">
<h2>Payment cancelled</h2>
<p>You can close this window and return to VeriScan.</p>
</body></html>"""


@api_router.post("/payments/razorpay/callback")
async def razorpay_callback(request: Request) -> HTMLResponse:
    """Razorpay redirects here with form-encoded payment fields. We verify the
    signature and credit the user; then render a simple confirmation page."""
    form = await request.form()
    order_id = str(form.get("razorpay_order_id", ""))
    payment_id = str(form.get("razorpay_payment_id", ""))
    signature = str(form.get("razorpay_signature", ""))
    if not order_id or not payment_id or not signature:
        return HTMLResponse("<html><body><h3>Missing payment data.</h3></body></html>", status_code=400)
    order = await db.payment_orders.find_one({"razorpay_order_id": order_id}, {"_id": 0})
    if not order:
        return HTMLResponse("<html><body><h3>Order not found.</h3></body></html>", status_code=404)
    if rp_client:
        try:
            rp_client.utility.verify_payment_signature({
                "razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature,
            })
        except Exception:
            return HTMLResponse("<html><body><h3>Signature verification failed.</h3></body></html>", status_code=400)
        await credit_if_new(order, payment_id)
    return HTMLResponse("""<!doctype html><html><body style="font-family:system-ui;text-align:center;padding:40px">
<h2 style="color:#2e7d32">Payment received</h2>
<p>Your credits are being added. Close this window and return to VeriScan.</p>
</body></html>""")


@api_router.post("/payments/razorpay/webhook")
async def razorpay_webhook(request: Request) -> Dict[str, bool]:
    raw = await request.body()
    supplied = request.headers.get("x-razorpay-signature", "")
    expected = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(400, "Bad signature")
    payload = json.loads(raw)
    event_id = request.headers.get("x-razorpay-event-id") or hashlib.sha256(raw).hexdigest()
    try:
        await db.webhook_events.insert_one({"event_id": event_id, "event": payload.get("event"), "received_at": time.time()})
    except Exception as exc:  # noqa: BLE001
        # DuplicateKeyError (code 11000) → acknowledge; anything else re-raise
        if getattr(exc, "code", None) != 11000 and "duplicate" not in str(exc).lower():
            raise
        return {"ok": True}
    event = payload.get("event", "")
    entity = payload.get("payload", {})
    if event in ("order.paid", "payment.captured"):
        pay = entity.get("payment", {}).get("entity", {})
        order_id = pay.get("order_id")
        order = await db.payment_orders.find_one({"razorpay_order_id": order_id}, {"_id": 0})
        if order:
            await credit_if_new(order, pay.get("id", ""))
    elif event == "subscription.charged":
        sub = entity.get("subscription", {}).get("entity", {})
        await db.subscriptions.update_one(
            {"razorpay_subscription_id": sub.get("id")},
            {"$set": {"status": "active", "last_charged_at": time.time()}},
        )
    elif event in ("subscription.pending", "subscription.halted", "subscription.cancelled"):
        sub = entity.get("subscription", {}).get("entity", {})
        await db.subscriptions.update_one(
            {"razorpay_subscription_id": sub.get("id")},
            {"$set": {"status": event.replace("subscription.", "")}},
        )
    return {"ok": True}


@api_router.post("/payments/subscription-session")
async def subscription_session(payload: SubscriptionPurchase, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization)
    if payload.plan not in {"monthly", "yearly"}:
        raise HTTPException(400, "Invalid subscription plan")
    if not os.environ.get("STRIPE_SECRET_KEY"):
        raise HTTPException(503, "Payments are not configured yet")
    price_id = os.environ.get("STRIPE_MONTHLY_PRICE_ID" if payload.plan == "monthly" else "STRIPE_YEARLY_PRICE_ID")
    if not price_id:
        raise HTTPException(503, "Subscription prices are not configured yet")
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    session = stripe.checkout.Session.create(
        mode="subscription", line_items=[{"price": price_id, "quantity": 1}],
        success_url=os.environ.get("STRIPE_CHECKOUT_SUCCESS_URL", "https://example.com/success"),
        cancel_url=os.environ.get("STRIPE_CHECKOUT_CANCEL_URL", "https://example.com/cancel"),
        metadata={"user_id": user["id"], "plan": payload.plan},
    )
    return {"url": session.url, "sessionId": session.id}


# ---------------------------------------------------------------------------
# Admin panel
# ---------------------------------------------------------------------------
@api_router.get("/admin/overview")
async def admin_overview(_: Dict[str, Any] = Depends(admin_user)) -> Dict[str, int]:
    return {
        "users": await db.users.count_documents({"role": {"$ne": "admin"}}),
        "suspended": await db.users.count_documents({"suspended": True}),
        "open_tickets": await db.support_tickets.count_documents({"status": "open"}),
        "open_reports": await db.reports.count_documents({"status": "open"}),
        "products": await db.products.count_documents({}),
        "contributions_pending": await db.contributions.count_documents({"status": "pending_verification"}),
    }


@api_router.get("/admin/users")
async def admin_users(_: Dict[str, Any] = Depends(admin_user), q: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"role": {"$ne": "admin"}}
    if q:
        query["email"] = {"$regex": q.lower(), "$options": "i"}
    users = await db.users.find(query, {"_id": 0, "password_hash": 0, "preferences": 0}).sort("created_at", -1).to_list(200)
    return [{
        "id": u["id"], "email_masked": mask_email(u["email"]),
        "suspended": u.get("suspended", False),
        "created_at": u.get("created_at"),
        "terms_version": u.get("terms_accepted", {}).get("version"),
    } for u in users]


@api_router.post("/admin/users/{user_id}/suspend")
async def admin_user_suspend(user_id: str, payload: UserSuspendRequest, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    result = await db.users.update_one({"id": user_id, "role": {"$ne": "admin"}}, {"$set": {"suspended": True, "suspension_reason": payload.reason}})
    if result.matched_count == 0:
        raise HTTPException(404, "User not found")
    return {"status": "suspended"}


@api_router.post("/admin/users/{user_id}/reactivate")
async def admin_user_reactivate(user_id: str, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    result = await db.users.update_one({"id": user_id}, {"$set": {"suspended": False}, "$unset": {"suspension_reason": ""}})
    if result.matched_count == 0:
        raise HTTPException(404, "User not found")
    return {"status": "active"}


@api_router.post("/admin/users/{user_id}/send-reset")
async def admin_send_reset(user_id: str, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")
    otp = f"{random.randint(0, 999999):06d}"
    await db.password_resets.insert_one({
        "email": user["email"], "otp": otp,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        "created_at": now_iso(),
    })
    subject, html = render_admin_reset_link(otp, user["email"])
    await send_email(to=user["email"], subject=subject, html=html)
    return {"status": "sent"}


@api_router.get("/admin/pricing")
async def admin_pricing(_: Dict[str, Any] = Depends(admin_user)) -> List[Dict[str, Any]]:
    return await db.country_pricing.find({}, {"_id": 0}).sort("country", 1).to_list(100)


@api_router.put("/admin/pricing/{country}")
async def admin_pricing_update(country: str, payload: AdminPricingUpdate, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    doc = payload.model_dump()
    doc["country"] = country.upper()
    await db.country_pricing.replace_one({"country": country.upper()}, doc, upsert=True)
    return {"status": "updated"}


@api_router.get("/admin/promocodes")
async def admin_promocodes(_: Dict[str, Any] = Depends(admin_user)) -> List[Dict[str, Any]]:
    return await db.promocodes.find({}, {"_id": 0}).sort("code", 1).to_list(200)


@api_router.post("/admin/promocodes")
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


@api_router.delete("/admin/promocodes/{code}")
async def admin_promocode_delete(code: str, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    result = await db.promocodes.update_one({"code": code.upper()}, {"$set": {"active": False}})
    if result.matched_count == 0:
        raise HTTPException(404, "Promo code not found")
    return {"status": "deactivated"}


@api_router.get("/admin/support")
async def admin_support(_: Dict[str, Any] = Depends(admin_user), status: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    tickets = await db.support_tickets.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    for ticket in tickets:
        if ticket.get("user_email"):
            ticket["user_email"] = mask_email(ticket["user_email"])
    return tickets


@api_router.put("/admin/support/{ticket_id}")
async def admin_support_update(ticket_id: str, payload: SupportUpdate, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    if payload.status not in {"open", "in_progress", "resolved", "closed"}:
        raise HTTPException(400, "Invalid status")
    result = await db.support_tickets.update_one({"id": ticket_id}, {"$set": {
        "status": payload.status, "admin_note": payload.admin_note, "updated_at": now_iso(),
    }})
    if result.matched_count == 0:
        raise HTTPException(404, "Ticket not found")
    return {"status": "updated"}


@api_router.get("/admin/reports")
async def admin_reports(_: Dict[str, Any] = Depends(admin_user), status: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    return await db.reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)


@api_router.put("/admin/reports/{report_id}")
async def admin_report_update(report_id: str, payload: SupportUpdate, _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    if payload.status not in {"open", "in_progress", "resolved", "closed"}:
        raise HTTPException(400, "Invalid status")
    result = await db.reports.update_one({"id": report_id}, {"$set": {
        "status": payload.status, "admin_note": payload.admin_note, "updated_at": now_iso(),
    }})
    if result.matched_count == 0:
        raise HTTPException(404, "Report not found")
    return {"status": "updated"}


@api_router.get("/admin/contributions")
async def admin_contributions(_: Dict[str, Any] = Depends(admin_user), status: Optional[str] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    items = await db.contributions.find(query, {"_id": 0, "images": 0}).sort("created_at", -1).to_list(100)
    return items


# ---------------------------------------------------------------------------
# App wiring & startup
# ---------------------------------------------------------------------------
app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def seed_database() -> None:
    # Seed sample products (idempotent)
    for product in SEEDED_PRODUCTS:
        enriched = {**product, "ingredients": parse_ingredients(product.get("ingredients_text", ""))}
        await db.products.update_one({"barcode": product["barcode"]}, {"$set": enriched}, upsert=True)
    # Seed default country pricing
    for entry in DEFAULT_COUNTRY_PRICING:
        await db.country_pricing.update_one({"country": entry["country"]}, {"$setOnInsert": entry}, upsert=True)
    # Ensure a promocode uniqueness index
    await db.promocodes.create_index("code", unique=True)
    await db.payment_orders.create_index("razorpay_order_id", unique=True)
    await db.webhook_events.create_index("event_id", unique=True)
    await db.subscriptions.create_index("razorpay_subscription_id", unique=True)
    # Seed admin user
    existing = await db.users.find_one({"email": ADMIN_SEED_EMAIL}, {"_id": 0})
    if existing:
        if existing.get("role") != "admin":
            await db.users.update_one({"email": ADMIN_SEED_EMAIL}, {"$set": {"role": "admin", "suspended": False}})
    else:
        admin = {
            "id": str(uuid.uuid4()), "email": ADMIN_SEED_EMAIL,
            "password_hash": bcrypt.hashpw(ADMIN_SEED_PASSWORD.encode(), bcrypt.gensalt()).decode(),
            "preferences": PREFERENCES.copy(), "role": "admin", "suspended": False,
            "terms_accepted": {"version": TERMS_VERSION, "at": now_iso()},
            "privacy_accepted": {"version": PRIVACY_VERSION, "at": now_iso()},
            "created_at": now_iso(),
        }
        await db.users.insert_one(admin)
        await db.entitlements.insert_one({
            "user_id": admin["id"], "free_month": datetime.now(timezone.utc).strftime("%Y-%m"),
            "free_used": 0, "purchased_balance": 0, "intro_used": 0, "subscribed": True,
        })


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()
