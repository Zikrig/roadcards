import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from bot.handlers import user, admin
from database.db import init_db

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Initialize database with retries
    max_retries = 5
    retry_delay = 5
    for i in range(max_retries):
        try:
            await init_db()
            logging.info("Database initialized successfully")
            break
        except Exception as e:
            if i < max_retries - 1:
                logging.error(f"Database connection failed: {e}. Retrying in {retry_delay} seconds... ({i+1}/{max_retries})")
                await asyncio.sleep(retry_delay)
            else:
                logging.error("Could not connect to the database. Exiting.")
                return
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register routers
    dp.include_router(admin.router)
    dp.include_router(user.router)
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

