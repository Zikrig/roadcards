from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import (
    get_user_by_tg_id, 
    is_in_whitelist, 
    register_user, 
    get_user_balance, 
    get_user_transactions, 
    count_user_transactions, 
    get_user_expense_stats,
    async_session, 
    get_user_by_card,
    get_all_user_cards
)
from sqlalchemy import select, and_
from database.models import Transaction
from bot.keyboards import (
    get_user_main_menu,
    get_transactions_kb,
    get_user_requisites_kb,
    get_user_delete_cards_kb,
    get_user_my_cards_kb,
)
from bot.utils import get_last_update_time
import math
import re

router = Router()

class Registration(StatesGroup):
    waiting_for_card = State()


MONTH_NAMES_RU = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}


def format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}".replace(",", " ")
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")

main_menu_text = (
    "Здравствуйте!\n"
    "Рады видеть вас в боте <b>Toplex</b>. Это ваш личный помощник по топливным картам — "
    "баланс, чеки, отчеты и связь с менеджером в одном месте.\n\n"
    "<b>3 шага для начала:</b>\n"
    "1. Изучите меню ниже — посмотрите, что умеет бот\n"
    "2. Если у вас есть <b>вторая карта</b> — добавьте ее в разделе «<b>Мои карты</b>»\n"
    "3. Возник вопрос? Напишите менеджеру в Telegram — @ToplexM"
)


def parse_cards_from_text(raw_value: str) -> list[str]:
    cards = [c.strip() for c in re.split(r"[,&;|\s]+", raw_value or "") if c.strip()]
    unique_cards = []
    seen = set()
    for card in cards:
        if card not in seen:
            seen.add(card)
            unique_cards.append(card)
    return unique_cards

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    user = await get_user_by_tg_id(message.from_user.id)
    if user:
        await message.answer(main_menu_text, reply_markup=get_user_main_menu(), parse_mode="HTML")
        return

    # Проверка на наличие аргумента в ссылке (Deep Linking)
    if command.args:
        card_numbers = parse_cards_from_text(command.args.strip())
        if not card_numbers:
            await message.answer("Ссылка регистрации не содержит номер карты.")
        else:
            missing_cards = []
            occupied_cards = []
            for card_number in card_numbers:
                if not await is_in_whitelist(card_number):
                    missing_cards.append(card_number)
                    continue
                existing_user = await get_user_by_card(card_number)
                if existing_user:
                    occupied_cards.append(card_number)

            if missing_cards:
                cards_str = ", ".join(missing_cards)
                await message.answer(f"Карты из ссылки не найдены в белом списке: {cards_str}.")
            elif occupied_cards:
                cards_str = ", ".join(occupied_cards)
                await message.answer(f"Карты из ссылки уже зарегистрированы другим пользователем: {cards_str}.")
            else:
                for card_number in card_numbers:
                    await register_user(message.from_user.id, card_number)
                cards_str = ", ".join(card_numbers)
                await message.answer(
                    f"Регистрация по картам {cards_str} прошла успешно!",
                    reply_markup=get_user_main_menu()
                )
                await state.clear()
                return

    # Если ссылки нет или она невалидна — обычный процесс
    await message.answer("Добро пожаловать! Пожалуйста, введите номер вашей топливной карты для регистрации.")
    await state.set_state(Registration.waiting_for_card)

