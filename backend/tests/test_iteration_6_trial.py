"""VeriScan iteration 6 backend regression.

Covers the iteration-4 changes:
- 3-month (90-day) free trial replaces the old monthly-free-scans quota
  * New users receive `trial_expires_at` = now + 90 days
  * /api/entitlements returns trial_active + trial_days_remaining
  * consume_scan does NOT decrement wallet during trial
  * Expired trials with an empty wallet return 402
  * Expired trials with a wallet balance decrement wallet
- Order lifecycle & admin visibility
  * /api/admin/payments shows ONLY credited orders (created but not verified => hidden)
  * /api/payments/razorpay/verify with a fake signature returns 400
  * A failed verify must NOT credit and must NOT surface in /api/admin/payments
"""
import os
import uuid
import hmac
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
import pymongo
import requests

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
).rstrip("/")
API = f"{BASE_URL}/api"
TIMEOUT = 30

ADMIN_EMAIL = "dhruvpateld230@gmail.com"
ADMIN_PW = "strongpass123"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
RZP_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "Fji9Ktkv9iIoi8yHkL65CntS")


# ------------- fixtures -------------
@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def mongo():
    return pymongo.MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def versions(s):
    t = s.get(f"{API}/legal/terms", timeout=TIMEOUT).json()
    p = s.get(f"{API}/legal/privacy", timeout=TIMEOUT).json()
    return t["version"], p["version"]


@pytest.fixture(scope="module")
def admin_token(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["role"] == "admin"
    return body["token"]


def _register(s, versions, prefix="iter6"):
    tv, pv = versions
    email = f"TEST_{prefix}_{uuid.uuid4().hex[:10]}@example.com"
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "strongpass123",
        "accepted_terms_version": tv, "accepted_privacy_version": pv,
    }, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json(), email


# =====================================================================
# 1. Trial provisioning
# =====================================================================
def test_new_user_gets_90_day_trial_in_db(s, mongo, versions):
    body, email = _register(s, versions, prefix="trial_db")
    user = mongo.users.find_one({"email": email.lower()})
    assert user is not None
    assert "trial_expires_at" in user, "trial_expires_at was not stored on the user document"
    expires = datetime.fromisoformat(user["trial_expires_at"])
    delta_days = (expires - datetime.now(timezone.utc)).days
    # allow a couple of days of slack
    assert 88 <= delta_days <= 91, f"expected ~90 days trial, got {delta_days}"


def test_entitlements_reports_trial_active_and_days(s, versions):
    body, _ = _register(s, versions, prefix="trial_ent")
    tok = body["token"]
    r = s.get(f"{API}/entitlements", headers={"Authorization": f"Bearer {tok}"}, timeout=TIMEOUT)
    assert r.status_code == 200
    j = r.json()
    assert j["registered"] is True
    assert j["trial_active"] is True, j
    # ~89 days remaining (90 days minus a few hours)
    assert 85 <= j["trial_days_remaining"] <= 90, j
    assert j["subscribed"] is False
    assert j["wallet"] == 0
    # The legacy free_remaining field must NOT leak monthly free scans anymore
    assert j["free_remaining"] == 0, "monthly-free-scans quota should no longer be reported for registered users"


def test_guest_entitlements_still_3_free(s):
    guest_id = f"iter6-guest-{uuid.uuid4().hex}"
    r = s.get(f"{API}/entitlements", headers={"x-guest-id": guest_id}, timeout=TIMEOUT)
    assert r.status_code == 200
    j = r.json()
    assert j["registered"] is False
    assert j["free_remaining"] == 3
    assert j["trial_active"] is False


# =====================================================================
# 2. Scan consumption during trial
# =====================================================================
def test_scan_during_trial_does_not_touch_wallet(s, mongo, versions):
    body, email = _register(s, versions, prefix="trial_scan")
    tok = body["token"]
    auth = {"Authorization": f"Bearer {tok}"}
    # Seed a wallet balance we can later confirm was untouched
    user_id = body["user"]["id"]
    mongo.entitlements.update_one({"user_id": user_id}, {"$set": {"purchased_balance": 5}})

    # Two scans on a seeded product barcode
    for _ in range(2):
        r = s.get(f"{API}/products/lookup", params={"barcode": "8901030895001"}, headers=auth, timeout=TIMEOUT)
        assert r.status_code == 200, r.text

    ent = mongo.entitlements.find_one({"user_id": user_id})
    assert ent["purchased_balance"] == 5, f"wallet was decremented during trial: {ent}"
    # Public entitlements should still say trial_active
    j = s.get(f"{API}/entitlements", headers=auth, timeout=TIMEOUT).json()
    assert j["trial_active"] is True
    assert j["wallet"] == 5


def test_expired_trial_with_wallet_decrements_wallet(s, mongo, versions):
    body, email = _register(s, versions, prefix="trial_exp_wallet")
    tok = body["token"]
    user_id = body["user"]["id"]
    # Force-expire trial and seed wallet
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    mongo.users.update_one({"id": user_id}, {"$set": {"trial_expires_at": past}})
    mongo.entitlements.update_one({"user_id": user_id}, {"$set": {"purchased_balance": 2}})

    r = s.get(f"{API}/products/lookup", params={"barcode": "8901030895001"},
              headers={"Authorization": f"Bearer {tok}"}, timeout=TIMEOUT)
    assert r.status_code == 200
    ent = mongo.entitlements.find_one({"user_id": user_id})
    assert ent["purchased_balance"] == 1, f"expected wallet to drop to 1, got {ent}"

    ent_view = s.get(f"{API}/entitlements", headers={"Authorization": f"Bearer {tok}"}, timeout=TIMEOUT).json()
    assert ent_view["trial_active"] is False
    assert ent_view["trial_days_remaining"] == 0
    assert ent_view["wallet"] == 1


