"""VeriScan iteration 5 backend tests — Razorpay payments (IN/INR).

Covers:
- POST /api/payments/razorpay/order (intro/standard tiers, validation, auth)
- POST /api/payments/razorpay/verify (bad signature, valid HMAC signature, idempotency)
- GET  /api/payments/razorpay/checkout/{order_id} (HTML page, 404 unknown)
- POST /api/payments/razorpay/webhook (bad signature, payment.captured credit, event dedup)
"""
import hashlib
import hmac
import json
import os
import uuid

import pymongo
import pytest
import requests

# --- config -----------------------------------------------------------------
def _load_env(path):
    env = {}
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"')
    return env


_fe_env = _load_env("/app/frontend/.env")
_be_env = _load_env("/app/backend/.env")

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or _fe_env.get("EXPO_PUBLIC_BACKEND_URL")
).rstrip("/")

API = f"{BASE_URL}/api"
TIMEOUT = 60  # Razorpay API calls can be slow
RZ_KEY_SECRET = _be_env["RAZORPAY_KEY_SECRET"]
RZ_WEBHOOK_SECRET = _be_env["RAZORPAY_WEBHOOK_SECRET"]
MONGO_URL = _be_env.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = _be_env.get("DB_NAME", "test_database")


# --- fixtures ---------------------------------------------------------------
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


