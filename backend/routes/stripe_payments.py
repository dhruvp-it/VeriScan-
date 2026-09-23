"""Stripe checkout — card + Apple Pay + Google Pay for non-India users.

Gated: an admin must enable Stripe for a country by setting a positive
`monthly` (and/or `yearly`) price and `provider='stripe'` in country_pricing.
While all prices remain zero the endpoint returns 200 with `enabled=false`
and the app treats the country as free — no checkout is offered.

Uses Stripe Checkout Sessions with automatic_payment_methods so Apple Pay and
Google Pay show up automatically on eligible devices and browsers, per Stripe's
guidance. The user is redirected back to a hosted success/cancel page.
"""
import os
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse

from core.config import db
from core.deps import admin_user, authenticated_user
from core.models import SubscriptionPurchase
from legal_content import PRIVACY_VERSION, TERMS_VERSION

router = APIRouter()

CURRENCY_ZERO_DECIMAL = {"JPY", "KRW", "VND"}  # currencies that don't use minor units


def _to_smallest_unit(amount: float, currency: str) -> int:
    return int(round(amount)) if currency.upper() in CURRENCY_ZERO_DECIMAL else int(round(amount * 100))


def _stripe_key() -> str:
    # Support both the Emergent-provided `STRIPE_API_KEY` and the more common `STRIPE_SECRET_KEY`.
    key = (os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY") or "").strip()
    if not key:
        raise HTTPException(503, "Stripe is not configured yet")
    return key


@router.get("/payments/stripe/status")
async def stripe_status(country: Optional[str] = None) -> Dict[str, Any]:
    """Called by the mobile app to decide whether to show the Upgrade CTA."""
    country = (country or "US").upper()
    row = await db.country_pricing.find_one({"country": country}, {"_id": 0})
    if not row:
        return {"country": country, "enabled": False, "reason": "no_pricing_row"}
    monthly = float(row.get("monthly", 0) or 0)
    yearly = float(row.get("yearly", 0) or 0)
    provider = row.get("provider", "")
    if provider != "stripe" or (monthly <= 0 and yearly <= 0):
        return {"country": country, "enabled": False, "reason": "free_until_admin_enables",
                "currency": row.get("currency"), "symbol": row.get("symbol")}
    return {
        "country": country, "enabled": True, "provider": "stripe",
        "currency": row.get("currency", "USD"), "symbol": row.get("symbol", "$"),
        "monthly": monthly, "yearly": yearly,
        "monthly_regular": float(row.get("monthly_regular", 0) or 0),
        "yearly_regular": float(row.get("yearly_regular", 0) or 0),
    }


@router.post("/payments/stripe/checkout")
async def stripe_checkout(payload: SubscriptionPurchase, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Create a Stripe Checkout Session. Cards, Apple Pay and Google Pay are
    activated automatically via `automatic_payment_methods` on eligible clients.
    Requires the user to have accepted the current T&C + Privacy versions."""
    user = await authenticated_user(authorization)
    # Mandatory current-version T&C acceptance for any subscription checkout
    terms_ok = user.get("terms_accepted", {}).get("version") == TERMS_VERSION
    privacy_ok = user.get("privacy_accepted", {}).get("version") == PRIVACY_VERSION
    if not (terms_ok and privacy_ok):
        raise HTTPException(428, "TERMS_ACCEPTANCE_REQUIRED")

    country = (payload.country or "US").upper()
    row = await db.country_pricing.find_one({"country": country}, {"_id": 0})
    if not row:
        raise HTTPException(404, "Country pricing not configured")
    if row.get("provider") != "stripe":
        raise HTTPException(400, "Stripe is not the payment provider for this country")
    if payload.plan not in {"monthly", "yearly"}:
        raise HTTPException(400, "Invalid subscription plan")
    price = float(row.get(payload.plan, 0) or 0)
    if price <= 0:
        raise HTTPException(409, "Subscriptions in this country are currently free — the admin has not enabled paid plans yet.")

    stripe.api_key = _stripe_key()
    currency = str(row.get("currency", "USD")).lower()
    amount = _to_smallest_unit(price, currency.upper())
    app_origin = os.environ.get("APP_URL", "https://example.com").rstrip("/")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            currency=currency,
            automatic_payment_methods={"enabled": True},
            line_items=[{
                "quantity": 1,
                "price_data": {
                    "currency": currency,
                    "unit_amount": amount,
                    "recurring": {"interval": "month" if payload.plan == "monthly" else "year"},
                    "product_data": {
                        "name": f"VeriScan {payload.plan.capitalize()} Subscription",
                        "description": "Unlimited scans, personalised match scoring, watchlist alerts.",
                    },
                },
            }],
            success_url=f"{app_origin}/api/payments/stripe/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{app_origin}/api/payments/stripe/cancelled",
            metadata={
                "user_id": user["id"], "plan": payload.plan, "country": country,
                "terms_version": TERMS_VERSION, "privacy_version": PRIVACY_VERSION,
                "consented_no_refund": "true",
            },
            client_reference_id=user["id"],
            payment_method_collection="always",
        )
    except stripe.error.StripeError as exc:  # noqa: BLE001
        raise HTTPException(400, f"Stripe checkout failed: {exc.user_message or str(exc)}")

    await db.payment_orders.insert_one({
        "razorpay_order_id": f"stripe_{session.id}",  # unified index across providers
        "stripe_session_id": session.id,
        "user_id": user["id"], "kind": "subscription", "plan": payload.plan,
        "amount_paise": amount, "currency": currency.upper(),
        "country": country, "status": "created", "credited": False,
        "provider": "stripe", "created_at": session.created,
    })
    return {"url": session.url, "session_id": session.id}


@router.get("/payments/stripe/success", response_class=HTMLResponse)
async def stripe_success(session_id: str) -> str:
    """Verifies the session server-side and credits the user."""
    try:
        stripe.api_key = _stripe_key()
        session = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
    except stripe.error.StripeError:
        return HTMLResponse("<html><body><h3>Could not confirm session.</h3></body></html>", status_code=400)
    if session.payment_status not in ("paid", "no_payment_required"):
        return HTMLResponse("<html><body><h3>Payment not completed.</h3></body></html>", status_code=402)
    order = await db.payment_orders.find_one({"stripe_session_id": session_id}, {"_id": 0})
    if not order:
        return HTMLResponse("<html><body><h3>Order not found.</h3></body></html>", status_code=404)
    if not order.get("credited"):
        # Give the user unlimited scans while their subscription is active
        await db.payment_orders.update_one({"stripe_session_id": session_id},
                                           {"$set": {"credited": True, "status": "paid",
                                                     "stripe_subscription_id": session.subscription}})
        await db.entitlements.update_one(
            {"user_id": order["user_id"]},
            {"$set": {"subscribed": True, "subscription_plan": order.get("plan"),
                      "subscription_provider": "stripe",
                      "subscription_expires_at": None}},  # renewal controlled by Stripe
            upsert=True,
        )
    return HTMLResponse("""<!doctype html><html><body style="font-family:system-ui;text-align:center;padding:40px">
<h2 style="color:#2e7d32">Payment received</h2>
<p>Your VeriScan subscription is now active. You can close this window and return to the app.</p>
</body></html>""")


@router.get("/payments/stripe/cancelled", response_class=HTMLResponse)
async def stripe_cancelled() -> str:
    return """<!doctype html><html><body style="font-family:system-ui;text-align:center;padding:40px">
<h2>Payment cancelled</h2>
<p>You can close this window and return to VeriScan.</p>
</body></html>"""


@router.post("/admin/pricing/stripe/toggle")
async def admin_stripe_toggle(payload: Dict[str, Any], _: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    """Admin quick-toggle: enable Stripe with a monthly/yearly price for a country."""
    country = str(payload.get("country", "")).upper()
    if not country:
        raise HTTPException(400, "country required")
    monthly = float(payload.get("monthly", 0) or 0)
    yearly = float(payload.get("yearly", 0) or 0)
    if monthly < 0 or yearly < 0:
        raise HTTPException(400, "Prices must be non-negative")
    row = await db.country_pricing.find_one({"country": country}, {"_id": 0})
    if not row:
        raise HTTPException(404, "Country pricing row not found")
    await db.country_pricing.update_one(
        {"country": country},
        {"$set": {"provider": "stripe", "monthly": monthly, "yearly": yearly,
                  "monthly_regular": float(payload.get("monthly_regular", monthly * 2.5)),
                  "yearly_regular": float(payload.get("yearly_regular", yearly * 2.5))}},
    )
    return {"status": "updated"}
