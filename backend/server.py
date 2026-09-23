import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
import jwt
import requests
import stripe
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
JWT_SECRET = os.environ.get("JWT_SECRET", "veriscan-local-development-secret")
TOKEN_ALGORITHM = "HS256"

app = FastAPI(title="VeriScan API")
api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ingredient knowledge base
# Each entry: keyword -> (score 0-100, hazard tier, function, effect)
# ---------------------------------------------------------------------------
INGREDIENT_DB: List[Tuple[str, int, str, str, str]] = [
    # Toxic / severe hazard (0-20)
    ("formaldehyde", 8, "toxic", "Preservative", "Classified as a human carcinogen by IARC; associated with respiratory irritation and long-term health risks."),
    ("coal tar", 10, "toxic", "Dye / anti-dandruff", "Coal-tar derived colorants are linked to cancer risk; banned in many EU cosmetic uses."),
    ("hydroquinone", 15, "toxic", "Skin lightener", "Restricted in the EU. Prolonged use is linked to ochronosis and endocrine disruption concerns."),
    ("triclosan", 18, "toxic", "Antibacterial", "Endocrine disruptor; contributes to antimicrobial resistance and bioaccumulation."),
    ("bha", 18, "toxic", "Preservative", "Butylated hydroxyanisole is classified as a possible human carcinogen and endocrine disruptor."),
    ("bht", 19, "toxic", "Preservative", "Butylated hydroxytoluene has estrogenic activity and may accumulate in body tissue."),
    ("aspartame", 20, "toxic", "Sweetener", "Recently classified as a possible carcinogen by IARC. Use in moderation, especially for children."),
    # High concern (21-40)
    ("paraben", 24, "harmful", "Preservative", "Parabens can mimic estrogen and disrupt hormones. Prefer paraben-free formulations."),
    ("sodium lauryl sulfate", 28, "harmful", "Surfactant", "Harsh cleanser that can strip the skin barrier and cause irritation in sensitive individuals."),
    ("sls", 28, "harmful", "Surfactant", "Sodium lauryl sulfate is a harsh cleanser that can strip skin oils and irritate sensitive scalps."),
    ("trans fat", 22, "harmful", "Fat", "Trans fats raise LDL cholesterol and cardiovascular risk. Avoid whenever possible."),
    ("partially hydrogenated", 24, "harmful", "Fat", "Source of trans fats; strongly linked to heart disease."),
    ("high fructose corn syrup", 30, "harmful", "Sweetener", "Excess consumption is linked to insulin resistance, fatty liver and weight gain."),
    ("monosodium glutamate", 35, "harmful", "Flavor enhancer", "MSG may cause headaches or flushing in sensitive people; used to boost savory taste."),
    ("sodium nitrite", 32, "harmful", "Curing agent", "Combines with amines in the body to form nitrosamines linked to colorectal cancer."),
    ("propylparaben", 24, "harmful", "Preservative", "Endocrine disrupting paraben. Restricted in the EU for infant products."),
    ("phthalate", 22, "harmful", "Plasticizer / fragrance carrier", "Endocrine disruptors linked to developmental and reproductive harm."),
    ("fragrance", 38, "harmful", "Sensory additive", "'Fragrance' can hide dozens of undisclosed compounds; a top allergen for sensitive skin."),
    ("parfum", 38, "harmful", "Sensory additive", "Undisclosed fragrance blend; may include phthalates and allergens."),
    ("aluminum chlorohydrate", 38, "harmful", "Antiperspirant", "Debated links to hormonal effects; some consumers prefer aluminum-free alternatives."),
    ("artificial color", 34, "harmful", "Color", "Synthetic dyes such as tartrazine (E102) are linked to hyperactivity in children."),
    ("red 40", 32, "harmful", "Color", "FD&C Red 40 is linked to hyperactivity in children; banned in several EU foods."),
    ("yellow 5", 30, "harmful", "Color", "Tartrazine may trigger asthma-like reactions and hyperactivity in some children."),
    # Moderation (41-60)
    ("palm oil", 50, "moderation", "Fat / emollient", "Palm oil is high in saturated fat; sourcing can contribute to deforestation."),
    ("maltodextrin", 48, "moderation", "Bulking agent", "High glycemic index. Fine as an occasional additive but not for blood-sugar sensitivity."),
    ("carrageenan", 46, "moderation", "Thickener", "Generally recognised as safe, but degraded forms may irritate the gut lining."),
    ("sucralose", 52, "moderation", "Sweetener", "Zero-calorie sweetener; some studies suggest gut microbiome effects with heavy use."),
    ("acesulfame", 52, "moderation", "Sweetener", "Non-nutritive sweetener; use moderately, especially during pregnancy."),
    ("dextrose", 50, "moderation", "Sugar", "Simple sugar that spikes blood glucose. Watch total daily added sugar."),
    ("sugar", 46, "moderation", "Sugar", "Added sugar contributes calories without nutrients; keep total daily intake moderate."),
    ("cane sugar", 50, "moderation", "Sugar", "Refined cane sugar; moderate use recommended by dietary guidelines."),
    ("glucose", 50, "moderation", "Sugar", "Simple sugar; spikes blood glucose. Watch total daily added sugar."),
    ("fructose", 42, "moderation", "Sugar", "Fructose in isolation is metabolised by the liver and adds to daily added-sugar totals."),
    ("vegetable fat", 44, "moderation", "Fat", "Often blends including palm oil; high in saturated fat depending on source."),
    ("hazelnut", 82, "beneficial", "Whole food", "Rich in vitamin E, magnesium, and monounsaturated fats; may be a nut allergen."),
    ("lecithin", 62, "safe", "Emulsifier", "Commonly derived from soy or sunflower; a well-tolerated food emulsifier."),
    ("soya", 58, "moderation", "Legume", "Nutritious legume; common allergen to declare."),
    ("skimmed milk", 66, "safe", "Dairy", "Low-fat dairy source of protein and calcium."),
    ("cocoa powder", 76, "beneficial", "Botanical", "Rich in flavanols; watch for added sugars in the final product."),
    ("vanillin", 58, "moderation", "Flavoring", "Synthetic vanilla flavoring; well tolerated at food-use levels."),
    ("citric acid", 60, "moderation", "Acidifier", "Widely used pH regulator; sensitive teeth may be affected by frequent exposure."),
    ("xanthan gum", 58, "moderation", "Thickener", "A common fermentation-derived stabilizer; occasional bloating in sensitive individuals."),
    ("guar gum", 58, "moderation", "Thickener", "Well-tolerated soluble fiber; high doses can cause GI discomfort."),
    ("sodium benzoate", 44, "moderation", "Preservative", "Safe at approved levels; can form benzene with vitamin C in beverages."),
    ("polysorbate", 50, "moderation", "Emulsifier", "Widely used emulsifier. Some evidence of gut microbiome disruption at high intake."),
    ("silicone", 55, "moderation", "Conditioner", "Provides smooth feel; can build up on hair over time."),
    ("dimethicone", 55, "moderation", "Silicone", "Sensory-focused occlusive; buildup possible on hair and scalp."),
    ("phenoxyethanol", 55, "moderation", "Preservative", "Safe under 1% in cosmetics; can be sensitizing for reactive skin."),
    # Safe (61-80)
    ("glycerin", 78, "safe", "Humectant", "Draws moisture to the skin barrier; well-tolerated across skin types."),
    ("hyaluronic acid", 82, "beneficial", "Humectant", "Binds water to plump and hydrate the skin surface."),
    ("niacinamide", 84, "beneficial", "Active", "Supports the skin barrier, evens tone, and calms redness."),
    ("panthenol", 78, "safe", "Conditioner", "Provitamin B5; soothes and moisturizes skin and hair."),
    ("salt", 62, "safe", "Mineral", "Essential mineral; watch total sodium if you have high blood pressure."),
    ("sea salt", 65, "safe", "Mineral", "Trace-mineral rich salt; still counts toward daily sodium."),
    ("iodized salt", 66, "safe", "Mineral", "Adds essential iodine to the diet; keep total sodium moderate."),
    ("whole grain", 88, "beneficial", "Whole food", "Whole grains bring fiber, B-vitamins and slow-release carbs."),
    ("oats", 90, "beneficial", "Whole food", "Beta-glucan fiber supports heart health, satiety and steady energy."),
    ("brown rice", 84, "beneficial", "Whole food", "Whole grain rice retains bran fiber, magnesium and antioxidants."),
    ("quinoa", 90, "beneficial", "Whole food", "Complete plant protein rich in fiber, iron and magnesium."),
    ("almond", 86, "beneficial", "Whole food", "Rich in vitamin E, magnesium and healthy monounsaturated fats."),
    ("cashew", 82, "beneficial", "Whole food", "Good source of magnesium, copper and heart-healthy fats."),
    ("olive oil", 88, "beneficial", "Oil", "Monounsaturated fats and polyphenols; a Mediterranean-diet staple."),
    ("coconut oil", 70, "safe", "Oil", "High in saturated fat; useful in moderation, better as part of balanced fats."),
    ("shea butter", 84, "beneficial", "Emollient", "Rich fatty acids nourish the skin barrier and soothe dryness."),
    ("aloe", 85, "beneficial", "Botanical", "Cooling and hydrating botanical, well-tolerated for sensitive skin."),
    ("aloe vera", 85, "beneficial", "Botanical", "Cooling humectant that supports the skin barrier."),
    ("green tea", 84, "beneficial", "Antioxidant", "Rich in polyphenols; supports antioxidant defense."),
    ("vitamin c", 84, "beneficial", "Antioxidant", "Water-soluble antioxidant; supports immunity and collagen synthesis."),
    ("ascorbic acid", 82, "beneficial", "Antioxidant", "Vitamin C form; potent antioxidant that also stabilizes food color."),
    ("tocopherol", 82, "beneficial", "Antioxidant", "Vitamin E form; protects fats from oxidation and supports the skin barrier."),
    ("vitamin e", 84, "beneficial", "Antioxidant", "Fat-soluble antioxidant that protects cell membranes."),
    ("probiotic", 86, "beneficial", "Active", "Live cultures that support gut microbiome balance."),
    ("prebiotic", 84, "beneficial", "Fiber", "Fiber that feeds beneficial gut bacteria."),
    ("turmeric", 84, "beneficial", "Botanical", "Curcumin has anti-inflammatory activity; pair with black pepper for bioavailability."),
    ("ginger", 82, "beneficial", "Botanical", "Digestive aid with anti-inflammatory potential."),
    ("honey", 74, "safe", "Sweetener", "A natural sweetener with minor antimicrobial benefits; still an added sugar."),
    ("stevia", 76, "safe", "Sweetener", "Plant-derived, zero-calorie sweetener; well-tolerated at moderate use."),
    ("chia", 88, "beneficial", "Whole food", "Rich in omega-3 ALA, fiber and plant protein."),
    ("flaxseed", 88, "beneficial", "Whole food", "Omega-3 ALA source that also supports gut regularity."),
    ("cocoa", 76, "safe", "Botanical", "Antioxidant-rich cacao; watch added sugars in finished products."),
    ("milk", 66, "safe", "Dairy", "Good source of calcium and protein; not suitable for those with lactose intolerance."),
    ("yogurt", 76, "beneficial", "Dairy", "Fermented dairy with live cultures supporting gut health."),
    ("egg", 78, "beneficial", "Whole food", "High-quality protein with choline for brain health."),
    ("water", 90, "beneficial", "Solvent", "Base solvent; essential for hydration and formulation."),
    ("aqua", 90, "beneficial", "Solvent", "INCI name for water; formulation base."),
    ("salt-free", 80, "safe", "Formulation", "Formulated without added salt; supports heart-friendly diet."),
]

