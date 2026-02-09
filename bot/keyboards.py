from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_user_main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="user_transactions"))
    builder.row(InlineKeyboardButton(text="💳 Реквизиты для оплаты", callback_data="user_requisites"))
    builder.row(InlineKeyboardButton(text="💰 Моя задолженность", callback_data="user_balance"))
    return builder.as_markup()

def get_admin_main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Загрузить отчет", callback_data="admin_upload"))
    builder.row(InlineKeyboardButton(text="Выгрузить сделки", callback_data="admin_export"))
    builder.row(InlineKeyboardButton(text="Рассылка всем", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="Создать ссылку регистрации", callback_data="admin_gen_link"))
    return builder.as_markup()

def get_report_type_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Траты клиентов", callback_data="report_expense"))
    builder.row(InlineKeyboardButton(text="Оплаты клиентов", callback_data="report_payment"))
    return builder.as_markup()

def get_confirm_format_kb(report_type: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Да", callback_data=f"confirm_yes_{report_type}"))
    builder.row(InlineKeyboardButton(text="Нет", callback_data="confirm_no"))
    return builder.as_markup()

def get_transactions_kb(transactions, page, total_pages):
    builder = InlineKeyboardBuilder()
    for t in transactions:
        # 🔴 для трат, 🟢 для оплат
        prefix = "🔴" if t.type.value == "expense" else "🟢"
        builder.row(InlineKeyboardButton(
            text=f"{prefix} {t.date.strftime('%d.%m.%Y %H:%M')}", 
            callback_data=f"trans_details_{t.id}"
        ))
    
    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"trans_page_{page-1}"))
    if page < total_pages - 1:
        pagination_row.append(InlineKeyboardButton(text="➡️", callback_data=f"trans_page_{page+1}"))
    
    if pagination_row:
        builder.row(*pagination_row)
    
    # Кнопка возврата в главное меню
    builder.row(InlineKeyboardButton(text="🏠 В главное меню", callback_data="user_main_menu"))
        
    return builder.as_markup()

def get_back_to_list_kb(page):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Назад", callback_data=f"trans_page_{page}"))
    return builder.as_markup()

