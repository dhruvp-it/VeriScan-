"""VeriScan iteration 4 backend tests.

Covers T&C acceptance, admin RBAC, password reset OTP, support tickets,
misinformation reports, watchlist, better-for-you alternatives, multi-country
plans, admin pricing, promocodes and email masking.
"""
import os
import uuid
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
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"


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


def _new_email(prefix="test_iter4"):
    return f"{prefix}_{uuid.uuid4().hex[:10]}@example.com"


def _register(s, versions, email=None, password="strongpass123"):
    tv, pv = versions
    email = email or _new_email()
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": password,
        "accepted_terms_version": tv, "accepted_privacy_version": pv,
    }, timeout=TIMEOUT)
    return r, email


# ------------- 1. Legal endpoints -------------
def test_legal_terms(s):
    r = s.get(f"{API}/legal/terms", timeout=TIMEOUT)
    assert r.status_code == 200
    j = r.json()
    assert {"version", "effective", "content"} <= set(j.keys())
    assert len(j["content"]) > 1000


def test_legal_privacy(s):
    r = s.get(f"{API}/legal/privacy", timeout=TIMEOUT)
    assert r.status_code == 200
    j = r.json()
    assert {"version", "effective", "content"} <= set(j.keys())
    assert len(j["content"]) > 1000


# ------------- 2. Register T&C enforcement -------------
def test_register_rejects_missing_terms(s, versions):
    _, pv = versions
    r = s.post(f"{API}/auth/register", json={
        "email": _new_email(), "password": "strongpass123",
        "accepted_privacy_version": pv,
    }, timeout=TIMEOUT)
    assert r.status_code == 400


def test_register_rejects_mismatched_terms(s, versions):
    _, pv = versions
    r = s.post(f"{API}/auth/register", json={
        "email": _new_email(), "password": "strongpass123",
        "accepted_terms_version": "0.0.1", "accepted_privacy_version": pv,
    }, timeout=TIMEOUT)
    assert r.status_code == 400


def test_register_succeeds_with_tc(s, versions):
    r, email = _register(s, versions)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == email
    assert body["user"]["role"] == "user"
    assert body["token"]


# ------------- 3. Admin RBAC -------------
def test_admin_login_returns_admin_role(admin_token):
    assert admin_token  # login worked in fixture


def test_admin_overview(s, admin_token):
    r = s.get(f"{API}/admin/overview", headers={"Authorization": f"Bearer {admin_token}"}, timeout=TIMEOUT)
    assert r.status_code == 200
    j = r.json()
    for k in ("users", "suspended", "open_tickets", "open_reports", "products", "contributions_pending"):
        assert isinstance(j.get(k), int), f"{k} not int: {j}"


def test_admin_users_masked(s, admin_token, versions):
    _register(s, versions)  # ensure at least one user
    r = s.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, timeout=TIMEOUT)
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list) and len(users) > 0
    for u in users:
        assert "email_masked" in u
        assert "*" in u["email_masked"]
        assert "password_hash" not in u
        assert "email" not in u  # raw email must NOT be exposed


def test_non_admin_forbidden_on_admin(s, versions):
    reg, _ = _register(s, versions)
    tok = reg.json()["token"]
    for path in ("/admin/overview", "/admin/users", "/admin/pricing", "/admin/promocodes", "/admin/support", "/admin/reports"):
        r = s.get(f"{API}{path}", headers={"Authorization": f"Bearer {tok}"}, timeout=TIMEOUT)
        assert r.status_code == 403, f"{path} returned {r.status_code}"


# ------------- 4. Suspend / reactivate -------------
def test_suspend_and_reactivate_flow(s, admin_token, versions):
    reg, email = _register(s, versions)
    user_id = reg.json()["user"]["id"]
    auth = {"Authorization": f"Bearer {admin_token}"}

    susp = s.post(f"{API}/admin/users/{user_id}/suspend", json={"reason": "Test suspension"}, headers=auth, timeout=TIMEOUT)
    assert susp.status_code == 200

    bad_login = s.post(f"{API}/auth/login", json={"email": email, "password": "strongpass123"}, timeout=TIMEOUT)
    assert bad_login.status_code == 403

    react = s.post(f"{API}/admin/users/{user_id}/reactivate", headers=auth, timeout=TIMEOUT)
    assert react.status_code == 200

    good_login = s.post(f"{API}/auth/login", json={"email": email, "password": "strongpass123"}, timeout=TIMEOUT)
    assert good_login.status_code == 200
    assert good_login.json()["user"]["role"] == "user"


