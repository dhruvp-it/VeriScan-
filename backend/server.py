import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
import requests
import stripe
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
JWT_SECRET = os.environ.get("JWT_SECRET", "veriscan-local-development-secret")
TOKEN_ALGORITHM = "HS256"

app = FastAPI(title="VeriScan API")
api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

PREFERENCES = {"dietary": [], "targets": [], "sensitivities": []}
SEEDED_PRODUCTS = [
    {
        "id": "seed-oats-001", "barcode": "8901030895001", "name": "Organic Rolled Oats",
        "brand": "Harvest Table", "category": "food", "description": "Whole grain oats for a simple, nourishing breakfast.",
        "dietary_type": "vegan", "origin_country": "India", "manufactured_in": "Pune, India",
        "first_detected_year": 2024, "price_tier": "affordable", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "500 g", "price_inr": 249,
        "ingredients": [
            {"name": "Whole grain oats", "score": 94, "hazard": "beneficial", "function": "Whole food base", "effect": "A naturally nourishing source of beta-glucan fiber that supports satiety and heart health."},
            {"name": "Vitamin E", "score": 86, "hazard": "beneficial", "function": "Antioxidant", "effect": "Helps protect cells from oxidative stress when consumed as part of a balanced diet."},
        ],
        "retailers": [{"name": "Nature's Basket", "price": 249, "url": "https://www.naturesbasket.co.in/"}, {"name": "BigBasket", "price": 239, "url": "https://www.bigbasket.com/"}],
    },
    {
        "id": "seed-cleanser-001", "barcode": "8906087771204", "name": "Calm Barrier Cleanser",
        "brand": "Moss & Mineral", "category": "personal_care", "description": "A fragrance-free daily cleanser designed for sensitive skin.",
        "dietary_type": "not_applicable", "origin_country": "India", "manufactured_in": "Bengaluru, India",
        "first_detected_year": 2023, "price_tier": "premium", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "150 ml", "price_inr": 695,
        "ingredients": [
            {"name": "Glycerin", "score": 82, "hazard": "beneficial", "function": "Humectant", "effect": "Draws water toward the skin surface and supports a comfortable skin barrier."},
            {"name": "Sodium Laureth Sulfate", "score": 48, "hazard": "moderation", "function": "Surfactant", "effect": "Cleans oils effectively; can feel drying for some sensitive skin types when overused."},
            {"name": "Fragrance", "score": 35, "hazard": "harmful", "function": "Sensory additive", "effect": "May be sensitising for fragrance-reactive skin; users with fragrance sensitivity may prefer an unscented formula."},
        ],
        "retailers": [{"name": "Nykaa", "price": 695, "url": "https://www.nykaa.com/"}, {"name": "Tata 1mg", "price": 679, "url": "https://www.1mg.com/"}],
    },
    {
        "id": "seed-protein-001", "barcode": "8908001234567", "name": "Plant Protein Vanilla",
        "brand": "Good Ground", "category": "supplement", "description": "Pea and brown rice protein with a lightly sweet vanilla finish.",
        "dietary_type": "vegan", "origin_country": "India", "manufactured_in": "Hyderabad, India",
        "first_detected_year": 2024, "price_tier": "high", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "500 g", "price_inr": 1299,
        "ingredients": [
            {"name": "Pea protein isolate", "score": 79, "hazard": "safe", "function": "Protein source", "effect": "Provides plant protein and can support muscle recovery alongside an adequate diet."},
            {"name": "Stevia extract", "score": 67, "hazard": "safe", "function": "Sweetener", "effect": "A high-intensity sweetener that reduces added sugar; individual tolerance can vary."},
            {"name": "Xanthan gum", "score": 55, "hazard": "moderation", "function": "Thickener", "effect": "A functional stabiliser that is generally well tolerated, though large amounts may feel bloating to some people."},
        ],
        "retailers": [{"name": "Amazon India", "price": 1299, "url": "https://www.amazon.in/"}, {"name": "HealthKart", "price": 1199, "url": "https://www.healthkart.com/"}],
    },
]


class AuthRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)


class ProfileRequest(BaseModel):
    dietary: List[str] = []
    targets: List[str] = []
    sensitivities: List[str] = []


class ContributionRequest(BaseModel):
    barcode: str
    product_name: Optional[str] = None
    notes: Optional[str] = None
    images: List[str] = []


class ScanPurchase(BaseModel):
    quantity: int = Field(ge=1, le=100)
    tier: str


