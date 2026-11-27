"""The Swift client's dining menu and saved plate API."""

import json
from uuid import uuid4

from flask import jsonify, request

from db import DiningHall, Mealplan, Menuitem, db
from dining import clock_label, dish_payload, ithaca_now, live_halls, menu_day, menu_items
from planner import PLANNING_PERIODS, PORTIONS, choose_plan, snapshot


def error(message, status=400):
    return jsonify(error=message), status


def halls():
    try:
        day = menu_day(request.args.get("date"))
    except ValueError:
        return error("Use YYYY-MM-DD for the service date.")
    now = ithaca_now()
    today = now.date().isoformat()
    timestamp = now.timestamp()
    result = []
    for hall in live_halls():
        dates = set()
        windows = set()
        active = None
        for menu in hall.menus:
            if not menu.published:
                continue
            dates.add(menu.service_date)
            if menu.starts_at is None or menu.ends_at is None:
                continue
            if menu.service_date == day:
                windows.add((menu.starts_at, menu.ends_at))
            if day == today and active is None and menu.starts_at <= timestamp < menu.ends_at:
                active = menu
        hours = [f"{clock_label(start)}–{clock_label(end)}" for start, end in sorted(windows)]
        result.append({
            "id": hall.eatery_id, "name": hall.name, "location": hall.location or "",
            "open_now": active is not None,
            "hours_summary": " · ".join(hours) or "No hours listed for this date",
            "available_dates": sorted(dates),
            "active_meal": active.meal_period if active else None,
            "active_date": active.service_date if active else None,
        })
    return jsonify(result)


def hall_menu(hall_id):
    period = request.args.get("meal", "lunch")
    if period not in PLANNING_PERIODS:
        return error("Choose breakfast, lunch, or dinner.")
    try:
        day = menu_day(request.args.get("date"))
    except ValueError:
        return error("Use YYYY-MM-DD for the service date.")
    hall = DiningHall.query.filter_by(eatery_id=hall_id).first()
    if hall is None or hall.eatery_id.lower().startswith("sample-"):
        return error("Dining hall not found.", 404)
    dishes = []
    for menu in hall.menus:
        if menu.published and menu.service_date == day and menu.meal_period == period:
            for item in menu_items(menu):
                dishes.append(dish_payload(item))
    return jsonify(hall_id=hall_id, date=day, meal=period, dishes=dishes)


def plan_payload(plan):
    # Older manually saved plans contain links but no portion snapshot.
    if plan.snapshot:
        data = json.loads(plan.snapshot)
    else:
        data = snapshot([(item, 1.0) for item in plan.menuitems], None)
    data["id"] = plan.id
    data["name"] = plan.name
    data["description"] = plan.description
    return data


def meal_plans():
    return jsonify([plan_payload(plan) for plan in Mealplan.query.order_by(Mealplan.id.desc()).all()])


def meal_plan(plan_id):
    plan = Mealplan.query.filter_by(id=plan_id).first()
    if plan is None:
        return error("Meal plan not found.", 404)
    return jsonify(plan_payload(plan))


def _available_menus(day, period, hall_id):
    menus = []
    timestamp = ithaca_now().timestamp()
    for hall in live_halls():
        if hall_id is not None and hall.eatery_id != hall_id:
            continue
        for menu in hall.menus:
            if not menu.published:
                continue
            if period == "now":
                if menu.starts_at is not None and menu.ends_at is not None:
                    if menu.starts_at <= timestamp < menu.ends_at:
                        menus.append(menu)
            elif menu.service_date == day and (period == "full_day" or menu.meal_period == period):
                menus.append(menu)
    return menus


def save_or_generate_plan():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error("Send a JSON object.")
    name = body.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > 120):
        return error("Use a name with 1–120 characters.")
    if "items" in body:
        items = body["items"]
        if not isinstance(items, list) or not 1 <= len(items) <= 50:
            return error("Choose between 1 and 50 plate items.")
        plate = []
        for entry in items:
            if not isinstance(entry, dict) or type(entry.get("menu_item_id")) is not int:
                return error("Each plate item needs a menu item ID.")
            portion = entry.get("portion", 1)
            if type(portion) not in (float, int) or portion not in PORTIONS:
                return error("Choose a portion of ½, 1, 1½, or 2 servings.")
            item = Menuitem.query.filter_by(id=entry["menu_item_id"]).first()
            if item is None:
                return error("Menu item not found.", 404)
            plate.append((item, portion))
        day = ithaca_now().date().isoformat()
        goals = None
        description = "Saved plate"
    else:
        try:
            day = menu_day(body.get("date"))
        except (ValueError, TypeError):
            return error("Use YYYY-MM-DD for the service date.")
        period = body.get("meal", "lunch")
        if period not in PLANNING_PERIODS + ("now", "full_day"):
            return error("Choose an available meal or a full-day plan.")
        goals = {"calorie_cap": body.get("calorie_cap"), "protein_minimum": body.get("protein_minimum", 0)}
        for field in ("carbs_target", "fat_target"):
            if body.get(field) is not None:
                goals[field] = body[field]
        for value in goals.values():
            if type(value) not in (int, float) or not 0 <= value <= 10000:
                return error("Use a positive calorie cap and nonnegative macro goals.")
        if goals["calorie_cap"] == 0:
            return error("Use a positive calorie cap and nonnegative macro goals.")
        menus = _available_menus(day, period, body.get("hall_id"))
        plate = choose_plan(menus, goals, full_day=period == "full_day")
        if not plate:
            return error("No available combination with nutrition data meets those goals.", 422)
        description = "Goal-based meal plan"
    name = name.strip() if name else f"{description} {uuid4().hex[:8]}"
    if Mealplan.query.filter_by(name=name).first():
        return error("A plan already uses that name.", 409)
    plan = Mealplan(name=name, description=description, goals=json.dumps(goals) if goals else None,
                    snapshot=json.dumps(snapshot(plate, day)))
    for item, _portion in plate:
        if item not in plan.menuitems:
            plan.menuitems.append(item)
    db.session.add(plan)
    db.session.commit()
    return jsonify(plan_payload(plan)), 201
