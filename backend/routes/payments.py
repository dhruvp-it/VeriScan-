"""Payments — Razorpay (IN/INR), Stripe checkout (non-IN), plans, promocodes."""
import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from core.config import (
    DEFAULT_COUNTRY_PRICING, RAZORPAY_KEY_ID, RAZORPAY_WEBHOOK_SECRET, db, rp_client,
)
from core.deps import admin_user, authenticated_user, now_iso
from core.models import (
    AdminRefundIn, ProductBadgesIn, ProductMergeIn, RazorpayOrderIn,
    RazorpaySubscriptionIn, RazorpayVerifyIn, SubscriptionPurchase,
)
from core.pricing_logic import apply_promo, credit_if_new, india_price_paise
from legal_content import PRIVACY_VERSION, TERMS_VERSION

router = APIRouter()


@router.get("/plans")
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


@router.get("/promocodes/{code}")
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


@router.post("/payments/razorpay/subscription")
async def razorpay_subscription(payload: RazorpaySubscriptionIn, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Simplified subscription: creates a one-time Razorpay order priced for the
    chosen plan and marks the user as subscribed for 30 days (monthly) or 365
    days (yearly) on successful payment. Users are re-prompted at renewal.
    Full mandate-based auto-charge can be added later via Razorpay Subscriptions."""
    user = await authenticated_user(authorization)
    if not rp_client:
        raise HTTPException(503, "Razorpay is not configured")
    # Mandatory current-version T&C acceptance for any subscription checkout
    _terms_ok = (user.get("terms_accepted") or {}).get("version") == TERMS_VERSION
    _privacy_ok = (user.get("privacy_accepted") or {}).get("version") == PRIVACY_VERSION
    if not (_terms_ok and _privacy_ok):
        raise HTTPException(428, "TERMS_ACCEPTANCE_REQUIRED")
    field = "monthly" if payload.plan == "monthly" else "yearly"
    row = await db.country_pricing.find_one({"country": "IN"}, {"_id": 0})
    price = float((row or {}).get(field, 0))
    if price <= 0:
        raise HTTPException(409, "Subscription price is not configured")
    base_amount_paise = int(round(price * 100))
    promo_result = await apply_promo(base_amount_paise, payload.promo_code, "IN")
    amount_paise = promo_result["amount"]
    order = await asyncio.to_thread(rp_client.order.create, data={
        "amount": amount_paise, "currency": "INR",
        "receipt": "sub_" + uuid.uuid4().hex[:30],
        "notes": {"user_id": user["id"], "kind": "subscription", "plan": payload.plan,
                  "promo_code": (payload.promo_code or "").upper()},
    })
    await db.payment_orders.insert_one({
        "razorpay_order_id": order["id"], "user_id": user["id"], "kind": "subscription",
        "plan": payload.plan, "amount_paise": amount_paise,
        "base_amount_paise": base_amount_paise, "discount_paise": promo_result["discount"],
        "promo_code": (payload.promo_code or "").upper() or None,
        "credits": 0, "bonus_credits": 0,
        "status": "created", "credited": False, "created_at": time.time(),
    })
    return {
        "key_id": RAZORPAY_KEY_ID, "order_id": order["id"],
        "amount": amount_paise, "base_amount": base_amount_paise,
        "discount": promo_result["discount"], "currency": "INR",
        "description": f"VeriScan {payload.plan} subscription",
    }


@router.post("/promocodes/preview")
async def promocode_preview(body: Dict[str, Any]) -> Dict[str, Any]:
    """Public preview endpoint — returns discount + final amount for a given
    base_paise + code without creating an order."""
    code = str(body.get("code", "")).strip()
    base = int(body.get("base_paise", 0))
    country = str(body.get("country", "IN")).upper()
    if base <= 0:
        raise HTTPException(400, "Invalid base amount")
    result = await apply_promo(base, code, country)
    return {
        "amount": result["amount"], "discount": result["discount"],
        "bonus_credits": result.get("bonus_credits", 0),
        "kind": (result.get("promo") or {}).get("kind"),
    }


# ---------------------------------------------------------------------------
# Admin: refunds & merges
# ---------------------------------------------------------------------------
@router.post("/admin/refund")
async def admin_refund(payload: AdminRefundIn, admin: Dict[str, Any] = Depends(admin_user)) -> Dict[str, Any]:
    if not rp_client:
        raise HTTPException(503, "Razorpay is not configured")
    order = await db.payment_orders.find_one({"razorpay_payment_id": payload.payment_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Payment not found")
    if order.get("refunded"):
        raise HTTPException(409, "Already refunded")
    try:
        refund = await asyncio.to_thread(
            rp_client.payment.refund, payload.payment_id, {"speed": "normal", "notes": {"reason": payload.reason}},
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Razorpay refund failed: {exc}")
    # Reverse the credit — but never below zero
    total_credits = int(order.get("credits", 0)) + int(order.get("bonus_credits", 0))
    if total_credits and order.get("kind") == "scan_credits":
        await db.entitlements.update_one(
            {"user_id": order["user_id"], "purchased_balance": {"$gte": total_credits}},
            {"$inc": {"purchased_balance": -total_credits}},
        )
    if order.get("kind") == "subscription":
        await db.entitlements.update_one(
            {"user_id": order["user_id"]},
            {"$set": {"subscribed": False}, "$unset": {"subscription_expires_at": ""}},
        )
    await db.payment_orders.update_one(
        {"razorpay_order_id": order["razorpay_order_id"]},
        {"$set": {"refunded": True, "refund_id": refund.get("id"), "refund_reason": payload.reason,
                  "refunded_at": now_iso()}},
    )
    # Auto-open a support ticket so the user is notified
    ticket = {
        "id": str(uuid.uuid4()), "user_id": order["user_id"], "user_email": None,
        "subject": "Your payment has been refunded",
        "message": f"Payment {payload.payment_id} was refunded by our team. Reason: {payload.reason}. "
                   f"Refund ID: {refund.get('id')}. Please allow 5–7 business days for the amount to reflect.",
        "category": "billing", "status": "resolved",
        "admin_note": f"Refund initiated by admin {admin['email']}. Razorpay refund_id: {refund.get('id')}.",
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.support_tickets.insert_one(ticket.copy())
    return {"refund_id": refund.get("id"), "status": refund.get("status", "processed"), "ticket_id": ticket["id"]}


@router.get("/admin/payments")
async def admin_payments(admin: Dict[str, Any] = Depends(admin_user), limit: int = 100) -> Any:
    _ = admin
    return await db.payment_orders.find({"credited": True}, {"_id": 0}).sort("created_at", -1).to_list(limit)


@router.get("/admin/duplicates")
async def admin_duplicates(admin: Dict[str, Any] = Depends(admin_user)) -> Any:
    _ = admin
    # Exact-match clusters via aggregation
    pipeline = [
        {"$match": {"status": {"$ne": "merged"}}},
        {"$group": {"_id": {"name": {"$toLower": "$name"}, "brand": {"$toLower": "$brand"}},
                    "products": {"$push": {"barcode": "$barcode", "name": "$name", "brand": "$brand",
                                             "category": "$category", "source": "$source",
                                             "status": "$status", "image_url": "$image_url"}},
                    "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 50},
    ]
    exact = await db.products.aggregate(pipeline).to_list(50)
    for cluster in exact:
        cluster["kind"] = "exact"; cluster["confidence"] = 100

    # Fuzzy-match suggestions using RapidFuzz token-set ratio on brand+name
    try:
        from rapidfuzz import fuzz, process as fuzz_process  # noqa: PLC0415
    except ImportError:
        return exact

    all_products = await db.products.find(
        {"status": {"$ne": "merged"}, "deleted_at": {"$exists": False}},
        {"_id": 0, "barcode": 1, "name": 1, "brand": 1, "category": 1, "image_url": 1, "source": 1, "status": 1},
    ).to_list(2000)
    # Skip barcodes already in exact clusters
    exact_barcodes: set = set()
    for cluster in exact:
        for prod in cluster["products"]:
            exact_barcodes.add(prod["barcode"])
    remaining = [p for p in all_products if p["barcode"] not in exact_barcodes]

    def _key(p: Dict[str, Any]) -> str:
        return f"{(p.get('brand') or '').strip()} {(p.get('name') or '').strip()}".strip().lower()

    keys = [_key(p) for p in remaining]
    seen: set = set()
    fuzzy_clusters: List[Dict[str, Any]] = []
    for idx, product in enumerate(remaining):
        if product["barcode"] in seen or not keys[idx]:
            continue
        matches = fuzz_process.extract(keys[idx], keys, scorer=fuzz.token_set_ratio, limit=6, score_cutoff=82)
        cluster_members = []
        for _match_string, score, match_idx in matches:
            if match_idx == idx:
                cluster_members.append({**remaining[match_idx], "match_score": 100})
                continue
            if remaining[match_idx]["barcode"] in seen:
                continue
            if remaining[match_idx].get("category") and product.get("category") \
                    and remaining[match_idx]["category"] != product["category"]:
                continue
            cluster_members.append({**remaining[match_idx], "match_score": int(score)})
        if len(cluster_members) > 1:
            for member in cluster_members:
                seen.add(member["barcode"])
            avg = int(sum(m["match_score"] for m in cluster_members if m["match_score"] < 100) /
                      max(1, len([m for m in cluster_members if m["match_score"] < 100])))
            fuzzy_clusters.append({
                "_id": {"name": product.get("name", ""), "brand": product.get("brand", "")},
                "products": cluster_members, "count": len(cluster_members),
                "kind": "fuzzy", "confidence": avg,
            })
    fuzzy_clusters.sort(key=lambda c: (c["confidence"], c["count"]), reverse=True)
    return exact + fuzzy_clusters[:25]


@router.post("/admin/products/merge")
async def admin_merge(payload: ProductMergeIn, admin: Dict[str, Any] = Depends(admin_user)) -> Dict[str, Any]:
    _ = admin
    primary = await db.products.find_one({"barcode": payload.primary_barcode}, {"_id": 0})
    if not primary:
        raise HTTPException(404, "Primary product not found")
    merged = 0
    for dup in payload.duplicate_barcodes:
        if dup == payload.primary_barcode:
            continue
        # Point watchlist, history, contributions, reports at the primary barcode
        await db.watchlist.update_many({"barcode": dup}, {"$set": {"barcode": payload.primary_barcode}})
        await db.reports.update_many({"barcode": dup}, {"$set": {"barcode": payload.primary_barcode}})
        await db.history.update_many({"product.barcode": dup}, {"$set": {"product.barcode": payload.primary_barcode}})
        await db.contributions.update_many({"barcode": dup}, {"$set": {"barcode": payload.primary_barcode}})
        # Soft-delete the duplicate product record (don't hard-delete)
        result = await db.products.update_one(
            {"barcode": dup},
            {"$set": {"deleted_at": now_iso(), "merged_into": payload.primary_barcode, "status": "merged"}},
        )
        merged += result.matched_count
    return {"merged": merged, "primary_barcode": payload.primary_barcode}


@router.put("/admin/products/{barcode}/badges")
async def admin_product_badges(barcode: str, payload: ProductBadgesIn, admin: Dict[str, Any] = Depends(admin_user)) -> Dict[str, str]:
    _ = admin
    update: Dict[str, Any] = {"badges_extra": payload.badges_extra}
    if payload.badges_override is not None:
        update["badges_override"] = payload.badges_override
    result = await db.products.update_one({"barcode": barcode}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Product not found")
    return {"status": "updated"}


@router.post("/payments/razorpay/order")
async def razorpay_order(payload: RazorpayOrderIn, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization)
    if not rp_client:
        raise HTTPException(503, "Razorpay is not configured")
    # Mandatory current-version T&C acceptance for scan credit purchases
    _terms_ok2 = (user.get("terms_accepted") or {}).get("version") == TERMS_VERSION
    _privacy_ok2 = (user.get("privacy_accepted") or {}).get("version") == PRIVACY_VERSION
    if not (_terms_ok2 and _privacy_ok2):
        raise HTTPException(428, "TERMS_ACCEPTANCE_REQUIRED")
    field = "scan_intro" if payload.tier == "intro" else "scan_standard"
    unit_paise = await india_price_paise(field)
    base_amount_paise = unit_paise * payload.credits
    promo_result = await apply_promo(base_amount_paise, payload.promo_code, "IN")
    amount_paise = promo_result["amount"]
    bonus_credits = promo_result.get("bonus_credits", 0)
    order = await asyncio.to_thread(rp_client.order.create, data={
        "amount": amount_paise, "currency": "INR",
        "receipt": "scan_" + uuid.uuid4().hex[:30],
        "notes": {"user_id": user["id"], "kind": "scan_credits", "credits": str(payload.credits),
                  "tier": payload.tier, "promo_code": (payload.promo_code or "").upper(),
                  "bonus_credits": str(bonus_credits)},
    })
    await db.payment_orders.insert_one({
        "razorpay_order_id": order["id"], "user_id": user["id"], "kind": "scan_credits",
        "credits": payload.credits, "bonus_credits": bonus_credits, "amount_paise": amount_paise,
        "base_amount_paise": base_amount_paise, "discount_paise": promo_result["discount"],
        "promo_code": (payload.promo_code or "").upper() or None,
        "status": "created", "credited": False, "created_at": time.time(),
    })
    return {
        "key_id": RAZORPAY_KEY_ID, "order_id": order["id"],
        "amount": amount_paise, "base_amount": base_amount_paise,
        "discount": promo_result["discount"], "bonus_credits": bonus_credits,
        "currency": "INR",
        "description": f"{payload.credits} VeriScan credit{'s' if payload.credits > 1 else ''}",
    }


@router.post("/payments/razorpay/verify")
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


@router.get("/payments/razorpay/checkout/{order_id}", response_class=HTMLResponse)
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


@router.get("/payments/razorpay/cancelled", response_class=HTMLResponse)
async def razorpay_cancelled() -> str:
    return """<!doctype html><html><body style="font-family:system-ui;text-align:center;padding:40px">
<h2>Payment cancelled</h2>
<p>You can close this window and return to VeriScan.</p>
</body></html>"""


@router.post("/payments/razorpay/callback")
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


@router.post("/payments/razorpay/webhook")
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


@router.post("/payments/subscription-session")
async def subscription_session(payload: SubscriptionPurchase, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization)
    if payload.plan not in {"monthly", "yearly"}:
        raise HTTPException(400, "Invalid subscription plan")
    if not os.environ.get("STRIPE_SECRET_KEY") and not os.environ.get("STRIPE_API_KEY"):
        raise HTTPException(503, "Payments are not configured yet")
    price_id = os.environ.get("STRIPE_MONTHLY_PRICE_ID" if payload.plan == "monthly" else "STRIPE_YEARLY_PRICE_ID")
    if not price_id:
        raise HTTPException(503, "Subscription prices are not configured yet")
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ["STRIPE_API_KEY"]
    session = stripe.checkout.Session.create(
        mode="subscription", line_items=[{"price": price_id, "quantity": 1}],
        success_url=os.environ.get("STRIPE_CHECKOUT_SUCCESS_URL", "https://example.com/success"),
        cancel_url=os.environ.get("STRIPE_CHECKOUT_CANCEL_URL", "https://example.com/cancel"),
        metadata={"user_id": user["id"], "plan": payload.plan},
    )
    return {"url": session.url, "sessionId": session.id}
