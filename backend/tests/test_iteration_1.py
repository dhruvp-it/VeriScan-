import os
import uuid

import requests


BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")


def test_core_api_contracts():
    assert BASE_URL
    guest = f"iteration-1-{uuid.uuid4()}"
    headers = {"x-guest-id": guest}

    health = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert health.status_code == 200 and health.json()["message"]

    entitlement = requests.get(f"{BASE_URL}/api/entitlements", headers=headers, timeout=15)
    assert entitlement.status_code == 200 and entitlement.json()["free_remaining"] == 3

    product = requests.get(f"{BASE_URL}/api/products/lookup", params={"barcode": "8901030895001"}, headers=headers, timeout=15)
    assert product.status_code == 200 and product.json()["name"] == "Organic Rolled Oats"
    assert product.json()["ingredients"] == sorted(product.json()["ingredients"], key=lambda item: item["score"])

    history = requests.get(f"{BASE_URL}/api/history", headers=headers, timeout=15)
    assert history.status_code == 200 and history.json()[0]["product"]["barcode"] == "8901030895001"

    plans = requests.get(f"{BASE_URL}/api/plans", timeout=15)
    assert plans.status_code == 200 and plans.json()["subscriptions"][0]["price"] == 72

    unknown = requests.get(f"{BASE_URL}/api/products/lookup", params={"barcode": "9999999999999"}, headers=headers, timeout=15)
    assert unknown.status_code == 404 and unknown.json()["detail"]["scan"]["source"] == "guest"
