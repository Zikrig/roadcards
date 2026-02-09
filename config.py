import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Получаем список ID администраторов через запятую
def get_admin_ids():
    ids = []
    # Из новой переменной ADMIN_IDS (через запятую)
    raw_ids = os.getenv("ADMIN_IDS", "")
    if raw_ids:
        ids.extend([int(i.strip()) for i in raw_ids.split(",") if i.strip().isdigit()])
    
    # Из старой переменной ADMIN_ID (одиночный)
    single_id = os.getenv("ADMIN_ID", "")
    if single_id and single_id.isdigit():
        ids.append(int(single_id))
    
    return list(set(ids)) # Убираем дубликаты

ADMIN_IDS = get_admin_ids()

# Собираем URL базы данных динамически
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "roadcards")
DB_HOST = os.getenv("DB_HOST", "localhost")  # По умолчанию localhost для локального запуска
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
