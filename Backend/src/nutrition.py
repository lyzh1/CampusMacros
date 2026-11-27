"""Look up comparable USDA foods without inventing missing nutrition."""

import math
import re
import time

import requests

from db import Dish, Menu, Menuitem, db
from dining import ithaca_now


BASE = "https://api.nal.usda.gov/fdc/v1"
NUTRIENT_IDS = {1008: "calories", 1003: "protein", 1005: "carbs", 1004: "fat"}


def tokens(value):
    return sorted(re.findall(r"[a-z0-9]+", value.casefold()))


def lookup(name, api_key, session):
    requested = tokens(name)
    if len(requested) < 2:
        return None  # Labels such as “rice” do not identify a preparation.
    response = session.post(f"{BASE}/foods/search", params={"api_key": api_key},
                            json={"query": name, "pageSize": 25,
                                  "dataType": ["Survey (FNDDS)", "Foundation", "SR Legacy"]}, timeout=15)
    response.raise_for_status()
    match = None
    for food in response.json().get("foods", []):
        if tokens(food.get("description", "")) != requested:
            continue
        # Prefer a matching survey food for prepared dishes.
        if food.get("dataType") == "Survey (FNDDS)":
            match = food
            break
        if match is None:
            match = food
    if match is None:
        return None

    fdc_id = match["fdcId"]
    response = session.get(f"{BASE}/food/{fdc_id}", params={"api_key": api_key}, timeout=15)
    response.raise_for_status()
    values = {}
    for row in response.json().get("foodNutrients", []):
        nutrient = row.get("nutrient", {})
        macro = NUTRIENT_IDS.get(nutrient.get("id"))
        if macro is None:
            continue
        unit = "KCAL" if macro == "calories" else "G"
        amount = row.get("amount")
        if nutrient.get("unitName", "").upper() == unit and valid(amount):
            values[macro] = amount
    if len(values) != len(NUTRIENT_IDS):
        return None
    return values, fdc_id


def valid(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def enrich_nutrition(api_key, limit):
    now = int(time.time())
    today = ithaca_now().date().isoformat()
    retry_before = now - 7 * 86400
    # Join dishes to their currently listed menu items and dated menus.
    query = Dish.query.join(Menuitem).join(Menu)
    query = query.filter(Dish.catalog_key.isnot(None), Dish.nutrition_source.is_(None))
    query = query.filter(Menu.published.is_(True), Menuitem.listed.is_(True), Menu.service_date >= today)
    query = query.filter(db.or_(Dish.usda_checked_at.is_(None), Dish.usda_checked_at < retry_before))
    candidates = query.distinct().order_by(Dish.id).limit(limit).all()
    results = {}
    matched = 0
    with requests.Session() as session:
        for dish in candidates:
            key = tuple(tokens(dish.name))
            if key not in results:
                results[key] = lookup(dish.name, api_key, session)
            match = results[key]
            dish.usda_checked_at = now
            if match is not None:
                values, fdc_id = match
                dish.calories = values["calories"]
                dish.protein = values["protein"]
                dish.carbs = values["carbs"]
                dish.fat = values["fat"]
                dish.serving_description = "100 g (USDA reference weight)"
                dish.nutrition_source = "usda"
                dish.nutrition_source_url = f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients"
                matched += 1
            db.session.commit()
    return {"checked": len(candidates), "matched": matched}
