from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

list_entry = db.Table(
    "list_association",
    db.Model.metadata,
    db.Column("mealplan_id", db.Integer, db.ForeignKey("mealplans.id"), primary_key=True),
    db.Column("menuitem_id", db.Integer, db.ForeignKey("menuitems.id"), primary_key=True)
)


class DiningHall(db.Model):
    """A Cornell dining hall with its identifier from Eatery."""

    __tablename__ = "dining_halls"
    id = db.Column(db.Integer, primary_key=True)
    eatery_id = db.Column(db.String, nullable=False, unique=True)
    name = db.Column(db.String, nullable=False)
    location = db.Column(db.String)

    menus = db.relationship("Menu", back_populates="hall")


class Menu(db.Model):
    """One dated meal service at a dining hall."""

    __tablename__ = "menus"
    id = db.Column(db.Integer, primary_key=True)
    hall_id = db.Column(db.Integer, db.ForeignKey("dining_halls.id"), nullable=False)
    service_date = db.Column(db.String, nullable=False)  # Ithaca date, YYYY-MM-DD
    meal_period = db.Column(db.String, nullable=False)
    starts_at = db.Column(db.Integer)  # UTC Unix seconds
    ends_at = db.Column(db.Integer)
    published = db.Column(db.Boolean, nullable=False, default=True)

    hall = db.relationship("DiningHall", back_populates="menus")
    items = db.relationship("Menuitem", back_populates="menu")


class Mealplan(db.Model):
    """
    Mealplan model (Table)
    Has a many-to-many relationship with menuitems
    """

    __tablename__ = "mealplans"
    id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    description = db.Column(db.String, nullable = False)
    name = db.Column(db.String, nullable = False, unique = True)
    prompt = db.Column(db.String)
    goals = db.Column(db.String)  # JSON text with the goals used to build the plan
    snapshot = db.Column(db.String)  # JSON text with the saved portions and totals
    menuitems = db.relationship("Menuitem", secondary=list_entry, back_populates="mealplans",)

    def __init__(self, **kwargs):
        """
        Initializes a Mealplan Object
        """
        self.name = kwargs.get("name", "")
        self.description = kwargs.get("description", "")
        self.prompt = kwargs.get("prompt")
        self.goals = kwargs.get("goals")
        self.snapshot = kwargs.get("snapshot")

    def serialize(self):
        """
        Prepare object to be sent to user
        """

        return {

            "id": self.id,
            "name": self.name,
            "description": self.description,
            "menuitems": [a.simple_serialize() for a in self.menuitems],
        }

    def simple_serialize(self):
        return {"id": self.id, "name": self.name, "description": self.description, }

class Menuitem(db.Model):
    """
    Menuitem model (Table)
    Belongs to a Menu and refers to a Dish.
    Can appear in many meal plans.
    """

    __tablename__ = "menuitems"
    id = db.Column(db.Integer, primary_key = True, autoincrement = True)
    # Older catalog items may be unassigned until they are placed on a menu.
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id"))
    dish_id = db.Column(db.Integer, db.ForeignKey("dishes.id"), nullable = False)
    station = db.Column(db.String)
    dietary_tags = db.Column(db.String)
    listed = db.Column(db.Boolean, nullable=False, default=True)
    menu = db.relationship("Menu", back_populates="items")
    dishes = db.relationship("Dish", back_populates="menuitems")
    mealplans = db.relationship("Mealplan",secondary=list_entry, back_populates="menuitems")

    def __init__(self, **kwargs):
        """
        Initializes a Menuitem Object
        """
        self.menu_id = kwargs.get("menu_id")
        self.dish_id = kwargs.get("dish_id")
        self.station = kwargs.get("station")

    def serialize(self):
        """
        Serialize a Menuitem Object
        """
        return {
            "id": self.id,
            "menu_id": self.menu_id,
            "dishes": self.dishes.simple_serialize(),
            "mealplans": [a.simple_serialize() for a in self.mealplans],
        }

    def simple_serialize(self):
        """
        Serialize a Menuitem Object
        """

        return {
            "id": self.id,
            "menu_id": self.menu_id,
            "dish_id": self.dish_id,
        }


class Dish(db.Model):
    """
    dish model (Table)
    Has a one-to-many relationship with MenuItem
    """

    __tablename__ = "dishes"
    id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable = False)
    serving_description = db.Column(db.String, nullable = False)
    menuitems = db.relationship("Menuitem", back_populates="dishes", cascade="all, delete-orphan")
    
    # Nutrition facts per serving
    calories = db.Column(db.Float, nullable = False)
    protein = db.Column(db.Float, nullable = False)
    carbs = db.Column(db.Float, nullable = False)
    fat = db.Column(db.Float, nullable = False)

    # Nutrition provenance and import metadata.
    nutrition_source = db.Column(db.String)
    nutrition_source_url = db.Column(db.String)
    catalog_key = db.Column(db.String)
    usda_checked_at = db.Column(db.Integer)


    def __init__(self, **kwargs):
        """
        Initializes a dish Object
        """
        self.name = kwargs.get("name", "")
        self.description = kwargs.get("description", "")
        self.serving_description = kwargs.get("serving_description", "")
        self.calories = kwargs.get("calories", 0)
        self.protein = kwargs.get("protein", 0)
        self.carbs = kwargs.get("carbs", 0)
        self.fat = kwargs.get("fat", 0)
        self.nutrition_source = kwargs.get("nutrition_source")
        self.nutrition_source_url = kwargs.get("nutrition_source_url")
        
    def serialize(self):
        """
        Serialize a dish Object
        """
        data = self.simple_serialize()
        data["menuitems"] = [fl.simple_serialize() for fl in self.menuitems]
        return data
        

    def simple_serialize(self):
        """
        Serialize a dish Object
        """

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "serving_description": self.serving_description,
            "calories": self.calories,
            "protein": self.protein,
            "carbs": self.carbs,
            "fat": self.fat,
        }