# ------------- 5. Password reset OTP -------------
def test_forgot_and_reset_password(s, mongo, versions):
    reg, email = _register(s, versions)
    assert reg.status_code == 200
    fp = s.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=TIMEOUT)
    assert fp.status_code == 200
    assert fp.json() == {"status": "sent"}

    doc = mongo.password_resets.find_one({"email": email}, sort=[("created_at", -1)])
    assert doc and doc.get("otp"), "OTP was not persisted"
    otp = doc["otp"]

    reset = s.post(f"{API}/auth/reset-password", json={
        "email": email, "otp": otp, "new_password": "newstrongpass123",
    }, timeout=TIMEOUT)
    assert reset.status_code == 200, reset.text

    # new password works
    ok = s.post(f"{API}/auth/login", json={"email": email, "password": "newstrongpass123"}, timeout=TIMEOUT)
    assert ok.status_code == 200
    # old password fails
    bad = s.post(f"{API}/auth/login", json={"email": email, "password": "strongpass123"}, timeout=TIMEOUT)
    assert bad.status_code == 401


def test_reset_invalid_otp(s, versions):
    reg, email = _register(s, versions)
    s.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=TIMEOUT)
    r = s.post(f"{API}/auth/reset-password", json={
        "email": email, "otp": "000000", "new_password": "anotherpass123",
    }, timeout=TIMEOUT)
    assert r.status_code == 400


def test_reset_expired_otp(s, mongo, versions):
    reg, email = _register(s, versions)
    otp = "999123"
    mongo.password_resets.insert_one({
        "email": email, "otp": otp,
        "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r = s.post(f"{API}/auth/reset-password", json={
        "email": email, "otp": otp, "new_password": "newerpass123",
    }, timeout=TIMEOUT)
    assert r.status_code == 400
    assert "expired" in (r.json().get("detail") or "").lower()


# ------------- 6. Support ticket -------------
def test_support_ticket_lifecycle(s, admin_token, versions):
    reg, email = _register(s, versions)
    tok = reg.json()["token"]
    user_auth = {"Authorization": f"Bearer {tok}"}
    admin_auth = {"Authorization": f"Bearer {admin_token}"}

    create = s.post(f"{API}/support", json={
        "subject": "TEST subject", "message": "This is a TEST support ticket message",
    }, headers=user_auth, timeout=TIMEOUT)
    assert create.status_code == 200
    tid = create.json()["id"]
    assert create.json()["status"] == "open"

    mine = s.get(f"{API}/support/mine", headers=user_auth, timeout=TIMEOUT)
    assert mine.status_code == 200
    assert any(t["id"] == tid for t in mine.json())

    # Admin listing shows masked email
    admin_list = s.get(f"{API}/admin/support", headers=admin_auth, timeout=TIMEOUT)
    assert admin_list.status_code == 200
    found = next((t for t in admin_list.json() if t["id"] == tid), None)
    assert found is not None
    assert "*" in (found.get("user_email") or "")

    upd = s.put(f"{API}/admin/support/{tid}", json={"status": "resolved", "admin_note": "done"},
                headers=admin_auth, timeout=TIMEOUT)
    assert upd.status_code == 200

    mine2 = s.get(f"{API}/support/mine", headers=user_auth, timeout=TIMEOUT).json()
    resolved = next(t for t in mine2 if t["id"] == tid)
    assert resolved["status"] == "resolved"


# ------------- 7. Reports -------------
def test_report_lifecycle(s, admin_token, versions):
    reg, _ = _register(s, versions)
    tok = reg.json()["token"]
    user_auth = {"Authorization": f"Bearer {tok}"}
    admin_auth = {"Authorization": f"Bearer {admin_token}"}

    r = s.post(f"{API}/reports", json={
        "barcode": "8901030895001", "reason": "Test misinformation report",
    }, headers=user_auth, timeout=TIMEOUT)
    assert r.status_code == 200
    rid = r.json()["id"]
    assert r.json()["status"] == "open"

    listed = s.get(f"{API}/admin/reports", params={"status": "open"}, headers=admin_auth, timeout=TIMEOUT)
    assert listed.status_code == 200
    assert any(rep["id"] == rid for rep in listed.json())

    upd = s.put(f"{API}/admin/reports/{rid}", json={"status": "resolved", "admin_note": "ok"},
                headers=admin_auth, timeout=TIMEOUT)
    assert upd.status_code == 200

    resolved = s.get(f"{API}/admin/reports", params={"status": "resolved"}, headers=admin_auth, timeout=TIMEOUT).json()
    assert any(rep["id"] == rid for rep in resolved)


