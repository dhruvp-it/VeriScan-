"""VeriScan ingredient safety knowledge base + parsing + scoring helpers."""
import re
from typing import Any, Dict, List, Tuple

# Each entry: (keyword, score 0-100, hazard tier, function, effect blurb)
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
    # Safe / beneficial
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
]

CLEAN_KEYWORDS = ("organic", "whole", "cold-pressed", "unrefined", "raw", "natural")


def _clean(text: str) -> str:
    return re.sub(r"[^a-z0-9\s-]", " ", text.lower()).strip()


def score_ingredient(name: str) -> Dict[str, Any]:
    clean_name = _clean(name)
    for keyword, score, hazard, function, effect in INGREDIENT_DB:
        if keyword in clean_name:
            return {"name": name.strip().title(), "score": score, "hazard": hazard, "function": function, "effect": effect}
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
    stripped = re.sub(r"[()]", " ", text)
    parts = re.split(r"[,;.]", stripped)
    seen: set[str] = set()
    result: List[Dict[str, Any]] = []
    for part in parts:
        name = re.sub(r"\s+", " ", part).strip()
        if not name or len(name) < 2:
            continue
        if ":" in name:
            name = name.split(":", 1)[1].strip()
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
    penalty = 0.0
    for s in scores:
        if s < 25:
            penalty += (25 - s) * 1.2
    return round(max(0.0, min(100.0, average - penalty)), 1)


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
        elif want == "keto":
            carbs = ((product.get("nutrition_per_100g") or {}).get("carbohydrates_g") or 0)
            checks.append(carbs < 10)
        elif "protein" in want:
            protein = ((product.get("nutrition_per_100g") or {}).get("protein_g") or 0)
            checks.append(protein >= 12)
        elif want == "halal":
            checks.append("halal" in labels)
        elif want == "jain":
            checks.append(not any(w in ingredients_text for w in ("onion", "garlic", "potato", "egg", "meat")))
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
        elif "sodium" in want:
            salt = ((product.get("nutrition_per_100g") or {}).get("salt_g") or 0)
            checks.append(salt < 1.2)
        elif "weight" in want:
            energy = ((product.get("nutrition_per_100g") or {}).get("energy_kcal") or 0)
            sugars_w = ((product.get("nutrition_per_100g") or {}).get("sugars_g") or 0)
            checks.append(energy < 400 and sugars_w < 8)
        elif "energy" in want or "focus" in want:
            checks.append(not any(w in ingredients_text for w in ("trans fat", "high fructose", "corn syrup")))
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
        elif "sulfate" in want or "sulphate" in want:
            ok = not any(w in ingredients_text for w in ("sulfate", "sulphate", "lauryl", "laureth"))
        elif "dairy" in want:
            ok = not any(w in ingredients_text for w in ("milk", "lactose", "whey", "casein", "ghee", "cream"))
        elif "soy" in want:
            ok = "soy" not in ingredients_text and "soya" not in ingredients_text
        elif "palm" in want:
            ok = "palm" not in ingredients_text
        else:
            ok = True
        checks.append(ok)
        if not ok:
            sensitivity_violations += 1

    if not checks:
        return max(40, min(100, int(base_health)))

    ratio = sum(1 for c in checks if c) / len(checks)
    base = 55 + ratio * 45
    base -= 18 * sensitivity_violations
    if min(scores) < 25:
        base -= 12
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
