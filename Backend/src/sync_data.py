"""Import dining and nutrition data into the app's SQLite database."""

import os
import sys
from pathlib import Path

import requests
from flask import Flask

from db import db
from dining import sync_menus
from nutrition import enrich_nutrition


def main():
    usage = "Usage: python sync_data.py menus | nutrition [limit]"
    if len(sys.argv) < 2 or sys.argv[1] not in ("menus", "nutrition"):
        raise SystemExit(usage)
    command = sys.argv[1]
    if len(sys.argv) > 3 or (command == "menus" and len(sys.argv) != 2):
        raise SystemExit(usage)

    if command == "nutrition":
        key = os.environ.get("USDA_API_KEY")
        if not key:
            raise SystemExit("Set USDA_API_KEY to look up nutrition.")
        limit = 25
        if len(sys.argv) == 3:
            try:
                limit = int(sys.argv[2])
            except ValueError:
                raise SystemExit("Use a limit between 1 and 500.") from None
        if not 1 <= limit <= 500:
            raise SystemExit("Use a limit between 1 and 500.") from None

    app = Flask(__name__, instance_path=str(Path(__file__).resolve().parent / "instance"))
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///campusmacros.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        try:
            if command == "menus":
                result = sync_menus()
                print(f"Imported {result['halls']} dining halls and {result['services']} meal services.")
            else:
                result = enrich_nutrition(key, limit)
                print(f"Checked {result['checked']} dishes and matched {result['matched']}.")
        except (requests.RequestException, ValueError, KeyError, TypeError):
            db.session.rollback()
            raise SystemExit(f"{command.capitalize()} sync failed. Previously saved data was retained.") from None


if __name__ == "__main__":
    main()
