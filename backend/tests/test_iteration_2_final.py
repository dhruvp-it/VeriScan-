import os
import uuid
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://veriscan-preview-1.preview.emergentagent.com").rstrip("/")


def test_final_regression_api():
    s = requests.Session()
    guest = f"final-{uuid.uuid4().hex}"
    h = {"x-guest-id": guest}
    assert s.get(f"{BASE_URL}/api/", timeout=15).json()["message"] == "VeriScan API is ready"
    ent = s.get(f"{BASE_URL}/api/entitlements", headers=h, timeout=15).json()
    assert ent["registered"] is False and ent["free_remaining"] == 3
    product = s.get(f"{BASE_URL}/api/products/lookup", params={"barcode": "8901030895001"}, headers=h, timeout=20).json()
    assert product["name"] == "Organic Rolled Oats"
    assert [x["name"] for x in product["ingredients"]] == ["Vitamin E", "Whole grain oats"]
    history = s.get(f"{BASE_URL}/api/history", headers=h, timeout=15).json()
    assert history and history[0]["product"]["barcode"] == "8901030895001"
    plans = s.get(f"{BASE_URL}/api/plans", timeout=15).json()
    assert [p["price"] for p in plans["subscriptions"]] == [72, 450]
    unknown = s.get(f"{BASE_URL}/api/products/lookup", params={"barcode": "9999999999999"}, headers={"x-guest-id": f"unknown-{uuid.uuid4().hex}"}, timeout=20)
    assert unknown.status_code == 404 and unknown.json()["detail"]["barcode"] == "9999999999999"
    email = "migration-check@example.com"
    reg = s.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "strongpass123"}, headers={"x-guest-id": guest}, timeout=20)
    if reg.status_code == 409:
        reg = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "strongpass123"}, timeout=20)
    assert reg.status_code == 200
    token = reg.json()["token"]
    auth_history = s.get(f"{BASE_URL}/api/history", headers={"Authorization": f"Bearer {token}"}, timeout=15).json()
    assert any(item["product"]["barcode"] == "8901030895001" for item in auth_history)