# ------------- 8. Watchlist -------------
def test_watchlist_add_list_delete(s, versions):
    reg, _ = _register(s, versions)
    tok = reg.json()["token"]
    auth = {"Authorization": f"Bearer {tok}"}
    barcode = "8901030895001"

    add = s.post(f"{API}/watchlist/{barcode}", headers=auth, timeout=TIMEOUT)
    assert add.status_code == 200
    assert add.json()["status"] == "saved"

    listed = s.get(f"{API}/watchlist", headers=auth, timeout=TIMEOUT)
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["barcode"] == barcode
    assert items[0]["product"]["name"] == "Organic Rolled Oats"
    assert "overall_health_score" in items[0]["product"]

    rem = s.delete(f"{API}/watchlist/{barcode}", headers=auth, timeout=TIMEOUT)
    assert rem.status_code == 200
    assert s.get(f"{API}/watchlist", headers=auth, timeout=TIMEOUT).json() == []


# ------------- 9. Better-for-you alternatives -------------
def test_alternatives_oats(s):
    r = s.get(f"{API}/products/alternatives", params={"barcode": "8901030895001"}, timeout=TIMEOUT)
    assert r.status_code == 200
    alts = r.json()
    assert isinstance(alts, list) and len(alts) >= 1
    # The seeded Steel-Cut oats (8901030895002) should be present with higher score.
    steel = next((a for a in alts if a["barcode"] == "8901030895002"), None)
    assert steel is not None, f"expected steel-cut alternative, got {alts}"
    # Compare against the baseline oats score
    base = s.get(f"{API}/products/lookup", params={"barcode": "8901030895001"},
                 headers={"x-guest-id": f"iter4-alt-{uuid.uuid4().hex}"}, timeout=TIMEOUT).json()
    assert steel["overall_health_score"] > base["overall_health_score"]


# ------------- 10. Multi-country plans -------------
@pytest.mark.parametrize("country,currency,provider", [
    ("US", "USD", "stripe"),
    ("IN", "INR", "razorpay"),
    ("NZ", "NZD", "stripe"),
])
def test_plans_multi_country(s, country, currency, provider):
    r = s.get(f"{API}/plans", params={"country": country}, timeout=TIMEOUT)
    assert r.status_code == 200
    j = r.json()
    assert j["country"] == country
    assert j["currency"] == currency
    assert j["provider"] == provider
    assert len(j["subscriptions"]) == 2


# ------------- 11. Admin pricing -------------
def test_admin_pricing_list_and_update(s, admin_token):
    auth = {"Authorization": f"Bearer {admin_token}"}
    listed = s.get(f"{API}/admin/pricing", headers=auth, timeout=TIMEOUT)
    assert listed.status_code == 200
    countries = {row["country"] for row in listed.json()}
    assert {"IN", "US", "CA", "EU", "GB", "AE", "AU", "NZ"} <= countries

    # Update US monthly
    original = next(row for row in listed.json() if row["country"] == "US")
    new_monthly = 2.49
    payload = {**original, "monthly": new_monthly}
    payload.pop("country", None)
    payload["country"] = "US"
    upd = s.put(f"{API}/admin/pricing/US", json=payload, headers=auth, timeout=TIMEOUT)
    assert upd.status_code == 200

    plans = s.get(f"{API}/plans", params={"country": "US"}, timeout=TIMEOUT).json()
    monthly = next(p for p in plans["subscriptions"] if p["id"] == "monthly")
    assert monthly["price"] == new_monthly

    # Restore original
    restore = {**original}
    restore["country"] = "US"
    s.put(f"{API}/admin/pricing/US", json=restore, headers=auth, timeout=TIMEOUT)


# ------------- 12. Promocodes -------------
def test_admin_promocode_create_lookup_delete(s, admin_token, mongo):
    auth = {"Authorization": f"Bearer {admin_token}"}
    code = "WELCOME20"
    # Clean any previous state
    mongo.promocodes.delete_many({"code": code})

    create = s.post(f"{API}/admin/promocodes", json={
        "code": code, "kind": "percent", "value": 20,
    }, headers=auth, timeout=TIMEOUT)
    assert create.status_code == 200

    look = s.get(f"{API}/promocodes/{code}", timeout=TIMEOUT)
    assert look.status_code == 200
    assert look.json()["code"] == code
    assert look.json()["value"] == 20

    delete = s.delete(f"{API}/admin/promocodes/{code}", headers=auth, timeout=TIMEOUT)
    assert delete.status_code == 200

    gone = s.get(f"{API}/promocodes/{code}", timeout=TIMEOUT)
    assert gone.status_code == 404

    mongo.promocodes.delete_many({"code": code})
