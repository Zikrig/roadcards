import datetime

def get_russian_month(month_idx):
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    return months[month_idx - 1]

def format_last_update(dt: datetime.datetime):
    if not dt:
        return "неизвестно"
    month = get_russian_month(dt.month)
    return dt.strftime(f"%H:%M %d {month} %Y")

def update_last_update_time():
    now = datetime.datetime.now()
    with open("last_update.txt", "w", encoding="utf-8") as f:
        f.write(now.isoformat())

def get_last_update_time():
    try:
        with open("last_update.txt", "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                dt = datetime.datetime.fromisoformat(content)
                return format_last_update(dt)
    except FileNotFoundError:
        pass
    return "неизвестно"