# Words we treat as clean-eating boosters when computing personalized match
CLEAN_KEYWORDS = ("organic", "whole", "cold-pressed", "unrefined", "raw", "natural")

PREFERENCES = {"dietary": [], "targets": [], "sensitivities": []}

SEEDED_PRODUCTS = [
    {
        "id": "seed-oats-001", "barcode": "8901030895001", "name": "Organic Rolled Oats",
        "brand": "Harvest Table", "category": "food",
        "description": "Whole grain oats for a simple, nourishing breakfast.",
        "dietary_type": "vegan", "origin_country": "India", "manufactured_in": "Pune, India",
        "first_detected_year": 2024, "price_tier": "affordable", "target_age_group": "Adults",
        "primary_region": "India", "serving_size": "500 g", "price_inr": 249,
        "image_url": None,
        "nutrition_per_100g": {
            "energy_kcal": 379, "protein_g": 13.2, "carbohydrates_g": 67.7, "sugars_g": 1.0,
            "fat_g": 6.5, "saturated_fat_g": 1.1, "fiber_g": 10.1, "salt_g": 0.02,
        },
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
        "primary_region": "India", "serving_size": "150 ml", "price_inr": 695,
        "image_url": None,
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
        "primary_region": "India", "serving_size": "500 g", "price_inr": 1299,
        "image_url": None,
        "nutrition_per_100g": {
            "energy_kcal": 380, "protein_g": 78.0, "carbohydrates_g": 5.0, "sugars_g": 1.5,
            "fat_g": 4.0, "saturated_fat_g": 1.0, "fiber_g": 4.0, "salt_g": 0.3,
        },
        "ingredients_text": "Pea protein isolate, Brown rice protein, Natural vanilla flavor, Stevia extract, Xanthan gum.",
        "labels": ["vegan", "gluten-free"],
        "retailers": [
            {"name": "Amazon India", "price": 1299, "url": "https://www.amazon.in/"},
            {"name": "HealthKart", "price": 1199, "url": "https://www.healthkart.com/"},
        ],
    },
]


class AuthRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)


class ProfileRequest(BaseModel):
    dietary: List[str] = []
    targets: List[str] = []
    sensitivities: List[str] = []


class ContributionRequest(BaseModel):
    barcode: str
    product_name: Optional[str] = None
    notes: Optional[str] = None
    images: List[str] = []


class ScanPurchase(BaseModel):
    quantity: int = Field(ge=1, le=100)
    tier: str


class SubscriptionPurchase(BaseModel):
    plan: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def token_for(user_id: str) -> str:
    return jwt.encode(
        {"sub": user_id, "exp": datetime.now(timezone.utc).timestamp() + 60 * 60 * 24 * 30},
        JWT_SECRET, algorithm=TOKEN_ALGORITHM,
    )


async def authenticated_user(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(authorization[7:], JWT_SECRET, algorithms=[TOKEN_ALGORITHM])
        user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    except (jwt.PyJWTError, TypeError):
        user = None
    if not user:
        raise HTTPException(401, "Session expired")
    return user


# ---------------------------------------------------------------------------
# Ingredient scoring
# ---------------------------------------------------------------------------
def _clean(text: str) -> str:
    return re.sub(r"[^a-z0-9\s-]", " ", text.lower()).strip()


def score_ingredient(name: str) -> Dict[str, Any]:
    """Score a single ingredient name against the knowledge base with fuzzy match."""
    clean_name = _clean(name)
    for keyword, score, hazard, function, effect in INGREDIENT_DB:
        if keyword in clean_name:
            return {"name": name.strip().title(), "score": score, "hazard": hazard, "function": function, "effect": effect}
    # unknown ingredient: neutral score
    return {
        "name": name.strip().title(),
        "score": 62,
        "hazard": "safe",
        "function": "Formulation ingredient",
        "effect": "Reviewed from the public product label. Individual responses may vary; check the packaging for full context.",
    }


def parse_ingredients(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    # Keep parenthetical hints inline so palm/soya etc. still match the safety DB
    stripped = re.sub(r"[()]", " ", text)
    parts = re.split(r"[,;.]", stripped)
    seen: set[str] = set()
    result: List[Dict[str, Any]] = []
    for part in parts:
        name = re.sub(r"\s+", " ", part).strip()
        if not name or len(name) < 2:
            continue
        # Trim leading role labels like "emulsifier: lecithins"
        if ":" in name:
            name = name.split(":", 1)[1].strip()
        # Skip numeric-only tokens like "7%" or "13"
        if re.fullmatch(r"[\d.,%\s]+", name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(score_ingredient(name))
        if len(result) >= 30:
            break
    return result


def overall_score(ingredients: List[Dict[str, Any]]) -> float:
    if not ingredients:
        return 60.0
    scores = [int(item.get("score", 60)) for item in ingredients]
    average = sum(scores) / len(scores)
    low = [s for s in scores if s < 25]
    # Exponential penalty for very-low-scoring ingredients
    penalty = 0.0
    for s in low:
        penalty += (25 - s) * 1.2
    return round(max(0.0, min(100.0, average - penalty)), 1)


# ---------------------------------------------------------------------------
# Personalized match
# ---------------------------------------------------------------------------
def personalized_match(product: Dict[str, Any], preferences: Dict[str, List[str]]) -> int:
    ingredients_text = " ".join(item.get("name", "").lower() for item in product.get("ingredients", []))
    labels = " ".join(product.get("labels", [])).lower()
    dietary_type = (product.get("dietary_type") or "").lower()
    scores = [int(item.get("score", 60)) for item in product.get("ingredients", [])] or [60]
    base_health = overall_score(product.get("ingredients", []))

    checks: List[bool] = []
    sensitivity_violations = 0

    for pref in preferences.get("dietary", []):
        want = pref.lower()
        if want == "vegan":
            checks.append(dietary_type == "vegan" or "vegan" in labels)
        elif want == "vegetarian":
            checks.append(dietary_type in ("vegan", "vegetarian") or dietary_type == "not_applicable")
        elif want == "pescatarian":
            checks.append(dietary_type != "non_vegetarian" or "fish" in ingredients_text)
        elif "whole" in want:
            checks.append(any(word in ingredients_text or word in labels for word in CLEAN_KEYWORDS))
        else:
            checks.append(True)

    for target in preferences.get("targets", []):
        want = target.lower()
        if "sugar" in want:
            sugars = ((product.get("nutrition_per_100g") or {}).get("sugars_g") or 0)
            checks.append(sugars < 8)
        elif "carb" in want:
            carbs = ((product.get("nutrition_per_100g") or {}).get("carbohydrates_g") or 0)
            checks.append(carbs < 25)
        elif "heart" in want:
            sat = ((product.get("nutrition_per_100g") or {}).get("saturated_fat_g") or 0)
            checks.append(sat < 4 and min(scores) >= 30)
        elif "gut" in want:
            checks.append(any(k in ingredients_text for k in ("probiotic", "prebiotic", "fiber", "yogurt")))
        elif "clean" in want:
            checks.append(min(scores) >= 30 and any(w in ingredients_text or w in labels for w in CLEAN_KEYWORDS))
        else:
            checks.append(True)

    for avoid in preferences.get("sensitivities", []):
        want = avoid.lower()
        if "paraben" in want:
            ok = "paraben" not in ingredients_text
        elif "fragrance" in want:
            ok = "fragrance" not in ingredients_text and "parfum" not in ingredients_text
        elif "additive" in want:
            ok = min(scores) >= 40
        elif "cruelty" in want:
            ok = "cruelty-free" in labels or "leaping bunny" in labels or product.get("category") in ("food", "supplement")
        elif "gluten" in want:
            ok = "gluten-free" in labels or "wheat" not in ingredients_text
        elif "nut" in want:
            ok = not any(n in ingredients_text for n in ("almond", "cashew", "peanut", "walnut", "hazelnut"))
        else:
            ok = True
        checks.append(ok)
        if not ok:
            sensitivity_violations += 1

    if not checks:
        return max(40, min(100, int(base_health)))

    ratio = sum(1 for c in checks if c) / len(checks)
    base = 55 + ratio * 45
    # Heavy penalty for sensitivity violations — those are user-declared avoidance rules.
    base -= 18 * sensitivity_violations
    # Penalty for red-flag ingredients
    if min(scores) < 25:
        base -= 12
    # If any sensitivity was violated, cap the match at the raw health score so
    # the user never sees a match that exceeds the underlying ingredient score.
    if sensitivity_violations > 0:
        base = min(base, base_health)
    return max(20, min(100, round(base)))


def build_public_product(product: Dict[str, Any], preferences: Dict[str, List[str]]) -> Dict[str, Any]:
    ingredients = product.get("ingredients")
    if not ingredients:
        ingredients = parse_ingredients(product.get("ingredients_text") or "")
    ingredients_sorted = sorted(ingredients, key=lambda item: item.get("score", 60))
    result = {key: value for key, value in product.items() if key not in {"_id", "ingredients"}}
    result["ingredients"] = ingredients_sorted
    result["overall_health_score"] = overall_score(ingredients_sorted)
    result["personal_match"] = personalized_match({**product, "ingredients": ingredients_sorted}, preferences)
    result["retailers"] = product.get("retailers", [])
    result.setdefault("nutrition_per_100g", None)
    result.setdefault("image_url", None)
    result.setdefault("labels", [])
    return result


# ---------------------------------------------------------------------------
# Scan quota
# ---------------------------------------------------------------------------
async def consume_scan(guest_id: Optional[str], user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if user:
        entitlement = await db.entitlements.find_one({"user_id": user["id"]}, {"_id": 0})
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        if not entitlement or entitlement.get("free_month") != month:
            entitlement = {"user_id": user["id"], "free_month": month, "free_used": 0, "purchased_balance": 0, "intro_used": 0, "subscribed": False}
            await db.entitlements.replace_one({"user_id": user["id"]}, entitlement, upsert=True)
        if entitlement.get("subscribed"):
            return {"remaining": None, "source": "subscription"}
        if entitlement.get("free_used", 0) < 5:
            await db.entitlements.update_one({"user_id": user["id"]}, {"$inc": {"free_used": 1}})
            return {"remaining": 4 - entitlement.get("free_used", 0), "source": "monthly_free"}
        if entitlement.get("purchased_balance", 0) > 0:
            await db.entitlements.update_one({"user_id": user["id"]}, {"$inc": {"purchased_balance": -1}})
            return {"remaining": entitlement.get("purchased_balance", 0) - 1, "source": "wallet"}
        raise HTTPException(402, "Monthly scans are used. Add credits or subscribe to continue.")
    if not guest_id:
        raise HTTPException(400, "Guest identifier required")
    guest = await db.guests.find_one({"guest_id": guest_id}, {"_id": 0})
    used = guest.get("used", 0) if guest else 0
    if used >= 3:
        raise HTTPException(401, "Your 3 guest scans are complete. Create your free account to keep scanning.")
    await db.guests.update_one({"guest_id": guest_id}, {"$set": {"used": used + 1}}, upsert=True)
    return {"remaining": 2 - used, "source": "guest"}


# ---------------------------------------------------------------------------
# External lookup
# ---------------------------------------------------------------------------
def _nutrition_from_off(nutriments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(nutriments, dict) or not nutriments:
        return None
    def num(key: str) -> Optional[float]:
        value = nutriments.get(f"{key}_100g")
        try:
            return round(float(value), 2) if value is not None else None
        except (TypeError, ValueError):
            return None
    out = {
        "energy_kcal": num("energy-kcal") or num("energy"),
        "protein_g": num("proteins"),
        "carbohydrates_g": num("carbohydrates"),
        "sugars_g": num("sugars"),
        "fat_g": num("fat"),
        "saturated_fat_g": num("saturated-fat"),
        "fiber_g": num("fiber"),
        "salt_g": num("salt"),
    }
    return out if any(v is not None for v in out.values()) else None


def _dietary_type_from_off(product: Dict[str, Any]) -> str:
    labels = " ".join([
        str(product.get("labels", "")),
        str(product.get("labels_tags", "")),
        str(product.get("categories", "")),
    ]).lower()
    if "vegan" in labels:
        return "vegan"
    if "vegetarian" in labels:
        return "vegetarian"
    if any(word in labels for word in ("meat", "chicken", "beef", "pork", "fish")):
        return "non_vegetarian"
    return "not_applicable"


def remote_lookup(barcode: str) -> Optional[Dict[str, Any]]:
    endpoints = [
        ("https://world.openfoodfacts.org/api/v2/product/", "food"),
        ("https://world.openbeautyfacts.org/api/v2/product/", "personal_care"),
    ]
    for endpoint, category in endpoints:
        try:
            response = requests.get(
                f"{endpoint}{barcode}.json",
                timeout=6,
                headers={"User-Agent": "VeriScan/1.0 (contact@veriscan.app)"},
            )
            data = response.json()
            if data.get("status") != 1:
                continue
            product = data.get("product", {})
            ingredients_text = product.get("ingredients_text_en") or product.get("ingredients_text") or ""
            labels_tags = product.get("labels_tags", []) or []
            image = product.get("image_front_url") or product.get("image_url")
            record = {
                "id": f"online-{barcode}",
                "barcode": barcode,
                "name": product.get("product_name") or product.get("generic_name") or "Scanned product",
                "brand": (product.get("brands") or "Public registry").split(",")[0].strip(),
                "category": category,
                "description": product.get("generic_name") or "Details sourced from the public product registry.",
                "dietary_type": _dietary_type_from_off(product),
                "origin_country": (product.get("countries") or "Global").split(",")[0].strip(),
                "manufactured_in": (product.get("manufacturing_places") or product.get("countries") or "Registry listing").split(",")[0].strip(),
                "first_detected_year": datetime.now(timezone.utc).year,
                "price_tier": "affordable",
                "target_age_group": "Adults",
                "primary_region": (product.get("countries") or "Global").split(",")[0].strip(),
                "serving_size": product.get("serving_size") or product.get("quantity") or "See label",
                "price_inr": 0,
                "image_url": image,
                "labels": [tag.replace("en:", "").replace("-", " ") for tag in labels_tags[:6]],
                "ingredients_text": ingredients_text,
                "nutrition_per_100g": _nutrition_from_off(product.get("nutriments", {})),
                "retailers": [],
            }
            record["ingredients"] = parse_ingredients(ingredients_text)
            return record
        except (requests.RequestException, ValueError, TypeError) as exc:
            logger.info("Remote lookup failed for %s: %s", endpoint, exc)
            continue
    return None


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
@api_router.get("/")
async def root() -> Dict[str, str]:
    return {"message": "VeriScan API is ready"}


@api_router.post("/auth/register")
async def register(payload: AuthRequest, x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    email = payload.email.strip().lower()
    if await db.users.find_one({"email": email}, {"_id": 0}):
        raise HTTPException(409, "An account with this email already exists")
    preferences = PREFERENCES.copy()
    if x_guest_id:
        guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0})
        if guest and guest.get("preferences"):
            preferences = guest["preferences"]
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode(),
        "preferences": preferences,
        "created_at": now_iso(),
    }
    await db.users.insert_one(user.copy())
    await db.entitlements.insert_one({
        "user_id": user["id"], "free_month": datetime.now(timezone.utc).strftime("%Y-%m"),
        "free_used": 0, "purchased_balance": 0, "intro_used": 0, "subscribed": False,
    })
    if x_guest_id:
        await db.history.update_many({"user_id": f"guest:{x_guest_id}"}, {"$set": {"user_id": user["id"]}})
    return {"token": token_for(user["id"]), "user": {"id": user["id"], "email": email, "preferences": user["preferences"]}}


@api_router.post("/auth/login")
async def login(payload: AuthRequest) -> Dict[str, Any]:
    user = await db.users.find_one({"email": payload.email.strip().lower()}, {"_id": 0})
    if not user or not bcrypt.checkpw(payload.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Email or password is incorrect")
    return {"token": token_for(user["id"]), "user": {"id": user["id"], "email": user["email"], "preferences": user.get("preferences", PREFERENCES)}}


@api_router.get("/profile")
async def get_profile(authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if authorization:
        user = await authenticated_user(authorization)
        return {"email": user["email"], "preferences": user.get("preferences", PREFERENCES), "registered": True}
    if x_guest_id:
        guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) or {}
        return {"email": None, "preferences": guest.get("preferences", PREFERENCES), "registered": False}
    return {"email": None, "preferences": PREFERENCES, "registered": False}


@api_router.put("/profile")
async def save_profile(payload: ProfileRequest, authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    preferences = payload.model_dump()
    if authorization:
        user = await authenticated_user(authorization)
        await db.users.update_one({"id": user["id"]}, {"$set": {"preferences": preferences}})
    elif x_guest_id:
        await db.guests.update_one({"guest_id": x_guest_id}, {"$set": {"preferences": preferences}}, upsert=True)
    return preferences


@api_router.get("/entitlements")
async def entitlements(authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if authorization:
        user = await authenticated_user(authorization)
        item = await db.entitlements.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        return {
            "registered": True,
            "free_remaining": max(0, 5 - item.get("free_used", 0)),
            "wallet": item.get("purchased_balance", 0),
            "subscribed": item.get("subscribed", False),
            "email": user["email"],
        }
    guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) if x_guest_id else None
    return {
        "registered": False,
        "free_remaining": max(0, 3 - (guest or {}).get("used", 0)),
        "wallet": 0,
        "subscribed": False,
        "email": None,
    }


@api_router.get("/products/lookup")
async def lookup_product(
    barcode: str,
    authorization: Optional[str] = Header(default=None),
    x_guest_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user = await authenticated_user(authorization) if authorization else None
    product = await db.products.find_one({"barcode": barcode}, {"_id": 0})
    if not product:
        product = remote_lookup(barcode)
        if product:
            await db.products.update_one({"barcode": barcode}, {"$set": product}, upsert=True)
    if not product:
        # Don't consume a scan when the product isn't found.
        raise HTTPException(404, detail={"message": "Product not found", "barcode": barcode})
    # Consume scan only after a successful resolution.
    consumed = await consume_scan(x_guest_id, user)
    if user:
        preferences = user.get("preferences", PREFERENCES)
    elif x_guest_id:
        guest = await db.guests.find_one({"guest_id": x_guest_id}, {"_id": 0}) or {}
        preferences = guest.get("preferences", PREFERENCES)
    else:
        preferences = PREFERENCES
    result = build_public_product(product, preferences)
    result["scan"] = consumed
    history_user = user["id"] if user else f"guest:{x_guest_id}"
    await db.history.insert_one({
        "id": str(uuid.uuid4()), "user_id": history_user, "product": result, "scanned_at": now_iso(),
    })
    return result


@api_router.get("/history")
async def history(authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> List[Dict[str, Any]]:
    user = await authenticated_user(authorization) if authorization else None
    owner = user["id"] if user else f"guest:{x_guest_id}"
    return await db.history.find({"user_id": owner}, {"_id": 0}).sort("scanned_at", -1).to_list(30)


@api_router.post("/contributions")
async def contribution(payload: ContributionRequest, authorization: Optional[str] = Header(default=None), x_guest_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization) if authorization else None
    item = {
        "id": str(uuid.uuid4()), "barcode": payload.barcode, "product_name": payload.product_name,
        "notes": payload.notes, "images": payload.images, "status": "pending_verification",
        "submitted_by": (user or {}).get("id", f"guest:{x_guest_id}"), "created_at": now_iso(),
    }
    await db.contributions.insert_one(item.copy())
    return {key: value for key, value in item.items() if key != "images"}


@api_router.get("/plans")
async def plans() -> Dict[str, Any]:
    return {
        "launch_promo": True,
        "scan_intro": {"price": 5, "label": "First 20 purchased scans"},
        "scan_standard": {"price": 15, "label": "After introductory credits"},
        "subscriptions": [
            {"id": "monthly", "price": 72, "regular_price": 180, "period": "month"},
            {"id": "yearly", "price": 450, "regular_price": 1500, "period": "year"},
        ],
    }


@api_router.post("/payments/scan-intent")
async def scan_intent(payload: ScanPurchase, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization)
    amount = {"intro": 500, "standard": 1500}.get(payload.tier)
    if amount is None:
        raise HTTPException(400, "Invalid scan tier")
    if not os.environ.get("STRIPE_SECRET_KEY"):
        raise HTTPException(503, "Payments are not configured yet")
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    intent = stripe.PaymentIntent.create(
        amount=amount * payload.quantity, currency="inr",
        automatic_payment_methods={"enabled": True},
        metadata={"user_id": user["id"], "kind": "scan_credits", "quantity": str(payload.quantity)},
    )
    await db.payments.insert_one({
        "stripe_payment_intent_id": intent.id, "user_id": user["id"], "quantity": payload.quantity,
        "status": "created", "created_at": now_iso(),
    })
    return {"paymentIntentClientSecret": intent.client_secret}


@api_router.post("/payments/subscription-session")
async def subscription_session(payload: SubscriptionPurchase, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    user = await authenticated_user(authorization)
    if payload.plan not in {"monthly", "yearly"}:
        raise HTTPException(400, "Invalid subscription plan")
    if not os.environ.get("STRIPE_SECRET_KEY"):
        raise HTTPException(503, "Payments are not configured yet")
    price_id = os.environ.get("STRIPE_MONTHLY_PRICE_ID" if payload.plan == "monthly" else "STRIPE_YEARLY_PRICE_ID")
    if not price_id:
        raise HTTPException(503, "Subscription prices are not configured yet")
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    session = stripe.checkout.Session.create(
        mode="subscription", line_items=[{"price": price_id, "quantity": 1}],
        success_url=os.environ.get("STRIPE_CHECKOUT_SUCCESS_URL", "https://example.com/success"),
        cancel_url=os.environ.get("STRIPE_CHECKOUT_CANCEL_URL", "https://example.com/cancel"),
        metadata={"user_id": user["id"], "plan": payload.plan},
    )
    return {"url": session.url, "sessionId": session.id}


@api_router.post("/payments/stripe/webhook")
async def stripe_webhook(request: Request) -> Dict[str, bool]:
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(503, "Webhook is not configured")
    try:
        event = stripe.Webhook.construct_event(await request.body(), request.headers.get("stripe-signature", ""), secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "Invalid Stripe webhook")
    try:
        await db.webhook_events.insert_one({"stripe_event_id": event["id"], "created_at": now_iso()})
    except Exception:  # noqa: BLE001
        return {"ok": True}
    obj = event["data"]["object"]
    if event["type"] == "payment_intent.succeeded":
        metadata = obj.get("metadata", {})
        quantity = int(metadata.get("quantity", "0"))
        await db.entitlements.update_one({"user_id": metadata.get("user_id")}, {"$inc": {"purchased_balance": quantity}})
        await db.payments.update_one({"stripe_payment_intent_id": obj["id"]}, {"$set": {"status": "succeeded"}})
    if event["type"] == "checkout.session.completed":
        await db.entitlements.update_one(
            {"user_id": obj.get("metadata", {}).get("user_id")},
            {"$set": {"subscribed": True, "subscription_plan": obj.get("metadata", {}).get("plan")}},
        )
    return {"ok": True}


app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def seed_database() -> None:
    for product in SEEDED_PRODUCTS:
        enriched = {**product, "ingredients": parse_ingredients(product.get("ingredients_text", ""))}
        await db.products.update_one({"barcode": product["barcode"]}, {"$set": enriched}, upsert=True)


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()
