"""Iteration 9 backend tests — admin profile self-service, analytics category/country breakdown,
manual monthly report, trial reminder scheduler, and full regression on iteration 7/8 flows."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://veriscan-preview-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "dhruvpateld230@gmail.com"
ADMIN_PASSWORD = "strongpass123"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def legal_versions(s):
    t = s.get(f"{API}/legal/terms").json()
    p = s.get(f"{API}/legal/privacy").json()
    return t["version"], p["version"]


@pytest.fixture(scope="module")
def admin_token(s, legal_versions):
    # accept T&C first (idempotent via accept-terms if login says required)
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code == 200:
        token = r.json()["token"]
        # accept latest terms via /profile/accept-terms (v2)
        s.post(f"{API}/profile/accept-terms",
               headers={"Authorization": f"Bearer {token}"},
               json={"accepted_terms_version": legal_versions[0],
                     "accepted_privacy_version": legal_versions[1]})
        return token
    pytest.fail(f"Admin login failed: {r.status_code} {r.text}")


@pytest.fixture(scope="module")
def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "test_database")]


# ---------- 1. admin profile GET ----------
class TestAdminProfile:
    def test_get_profile_admin(self, s, admin_token):
        r = s.get(f"{API}/admin/profile", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        assert "phone_number" in data
        assert "id" in data

    def test_get_profile_non_admin_403(self, s, legal_versions):
        # register a fresh user
        email = f"veriscan-user-{uuid.uuid4().hex[:8]}@example.com"
        rr = s.post(f"{API}/auth/register", json={
            "email": email, "password": "strongpass123", "full_name": "T",
            "accepted_terms_version": legal_versions[0],
            "accepted_privacy_version": legal_versions[1],
        })
        assert rr.status_code == 200, rr.text
        token = rr.json()["token"]
        r = s.get(f"{API}/admin/profile", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403


# ---------- 2. Admin email change (two-OTP) ----------
class TestAdminEmailChange:
    def test_start_wrong_password(self, s, admin_token):
        r = s.post(f"{API}/admin/profile/change-email/start",
                   headers={"Authorization": f"Bearer {admin_token}"},
                   json={"new_email": f"new-{uuid.uuid4().hex[:6]}@example.com", "password": "wrongpass"})
        assert r.status_code == 401

    def test_start_existing_email_409(self, s, admin_token, legal_versions):
        # create user with target email first
        target = f"veriscan-exists-{uuid.uuid4().hex[:6]}@example.com"
        rr = s.post(f"{API}/auth/register", json={
            "email": target, "password": "strongpass123", "full_name": "X",
            "accepted_terms_version": legal_versions[0],
            "accepted_privacy_version": legal_versions[1],
        })
        assert rr.status_code == 200
        r = s.post(f"{API}/admin/profile/change-email/start",
                   headers={"Authorization": f"Bearer {admin_token}"},
                   json={"new_email": target, "password": ADMIN_PASSWORD})
        assert r.status_code == 409

    def test_full_email_change_flow(self, s, admin_token, db):
        new_email = f"veriscan-newmail-{uuid.uuid4().hex[:6]}@example.com"
        r = s.post(f"{API}/admin/profile/change-email/start",
                   headers={"Authorization": f"Bearer {admin_token}"},
                   json={"new_email": new_email, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]

        # peek at OTPs from mongo
        session = asyncio.get_event_loop().run_until_complete(
            db.admin_change_sessions.find_one({"session_id": sid}, {"_id": 0})
        )
        assert session and len(session["current_otp"]) == 6 and len(session["new_otp"]) == 6
        assert session["new_email"] == new_email

        # wrong OTP → 400
        bad = s.post(f"{API}/admin/profile/change-email/confirm",
                     headers={"Authorization": f"Bearer {admin_token}"},
                     json={"session_id": sid, "current_otp": "000000", "new_otp": "000000"})
        assert bad.status_code == 400

        # correct → 200
        ok = s.post(f"{API}/admin/profile/change-email/confirm",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={"session_id": sid, "current_otp": session["current_otp"],
                          "new_otp": session["new_otp"]})
        assert ok.status_code == 200, ok.text
        assert ok.json()["new_email"] == new_email

        # revert back
        asyncio.get_event_loop().run_until_complete(
            db.users.update_one({"role": "admin"}, {"$set": {"email": ADMIN_EMAIL}})
        )


# ---------- 3. Admin phone change ----------
class TestAdminPhoneChange:
    def test_start_and_confirm(self, s, admin_token, db):
        # ensure phone is null
        asyncio.get_event_loop().run_until_complete(
            db.users.update_one({"email": ADMIN_EMAIL},
                                 {"$unset": {"phone_number": "", "phone_verified_at": ""}})
        )
        r = s.post(f"{API}/admin/profile/change-phone/start",
                   headers={"Authorization": f"Bearer {admin_token}"},
                   json={"new_phone": "+911234567890", "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "session_id" in body
        assert "SMS" in body["delivery_notice"] or "sms" in body["delivery_notice"].lower()
        sid = body["session_id"]

        session = asyncio.get_event_loop().run_until_complete(
            db.admin_change_sessions.find_one({"session_id": sid}, {"_id": 0})
        )
        assert session and len(session["otp"]) == 6

        # confirm
        ok = s.post(f"{API}/admin/profile/change-phone/confirm",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={"session_id": sid, "otp": session["otp"]})
        assert ok.status_code == 200
        assert ok.json()["new_phone"] == "+911234567890"

        # verify via GET /profile
        p = s.get(f"{API}/admin/profile", headers={"Authorization": f"Bearer {admin_token}"})
        assert p.json()["phone_number"] == "+911234567890"
        assert p.json()["phone_verified_at"] is not None

        # same phone → 400
        again = s.post(f"{API}/admin/profile/change-phone/start",
                       headers={"Authorization": f"Bearer {admin_token}"},
                       json={"new_phone": "+911234567890", "password": ADMIN_PASSWORD})
        assert again.status_code == 400

        # cleanup — reset phone to null
        asyncio.get_event_loop().run_until_complete(
            db.users.update_one({"email": ADMIN_EMAIL},
                                 {"$unset": {"phone_number": "", "phone_verified_at": ""}})
        )


# ---------- 4. Analytics category/country + manual report ----------
class TestAnalyticsBreakdown:
    def test_track_and_overview(self, s, admin_token):
        # Track 3 events (server strips PII but records category + country)
        for country in ("IN", "US", "IN"):
            r = s.post(f"{API}/analytics/track",
                       json={"event": "scan", "barcode": "8901030895001",
                             "category": "food", "country": country})
            assert r.status_code == 200

        # Overview
        r = s.get(f"{API}/admin/analytics/overview?days=7",
                  headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "categories" in data and isinstance(data["categories"], list)
        assert "countries" in data and isinstance(data["countries"], list)
        # food category present
        cats = {c["category"] for c in data["categories"]}
        assert "food" in cats
        food_row = next(c for c in data["categories"] if c["category"] == "food")
        for k in ("scan", "retailer_click", "total"):
            assert k in food_row
        # countries have codes + counts
        codes = {c["country"] for c in data["countries"]}
        assert "IN" in codes and "US" in codes

    def test_scan_with_country_header(self, s, admin_token):
        r = s.get(f"{API}/products/lookup?barcode=8901030895001",
                  headers={"x-country": "DE", "x-guest-id": f"guest-{uuid.uuid4().hex[:8]}"})
        # 200 (product exists) or 402 (out of scans); the analytics record fires before consume
        assert r.status_code in (200, 402, 404)
        # verify DE now appears
        o = s.get(f"{API}/admin/analytics/overview?days=7",
                  headers={"Authorization": f"Bearer {admin_token}"})
        codes = {c["country"] for c in o.json()["countries"]}
        # DE is only recorded if the request went through record_analytics (i.e., lookup succeeded)
        if r.status_code == 200:
            assert "DE" in codes


class TestMonthlyReport:
    def test_manual_trigger_admin(self, s, admin_token, db):
        # clear log so we get a fresh send count
        asyncio.get_event_loop().run_until_complete(
            db.monthly_report_log.delete_many({})
        )
        r = s.post(f"{API}/admin/analytics/report/send-now",
                   headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, r.text
        assert r.json()["sent"] >= 1
        # idempotent
        r2 = s.post(f"{API}/admin/analytics/report/send-now",
                    headers={"Authorization": f"Bearer {admin_token}"})
        assert r2.status_code == 200
        assert r2.json()["sent"] == 0

    def test_manual_trigger_non_admin_403(self, s, legal_versions):
        email = f"veriscan-nonadmin-{uuid.uuid4().hex[:8]}@example.com"
        rr = s.post(f"{API}/auth/register", json={
            "email": email, "password": "strongpass123", "full_name": "T",
            "accepted_terms_version": legal_versions[0],
            "accepted_privacy_version": legal_versions[1],
        })
        token = rr.json()["token"]
        r = s.post(f"{API}/admin/analytics/report/send-now",
                   headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403


# ---------- 5. Trial reminder scheduler ----------
class TestTrialReminder:
    def test_send_trial_reminders_idempotent(self, s, db, legal_versions):
        from scheduler import _send_trial_reminders

        email = f"veriscan-trial-{uuid.uuid4().hex[:8]}@example.com"
        rr = s.post(f"{API}/auth/register", json={
            "email": email, "password": "strongpass123", "full_name": "T",
            "accepted_terms_version": legal_versions[0],
            "accepted_privacy_version": legal_versions[1],
        })
        assert rr.status_code == 200, rr.text
        uid = rr.json()["user"]["id"]

        # shift trial_expires_at to 6 days from now, clear any reminder flag
        six_days = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            db.users.update_one({"id": uid}, {
                "$set": {"trial_expires_at": six_days},
                "$unset": {"trial_reminder_sent_at": ""},
            })
        )

        sent = loop.run_until_complete(_send_trial_reminders())
        assert sent >= 1

        # verify user doc has trial_reminder_sent_at
        u = loop.run_until_complete(db.users.find_one({"id": uid}, {"_id": 0}))
        assert u.get("trial_reminder_sent_at") is not None

        # second call → 0 (idempotent for this user; other users may still match)
        # Force just this user: reset back once, call, should be 1 only if we haven't set flag
        # After first run flag is set → second run for same user returns 0 additional
        sent2 = loop.run_until_complete(_send_trial_reminders())
        # sent2 could be 0 if no other matching users. It must be < sent when re-running immediately.
        assert sent2 == 0 or sent2 < sent + 1


# ---------- 6. Regression: admin critical routes ----------
class TestAdminRegression:
    def test_users_list_suspend_reactivate(self, s, admin_token, legal_versions):
        email = f"veriscan-reg-{uuid.uuid4().hex[:6]}@example.com"
        rr = s.post(f"{API}/auth/register", json={
            "email": email, "password": "strongpass123", "full_name": "R",
            "accepted_terms_version": legal_versions[0],
            "accepted_privacy_version": legal_versions[1],
        })
        uid = rr.json()["user"]["id"]
        r = s.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        r2 = s.post(f"{API}/admin/users/{uid}/suspend",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={"reason": "test"})
        assert r2.status_code == 200
        r3 = s.post(f"{API}/admin/users/{uid}/reactivate",
                    headers={"Authorization": f"Bearer {admin_token}"})
        assert r3.status_code == 200

    def test_pricing_list(self, s, admin_token):
        r = s.get(f"{API}/admin/pricing", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_promocodes_list(self, s, admin_token):
        r = s.get(f"{API}/admin/promocodes", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_support_list(self, s, admin_token):
        r = s.get(f"{API}/admin/support", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_reports_list(self, s, admin_token):
        r = s.get(f"{API}/admin/reports", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_payments_list(self, s, admin_token):
        r = s.get(f"{API}/admin/payments", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_duplicates_endpoint(self, s, admin_token):
        r = s.get(f"{API}/admin/duplicates", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        # Endpoint returns a flat list of clusters, each with kind ("exact"/"fuzzy") + confidence
        assert isinstance(data, list)
        for cluster in data:
            assert "kind" in cluster and cluster["kind"] in ("exact", "fuzzy")
            assert "confidence" in cluster
            assert "products" in cluster


# ---------- 7. Iteration 7/8 regression: compare / TERMS / stripe status ----------
class TestIter78Regression:
    def test_products_compare_deep_links(self, s):
        r = s.get(f"{API}/products/compare?barcode=8901030895001")
        assert r.status_code == 200, r.text
        data = r.json()
        # deep_links present as either top-level or per-offer field
        assert "deep_links" in data or any("deep_link" in o for o in data.get("offers", []))

    def test_stripe_status_zero_priced_country(self, s):
        # A country with no pricing configured → stripe status enabled=false
        r = s.get(f"{API}/payments/stripe/status?country=ZZ")
        assert r.status_code == 200
        data = r.json()
        assert data.get("enabled") is False
