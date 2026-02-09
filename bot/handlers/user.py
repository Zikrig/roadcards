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
    async_session, 
    get_user_by_card,
    get_all_user_cards
)
from sqlalchemy import select, and_
from database.models import Transaction
from bot.keyboards import get_user_main_menu, get_transactions_kb, get_user_requisites_kb, get_user_delete_cards_kb
from bot.utils import get_last_update_time
import math

router = Router()

class Registration(StatesGroup):
    waiting_for_card = State()

main_menu_text = "Добро пожаловать! Здесь вы можете узнать о своем счете по топливным картам."

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    user = await get_user_by_tg_id(message.from_user.id)
    if user:
        await message.answer(main_menu_text, reply_markup=get_user_main_menu())
        return

    # Проверка на наличие аргумента в ссылке (Deep Linking)
    if command.args:
        card_number = command.args.strip()
        if await is_in_whitelist(card_number):
            existing_user = await get_user_by_card(card_number)
            if existing_user:
                await message.answer("Этот номер карты из ссылки уже зарегистрирован другим пользователем.")
            else:
                await register_user(message.from_user.id, card_number)
                await message.answer(f"Регистрация по карте {card_number} прошла успешно!", reply_markup=get_user_main_menu())
                await state.clear()
                return
        else:
            await message.answer("Карта из ссылки не найдена в белом списке.")

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
        text = f"Отлично. Вы в плюсе на {abs(balance):.2f} рублей"
    else:
        text = f"С вас {balance:.2f} рублей"
    
    text += f"\n\n🕒 Данные обновлены {last_update}"
        
    await callback.message.answer(text, reply_markup=get_user_main_menu())
    await callback.answer()

@router.callback_query(F.data == "user_requisites")
async def show_requisites(callback: CallbackQuery):
    user_id = callback.from_user.id
    cards = await get_all_user_cards(user_id)
    cards_str = ", ".join(cards) if cards else "не привязаны"
    
    text = (
        "💳 Реквизиты для оплаты:\n\n"
        "<code>2200 1545 0861 8864</code> Федаш Е. А.\n"
        "Альфа банк\n\n"
        f"<i>Привязанные карты: {cards_str}</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_user_requisites_kb(), parse_mode="HTML")
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
    
    # Возвращаемся в реквизиты
    await show_requisites(callback)

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
    
    kb = get_transactions_kb(transactions, page, total_pages)
    text = f"Ваши сделки (страница {page + 1} из {max(1, total_pages)}):"
    
    # We always use edit_text or answer a new message with the menu
    if message.text.startswith("Ваши сделки") or message.text == main_menu_text:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)

@router.callback_query(F.data == "user_main_menu")
async def process_back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(main_menu_text, reply_markup=get_user_main_menu())
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
                f"Вид транзакции: Трата\n"
                f"Стоимость: {transaction.cost:.2f} руб."
            )
        else:
            # Для оплат (пополнений) можно оставить полный вид или тоже сократить
            text = (
                f"🟢 Пополнение\n"
                f"Карта: {transaction.card_number}\n"
                f"Дата: {transaction.date.strftime('%d.%m.%Y %H:%M')}\n"
                f"Имя: {transaction.item_name}\n"
                f"Вид транзакции: Оплата\n"
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
        await message.answer(main_menu_text, reply_markup=get_user_main_menu())