def _register(s, versions, prefix="rzpay"):
    email = f"{prefix}_{uuid.uuid4().hex[:10]}@example.com"
    tv, pv = versions
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "strongpass123",
        "accepted_terms_version": tv, "accepted_privacy_version": pv,
    }, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    return body["token"], body["user"]["id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _balance(mongo, user_id):
    doc = mongo.entitlements.find_one({"user_id": user_id}, {"_id": 0})
    return (doc or {}).get("purchased_balance", 0)


def _create_order(s, token, credits, tier):
    r = s.post(f"{API}/payments/razorpay/order",
               json={"credits": credits, "tier": tier},
               headers=_auth(token), timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    return r.json()


def _valid_signature(order_id, payment_id):
    msg = f"{order_id}|{payment_id}".encode()
    return hmac.new(RZ_KEY_SECRET.encode(), msg, hashlib.sha256).hexdigest()


# --- order creation ---------------------------------------------------------
class TestRazorpayOrder:
    """POST /api/payments/razorpay/order"""

    def test_order_intro_tier_amount(self, s, versions):
        token, _ = _register(s, versions, "rz_intro")
        body = _create_order(s, token, 10, "intro")
        assert body["amount"] == 5000, body  # ₹5 x 10 = 5000 paise
        assert body["currency"] == "INR"
        assert body["order_id"].startswith("order_")
        assert body["key_id"] == "rzp_test_TfYSkIrEHC3Shb"

    def test_order_standard_tier_amount(self, s, versions):
        token, _ = _register(s, versions, "rz_std")
        body = _create_order(s, token, 10, "standard")
        assert body["amount"] == 15000, body  # ₹15 x 10 = 15000 paise
        assert body["currency"] == "INR"
        assert body["order_id"].startswith("order_")

    def test_order_invalid_tier_422(self, s, versions):
        token, _ = _register(s, versions, "rz_badtier")
        r = s.post(f"{API}/payments/razorpay/order",
                   json={"credits": 10, "tier": "premium"},
                   headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 422, r.text

    def test_order_unauthenticated_401(self, s):
        r = s.post(f"{API}/payments/razorpay/order",
                   json={"credits": 10, "tier": "intro"}, timeout=TIMEOUT)
        assert r.status_code == 401, r.text


# --- verify endpoint --------------------------------------------------------
class TestRazorpayVerify:
    """POST /api/payments/razorpay/verify"""

    def test_verify_fake_signature_rejected_no_credit(self, s, versions, mongo):
        token, uid = _register(s, versions, "rz_fakesig")
        order = _create_order(s, token, 5, "intro")
        before = _balance(mongo, uid)
        r = s.post(f"{API}/payments/razorpay/verify", json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": "pay_fake123456",
            "razorpay_signature": "deadbeef" * 8,
        }, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 400, r.text
        assert _balance(mongo, uid) == before, "wallet must NOT be credited on bad signature"

    def test_verify_valid_signature_credits_wallet(self, s, versions, mongo):
        token, uid = _register(s, versions, "rz_goodsig")
        credits = 7
        order = _create_order(s, token, credits, "intro")
        pay_id = "pay_" + uuid.uuid4().hex[:14]
        sig = _valid_signature(order["order_id"], pay_id)
        before = _balance(mongo, uid)
        r = s.post(f"{API}/payments/razorpay/verify", json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": pay_id,
            "razorpay_signature": sig,
        }, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        assert _balance(mongo, uid) == before + credits

    def test_verify_replay_does_not_double_credit(self, s, versions, mongo):
        token, uid = _register(s, versions, "rz_replay")
        credits = 4
        order = _create_order(s, token, credits, "standard")
        pay_id = "pay_" + uuid.uuid4().hex[:14]
        sig = _valid_signature(order["order_id"], pay_id)
        payload = {"razorpay_order_id": order["order_id"],
                   "razorpay_payment_id": pay_id,
                   "razorpay_signature": sig}
        r1 = s.post(f"{API}/payments/razorpay/verify", json=payload,
                    headers=_auth(token), timeout=TIMEOUT)
        assert r1.status_code == 200, r1.text
        mid = _balance(mongo, uid)
        r2 = s.post(f"{API}/payments/razorpay/verify", json=payload,
                    headers=_auth(token), timeout=TIMEOUT)
        assert r2.status_code == 200, r2.text
        assert _balance(mongo, uid) == mid, "replay must NOT double-credit"


# --- hosted checkout page ---------------------------------------------------
class TestRazorpayCheckoutPage:
    """GET /api/payments/razorpay/checkout/{order_id}"""

    def test_checkout_page_renders_razorpay_script(self, s, versions):
        token, _ = _register(s, versions, "rz_checkout")
        order = _create_order(s, token, 3, "intro")
        r = s.get(f"{API}/payments/razorpay/checkout/{order['order_id']}", timeout=TIMEOUT)
        assert r.status_code == 200, r.text
        assert "text/html" in r.headers.get("content-type", "")
        assert "checkout.razorpay.com" in r.text
        assert "callback_url" in r.text
        assert order["order_id"] in r.text

    def test_checkout_unknown_order_404(self, s):
        r = s.get(f"{API}/payments/razorpay/checkout/order_nonexistent123", timeout=TIMEOUT)
        assert r.status_code == 404, r.text


# --- webhook ----------------------------------------------------------------
class TestRazorpayWebhook:
    """POST /api/payments/razorpay/webhook"""

    def _post_webhook(self, s, body: dict, event_id: str, sign_correctly=True):
        raw = json.dumps(body).encode()
        if sign_correctly:
            sig = hmac.new(RZ_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        else:
            sig = "badbad" * 10
        return s.post(f"{API}/payments/razorpay/webhook", data=raw,
                      headers={"Content-Type": "application/json",
                               "x-razorpay-signature": sig,
                               "x-razorpay-event-id": event_id},
                      timeout=TIMEOUT)

    def test_webhook_bad_signature_400(self, s):
        body = {"event": "payment.captured", "payload": {"payment": {"entity": {}}}}
        r = self._post_webhook(s, body, "evt_bad_" + uuid.uuid4().hex[:8], sign_correctly=False)
        assert r.status_code == 400, r.text

    def test_webhook_payment_captured_credits_once_and_dedupes(self, s, versions, mongo):
        token, uid = _register(s, versions, "rz_webhook")
        credits = 6
        order = _create_order(s, token, credits, "standard")
        pay_id = "pay_" + uuid.uuid4().hex[:14]
        event_id = "evt_" + uuid.uuid4().hex[:12]
        body = {
            "event": "payment.captured",
            "payload": {"payment": {"entity": {
                "id": pay_id, "order_id": order["order_id"],
                "amount": 9000, "currency": "INR", "status": "captured",
            }}},
        }
        before = _balance(mongo, uid)
        r1 = self._post_webhook(s, body, event_id)
        assert r1.status_code == 200 and r1.json().get("ok") is True, r1.text
        mid = _balance(mongo, uid)
        assert mid == before + credits, f"expected +{credits}, got {mid - before}"
        # duplicate event_id replay must not double-credit
        r2 = self._post_webhook(s, body, event_id)
        assert r2.status_code == 200, r2.text
        assert _balance(mongo, uid) == mid, "duplicate webhook event must NOT double-credit"
