from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

list_entry = db.Table(
    "list_association",
    db.Model.metadata,
    db.Column("mealplan_id", db.Integer, db.ForeignKey("mealplans.id"), primary_key=True),
    db.Column("menuitem_id", db.Integer, db.ForeignKey("menuitems.id"), primary_key=True)
)

class DiningHall(db.Model):
    """
    DiningHall model (Table)
    Has a one-to-many relationship with Menu
    """

    __tablename__ = "dininghalls"
    id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    eatery_id = db.Column(db.Integer) #To be finished once Menu is done
    name = db.Column(db.String, nullable = False)
    location = db.Column(db.String, nullable = False)
    menus = db.relationship("Menu", back_populates="dininghall", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        """
        Initializes DiningHall Object
        """
        self.name = kwargs.get("name", "")
        self.location = kwargs.get("location", "")
        self. eatery_id = kwargs.get("eatery_id", 0)

    def serialize(self):
        """
        Prepare object to be sent to user
        """

        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "menus": [m.simple_serialize() for m in self.menus],
        }

    def simple_serialize(self):
        return {
            "id": self.id,
            "eatery_id": self.eatery_id,
            "name": self.name,
            "location": self.location,
        }

class Menu(db.Model):
    """
    Menu model (Table)
    Has a one-to-many relationship with Dining Hall
    Has a one-to-many relationship with Menu Item
    """
    
    __tablename__ = "menus"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    hall_id = db.Column(db.Integer, db.ForeignKey("dininghalls.id"), nullable = False)
    #What purpose is service date and meal_period?
    service_date = db.Column(db.String, nullable = False)
    meal_period = db.Column(db.String, nullable = False)
    starts_at = db.Column(db.String, nullable = False)
    ends_at = db.Column(db.String, nullable = False)

    menuitems = db.relationship("Menuitem", back_populates="menu", cascade="all, delete-orphan")
    dininghall = db.relationship("DiningHall", back_populates="menus")

    def __init__(self, **kwargs):
        """
        Initializes a Menu Object
        """
        self.hall_id = kwargs.get("hall_id", 0)
        self.service_date = kwargs.get("service_date", "")
        self.meal_period = kwargs.get("meal_period", "")
        self.starts_at = kwargs.get("starts_at", "")
        self.ends_at = kwargs.get("ends_at", "")

    def serialize(self):
        """
        Prepares object to be sent to user
        """
        return {

            "id": self.id,
            "service_date": self.service_date,
            "meal_period": self.meal_period,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
            "menuitems": [mi.simple_serialize() for mi in self.menuitems],
            "dininghall": self.dininghall.simple_serialize(),
        }

    def simple_serialize(self):
        return {
            "id": self.id,
            "hall_id": self.hall_id,
            "service_date": self.service_date,
            "meal_period": self.meal_period,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
        }
        

class Mealplan(db.Model):
    """
    Mealplan model (Table)
    Has a many-to-many relationship with menuitems
    """

    __tablename__ = "mealplans"
    id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    description = db.Column(db.String, nullable = False)
    name = db.Column(db.String, nullable = False, unique = True)
    #Prompt & Snapshot go here
    menuitems = db.relationship("Menuitem", secondary=list_entry, back_populates="mealplans",)

    def __init__(self, **kwargs):
        """
        Initializes a Mealplan Object
        """
        self.name = kwargs.get("name", "")
        self.description = kwargs.get("description", "")

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
    Has a many-to-many relationship with Mealplan
    Has a one-to-many relationship with Dish
    """

    __tablename__ = "menuitems"
    id = db.Column(db.Integer, primary_key = True, autoincrement = True)
    menu_id = db.Column(db.Integer, db.ForeignKey("menus.id"), nullable = False) #Need to implement Menu first 
    dish_id = db.Column(db.Integer, db.ForeignKey("dishes.id"), nullable = False)
    menu = db.relationship("Menu", back_populates="menuitems")
    dish = db.relationship("Dish", back_populates="menuitems")
    #Unclear on Station parameter. String?
    mealplans = db.relationship("Mealplan",secondary=list_entry, back_populates="menuitems")

    def __init__(self, **kwargs):
        """
        Initializes a Menuitem Object
        """
        self.menu_id = kwargs.get("menu_id")
        self.dish_id = kwargs.get("dish_id")
        #Initialize station here

    def serialize(self):
        """
        Serialize a Menuitem Object
        """
        return {
            "id": self.id,
            "menu_id": self.menu_id,
            "dish": self.dish.simple_serialize(),
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
    menuitems = db.relationship("Menuitem", back_populates="dish", cascade="all, delete-orphan")    
    # Nutrition facts per serving
    calories = db.Column(db.Float, nullable = False)
    protein = db.Column(db.Float, nullable = False)
    carbs = db.Column(db.Float, nullable = False)
    fat = db.Column(db.Float, nullable = False)


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
