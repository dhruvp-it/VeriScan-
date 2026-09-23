"""Iteration 7: post-refactor API regression + NEW /products/compare + new preferences.

Covers:
- Full API surface regression after server.py -> routes/* modular refactor
- NEW hybrid price comparison endpoint (category-routed deep links, live disabled)
- NEW preference options (Keto, Low sodium, Dairy-free) persistence + personal_match
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
assert BASE_URL, "EXPO_BACKEND_URL env var is required"
BASE_URL = BASE_URL.rstrip("/")

ADMIN_EMAIL = "dhruvpateld230@gmail.com"
ADMIN_PASSWORD = "strongpass123"
FOOD_BARCODE = "8901030895001"
SUPPLEMENT_BARCODE = "8908001234567"
PERSONAL_CARE_BARCODE = "8906087771204"


@pytest.fixture(scope="session")
def client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def legal_versions(client):
    terms = client.get(f"{BASE_URL}/api/legal/terms").json()
    privacy = client.get(f"{BASE_URL}/api/legal/privacy").json()
    return {"terms": terms["version"], "privacy": privacy["version"]}


@pytest.fixture(scope="session")
def user_token(client, legal_versions):
    email = f"test_i7_{uuid.uuid4().hex[:10]}@example.com"
    resp = client.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": "strongpass123",
        "accepted_terms_version": legal_versions["terms"],
        "accepted_privacy_version": legal_versions["privacy"],
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


@pytest.fixture(scope="session")
def admin_token(client):
    resp = client.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["user"]["role"] == "admin"
    return data["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Regression: health, legal, auth
# ---------------------------------------------------------------------------

class TestHealthAndAuth:
    def test_health(self, client):
        resp = client.get(f"{BASE_URL}/api/")
        assert resp.status_code == 200
        assert "VeriScan" in resp.json().get("message", "")

    def test_legal_endpoints(self, legal_versions):
        assert legal_versions["terms"]
        assert legal_versions["privacy"]

    def test_register_requires_terms(self, client):
        resp = client.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"test_i7_notc_{uuid.uuid4().hex[:8]}@example.com", "password": "strongpass123",
        })
        assert resp.status_code in (400, 422)

    def test_login(self, client, user_token):
        assert user_token

    def test_admin_login_role(self, admin_token):
        assert admin_token


# ---------------------------------------------------------------------------
# Regression: profile, entitlements, plans
# ---------------------------------------------------------------------------

class TestProfileAndEntitlements:
    def test_profile_get(self, client, user_token):
        resp = client.get(f"{BASE_URL}/api/profile", headers=auth(user_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["registered"] is True
        assert set(data["preferences"].keys()) == {"dietary", "targets", "sensitivities"}

    def test_profile_put_roundtrip(self, client, user_token):
        payload = {"dietary": ["Vegan"], "targets": ["High protein"], "sensitivities": ["Gluten"]}
        resp = client.put(f"{BASE_URL}/api/profile", json=payload, headers=auth(user_token))
        assert resp.status_code == 200
        got = client.get(f"{BASE_URL}/api/profile", headers=auth(user_token)).json()["preferences"]
        assert got["dietary"] == ["Vegan"] and got["sensitivities"] == ["Gluten"]

    def test_entitlements_registered(self, client, user_token):
        resp = client.get(f"{BASE_URL}/api/entitlements", headers=auth(user_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["registered"] is True and data["trial_active"] is True
        assert isinstance(data["wallet"], (int, float))

    def test_entitlements_guest(self, client):
        resp = client.get(f"{BASE_URL}/api/entitlements", headers={"X-Guest-Id": f"guest-i7-{uuid.uuid4().hex[:8]}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["registered"] is False and data["free_remaining"] == 3

    def test_plans(self, client):
        resp = client.get(f"{BASE_URL}/api/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["country"] == "IN" and len(data["subscriptions"]) == 2

    def test_promocode_preview_no_code(self, client):
        resp = client.post(f"{BASE_URL}/api/promocodes/preview", json={"code": "", "base_paise": 10000})
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount"] == 10000 and data["discount"] == 0

    def test_promocode_preview_invalid_code_400(self, client):
        resp = client.post(f"{BASE_URL}/api/promocodes/preview", json={"code": "NONEXISTENT", "base_paise": 10000})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Regression: products lookup / alternatives / history
# ---------------------------------------------------------------------------

class TestProducts:
    def test_lookup_guest(self, client):
        resp = client.get(f"{BASE_URL}/api/products/lookup",
                          params={"barcode": FOOD_BARCODE},
                          headers={"X-Guest-Id": f"guest-i7-{uuid.uuid4().hex[:8]}"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["barcode"] == FOOD_BARCODE
        assert "personal_match" in data and "ingredients" in data and "scan" in data

    def test_lookup_registered(self, client, user_token):
        resp = client.get(f"{BASE_URL}/api/products/lookup",
                          params={"barcode": FOOD_BARCODE}, headers=auth(user_token))
        assert resp.status_code == 200
        assert resp.json()["barcode"] == FOOD_BARCODE

    def test_lookup_unknown_404(self, client):
        resp = client.get(f"{BASE_URL}/api/products/lookup",
                          params={"barcode": f"000{uuid.uuid4().hex[:10]}"},
                          headers={"X-Guest-Id": f"guest-i7-{uuid.uuid4().hex[:8]}"})
        assert resp.status_code == 404

    def test_alternatives(self, client, user_token):
        resp = client.get(f"{BASE_URL}/api/products/alternatives",
                          params={"barcode": FOOD_BARCODE}, headers=auth(user_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_history(self, client, user_token):
        resp = client.get(f"{BASE_URL}/api/history", headers=auth(user_token))
        assert resp.status_code == 200
        rows = resp.json()
        assert isinstance(rows, list) and any(r["product"]["barcode"] == FOOD_BARCODE for r in rows)


# ---------------------------------------------------------------------------
# Regression: watchlist / support / reports
# ---------------------------------------------------------------------------

class TestMisc:
    def test_watchlist_add_list_remove(self, client, user_token):
        add = client.post(f"{BASE_URL}/api/watchlist/{SUPPLEMENT_BARCODE}", headers=auth(user_token))
        assert add.status_code == 200
        items = client.get(f"{BASE_URL}/api/watchlist", headers=auth(user_token)).json()
        assert any(i["barcode"] == SUPPLEMENT_BARCODE for i in items)
        rem = client.delete(f"{BASE_URL}/api/watchlist/{SUPPLEMENT_BARCODE}", headers=auth(user_token))
        assert rem.status_code == 200
        items = client.get(f"{BASE_URL}/api/watchlist", headers=auth(user_token)).json()
        assert all(i["barcode"] != SUPPLEMENT_BARCODE for i in items)

    def test_support_ticket_flow(self, client, user_token):
        resp = client.post(f"{BASE_URL}/api/support",
                           json={"subject": "TEST_i7 support ticket", "message": "Testing support flow after refactor."},
                           headers=auth(user_token))
        assert resp.status_code == 200
        ticket_id = resp.json()["id"]
        mine = client.get(f"{BASE_URL}/api/support/mine", headers=auth(user_token)).json()
        assert any(t["id"] == ticket_id for t in mine)

    def test_report_submit(self, client, user_token):
        resp = client.post(f"{BASE_URL}/api/reports",
                           json={"barcode": FOOD_BARCODE, "reason": "TEST_i7 incorrect ingredients"},
                           headers=auth(user_token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "open"


# ---------------------------------------------------------------------------
# Regression: admin endpoints
# ---------------------------------------------------------------------------

class TestAdmin:
    def test_admin_overview(self, client, admin_token):
        resp = client.get(f"{BASE_URL}/api/admin/overview", headers=auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data and "products" in data

    def test_admin_users(self, client, admin_token):
        resp = client.get(f"{BASE_URL}/api/admin/users", headers=auth(admin_token))
        assert resp.status_code == 200
        users = resp.json()
        # admin list masks emails and excludes admin accounts by design
        assert isinstance(users, list) and len(users) > 0
        assert all("email_masked" in u and "password_hash" not in u for u in users)

    def test_admin_payments(self, client, admin_token):
        resp = client.get(f"{BASE_URL}/api/admin/payments", headers=auth(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_admin_duplicates(self, client, admin_token):
        resp = client.get(f"{BASE_URL}/api/admin/duplicates", headers=auth(admin_token))
        assert resp.status_code == 200

    def test_admin_requires_role(self, client, user_token):
        resp = client.get(f"{BASE_URL}/api/admin/overview", headers=auth(user_token))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# NEW: hybrid price comparison endpoint
# ---------------------------------------------------------------------------

class TestPriceComparison:
    def _names(self, data):
        return [l["name"] for l in data["deep_links"]]

    def test_compare_food_links(self, client):
        resp = client.get(f"{BASE_URL}/api/products/compare", params={"barcode": FOOD_BARCODE})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        names = self._names(data)
        for expected in ("Amazon India", "Flipkart", "Blinkit", "Zepto"):
            assert expected in names, names
        for excluded in ("Nykaa", "Tata 1mg", "HealthKart"):
            assert excluded not in names, names

    def test_compare_supplement_links(self, client):
        data = client.get(f"{BASE_URL}/api/products/compare", params={"barcode": SUPPLEMENT_BARCODE}).json()
        names = self._names(data)
        for expected in ("Amazon India", "Flipkart", "Tata 1mg", "HealthKart"):
            assert expected in names, names
        assert "Blinkit" not in names and "Nykaa" not in names

    def test_compare_personal_care_links(self, client):
        data = client.get(f"{BASE_URL}/api/products/compare", params={"barcode": PERSONAL_CARE_BARCODE}).json()
        names = self._names(data)
        for expected in ("Amazon India", "Flipkart", "Blinkit", "Zepto", "Nykaa"):
            assert expected in names, names
        assert "Tata 1mg" not in names and "HealthKart" not in names

    def test_compare_live_disabled(self, client):
        data = client.get(f"{BASE_URL}/api/products/compare", params={"barcode": FOOD_BARCODE}).json()
        assert data["live_enabled"] is False
        assert data["products"] == []

    def test_compare_deep_links_valid_urls(self, client):
        data = client.get(f"{BASE_URL}/api/products/compare", params={"barcode": FOOD_BARCODE}).json()
        for link in data["deep_links"]:
            assert link["url"].startswith("https://")
            assert link["id"] and link["name"] and link["icon"] and link["color"]

    def test_compare_unknown_barcode_404(self, client):
        resp = client.get(f"{BASE_URL}/api/products/compare", params={"barcode": "0009998887776"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# NEW: expanded preferences persist and drive personal_match
# ---------------------------------------------------------------------------

class TestNewPreferences:
    def test_new_preference_options_roundtrip(self, client, user_token):
        payload = {"dietary": ["Keto"], "targets": ["Low sodium"], "sensitivities": ["Dairy-free"]}
        resp = client.put(f"{BASE_URL}/api/profile", json=payload, headers=auth(user_token))
        assert resp.status_code == 200
        got = client.get(f"{BASE_URL}/api/profile", headers=auth(user_token)).json()["preferences"]
        assert got["dietary"] == ["Keto"]
        assert got["targets"] == ["Low sodium"]
        assert got["sensitivities"] == ["Dairy-free"]

    def test_lookup_personal_match_integer(self, client, user_token):
        resp = client.get(f"{BASE_URL}/api/products/lookup",
                          params={"barcode": FOOD_BARCODE}, headers=auth(user_token))
        assert resp.status_code == 200
        assert isinstance(resp.json()["personal_match"], int)