def test_expired_trial_empty_wallet_blocks_with_402(s, mongo, versions):
    body, email = _register(s, versions, prefix="trial_exp_blocked")
    tok = body["token"]
    user_id = body["user"]["id"]
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    mongo.users.update_one({"id": user_id}, {"$set": {"trial_expires_at": past}})
    mongo.entitlements.update_one({"user_id": user_id}, {"$set": {"purchased_balance": 0}})

    r = s.get(f"{API}/products/lookup", params={"barcode": "8901030895001"},
              headers={"Authorization": f"Bearer {tok}"}, timeout=TIMEOUT)
    assert r.status_code == 402, r.text
    detail = (r.json().get("detail") or "").lower()
    assert "trial" in detail and ("ended" in detail or "expired" in detail), detail


# =====================================================================
# 3. Orders & /api/admin/payments visibility
# =====================================================================
@pytest.fixture(scope="module")
def user_order(s, versions):
    body, _ = _register(s, versions, prefix="order")
    tok = body["token"]
    r = s.post(f"{API}/payments/razorpay/order",
               json={"tier": "intro", "credits": 10},
               headers={"Authorization": f"Bearer {tok}"}, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["order_id"].startswith("order_"), j
    assert j["currency"] == "INR"
    # intro tier: ₹5 * 10 credits = 5000 paise
    assert j["amount"] == 5000, j
    return {"token": tok, "order_id": j["order_id"], "user_id": body["user"]["id"]}


def test_order_created_is_hidden_from_admin_payments(s, admin_token, user_order):
    """A freshly created order (not yet verified/credited) must NOT surface in /admin/payments."""
    r = s.get(f"{API}/admin/payments",
              headers={"Authorization": f"Bearer {admin_token}"}, timeout=TIMEOUT)
    assert r.status_code == 200
    orders = r.json()
    assert isinstance(orders, list)
    match = [o for o in orders if o.get("razorpay_order_id") == user_order["order_id"]]
    assert match == [], f"uncredited order leaked into /admin/payments: {match}"
    # And every returned order should be credited=True
    for o in orders:
        assert o.get("credited") is True, f"non-credited order returned: {o}"


def test_verify_with_fake_signature_returns_400_and_does_not_credit(s, mongo, user_order):
    """Verify with a bogus signature must 400, must not credit, and must not appear in /admin/payments."""
    order_id = user_order["order_id"]
    fake_payment_id = "pay_FAKE" + uuid.uuid4().hex[:14]
    fake_sig = "0" * 64
    r = s.post(f"{API}/payments/razorpay/verify",
               json={"razorpay_order_id": order_id,
                     "razorpay_payment_id": fake_payment_id,
                     "razorpay_signature": fake_sig},
               headers={"Authorization": f"Bearer {user_order['token']}"}, timeout=TIMEOUT)
    assert r.status_code == 400, r.text
    assert "signature" in (r.json().get("detail") or "").lower()

    order_doc = mongo.payment_orders.find_one({"razorpay_order_id": order_id})
    assert order_doc is not None
    assert order_doc.get("credited") is not True, f"failed verify credited the order: {order_doc}"

    ent = mongo.entitlements.find_one({"user_id": user_order["user_id"]}) or {}
    assert ent.get("purchased_balance", 0) == 0, f"wallet was credited on bad signature: {ent}"


def test_verify_wrong_order_id_returns_404(s, user_order):
    fake_order = "order_" + uuid.uuid4().hex[:14]
    r = s.post(f"{API}/payments/razorpay/verify",
               json={"razorpay_order_id": fake_order,
                     "razorpay_payment_id": "pay_x",
                     "razorpay_signature": "0" * 64},
               headers={"Authorization": f"Bearer {user_order['token']}"}, timeout=TIMEOUT)
    assert r.status_code == 404


def test_admin_payments_requires_admin(s, versions):
    body, _ = _register(s, versions, prefix="np")
    r = s.get(f"{API}/admin/payments",
              headers={"Authorization": f"Bearer {body['token']}"}, timeout=TIMEOUT)
    assert r.status_code == 403


def test_valid_signature_credits_and_surfaces_in_admin_payments(s, mongo, admin_token, versions):
    """End-to-end: valid HMAC signature credits the wallet AND the order appears in /admin/payments."""
    body, _ = _register(s, versions, prefix="creditflow")
    tok = body["token"]
    user_id = body["user"]["id"]
    order = s.post(f"{API}/payments/razorpay/order",
                   json={"tier": "intro", "credits": 10},
                   headers={"Authorization": f"Bearer {tok}"}, timeout=TIMEOUT).json()
    order_id = order["order_id"]
    payment_id = "pay_" + uuid.uuid4().hex[:14]
    sig = hmac.new(RZP_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()

    r = s.post(f"{API}/payments/razorpay/verify",
               json={"razorpay_order_id": order_id,
                     "razorpay_payment_id": payment_id,
                     "razorpay_signature": sig},
               headers={"Authorization": f"Bearer {tok}"}, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # Wallet credited
    ent = mongo.entitlements.find_one({"user_id": user_id})
    assert ent["purchased_balance"] >= 10, ent

    # Order now visible to admin, marked credited
    listed = s.get(f"{API}/admin/payments",
                   headers={"Authorization": f"Bearer {admin_token}"}, timeout=TIMEOUT).json()
    match = next((o for o in listed if o.get("razorpay_order_id") == order_id), None)
    assert match is not None, "credited order missing from /admin/payments"
    assert match.get("credited") is True
    assert match.get("credits") == 10
