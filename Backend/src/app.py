import json
from pathlib import Path

from flask import Flask, request

import api_v1
from db import db, Dish, Menuitem, Mealplan
from seed import seed_database

app = Flask(__name__, instance_path=str(Path(__file__).resolve().parent / "instance"))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///campusmacros.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
with app.app_context():
    db.create_all()
    seed_database()


# Generalized response formats
def success_response(data, code=200):
    return json.dumps(data), code


def failure_response(message, code=404):
    return json.dumps({"error": message}), code


@app.route("/api/dishes/", methods=["GET"])
def get_all_dishes():
    dishes = db.session.scalars(db.select(Dish)).all()

    return success_response({"dishes": [dish.serialize() for dish in dishes]})


@app.route("/api/dishes/<int:dish_id>/", methods=["GET"])
def get_dish_by_id(dish_id):
    dish = db.session.get(Dish, dish_id)

    if dish is None:
        return failure_response("Dish not found")

    return success_response(dish.serialize())


@app.route("/api/mealplans/", methods=["GET"])
def get_all_mealplans():
    mealplans = db.session.scalars(db.select(Mealplan)).all()

    return success_response({"mealplans": [plan.serialize() for plan in mealplans]})


@app.route("/api/mealplans/<int:plan_id>/", methods=["GET"])
def get_mealplan_by_id(plan_id):
    plan = db.session.get(Mealplan, plan_id)

    if plan is None:
        return failure_response("Meal plan not found")

    return success_response(plan.serialize())


@app.route("/api/mealplans/", methods=["POST"])
def create_mealplan():
    body = request.get_json(silent=True)

    if not isinstance(body, dict):
        return failure_response("Invalid JSON body", 400)

    name = body.get("name")
    description = body.get("description", "")
    menuitem_ids = body.get("menuitem_ids", [])

    if not isinstance(name, str) or not name.strip():
        return failure_response("Name is required", 400)

    if not isinstance(description, str):
        return failure_response("Description must be a string", 400)

    if not isinstance(menuitem_ids, list) or any(
        type(item_id) is not int for item_id in menuitem_ids
    ):
        return failure_response("Invalid menu item IDs", 400)

    existing = db.session.scalar(db.select(Mealplan).filter_by(name=name))

    if existing is not None:
        return failure_response("Meal plan already exists", 409)

    menuitems = []

    for item_id in menuitem_ids:
        item = db.session.get(Menuitem, item_id)

        if item is None:
            return failure_response(f"Menu item {item_id} not found", 404)

        if item not in menuitems:
            menuitems.append(item)

    plan = Mealplan(name=name, description=description)

    plan.menuitems = menuitems

    db.session.add(plan)
    db.session.commit()

    return success_response(plan.serialize(), 201)


@app.route("/api/mealplans/<int:plan_id>/", methods=["DELETE"])
def delete_mealplan(plan_id):
    plan = db.session.get(Mealplan, plan_id)

    if plan is None:
        return failure_response("Meal plan not found")

    db.session.delete(plan)
    db.session.commit()

    return success_response({"message": "Meal plan deleted successfully"})


@app.route("/v1/halls", methods=["GET"])
def get_dining_halls():
    return api_v1.halls()


@app.route("/v1/halls/<hall_id>/menu", methods=["GET"])
def get_hall_menu(hall_id):
    return api_v1.hall_menu(hall_id)


@app.route("/v1/meal-plans", methods=["GET"])
def get_saved_plans():
    return api_v1.meal_plans()


@app.route("/v1/meal-plans/<int:plan_id>", methods=["GET"])
def get_saved_plan(plan_id):
    return api_v1.meal_plan(plan_id)


@app.route("/v1/meal-plans", methods=["POST"])
def save_meal_plan():
    return api_v1.save_or_generate_plan()


@app.route("/v1/meal-plans/<int:plan_id>", methods=["DELETE"])
def delete_saved_plan(plan_id):
    return delete_mealplan(plan_id)


if __name__ == "__main__":
    app.run(debug=True, port=8000)