class SubscriptionPurchase(BaseModel):
    plan: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def token_for(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": datetime.now(timezone.utc).timestamp() + 60 * 60 * 24 * 30}, JWT_SECRET, algorithm=TOKEN_ALGORITHM)


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
    return user


def score_for(ingredients: List[Dict[str, Any]]) -> float:
    if not ingredients:
        return 60.0
    average = sum(int(item.get("score", 60)) for item in ingredients) / len(ingredients)
    low_scores = [int(item.get("score", 60)) for item in ingredients if int(item.get("score", 60)) < 25]
    return round(max(0, average - (12 * len(low_scores))), 1)


def personal_match(product: Dict[str, Any], preferences: Dict[str, List[str]]) -> int:
    ingredients = " ".join(item.get("name", "").lower() for item in product.get("ingredients", []))
    total = 0
    possible = 0
    for target in preferences.get("targets", []):
        possible += 1
        if target.lower().replace(" ", "") in ingredients or target.lower() == "clean eating":
            total += 1
    if preferences.get("dietary"):
        possible += 1
        if product.get("dietary_type") in preferences["dietary"] or product.get("dietary_type") == "not_applicable":
            total += 1
    return round(88 if possible == 0 else 72 + (total / possible) * 28)


def public_product(product: Dict[str, Any], preferences: Dict[str, List[str]]) -> Dict[str, Any]:
    ingredients = sorted(product.get("ingredients", []), key=lambda item: item.get("score", 60))
    result = {key: value for key, value in product.items() if key not in {"_id", "ingredients", "retailers"}}
    result.update({"ingredients": ingredients, "retailers": product.get("retailers", []), "overall_health_score": score_for(ingredients), "personal_match": personal_match(product, preferences)})
    return result


async def consume_scan(guest_id: Optional[str], user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if user:
        entitlement = await db.entitlements.find_one({"user_id": user["id"]}, {"_id": 0})
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        if not entitlement or entitlement.get("free_month") != month:
            entitlement = {"user_id": user["id"], "free_month": month, "free_used": 0, "purchased_balance": 0, "intro_used": 0, "subscribed": False}
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


def remote_lookup(barcode: str) -> Optional[Dict[str, Any]]:
    for endpoint, category in [("https://world.openfoodfacts.org/api/v2/product/", "food"), ("https://world.openbeautyfacts.org/api/v2/product/", "personal_care")]:
        try:
            response = requests.get(f"{endpoint}{barcode}.json", timeout=4)
            data = response.json()
            if data.get("status") != 1:
                continue
            product = data.get("product", {})
            names = [part.strip() for part in (product.get("ingredients_text", "").split(",") if product.get("ingredients_text") else []) if part.strip()]
            ingredients = [{"name": name.title(), "score": 62, "hazard": "safe", "function": "Formulation ingredient", "effect": "Reviewed from the public product label; individual responses may vary."} for name in names[:12]]
            return {"id": f"online-{barcode}", "barcode": barcode, "name": product.get("product_name") or "Scanned product", "brand": product.get("brands") or "Public registry", "category": category, "description": "Details sourced from the public product registry.", "dietary_type": "vegan" if "vegan" in str(product.get("labels", "")).lower() else "not_applicable", "origin_country": "Global", "manufactured_in": "Registry listing", "first_detected_year": datetime.now(timezone.utc).year, "price_tier": "affordable", "target_age_group": "Adults", "primary_region": "Global", "serving_size": product.get("quantity") or "See label", "price_inr": 0, "ingredients": ingredients, "retailers": []}
        except (requests.RequestException, ValueError, TypeError):
            continue
    return None


@api_router.get("/")
async def root() -> Dict[str, str]:
    return {"message": "VeriScan API is ready"}


@api_router.post("/auth/register")
async def register(payload: AuthRequest, x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    email = payload.email.strip().lower()
    if await db.users.find_one({"email": email}, {"_id": 0}):
        raise HTTPException(409, "An account with this email already exists")
    user = {"id": str(uuid.uuid4()), "email": email, "password_hash": bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode(), "preferences": PREFERENCES.copy(), "created_at": now_iso()}
    await db.users.insert_one(user.copy())
    await db.entitlements.insert_one({"user_id": user["id"], "free_month": datetime.now(timezone.utc).strftime("%Y-%m"), "free_used": 0, "purchased_balance": 0, "intro_used": 0, "subscribed": False})
    if x_guest_id:
        await db.history.update_many({"user_id": f"guest:{x_guest_id}"}, {"$set": {"user_id": user["id"]}})
    return {"token": token_for(user["id"]), "user": {"id": user["id"], "email": email, "preferences": user["preferences"]}}


@api_router.post("/auth/login")
async def login(payload: AuthRequest) -> Dict[str, Any]:
    user = await db.users.find_one({"email": payload.email.strip().lower()}, {"_id": 0})
    if not user or not bcrypt.checkpw(payload.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Email or password is incorrect")
    return {"token": token_for(user["id"]), "user": {"id": user["id"], "email": user["email"], "preferences": user.get("preferences", PREFERENCES)}}


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
        return {"registered": True, "free_remaining": max(0, 5 - item.get("free_used", 0)), "wallet": item.get("purchased_balance", 0), "subscribed": item.get("subscribed", False)}
    guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) if x_guest_id else None
    return {"registered": False, "free_remaining": max(0, 3 - (guest or {}).get("used", 0)), "wallet": 0, "subscribed": False}


@api_router.get("/products/lookup")
async def lookup_product(barcode: str, authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization) if authorization else None
    consumed = await consume_scan(x_guest_id, user)
    product = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    if not product:
        product = remote_lookup(barcode)
        if product:
            await db.products.update_one({"barcode": barcode}, {"$set": product}, upsert=True)
    if not product:
        raise HTTPException(404, detail={"message": "Product not found", "barcode": barcode, "scan": consumed})
    preferences = (user or {}).get("preferences", PREFERENCES)
    result = public_product(product, preferences)
    result["scan"] = consumed
    history_user = user["id"] if user else f"guest:{x_guest_id}"
    await db.history.insert_one({"id": str(uuid.uuid4()), "user_id": history_user, "product": result, "scanned_at": now_iso()})
    return result


@api_router.get("/history")
async def history(authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> List[Dict[str, Any]]:
    user = await authenticated_user(authorization) if authorization else None
    owner = user["id"] if user else f"guest:{x_guest_id}"
    return await db.history.find({"user_id": owner}, {"_id": 0}).sort("scanned_at", -1).to_list(30)


@api_router.post("/contributions")
async def contribution(payload: ContributionRequest, authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization) if authorization else None
    item = {"id": str(uuid.uuid4()), "barcode": payload.barcode, "product_name": payload.product_name, "notes": payload.notes, "images": payload.images, "status": "pending_verification", "submitted_by": (user or {}).get("id", f"guest:{x_guest_id}"), "created_at": now_iso()}
    await db.contributions.insert_one(item.copy())
    return {key: value for key, value in item.items() if key != "images"}


@api_router.get("/plans")
async def plans() -> Dict[str, Any]:
    return {"launch_promo": True, "scan_intro": {"price": 5, "label": "First 20 purchased scans"}, "scan_standard": {"price": 15, "label": "After introductory credits"}, "subscriptions": [{"id": "monthly", "price": 72, "regular_price": 180, "period": "month"}, {"id": "yearly", "price": 450, "regular_price": 1500, "period": "year"}]}


@api_router.post("/payments/scan-intent")
async def scan_intent(payload: ScanPurchase, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization)
    amount = {"intro": 500, "standard": 1500}.get(payload.tier)
    if amount is None:
        raise HTTPException(400, "Invalid scan tier")
    if not os.environ.get("STRIPE_SECRET_KEY"):
        raise HTTPException(503, "Payments are not configured yet")
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    intent = stripe.PaymentIntent.create(amount=amount * payload.quantity, currency="inr", automatic_payment_methods={"enabled": True}, metadata={"user_id": user["id"], "kind": "scan_credits", "quantity": str(payload.quantity)})
    await db.payments.insert_one({"stripe_payment_intent_id": intent.id, "user_id": user["id"], "quantity": payload.quantity, "status": "created", "created_at": now_iso()})
    return {"paymentIntentClientSecret": intent.client_secret}


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
    session = stripe.checkout.Session.create(mode="subscription", line_items=[{"price": price_id, "quantity": 1}], success_url=os.environ.get("STRIPE_CHECKOUT_SUCCESS_URL", "https://example.com/success"), cancel_url=os.environ.get("STRIPE_CHECKOUT_CANCEL_URL", "https://example.com/cancel"), metadata={"user_id": user["id"], "plan": payload.plan})
    return {"url": session.url, "sessionId": session.id}


@api_router.post("/payments/stripe/webhook")
async def stripe_webhook(request: Request) -> Dict[str, bool]:
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(503, "Webhook is not configured")
    try:
        event = stripe.Webhook.construct_event(await request.body(), request.headers.get("stripe-signature", ""), secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "Invalid Stripe webhook")
    try:
        await db.webhook_events.insert_one({"stripe_event_id": event["id"], "created_at": now_iso()})
    except Exception:
        return {"ok": True}
    obj = event["data"]["object"]
    if event["type"] == "payment_intent.succeeded":
        metadata = obj.get("metadata", {})
        quantity = int(metadata.get("quantity", "0"))
        await db.entitlements.update_one({"user_id": metadata.get("user_id")}, {"$inc": {"purchased_balance": quantity}})
        await db.payments.update_one({"stripe_payment_intent_id": obj["id"]}, {"$set": {"status": "succeeded"}})
    if event["type"] == "checkout.session.completed":
        await db.entitlements.update_one({"user_id": obj.get("metadata", {}).get("user_id")}, {"$set": {"subscribed": True, "subscription_plan": obj.get("metadata", {}).get("plan")}})
    return {"ok": True}


app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def seed_database() -> None:
    for product in SEEDED_PRODUCTS:
        await db.products.update_one({"barcode": product["barcode"]}, {"$setOnInsert": product}, upsert=True)


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()
