"""VeriScan iteration 3 backend tests.

Covers real Open Food Facts / Open Beauty Facts lookup, nutrition_per_100g,
guest / registered quota, personalized match, contributions, plans,
guest -> registered migration, and profile persistence.
"""
import os
import uuid
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://veriscan-preview-1.preview.emergentagent.com"
).rstrip("/")

API = f"{BASE_URL}/api"
TIMEOUT = 20


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture
def guest_id():
    return f"iter3-{uuid.uuid4().hex}"


def _register(session, email=None, password="strongpass123", guest_id=None):
    email = email or f"test_iter3_{uuid.uuid4().hex[:10]}@example.com"
    headers = {"x-guest-id": guest_id} if guest_id else {}
    r = session.post(f"{API}/auth/register", json={"email": email, "password": password}, headers=headers, timeout=TIMEOUT)
    return r, email


# ---------- health ----------
def test_root_health(session):
    r = session.get(f"{API}/", timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json()["message"] == "VeriScan API is ready"


# ---------- auth ----------
def test_register_creates_user_with_token_and_preferences(session):
    r, email = _register(session)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data and data["token"]
    assert data["user"]["email"] == email
    assert data["user"]["preferences"] == {"dietary": [], "targets": [], "sensitivities": []}


def test_login_success(session):
    r, email = _register(session)
    assert r.status_code == 200
    login = session.post(f"{API}/auth/login", json={"email": email, "password": "strongpass123"}, timeout=TIMEOUT)
    assert login.status_code == 200
    assert login.json()["user"]["email"] == email
    assert "token" in login.json()


def test_login_wrong_password(session):
    r, email = _register(session)
    assert r.status_code == 200
    bad = session.post(f"{API}/auth/login", json={"email": email, "password": "wrongwrong"}, timeout=TIMEOUT)
    assert bad.status_code == 401


# ---------- guest quota ----------
def test_guest_entitlements_and_quota(session, guest_id):
    h = {"x-guest-id": guest_id}
    ent = session.get(f"{API}/entitlements", headers=h, timeout=TIMEOUT).json()
    assert ent["registered"] is False
    assert ent["free_remaining"] == 3
    assert ent["wallet"] == 0

    remaining_after = []
    for _ in range(3):
        r = session.get(f"{API}/products/lookup", params={"barcode": "8901030895001"}, headers=h, timeout=TIMEOUT)
        assert r.status_code == 200
        remaining_after.append(session.get(f"{API}/entitlements", headers=h, timeout=TIMEOUT).json()["free_remaining"])
    assert remaining_after == [2, 1, 0]

    r4 = session.get(f"{API}/products/lookup", params={"barcode": "8901030895001"}, headers=h, timeout=TIMEOUT)
    assert r4.status_code == 401
    msg = (r4.json().get("detail") or "").lower() if isinstance(r4.json().get("detail"), str) else str(r4.json())
    assert "account" in msg or "guest" in msg


# ---------- seeded products ----------
def test_seeded_oats_product(session, guest_id):
    h = {"x-guest-id": guest_id}
    r = session.get(f"{API}/products/lookup", params={"barcode": "8901030895001"}, headers=h, timeout=TIMEOUT)
    assert r.status_code == 200
    p = r.json()
    assert p["name"] == "Organic Rolled Oats"
    assert isinstance(p["ingredients"], list) and len(p["ingredients"]) >= 1
    for ing in p["ingredients"]:
        for key in ("score", "hazard", "function", "effect"):
            assert key in ing, f"missing {key} in ingredient {ing}"
    nut = p["nutrition_per_100g"]
    assert nut and nut.get("protein_g") == 13.2 and nut.get("energy_kcal") == 379
    assert 0 <= p["overall_health_score"] <= 100
    assert 0 <= p["personal_match"] <= 100


# ---------- Real external lookup (Open Food Facts) ----------
def test_nutella_real_lookup(session, guest_id):
    h = {"x-guest-id": guest_id}
    r = session.get(f"{API}/products/lookup", params={"barcode": "3017620422003"}, headers=h, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Open Food Facts unreachable: {r.status_code} {r.text[:200]}")
    p = r.json()
    assert p["ingredients"], "ingredients should not be empty from OFF"
    names = " ".join(i["name"].lower() for i in p["ingredients"])
    assert "sugar" in names
    # Sugar should be scored as moderation <= 50
    sugar_scores = [i["score"] for i in p["ingredients"] if "sugar" in i["name"].lower()]
    assert sugar_scores and min(sugar_scores) <= 50
    # Palm-related ingredient scored as moderation
    palm_scores = [i["score"] for i in p["ingredients"] if "palm" in i["name"].lower()]
    assert palm_scores, "expected a palm-related ingredient"
    assert min(palm_scores) <= 50
    nut = p["nutrition_per_100g"]
    assert nut and nut.get("sugars_g") is not None
    # allow a wide tolerance around 56g
    assert 45 <= nut["sugars_g"] <= 65, f"unexpected sugars_g={nut['sugars_g']}"


# ---------- personalized match ----------
def test_personalized_match_decreases_for_fragrance(session):
    # Baseline (no preferences)
    guest1 = f"iter3-base-{uuid.uuid4().hex}"
    r = session.get(f"{API}/products/lookup", params={"barcode": "8906087771204"}, headers={"x-guest-id": guest1}, timeout=TIMEOUT)
    assert r.status_code == 200
    baseline = r.json()["personal_match"]

    # With Vegan + Paraben-free + Fragrance-free preferences via registered user
    reg, _ = _register(session)
    assert reg.status_code == 200
    token = reg.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    prefs = {"dietary": ["Vegan"], "targets": [], "sensitivities": ["Paraben-free", "Fragrance-free"]}
    put = session.put(f"{API}/profile", json=prefs, headers=auth, timeout=TIMEOUT)
    assert put.status_code == 200
    assert put.json() == prefs

    look = session.get(f"{API}/products/lookup", params={"barcode": "8906087771204"}, headers=auth, timeout=TIMEOUT)
    assert look.status_code == 200
    personalised = look.json()["personal_match"]
    assert personalised < baseline, f"expected personalised({personalised}) < baseline({baseline})"


# ---------- profile read/write ----------
def test_profile_get_after_put(session):
    reg, _ = _register(session)
    token = reg.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    prefs = {"dietary": ["Vegan"], "targets": ["Low sugar"], "sensitivities": ["Paraben-free"]}
    put = session.put(f"{API}/profile", json=prefs, headers=auth, timeout=TIMEOUT)
    assert put.status_code == 200
    got = session.get(f"{API}/profile", headers=auth, timeout=TIMEOUT)
    assert got.status_code == 200
    body = got.json()
    assert body["registered"] is True
    assert body["preferences"] == prefs


# ---------- registered quota ----------
def test_registered_entitlements_and_consumption(session):
    reg, _ = _register(session)
    token = reg.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    ent = session.get(f"{API}/entitlements", headers=auth, timeout=TIMEOUT).json()
    assert ent["registered"] is True
    assert ent["free_remaining"] == 5
    assert ent["wallet"] == 0

    r = session.get(f"{API}/products/lookup", params={"barcode": "8901030895001"}, headers=auth, timeout=TIMEOUT)
    assert r.status_code == 200
    ent2 = session.get(f"{API}/entitlements", headers=auth, timeout=TIMEOUT).json()
    assert ent2["free_remaining"] == 4


# ---------- guest -> registered migration ----------
def test_guest_history_migration_on_register(session):
    gid = f"iter3-mig-{uuid.uuid4().hex}"
    h = {"x-guest-id": gid}
    r = session.get(f"{API}/products/lookup", params={"barcode": "8901030895001"}, headers=h, timeout=TIMEOUT)
    assert r.status_code == 200
    reg, _ = _register(session, guest_id=gid)
    assert reg.status_code == 200
    token = reg.json()["token"]
    hist = session.get(f"{API}/history", headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT).json()
    assert any(item["product"]["barcode"] == "8901030895001" for item in hist), hist


# ---------- contributions ----------
def test_contribution_creates_pending_record(session, guest_id):
    payload = {"barcode": f"TEST-{uuid.uuid4().hex[:10]}", "product_name": "TEST Custom Bar", "notes": "unit test", "images": []}
    r = session.post(f"{API}/contributions", json=payload, headers={"x-guest-id": guest_id}, timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending_verification"
    assert body["barcode"] == payload["barcode"]
    assert body["product_name"] == payload["product_name"]


# ---------- plans ----------
def test_plans_launch_promo_pricing(session):
    r = session.get(f"{API}/plans", timeout=TIMEOUT)
    assert r.status_code == 200
    data = r.json()
    assert data["launch_promo"] is True
    prices = {p["id"]: p for p in data["subscriptions"]}
    assert prices["monthly"]["price"] == 72
    assert prices["yearly"]["price"] == 450
