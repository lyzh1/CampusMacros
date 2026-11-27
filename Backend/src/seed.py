"""Sample halls, menus, dishes, and starter meal plans."""
import json
from pathlib import Path

from db import DiningHall, Dish, Mealplan, Menu, Menuitem, db

DATA_FILE = Path(__file__).with_name("seed_data.json")


def seed_database():
    data = json.loads(DATA_FILE.read_text())

    dishes_by_name = {}
    for row in data["dishes"]:
        dish = Dish.query.filter_by(name=row["name"], catalog_key=None).first()
        if dish is None:
            dish = Dish(**row)
            db.session.add(dish)
        dishes_by_name[dish.name] = dish

    halls_by_eatery_id = {}
    first_seed = DiningHall.query.filter(DiningHall.eatery_id.like("sample-%")).first() is None
    for row in data["dining_halls"]:
        hall = DiningHall.query.filter_by(eatery_id=row["eatery_id"]).first()
        if hall is None:
            hall = DiningHall(**row)
            db.session.add(hall)
        halls_by_eatery_id[hall.eatery_id] = hall

    menuitems_by_dish_name = {}
    for row in data["menus"]:
        hall = halls_by_eatery_id[row["hall_eatery_id"]]
        menu = Menu.query.filter_by(
            hall=hall, service_date=row["service_date"], meal_period=row["meal_period"]
        ).first()
        if menu is None:
            menu = Menu(hall=hall, service_date=row["service_date"], meal_period=row["meal_period"])
            db.session.add(menu)

        for entry in row["items"]:
            dish = dishes_by_name[entry["dish"]]
            item = Menuitem.query.filter_by(menu=menu, dish_id=dish.id).first()
            if item is None:
                # Reuse an older unassigned item so saved plans keep the same item ID.
                item = Menuitem.query.filter_by(menu_id=None, dish_id=dish.id).first()
                if item is None:
                    item = Menuitem(dish_id=dish.id)
                    db.session.add(item)
                item.menu = menu
            item.station = entry.get("station")
            if dish.name not in menuitems_by_dish_name:
                menuitems_by_dish_name[dish.name] = item

    if first_seed:
        for row in data.get("mealplans", []):
            plan = Mealplan.query.filter_by(name=row["name"]).first()
            if plan is None:
                plan = Mealplan(name=row["name"], description=row.get("description", ""))
                for name in row["dishes"]:
                    plan.menuitems.append(menuitems_by_dish_name[name])
                db.session.add(plan)

    db.session.commit()
