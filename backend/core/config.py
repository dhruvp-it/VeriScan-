"""Shared environment loading, database client, and seed constants."""
import os
from pathlib import Path
from typing import Dict, List

import razorpay
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ.get("JWT_SECRET", "")
if len(JWT_SECRET.encode()) < 32 or JWT_SECRET.lower() in {
    "secret", "change-me", "changeme", "veriscan-local-development-secret",
}:
    raise RuntimeError(
        "JWT_SECRET is missing or too weak. Set a strong, unique JWT_SECRET "
        "(>= 32 chars) in backend/.env before starting the server."
    )
TOKEN_ALGORITHM = "HS256"
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
ADMIN_SEED_EMAIL = os.environ.get("ADMIN_SEED_EMAIL", "admin@veriscan.app").strip().lower()
ADMIN_SEED_PASSWORD = os.environ.get("ADMIN_SEED_PASSWORD", "changeme-strong")

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
rp_client = (
    razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    if (RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)
    else None
)

PREFERENCES: Dict[str, List[str]] = {"dietary": [], "targets": [], "sensitivities": []}

DEFAULT_COUNTRY_PRICING = [
    # Base rates in INR; other currencies remain free until admin enables pricing
    {"country": "IN", "currency": "INR", "symbol": "₹",
     "scan_intro": 5, "scan_standard": 15, "monthly": 72, "yearly": 450,
     "monthly_regular": 180, "yearly_regular": 1500, "provider": "razorpay"},
    {"country": "US", "currency": "USD", "symbol": "$",
     "scan_intro": 0, "scan_standard": 0, "monthly": 0, "yearly": 0,
     "monthly_regular": 0, "yearly_regular": 0, "provider": "stripe"},
    {"country": "CA", "currency": "CAD", "symbol": "CA$",
     "scan_intro": 0, "scan_standard": 0, "monthly": 0, "yearly": 0,
     "monthly_regular": 0, "yearly_regular": 0, "provider": "stripe"},
    {"country": "EU", "currency": "EUR", "symbol": "€",
     "scan_intro": 0, "scan_standard": 0, "monthly": 0, "yearly": 0,
     "monthly_regular": 0, "yearly_regular": 0, "provider": "stripe"},
    {"country": "GB", "currency": "GBP", "symbol": "£",
     "scan_intro": 0, "scan_standard": 0, "monthly": 0, "yearly": 0,
     "monthly_regular": 0, "yearly_regular": 0, "provider": "stripe"},
    {"country": "AE", "currency": "AED", "symbol": "د.إ",
     "scan_intro": 0, "scan_standard": 0, "monthly": 0, "yearly": 0,
     "monthly_regular": 0, "yearly_regular": 0, "provider": "stripe"},
    {"country": "AU", "currency": "AUD", "symbol": "A$",
     "scan_intro": 0, "scan_standard": 0, "monthly": 0, "yearly": 0,
     "monthly_regular": 0, "yearly_regular": 0, "provider": "stripe"},
    {"country": "NZ", "currency": "NZD", "symbol": "NZ$",
     "scan_intro": 0, "scan_standard": 0, "monthly": 0, "yearly": 0,
     "monthly_regular": 0, "yearly_regular": 0, "provider": "stripe"},
]

SEEDED_PRODUCTS = [
    {
        "id": "seed-oats-001", "barcode": "8901030895001", "name": "Organic Rolled Oats",
        "brand": "Harvest Table", "category": "food",
        "description": "Whole grain oats for a simple, nourishing breakfast.",
        "dietary_type": "vegan", "origin_country": "India", "manufactured_in": "Pune, India",
        "first_detected_year": 2024, "price_tier": "affordable", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "500 g", "price_inr": 249, "image_url": None,
        "nutrition_per_100g": {"energy_kcal": 379, "protein_g": 13.2, "carbohydrates_g": 67.7, "sugars_g": 1.0,
                                "fat_g": 6.5, "saturated_fat_g": 1.1, "fiber_g": 10.1, "salt_g": 0.02},
        "ingredients_text": "Whole grain rolled oats, Vitamin E (tocopherol).",
        "labels": ["vegan", "whole grain"],
        "retailers": [
            {"name": "Nature's Basket", "price": 249, "url": "https://www.naturesbasket.co.in/"},
            {"name": "BigBasket", "price": 239, "url": "https://www.bigbasket.com/"},
        ],
    },
    {
        "id": "seed-cleanser-001", "barcode": "8906087771204", "name": "Calm Barrier Cleanser",
        "brand": "Moss & Mineral", "category": "personal_care",
        "description": "A fragrance-free daily cleanser designed for sensitive skin.",
        "dietary_type": "not_applicable", "origin_country": "India", "manufactured_in": "Bengaluru, India",
        "first_detected_year": 2023, "price_tier": "premium", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "150 ml", "price_inr": 695, "image_url": None,
        "nutrition_per_100g": None,
        "ingredients_text": "Aqua, Glycerin, Sodium Laureth Sulfate, Panthenol, Phenoxyethanol, Fragrance.",
        "labels": [],
        "retailers": [
            {"name": "Nykaa", "price": 695, "url": "https://www.nykaa.com/"},
            {"name": "Tata 1mg", "price": 679, "url": "https://www.1mg.com/"},
        ],
    },
    {
        "id": "seed-protein-001", "barcode": "8908001234567", "name": "Plant Protein Vanilla",
        "brand": "Good Ground", "category": "supplement",
        "description": "Pea and brown rice protein with a lightly sweet vanilla finish.",
        "dietary_type": "vegan", "origin_country": "India", "manufactured_in": "Hyderabad, India",
        "first_detected_year": 2024, "price_tier": "high", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "500 g", "price_inr": 1299, "image_url": None,
        "nutrition_per_100g": {"energy_kcal": 380, "protein_g": 78.0, "carbohydrates_g": 5.0, "sugars_g": 1.5,
                                "fat_g": 4.0, "saturated_fat_g": 1.0, "fiber_g": 4.0, "salt_g": 0.3},
        "ingredients_text": "Pea protein isolate, Brown rice protein, Natural vanilla flavor, Stevia extract, Xanthan gum.",
        "labels": ["vegan", "gluten-free"],
        "retailers": [
            {"name": "Amazon India", "price": 1299, "url": "https://www.amazon.in/"},
            {"name": "HealthKart", "price": 1199, "url": "https://www.healthkart.com/"},
        ],
    },
    {
        "id": "seed-oats-002", "barcode": "8901030895002", "name": "Steel-Cut Whole Oats",
        "brand": "Field & Grain", "category": "food",
        "description": "Minimally-processed steel-cut oats with a nutty bite.",
        "dietary_type": "vegan", "origin_country": "India", "manufactured_in": "Pune, India",
        "first_detected_year": 2025, "price_tier": "affordable", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "500 g", "price_inr": 289, "image_url": None,
        "nutrition_per_100g": {"energy_kcal": 375, "protein_g": 14.0, "carbohydrates_g": 62.0, "sugars_g": 0.6,
                                "fat_g": 6.0, "saturated_fat_g": 1.0, "fiber_g": 12.0, "salt_g": 0.01},
        "ingredients_text": "Organic whole grain steel-cut oats.",
        "labels": ["organic", "vegan", "whole grain"],
        "retailers": [{"name": "BigBasket", "price": 289, "url": "https://www.bigbasket.com/"}],
    },
]
