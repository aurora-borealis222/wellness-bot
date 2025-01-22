from datetime import date

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import service
from service import *
from states import UserProfile

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Добро пожаловать! \nВас приветствует бот для расчёта нормы воды, калорий и трекинга активности.\n\n"
                         + "Введите /help для списка команд.\n\nТакже для использования некоторых команд можно открыть Меню.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Доступные команды:\n"
        "/start - Начало работы\n"
        "/set_profile - Настройка профиля пользователя\n"
        "/log_water - Логгирование воды (с параметром)\n"
        "/log_food - Логгирование еды (с параметрами)\n"
        "/log_workout - Логгирование тренировок (с параметрами)\n"
        "/check_progress - Прогресс по воде и калориям"
    )

@router.message(Command("set_profile"))
async def set_profile(message: Message, state: FSMContext):
    await message.answer("Введите ваш вес (в кг):")
    await state.set_state(UserProfile.weight)

@router.message(UserProfile.weight)
async def process_weight(message: Message, state: FSMContext):
    await state.update_data(weight=int(message.text))
    await message.answer("Введите ваш рост (в см):")
    await state.set_state(UserProfile.height)

@router.message(UserProfile.height)
async def process_height(message: Message, state: FSMContext):
    await state.update_data(height=int(message.text))
    await message.answer("Введите ваш возраст:")
    await state.set_state(UserProfile.age)

@router.message(UserProfile.age)
async def process_age(message: Message, state: FSMContext):
    await state.update_data(age=int(message.text))
    await message.answer("Сколько минут активности у вас в день?")
    await state.set_state(UserProfile.activity)

@router.message(UserProfile.activity)
async def process_activity(message: Message, state: FSMContext):
    await state.update_data(activity=int(message.text))
    await message.answer("В каком городе вы находитесь?")
    await state.set_state(UserProfile.city)

@router.message(UserProfile.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    data = await state.get_data()
    saved_profile = await save_profile(data.copy(), message.from_user.id)
    await state.clear()
    await message.answer(f"Ваши данные сохранены:\n{profile_to_str(saved_profile)}")

@router.message(Command("log_water"))
async def log_water(message: Message, command: CommandObject, state: FSMContext):
    logged_water = int(command.args)
    await state.set_state(UserProfile.logged_water)
    await state.update_data(logged_water=logged_water)

    mls_to_goal = service.get_water_goal_by_logged(logged_water, message.from_user.id)
    result_message = f"Сохранено: {logged_water} мл. До выполнения нормы воды осталось: {str(mls_to_goal)}"

    await state.clear()
    if mls_to_goal > 0:
        await message.answer(result_message)
    elif mls_to_goal == 0:
        await message.answer(result_message + f"\nНорма воды достигнута!")

@router.message(Command("log_food"))
async def log_food(message: Message, command: CommandObject, state: FSMContext):
    logged_food = command.args
    await state.set_state(UserProfile.logged_food)
    await state.update_data(logged_food=logged_food)

    calories_per_100g = await get_calories(logged_food, 100)

    await message.answer(f"{logged_food} - {calories_per_100g} ккал на 100 г. Сколько грамм вы съели?")
    await state.set_state(UserProfile.logged_calories)

@router.message(UserProfile.logged_calories)
async def process_logged_calories(message: Message, state: FSMContext):
    logged_calories = int(message.text)
    await state.update_data(logged_calories=logged_calories)

    data = await state.get_data()
    logged_food = data.get('logged_food')
    calories = await get_calories(logged_food, logged_calories)
    log_calories(calories, message.from_user.id)

    await state.clear()
    await message.answer(f"Записано: {calories} ккал.")

@router.message(Command("log_workout"))
async def log_workout(message: Message, command: CommandObject):
    workout_type, duration = command.args.split()
    duration = int(duration)

    calories_burned_dict = await get_calories_burned_and_update_data(workout_type, duration, message.from_user.id)

    result_message = f"{workout_type} {duration} минут — {calories_burned_dict['calories_burned']} ккал."
    if calories_burned_dict["water_goal_addition"] > 0:
        result_message += f" Дополнительно: выпейте {calories_burned_dict['water_goal_addition']} мл воды."

    await message.answer(result_message)

@router.message(Command("check_progress"))
async def check_progress(message: Message):
    user_data = get_user_data(message.from_user.id)

    total_water = 0
    if "logged_water" in user_data:
        total_water = sum(value for key, value in user_data["logged_water"].items() if key.date() == date.today())

    total_calories = 0
    if "logged_calories" in user_data:
        total_calories = sum(value for key, value in user_data["logged_calories"].items() if key.date() == date.today())

    calories_burned = user_data["calories_burned"] if "calories_burned" in user_data else 0

    result_message = (
            f"📊 Прогресс:\n Вода:\n - Выпито: {total_water} мл из {user_data['water_goal']} мл.\n - Осталось: "
            f"{user_data['water_goal'] - total_water} мл.\n\n Калории:\n- Потреблено: {total_calories} ккал из "
            f"{user_data['calories_goal']} ккал.\n- Сожжено: {calories_burned} ккал.\n"
            f"- Баланс: {total_calories - calories_burned} ккал."
    )
    await message.answer(result_message)

def setup_handlers(dp):
    dp.include_router(router)
