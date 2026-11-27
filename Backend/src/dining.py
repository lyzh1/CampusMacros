"""Import Eatery dining-room menus and expose them in the iOS menu format."""

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

from db import DiningHall, Dish, Menu, Menuitem, db


EATERY_URL = "https://eatery-backend.cornellappdev.com/eateries"
ITHACA = ZoneInfo("America/New_York")
MACROS = ("calories", "protein", "carbs", "fat")
PERIODS = {
    "BREAKFAST": "breakfast", "CONTINENTAL_BREAKFAST": "breakfast",
    "BRUNCH": "lunch", "LUNCH": "lunch", "LATE_LUNCH": "lunch",
    "DINNER": "dinner", "LATE_NIGHT": "dinner",
}
TAGS = {"vegan": "vegan", "vegetarian": "vegetarian", "gluten free": "gluten-free"}


def ithaca_now():
    return datetime.now(ITHACA)


def clock_label(timestamp):
    return datetime.fromtimestamp(timestamp, ITHACA).strftime("%I:%M %p").lstrip("0")


def normalized_name(name):
    return " ".join(name.casefold().split())


def sync_menus():
    response = requests.get(EATERY_URL, timeout=20)
    response.raise_for_status()
    return import_menus(response.json())


def import_menus(payload):
    if not isinstance(payload, list):
        raise ValueError("Eatery did not return an eatery list.")

    rooms = []
    for room in payload:
        if not isinstance(room, dict):
            raise ValueError("Eatery did not return an eatery list.")
        if not room.get("cornellDining") or "DINING_ROOM" not in room.get("eateryTypes", []):
            continue
        if room.get("cornellId") is None or not isinstance(room.get("events"), list):
            raise ValueError("Eatery returned incomplete dining-room data.")
        rooms.append(room)
    if not rooms:
        raise ValueError("Eatery returned incomplete dining-room data.")

    today = ithaca_now().date().isoformat()
    room_ids = [str(room["cornellId"]) for room in rooms]
    # Keep old records for saved plans and list only services still in the feed.
    for menu in Menu.query.filter(Menu.service_date >= today).all():
        if menu.hall.eatery_id in room_ids:
            menu.published = False

    service_count = 0
    for room in rooms:
        eatery_id = str(room["cornellId"])
        hall = DiningHall.query.filter_by(eatery_id=eatery_id).first()
        if hall is None:
            hall = DiningHall(eatery_id=eatery_id, name=room["name"])
            db.session.add(hall)
        hall.name = room["name"]
        hall.location = room.get("location") or ""

        for event in room["events"]:
            period = PERIODS.get(event.get("type"))
            if period is None:
                continue
            start = datetime.fromisoformat(event["startTimestamp"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(event["endTimestamp"].replace("Z", "+00:00"))
            if start.tzinfo is None or end.tzinfo is None or end <= start:
                raise ValueError("Eatery returned an invalid meal window.")
            timestamp = int(start.timestamp())
            day = start.astimezone(ITHACA).date().isoformat()
            menu = Menu.query.filter_by(hall=hall, starts_at=timestamp, meal_period=period).first()
            if menu is None:
                menu = Menu(hall=hall, meal_period=period, service_date=day, starts_at=timestamp)
                db.session.add(menu)
            menu.ends_at = int(end.timestamp())
            menu.published = True
            _save_menu_items(menu, event.get("menu") or [])
            service_count += 1

    db.session.commit()
    return {"halls": len(rooms), "services": service_count}


def _save_menu_items(menu, categories):
    for item in menu.items:
        item.listed = False

    for category in categories:
        station = category["name"].strip()
        if normalized_name(station) == "special menu event":
            continue  # This section contains event announcements and ticket instructions.
        for entry in category.get("items") or []:
            name = entry["name"].strip()
            if not name:
                continue
            key = f"{menu.hall.eatery_id}:{normalized_name(name)}"
            dish = Dish.query.filter_by(catalog_key=key).first()
            if dish is None:
                dish = Dish(name=name, description="", serving_description="")
                dish.catalog_key = key
                db.session.add(dish)

            item = Menuitem.query.filter_by(menu=menu, dishes=dish, station=station).first()
            if item is None:
                item = Menuitem(station=station)
                item.menu = menu
                item.dishes = dish
                db.session.add(item)
            item.listed = True
            item.dietary_tags = json.dumps(_dietary_tags(entry))


def _dietary_tags(entry):
    tags = []
    for preference in entry.get("dietaryPreferences") or []:
        if isinstance(preference, dict):
            preference = preference.get("name", "")
        if not isinstance(preference, str):
            continue
        tag = TAGS.get(preference.lower().replace("-", " "))
        if tag and tag not in tags:
            tags.append(tag)
    return sorted(tags)


def live_halls():
    return (DiningHall.query.filter(DiningHall.eatery_id.notlike("sample-%"))
            .order_by(DiningHall.name).all())


def menu_items(menu):
    return [item for item in menu.items if item.listed]


def dish_payload(item):
    dish = item.dishes
    menu = item.menu
    hall_name = None
    meal = None
    service_date = None
    sample = False
    if menu is not None:
        hall_name = menu.hall.name
        meal = menu.meal_period
        service_date = menu.service_date
        sample = menu.hall.eatery_id.startswith("sample-")

    source = dish.nutrition_source or None
    macros = None
    if source or sample or dish.serving_description:
        macros = {
            "calories": dish.calories,
            "protein": dish.protein,
            "carbs": dish.carbs,
            "fat": dish.fat,
        }
        if source is None:
            source = "sample" if sample else "manual"

    ranges = {}
    for macro in MACROS:
        low = getattr(dish, f"{macro}_low", None)
        high = getattr(dish, f"{macro}_high", None)
        if low is not None and high is not None:
            ranges[macro] = {"low": low, "high": high}

    return {
        "id": str(item.id), "name": dish.name, "station": item.station or "",
        "serving_description": dish.serving_description or "Serving size unavailable",
        "dietary_tags": json.loads(item.dietary_tags or "[]"),
        "macros": macros,
        "macro_ranges": ranges,
        "source": source,
        "source_url": dish.nutrition_source_url,
        "hall_name": hall_name,
        "meal": meal,
        "service_date": service_date,
    }


def menu_day(raw):
    if raw:
        return date.fromisoformat(raw).isoformat()
    return ithaca_now().date().isoformat()
