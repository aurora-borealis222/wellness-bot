import asyncio
from aiogram import Bot, Dispatcher
from config import TOKEN
from handlers import setup_handlers
from middlewares import LoggingMiddleware
from service import on_startup

bot = Bot(token=TOKEN)
dp = Dispatcher()

dp.message.middleware(LoggingMiddleware())
setup_handlers(dp)

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot, on_startup=on_startup)

if __name__ == "__main__":
    asyncio.run(main())
