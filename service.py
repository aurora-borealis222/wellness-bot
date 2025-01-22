from typing import Any
import aiohttp
from aiohttp import web
from config import OWM_API_KEY, NTX_APP_ID, NTX_APP_KEY
import datetime
from googletrans import Translator
import asyncio
import aioschedule

OWM_BASE_URL = "https://api.openweathermap.org"
GEOCODING_URL = "/geo/1.0/direct"
WEATHER_URL = "/data/2.5/weather"

NUTRITIONIX_BASE_URL = "https://trackapi.nutritionix.com"
NUTRIENTS_URL = "/v2/natural/nutrients"
EXERCISE_URL = "/v2/natural/exercise"

users_data = {}
translator = Translator()

profile_labels_dict = {
    "weight": "Вес (кг)",
    "height": "Рост (см)",
    "age": "Возраст",
    "activity": "Активность в день (мин)",
    "city": "Город",
    "water_goal": "Норма воды (мл)",
    "calories_goal": "Норма калорий"
}

async def save_profile(profile: dict[str, Any], user_id: int) -> dict[str, Any]:
    if user_id not in users_data:
        users_data[user_id] = profile
    else:
        users_data[user_id].update(profile)

    await calculate_goals(profile)
    return users_data[user_id]

async def calculate_goals(profile: dict[str, Any]) -> None:
    weight = profile.get("weight")
    water_goal = weight * 30

    activity = profile.get("activity")
    activity_divisors_count = activity // 30
    water_goal_addition = sum(500 for i in range(activity_divisors_count))
    water_goal += water_goal_addition

    city = profile.get("city")
    temperature = await get_temperature_by_city(city_name=city)
    if temperature > 25:
        water_goal += 500

    profile["water_goal"] = water_goal

    calories_goal = 10 * weight + 6.25 * profile.get("height") - 5 * profile.get("age")
    profile["calories_goal"] = calories_goal

async def get_temperature_by_city(city_name: str, state_code: str = '', country_code: str = '',
                                  limit: int = 1) -> float:
    try:
        async with aiohttp.ClientSession(OWM_BASE_URL) as session:
            params = {"q": f"{city_name},{state_code},{country_code}", "limit": limit, "appid": OWM_API_KEY}

            async with session.get(GEOCODING_URL, params=params) as response:
                coords_json = await response.json()
                lat = coords_json[0]['lat']
                lon = coords_json[0]['lon']

                params = {"lat": lat, "lon": lon, "units": "metric", "appid": OWM_API_KEY}
                async with session.get(WEATHER_URL, params=params) as response:
                    weather_json = await response.json()
                    return weather_json["main"]["temp"]

    except (BaseException, Exception):
        raise web.HTTPUnauthorized(text="Invalid API key. Please see https://openweathermap.org/faq#error401 for more info.")

def profile_to_str(profile: dict[str, Any]) -> str:
    result = (
        f"{profile_labels_dict.get("weight")}: {profile["weight"]}\n"
        f"{profile_labels_dict.get("height")}: {profile["height"]}\n"
        f"{profile_labels_dict.get("age")}: {profile["age"]}\n"
        f"{profile_labels_dict.get("activity")}: {profile["activity"]}\n"
        f"{profile_labels_dict.get("city")}: {profile["city"]}\n"
        f"{profile_labels_dict.get("water_goal")}: {profile["water_goal"]}\n"
        f"{profile_labels_dict.get("calories_goal")}: {profile["calories_goal"]}"
    )
    return result

def get_water_goal_by_logged(logged_water: int, user_id: int) -> int:
    if "logged_water" not in users_data[user_id]:
        users_data[user_id]["logged_water"] = {}
    users_data[user_id]["logged_water"][datetime.datetime.now()] = logged_water

    mls_to_goal = users_data[user_id]["water_goal"] - sum(users_data[user_id]["logged_water"].values())
    if mls_to_goal > users_data[user_id]["water_goal"]:
        mls_to_goal = 0
    return mls_to_goal

async def get_calories(food: str, quantity: float = 0) -> float:
    food_translated = await translator.translate(food, src="ru", dest="en")
    food_en = food_translated.text

    try:
        async with aiohttp.ClientSession(NUTRITIONIX_BASE_URL) as session:
            headers = {"Content-Type": "application/json", "x-app-id": NTX_APP_ID, "x-app-key": NTX_APP_KEY}
            query_json = {"query": f"{food_en} {quantity} g"}

            async with session.post(NUTRIENTS_URL, headers=headers, json=query_json) as response:
                response_json = await response.json()
                return response_json["foods"][0]["nf_calories"]

    except (BaseException, Exception):
        raise web.HTTPBadRequest(text="Invalid API id or/and key")

def log_calories(logged_calories: float, user_id: int) -> None:
    if "logged_calories" not in users_data[user_id]:
        users_data[user_id]["logged_calories"] = {}
    users_data[user_id]["logged_calories"][datetime.datetime.now()] = logged_calories

async def get_calories_burned_and_update_data(workout_type: str, duration: float, user_id: int) -> dict[str, Any]:
    workout_type_translated = await translator.translate(workout_type, src="ru", dest="en")
    workout_type_en = workout_type_translated.text

    try:
        async with aiohttp.ClientSession(NUTRITIONIX_BASE_URL) as session:
            headers = {"Content-Type": "application/json", "x-app-id": NTX_APP_ID, "x-app-key": NTX_APP_KEY}
            query_json = {"query": f"{workout_type_en} {duration}"}

            async with session.post(EXERCISE_URL, headers=headers, json=query_json) as response:
                response_json = await response.json()
                calories_burned = response_json["exercises"][0]["nf_calories"]
                if "calories_burned" not in users_data[user_id]:
                    users_data[user_id]["calories_burned"] = 0
                users_data[user_id]["calories_burned"] += calories_burned

                if duration >= 30:
                    duration_divisors_count = int(duration // 30)
                    water_goal_addition = sum(500 for i in range(duration_divisors_count))
                    users_data[user_id]["water_goal"] += water_goal_addition

                if duration >= users_data[user_id]["activity"]:
                    users_data[user_id]["calories_goal"] += 400

                return {"calories_burned": calories_burned, "water_goal_addition": water_goal_addition}

    except (BaseException, Exception):
        raise web.HTTPBadRequest(text="Invalid API id or/and key")

def get_user_data(user_id: int) -> dict[str, Any]:
    return users_data[user_id]

async def update_profiles() -> None:
    for user_id in users_data:
        await calculate_goals(users_data[user_id])

async def scheduler():
    aioschedule.every().day.at("00:00").do(update_profiles())
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)

async def on_startup(_):
    asyncio.create_task(scheduler())