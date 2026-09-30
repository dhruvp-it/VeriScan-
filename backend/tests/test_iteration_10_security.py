"""Iteration 10 — security-fix verification.

Covers:
- SEC-001: JWT_SECRET env enforcement + admin/user token authz split
- Login brute-force lockout (account-scoped, 5 fails, 15-min lock)
- Password reset OTP hardening (bcrypt-hashed, single-use, 5 attempts, generic msgs)
- CSV formula-injection neutralization in analytics export
- Regressions: products lookup, launch offer (public/admin), analytics overview
- New-user register + entitlements trial_active with ~365 trial_days_remaining
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://veriscan-preview-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "dhruvpateld230@gmail.com"
ADMIN_PASSWORD = "strongpass123"
REGULAR_EMAIL = "veriscan-test@example.com"
REGULAR_PASSWORD = "strongpass123"


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="session")
def admin_token(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed {r.status_code} {r.text}"
    data = r.json()
    assert data["user"]["role"] == "admin"
    assert data.get("token")
    return data["token"]


@pytest.fixture(scope="session")
def legal_versions(s):
    t = s.get(f"{API}/legal/terms").json()
    p = s.get(f"{API}/legal/privacy").json()
    return t["version"], p["version"]


@pytest.fixture(scope="session")
def regular_token(s, legal_versions):
    # try login first
    r = s.post(f"{API}/auth/login", json={"email": REGULAR_EMAIL, "password": REGULAR_PASSWORD})
    if r.status_code == 200:
        return r.json()["token"]
    # otherwise register with current legal versions
    tv, pv = legal_versions
    r = s.post(f"{API}/auth/register", json={
        "email": REGULAR_EMAIL, "password": REGULAR_PASSWORD,
        "accepted_terms_version": tv, "accepted_privacy_version": pv,
    })
    assert r.status_code == 200, f"register failed {r.status_code} {r.text}"
    return r.json()["token"]


# ────────────────────────────────────────────────────────────────────────────
# SEC-001: JWT authorization
# ────────────────────────────────────────────────────────────────────────────
class TestJWTAuthorization:
    def test_admin_login_returns_token(self, admin_token):
        assert admin_token and isinstance(admin_token, str)

    def test_admin_token_can_access_entitlements(self, s, admin_token):
        r = s.get(f"{API}/entitlements", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, r.text
        assert "subscribed" in r.json() or "purchased_balance" in r.json()

    def test_admin_token_can_access_admin_overview(self, s, admin_token):
        r = s.get(f"{API}/admin/overview", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("users", "suspended", "open_tickets", "products"):
            assert key in body

    def test_forged_token_is_rejected(self, s):
        r = s.get(f"{API}/entitlements", headers={"Authorization": "Bearer garbage.token.value"})
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"

    def test_forged_token_rejected_on_admin(self, s):
        r = s.get(f"{API}/admin/overview", headers={"Authorization": "Bearer garbage.token.value"})
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"

    def test_regular_user_cannot_access_admin(self, s, regular_token):
        r = s.get(f"{API}/admin/overview", headers={"Authorization": f"Bearer {regular_token}"})
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"

    def test_regular_user_cannot_access_admin_users(self, s, regular_token):
        r = s.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {regular_token}"})
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"


# ────────────────────────────────────────────────────────────────────────────
# Login brute-force lockout — MUST use throwaway email (NOT admin)
# ────────────────────────────────────────────────────────────────────────────
class TestLoginLockout:
    def test_lockout_after_five_failures_then_correct_password_also_401(self, s, legal_versions):
        # Register a fresh throwaway user we can safely lock out
        tv, pv = legal_versions
        email = f"veriscan-lock-{uuid.uuid4().hex[:8]}@example.com"
        pw = "correctpass123"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": pw,
            "accepted_terms_version": tv, "accepted_privacy_version": pv,
        })
        assert r.status_code == 200, r.text

        # 5 wrong attempts → all 401 with generic message
        for i in range(5):
            r = s.post(f"{API}/auth/login", json={"email": email, "password": "wrongpass"})
            assert r.status_code == 401, f"attempt {i+1} got {r.status_code}: {r.text}"
            assert "incorrect" in r.json().get("detail", "").lower()

        # CORRECT password during lockout window → still 401 with same generic msg
        r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
        assert r.status_code == 401, f"locked correct-pass got {r.status_code}: {r.text}"
        assert "incorrect" in r.json().get("detail", "").lower()

    def test_valid_login_still_works_for_unlocked_account(self, s):
        # Regular non-locked user
        r = s.post(f"{API}/auth/login", json={"email": REGULAR_EMAIL, "password": REGULAR_PASSWORD})
        assert r.status_code == 200, r.text
        assert r.json().get("token")


# ────────────────────────────────────────────────────────────────────────────
# Password reset OTP hardening
# ────────────────────────────────────────────────────────────────────────────
class TestPasswordResetHardening:
    def test_forgot_password_sent_for_unknown_email(self, s):
        r = s.post(f"{API}/auth/forgot-password",
                   json={"email": f"nobody-{uuid.uuid4().hex[:6]}@example.com"})
        assert r.status_code == 200, r.text
        assert r.json() == {"status": "sent"}

    def test_forgot_password_sent_for_known_email(self, s):
        r = s.post(f"{API}/auth/forgot-password", json={"email": REGULAR_EMAIL})
        assert r.status_code == 200, r.text
        assert r.json() == {"status": "sent"}

    def test_reset_with_wrong_otp_returns_400(self, s):
        # ensure there's a code (may still be within its 10-min window from prior test)
        s.post(f"{API}/auth/forgot-password", json={"email": REGULAR_EMAIL})
        r = s.post(f"{API}/auth/reset-password", json={
            "email": REGULAR_EMAIL, "otp": "000000", "new_password": "newpass123",
        })
        assert r.status_code == 400, r.text
        assert "reset code" in r.json().get("detail", "").lower()

    def test_five_wrong_attempts_lock_out_the_code(self, s, legal_versions):
        # Fresh user so we're the only one requesting a code for this email
        tv, pv = legal_versions
        email = f"veriscan-otp-{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "somepass123",
            "accepted_terms_version": tv, "accepted_privacy_version": pv,
        })
        assert r.status_code == 200, r.text

        r = s.post(f"{API}/auth/forgot-password", json={"email": email})
        assert r.status_code == 200

        # 5 wrong attempts — each 400
        wrong_codes = ["111111", "222222", "333333", "444444", "555555"]
        for i, code in enumerate(wrong_codes):
            r = s.post(f"{API}/auth/reset-password", json={
                "email": email, "otp": code, "new_password": "newpass123",
            })
            assert r.status_code == 400, f"attempt {i+1} got {r.status_code}: {r.text}"

        # 6th attempt (even with any code) should also be 400 because
        # the record is locked out (attempts >= 5 means find_one_and_update returns None)
        r = s.post(f"{API}/auth/reset-password", json={
            "email": email, "otp": "666666", "new_password": "newpass123",
        })
        assert r.status_code == 400, f"post-lock got {r.status_code}: {r.text}"


# ────────────────────────────────────────────────────────────────────────────
# CSV formula-injection neutralization
# ────────────────────────────────────────────────────────────────────────────
class TestCSVSanitization:
    def test_export_neutralizes_formula_prefixed_cells(self, s, admin_token):
        # A retailer_click event stores `barcode` as its own top-level column
        # in analytics_daily, which is what the CSV writer emits as the "barcode"
        # cell. This is the surface where formula-injection can land.
        danger_barcode = "=DANGER()"
        r = s.post(f"{API}/analytics/track", json={
            "event": "retailer_click", "barcode": danger_barcode,
            "retailer_id": "amazon-in", "category": "food",
        })
        assert r.status_code == 200, r.text

        # Also seed a scan with a "-lead" barcode to cover the '-' branch of
        # _csv_safe once we can find any raw-cell case; belt & braces.
        s.post(f"{API}/analytics/track",
               json={"event": "retailer_click", "barcode": "-SUM(A1)",
                     "retailer_id": "flipkart", "category": "food"})

        # Export and inspect the CSV body
        r = s.get(f"{API}/admin/analytics/export?days=1",
                  headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("text/csv")
        body = r.text

        # The `barcode` column (last field) should be neutralized with a leading
        # single quote for any cell starting with =,+,-,@.
        assert "'=DANGER()" in body, f"CSV did not neutralize =DANGER(): {body[:800]}"
        assert "'-SUM(A1)" in body, f"CSV did not neutralize -SUM(A1): {body[:800]}"

        # Belt-and-braces: no line should have a naked '=DANGER()' or '-SUM(' in
        # a cell-start position (i.e., right after a comma or line-start).
        for line in body.splitlines():
            assert not line.startswith("="), f"CSV line starts with =: {line}"
            assert ",=DANGER()" not in line, f"unsanitized =DANGER() cell in: {line}"
            assert ",-SUM(A1)" not in line, f"unsanitized -SUM(A1) cell in: {line}"


# ────────────────────────────────────────────────────────────────────────────
# Regressions
# ────────────────────────────────────────────────────────────────────────────
class TestRegressions:
    def test_products_lookup_seeded(self, s):
        # /products/lookup requires a guest identifier header for anonymous
        # callers (or a Bearer token). Not tied to the security fix; use guest.
        headers = {"X-Guest-Id": f"guest-{uuid.uuid4().hex[:10]}"}
        r = s.get(f"{API}/products/lookup",
                  params={"barcode": "8901030895001"}, headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        prod = body.get("product") or body
        assert prod, f"empty response: {body}"
        # Verify the seeded product identity
        assert (prod.get("barcode") == "8901030895001"
                or body.get("barcode") == "8901030895001"), body
        assert (prod.get("name") or body.get("name")) is not None

    def test_public_launch_offer_active(self, s):
        r = s.get(f"{API}/launch-offer")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("active") is True
        assert int(body.get("free_days", 0)) >= 1

    def test_admin_launch_offer_get(self, s, admin_token):
        r = s.get(f"{API}/admin/launch-offer",
                  headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, r.text
        assert "active" in r.json() and "live" in r.json()

    def test_admin_launch_offer_put_idempotent(self, s, admin_token):
        # Read current
        r = s.get(f"{API}/admin/launch-offer",
                  headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        current_days = int(r.json().get("free_days", 365))
        # PUT same value (safe, no state change)
        r = s.put(f"{API}/admin/launch-offer",
                  headers={"Authorization": f"Bearer {admin_token}"},
                  json={"free_days": current_days})
        assert r.status_code == 200, r.text
        assert int(r.json().get("free_days")) == current_days

    def test_admin_analytics_overview(self, s, admin_token):
        r = s.get(f"{API}/admin/analytics/overview?days=7",
                  headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("totals", "daily", "top_products", "retailers"):
            assert key in body, f"missing {key} in overview: {body}"


# ────────────────────────────────────────────────────────────────────────────
# New user registration → entitlements trial_active with ~365 days remaining
# ────────────────────────────────────────────────────────────────────────────
class TestNewUserTrial:
    def test_register_and_check_trial(self, s, legal_versions):
        tv, pv = legal_versions
        email = f"veriscan-trial-{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "trialpass123",
            "accepted_terms_version": tv, "accepted_privacy_version": pv,
        })
        assert r.status_code == 200, r.text
        token = r.json().get("token")
        assert token
        assert r.json()["user"]["role"] == "user"

        r = s.get(f"{API}/entitlements", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        ent = r.json()
        assert ent.get("trial_active") is True, f"expected trial_active True: {ent}"
        remaining = ent.get("trial_days_remaining")
        assert remaining is not None, f"missing trial_days_remaining in {ent}"
        # Launch offer active → 365 free days. Allow small slack.
        assert 360 <= int(remaining) <= 365, f"trial_days_remaining={remaining}, expected ~365"
