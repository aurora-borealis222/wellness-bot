from aiogram.fsm.state import State, StatesGroup

class UserProfile(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    city = State()
    logged_water = State()
    logged_food = State()
    logged_calories = State()