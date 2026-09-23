"""VeriScan FastAPI backend — app factory wiring all modular routers.

Route handlers live in `routes/` (auth, profile, products, payments, admin,
misc); shared state and helpers live in `core/` (config, models, deps,
product_logic, pricing_logic).
"""
import uuid
from datetime import datetime, timezone

import bcrypt
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core.config import (
    ADMIN_SEED_EMAIL, ADMIN_SEED_PASSWORD, DEFAULT_COUNTRY_PRICING, PREFERENCES,
    SEEDED_PRODUCTS, client, db,
)
from core.deps import now_iso
from ingredients_db import parse_ingredients
from routes.admin import router as admin_router
from routes.analytics import router as analytics_router
from routes.auth import router as auth_router
from routes.misc import router as misc_router
from routes.payments import router as payments_router
from routes.products import router as products_router
from routes.profile import router as profile_router
from routes.stripe_payments import router as stripe_router

app = FastAPI(title="VeriScan API")

for router in (auth_router, profile_router, products_router, payments_router,
               admin_router, misc_router, analytics_router, stripe_router):
    app.include_router(router, prefix="/api")

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
    # Ensure uniqueness indexes
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
            "terms_accepted": {"version": "seed", "at": now_iso()},
            "privacy_accepted": {"version": "seed", "at": now_iso()},
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
