"""Build meals from known nutrition and save the original serving estimates."""

from itertools import combinations, product

from dining import MACROS, dish_payload, menu_items


PORTIONS = (0.5, 1.0, 1.5, 2.0)
PLANNING_PERIODS = ("breakfast", "lunch", "dinner")


def snapshot(items, day):
    totals = dict.fromkeys(MACROS, 0.0)
    missing = 0
    rows = []
    for item, portion in items:
        dish = dish_payload(item)
        rows.append({"dish": dish, "portion": portion})
        if dish["macros"] is None:
            missing += 1
            continue
        for macro in MACROS:
            totals[macro] += dish["macros"][macro] * portion
    return {"date": day, "items": rows, "macros": {key: round(value, 2) for key, value in totals.items()},
            "missing_nutrition_count": missing}


def _score(values, goals):
    calories, protein, carbs, fat = values
    distance = 0
    for name, value in (("carbs_target", carbs), ("fat_target", fat)):
        target = goals.get(name)
        if target is not None:
            distance += abs(value - target) / max(target, 1)
    return distance, -protein, calories


def _options(menu, cap):
    options = []
    for item in menu_items(menu):
        macros = dish_payload(item)["macros"]
        if macros is None or macros["calories"] <= 0:
            continue
        values = tuple(macros[name] for name in MACROS)
        if values[0] * 0.5 <= cap:
            options.append((item, values))
    # Keep the enumeration bounded for dining rooms with hundreds of entries.
    options.sort(key=lambda option: (-option[1][1] / max(option[1][0], 1), option[0].id))
    candidates = []
    seen_dishes = set()
    for item, values in options:
        if item.dish_id not in seen_dishes:
            candidates.append((item, values))
            seen_dishes.add(item.dish_id)
        if len(candidates) == 12:
            break
    for size in range(1, min(3, len(candidates)) + 1):
        for selected in combinations(candidates, size):
            for portions in product(PORTIONS, repeat=size):
                totals = [0.0, 0.0, 0.0, 0.0]
                plate = []
                for (item, values), portion in zip(selected, portions):
                    plate.append((item, portion))
                    for index in range(len(MACROS)):
                        totals[index] += values[index] * portion
                if totals[0] <= cap:
                    yield totals, plate


def choose_plan(menus, goals, full_day=False):
    cap = goals["calorie_cap"]
    minimum = goals.get("protein_minimum", 0)
    if full_day:
        groups = [_full_day_options(menus, cap)]
    else:
        groups = [_options(menu, cap) for menu in menus]

    best_plate = None
    best_score = None
    for options in groups:
        for values, plate in options:
            if values[1] < minimum:
                continue
            score = _score(values, goals)
            if best_score is None or score < best_score:
                best_score = score
                best_plate = plate
    return best_plate


def _full_day_options(menus, cap):
    # Keep one option per 50-calorie band to leave room for later meals.
    day_options = [([0.0, 0.0, 0.0, 0.0], [])]
    for period in PLANNING_PERIODS:
        meal_options = {}
        for menu in menus:
            if menu.meal_period != period:
                continue
            for values, items in _options(menu, cap):
                key = int(values[0] // 50)
                existing = meal_options.get(key)
                if existing is None or values[1] > existing[0][1]:
                    meal_options[key] = (values, items)
        expanded = {}
        for running, plate in day_options:
            for values, items in meal_options.values():
                combined = [a + b for a, b in zip(running, values)]
                if combined[0] > cap:
                    continue
                key = int(combined[0] // 50)
                existing = expanded.get(key)
                if existing is None or combined[1] > existing[0][1]:
                    expanded[key] = (combined, plate + items)
        day_options = list(expanded.values())
    return day_options