@router.message(Command("null"))
async def cmd_null(message: Message, state: FSMContext):
    user = await get_user_by_tg_id(message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы в системе.")
        return
    
    async with async_session() as session:
        from database.models import User
        # Находим всех пользователей с этим telegram_id и удаляем их
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        db_users = result.scalars().all()
        
        cards = [u.card_number for u in db_users]
        
        for u in db_users:
            await session.delete(u)
        await session.commit()
            
    await state.clear()
    cards_str = ", ".join(cards)
    await message.answer(f"Вы успешно разлогинены. Все ваши карты (<code>{cards_str}</code>) теперь свободны для регистрации.", parse_mode="HTML")

@router.message(Registration.waiting_for_card)
async def process_card_number(message: Message, state: FSMContext):
    card_number = message.text.strip()
    if await is_in_whitelist(card_number):
        # Проверяем, не занята ли уже эта карта кем-то другим
        existing_user = await get_user_by_card(card_number)
        if existing_user:
            await message.answer("Этот номер карты уже зарегистрирован другим пользователем.")
            return

        await register_user(message.from_user.id, card_number)
        await message.answer("Регистрация прошла успешно!", reply_markup=get_user_main_menu())
        await state.clear()
    else:
        await message.answer("Этого номера карты нет в белом списке. Обратитесь к администратору.")

@router.callback_query(F.data == "user_balance")
async def show_balance(callback: CallbackQuery):
    user = await get_user_by_tg_id(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
    balance = await get_user_balance(callback.from_user.id)
    
    last_update = get_last_update_time()
    
    if balance < 0:
        text = f"Ваш баланс: +{abs(balance):.2f} рублей"
    else:
        text = f"Ваш баланс к оплате: {balance:.2f} рублей"
    
    text += f"\n\n🕒 Данные обновлены {last_update}"
        
    await callback.message.answer(text, reply_markup=get_user_main_menu())
    await callback.answer()

@router.callback_query(F.data == "user_requisites")
async def show_requisites(callback: CallbackQuery):
    text = (
        "💳 Реквизиты для оплаты:\n\n"
        "<code>2200 1545 0861 8864</code> Федаш Е. А.\n"
        "Альфа банк\n\n"
        "<code>2200 2479 6490 8215</code> Федаш Е. А.\n"
        "ВТБ банк\n\n"
        "<code>2202 2061 5142 4897</code> Федаш Е. А.\n"
        "Сбер банк\n\n"
        "Для пополнения баланса наличными обращайтесь к менеджеру @ToplexM"
    )
    await callback.message.edit_text(text, reply_markup=get_user_requisites_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "user_my_cards")
async def show_my_cards(callback: CallbackQuery):
    user_id = callback.from_user.id
    cards = await get_all_user_cards(user_id)
    cards_str = ", ".join(cards) if cards else "не привязаны"
    text = f"🧾 Мои карты:\n\n<i>{cards_str}</i>"
    await callback.message.edit_text(text, reply_markup=get_user_my_cards_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "user_add_card")
async def add_card_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Пожалуйста, введите номер топливной карты, которую вы хотите добавить:")
    await state.set_state(Registration.waiting_for_card)
    await callback.answer()

@router.callback_query(F.data == "user_del_card_list")
async def del_card_list(callback: CallbackQuery):
    cards = await get_all_user_cards(callback.from_user.id)
    if not cards:
        await callback.answer("У вас нет привязанных карт.")
        return
    await callback.message.edit_text("Выберите карту для удаления из вашего профиля:", reply_markup=get_user_delete_cards_kb(cards))
    await callback.answer()

@router.callback_query(F.data.startswith("user_del_card_exec_"))
async def del_card_exec(callback: CallbackQuery):
    card_number = callback.data.split("_")[-1]
    async with async_session() as session:
        from database.models import User
        result = await session.execute(
            select(User).where(and_(User.telegram_id == callback.from_user.id, User.card_number == card_number))
        )
        db_user = result.scalar_one_or_none()
        if db_user:
            await session.delete(db_user)
            await session.commit()
            await callback.answer(f"Карта {card_number} удалена.")
        else:
            await callback.answer("Карта не найдена.")
    
    # Возвращаемся в "Мои карты"
    await show_my_cards(callback)

@router.callback_query(F.data == "user_transactions")
async def show_transactions(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_tg_id(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
    
    await state.update_data(page=0)
    await send_transaction_page(callback.message, callback.from_user.id, 0)
    await callback.answer()

async def send_transaction_page(message: Message, telegram_id: int, page: int):
    page_size = 10
    transactions = await get_user_transactions(telegram_id, limit=page_size, offset=page * page_size)
    total_count = await count_user_transactions(telegram_id)
    total_pages = math.ceil(total_count / page_size)
    stats = await get_user_expense_stats(telegram_id)
    
    kb = get_transactions_kb(transactions, page, total_pages)
    stats_text = (
        "📊 Ваша статистика заправок:\n\n"
        f"⛽ Итого заправлено: {format_number(stats['total_liters'])} л\n"
        f"💰 Общая сумма: {format_number(stats['total_cost'])} ₽\n"
        f"🧾 Количество заправок: {stats['total_count']}\n"
    )

    if stats["monthly"]:
        stats_text += "\n📅 По месяцам:\n"
        current_year = None
        for item in stats["monthly"]:
            year = item["year"]
            month = item["month"]
            liters = item["liters"]
            cost = item["cost"]
            if year != current_year:
                current_year = year
                stats_text += f"\n{year} г.:\n"
            month_name = MONTH_NAMES_RU.get(month, str(month))
            stats_text += f"• {month_name}: {format_number(liters)} л ({format_number(cost)} ₽)\n"

    stats_text += f"\n\nВаши сделки (страница {page + 1} из {max(1, total_pages)}):"
    
    # We always use edit_text or answer a new message with the menu
    if (
        message.text.startswith("Ваши сделки")
        or message.text.startswith("Здравствуйте!")
        or message.text.startswith("📊 Ваша статистика заправок:")
    ):
        await message.edit_text(stats_text, reply_markup=kb)
    else:
        await message.answer(stats_text, reply_markup=kb)

@router.callback_query(F.data == "user_main_menu")
async def process_back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(main_menu_text, reply_markup=get_user_main_menu(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("trans_page_"))
async def process_pagination(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[-1])
    await state.update_data(page=page)
    await send_transaction_page(callback.message, callback.from_user.id, page)
    await callback.answer()

@router.callback_query(F.data.startswith("trans_details_"))
async def show_transaction_details(callback: CallbackQuery, state: FSMContext):
    transaction_id = int(callback.data.split("_")[-1])
    
    async with async_session() as session:
        transaction = await session.get(Transaction, transaction_id)
        if not transaction:
            await callback.answer("Сделка не найдена")
            return
        
        if transaction.type.value == 'expense':
            # Только Карта, дата, имя, вид транзакции, Стоимость
            text = (
                f"🔴 Списание\n"
                f"Карта: {transaction.card_number}\n"
                f"Дата: {transaction.date.strftime('%d.%m.%Y %H:%M')}\n"
                f"Имя: {transaction.item_name}\n"
                f"Вид транзакции: Списание\n"
                f"Стоимость: {transaction.cost:.2f} руб."
            )
        else:
            # Для оплат (пополнений) можно оставить полный вид или тоже сократить
            text = (
                f"🟢 Пополнение\n"
                f"Карта: {transaction.card_number}\n"
                f"Дата: {transaction.date.strftime('%d.%m.%Y %H:%M')}\n"
                f"Имя: {transaction.item_name}\n"
                f"Вид транзакции: Пополнение\n"
                f"Стоимость: {transaction.cost:.2f} руб."
            )
        
        data = await state.get_data()
        page = data.get("page", 0)
        
        # We need a back to list kb but let's define it or import if exists
        from bot.keyboards import InlineKeyboardBuilder, InlineKeyboardButton
        kb_builder = InlineKeyboardBuilder()
        kb_builder.row(InlineKeyboardButton(text="Назад", callback_data=f"trans_page_{page}"))
        
        await callback.message.edit_text(text, reply_markup=kb_builder.as_markup())
        await callback.answer()

@router.message()
async def main_menu_fallback(message: Message):
    user = await get_user_by_tg_id(message.from_user.id)
    if user:
        await message.answer(main_menu_text, reply_markup=get_user_main_menu(), parse_mode="HTML")
