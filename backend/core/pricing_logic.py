"""Promo validation, India pricing, and post-payment crediting."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException

from core.config import db


async def apply_promo(amount_paise: int, code: Optional[str], country: str = "IN") -> Dict[str, Any]:
    """Validate a promo code against the same rules as the public lookup and
    return {new_amount, promo_applied, discount_paise}. Increments the promo's
    redemption counter if applied."""
    if not code:
        return {"amount": amount_paise, "promo": None, "discount": 0}
    now = datetime.now(timezone.utc)
    promo = await db.promocodes.find_one({"code": code.upper(), "active": True}, {"_id": 0})
    if not promo:
        raise HTTPException(400, "That promo code isn't valid.")
    if promo.get("expires_at"):
        try:
            if datetime.fromisoformat(promo["expires_at"]) < now:
                raise HTTPException(410, "That promo code has expired.")
        except ValueError:
            pass
    if promo.get("redemptions", 0) >= promo.get("max_redemptions", 100):
        raise HTTPException(410, "That promo code is fully redeemed.")
    if promo.get("countries") and country.upper() not in promo["countries"]:
        raise HTTPException(400, "That promo code isn't available in your region.")
    kind = promo["kind"]; value = float(promo["value"])
    discount = 0
    if kind == "percent":
        discount = int(round(amount_paise * (value / 100.0)))
    elif kind == "flat":
        discount = int(round(value * 100))  # value is in rupees, convert to paise
    elif kind == "free_scans":
        # For free_scans codes, applied on the wallet directly at verify time.
        return {"amount": amount_paise, "promo": promo, "discount": 0, "bonus_credits": int(value)}
    else:
        discount = 0
    new_amount = max(100, amount_paise - discount)  # never below ₹1 (Razorpay min)
    return {"amount": new_amount, "promo": promo, "discount": amount_paise - new_amount}


async def redeem_promo(promo: Optional[Dict[str, Any]]) -> None:
    if not promo:
        return
    await db.promocodes.update_one({"code": promo["code"]}, {"$inc": {"redemptions": 1}})


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
        total_credits = int(order.get("credits", 0)) + int(order.get("bonus_credits", 0))
        if total_credits:
            await db.entitlements.update_one(
                {"user_id": order["user_id"]},
                {"$inc": {"purchased_balance": total_credits}}, upsert=True,
            )
        if order.get("promo_code"):
            await db.promocodes.update_one({"code": order["promo_code"]}, {"$inc": {"redemptions": 1}})
        if order.get("kind") == "subscription":
            months = 1 if order.get("plan") == "monthly" else 12
            expires = datetime.now(timezone.utc) + timedelta(days=30 * months)
            await db.entitlements.update_one(
                {"user_id": order["user_id"]},
                {"$set": {"subscribed": True, "subscription_plan": order.get("plan"),
                          "subscription_expires_at": expires.isoformat()}},
                upsert=True,
            )
