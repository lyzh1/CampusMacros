"""Look up comparable USDA foods without inventing missing nutrition."""

import math
import re
import time

import requests

from db import Dish, Menu, Menuitem, db
from dining import ithaca_now, normalized_name


BASE = "https://api.nal.usda.gov/fdc/v1"
FOOD_DATA_TYPES = ("Survey (FNDDS)", "Foundation", "SR Legacy")
MACRO_IDS = {1003: "protein", 1005: "carbs", 1004: "fat"}
# USDA reports Foundation Food energy under the Atwater IDs.
ENERGY_IDS = (1008, 2048, 2047)
MENU_CATEGORIES = {
    "salad bar",
    "hot & cold beverages",
    "cookies, cakes & desserts",
    "lettuce, tomato, onion, & pickles",
}
# Explicit USDA reference foods for Eatery labels we have reviewed.
REFERENCE_FOODS = {
    "egg salad": (2707182, "Egg salad, made with mayonnaise"),
    "french fries": (2709456, "Potato, french fries, NFS"),
    "pocketless pita": (2707616, "Bread, pita"),
    "seasoned spiral french fries": (2709456, "Potato, french fries, NFS"),
    "tabbouleh": (2709131, "Tabbouleh"),
    "tuna salad": (175160, "Fish, tuna salad"),
}


def tokens(value):
    words = re.findall(r"[a-z0-9]+", value.casefold())
    if words and words[-1] == "nfs":
        words.pop()  # USDA's suffix for "not further specified."
    return sorted(words)


def lookup(name, api_key, session):
    label = normalized_name(name)
    if label in MENU_CATEGORIES:
        return None
    reference = REFERENCE_FOODS.get(label)
    if reference is not None:
        fdc_id, description = reference
        match = _reference_nutrition(fdc_id, description, api_key, session)
        if match is not None:
            return match

    requested = tokens(name)
    if len(requested) < 2:
        return None  # Labels such as “rice” do not identify a preparation.
    response = session.post(
        f"{BASE}/foods/search",
        params={"api_key": api_key},
        json={"query": name, "pageSize": 25, "dataType": list(FOOD_DATA_TYPES)},
        timeout=15,
    )
    response.raise_for_status()
    matches = []
    for food in response.json().get("foods", []):
        if food.get("dataType") in FOOD_DATA_TYPES and tokens(food.get("description", "")) == requested:
            matches.append(food)
    # Try a few matching records in case one is missing nutrients.
    matches.sort(key=lambda food: FOOD_DATA_TYPES.index(food["dataType"]))
    for food in matches[:3]:
        match = _reference_nutrition(food["fdcId"], food["description"], api_key, session)
        if match is not None:
            return match
    return None


def _reference_nutrition(fdc_id, description, api_key, session):
    response = session.get(f"{BASE}/food/{fdc_id}", params={"api_key": api_key}, timeout=15)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    food = response.json()
    reference_name = food.get("description", "")
    if tokens(reference_name) != tokens(description):
        return None

    values = {}
    energy = {}
    for row in food.get("foodNutrients", []):
        nutrient = row.get("nutrient", {})
        nutrient_id = nutrient.get("id")
        unit = nutrient.get("unitName", "").upper()
        amount = row.get("amount")
        if not valid(amount):
            continue
        if nutrient_id in ENERGY_IDS and unit == "KCAL":
            energy[nutrient_id] = amount
        if nutrient_id in MACRO_IDS and unit == "G":
            values[MACRO_IDS[nutrient_id]] = amount

    for nutrient_id in ENERGY_IDS:
        if nutrient_id in energy:
            values["calories"] = energy[nutrient_id]
            break
    if len(values) != 4:
        return None
    return values, fdc_id, reference_name


def valid(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def enrich_nutrition(api_key, limit, retry_unmatched=False):
    now = int(time.time())
    today = ithaca_now().date().isoformat()
    retry_before = now - 7 * 86400
    # Join dishes to their currently listed menu items and dated menus.
    query = Dish.query.join(Menuitem).join(Menu)
    query = query.filter(Dish.catalog_key.isnot(None), Dish.nutrition_source.is_(None))
    query = query.filter(Menu.published.is_(True), Menuitem.listed.is_(True), Menu.service_date >= today)
    if retry_unmatched:
        query = query.filter(Dish.usda_checked_at.isnot(None))
    else:
        query = query.filter(db.or_(Dish.usda_checked_at.is_(None), Dish.usda_checked_at < retry_before))
    candidates = query.distinct().order_by(Dish.id).limit(limit).all()
    results = {}
    matched = 0
    with requests.Session() as session:
        for dish in candidates:
            key = normalized_name(dish.name)
            if key not in results:
                results[key] = lookup(dish.name, api_key, session)
            match = results[key]
            dish.usda_checked_at = now
            if match is not None:
                values, fdc_id, reference_name = match
                dish.calories = values["calories"]
                dish.protein = values["protein"]
                dish.carbs = values["carbs"]
                dish.fat = values["fat"]
                dish.serving_description = f"100 g of USDA reference: {reference_name}"
                dish.nutrition_source = "usda"
                dish.nutrition_source_url = f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients"
                matched += 1
            db.session.commit()
    return {"checked": len(candidates), "matched": matched}
