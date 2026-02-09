from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, and_
from .models import Base, User, Whitelist, Transaction, TransactionType
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/roadcards")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_user_by_tg_id(telegram_id: int) -> User:
    async with async_session() as session:
        # returns the first card found for this user
        result = await session.execute(select(User).where(User.telegram_id == telegram_id).limit(1))
        return result.scalar_one_or_none()

async def get_all_user_cards(telegram_id: int):
    async with async_session() as session:
        result = await session.execute(select(User.card_number).where(User.telegram_id == telegram_id))
        return result.scalars().all()

async def get_user_by_card(card_number: str) -> User:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.card_number == card_number))
        return result.scalar_one_or_none()

async def is_in_whitelist(card_number: str) -> bool:
    async with async_session() as session:
        result = await session.execute(select(Whitelist).where(Whitelist.card_number == card_number))
        return result.scalar_one_or_none() is not None

async def register_user(telegram_id: int, card_number: str, is_admin: bool = False):
    async with async_session() as session:
        user = User(telegram_id=telegram_id, card_number=card_number, is_admin=is_admin)
        session.add(user)
        await session.commit()

async def add_to_whitelist(card_number: str):
    async with async_session() as session:
        # Check if already exists
        exists = await is_in_whitelist(card_number)
        if not exists:
            session.add(Whitelist(card_number=card_number))
            await session.commit()

async def get_user_balance(telegram_id: int) -> float:
    async with async_session() as session:
        cards = await get_all_user_cards(telegram_id)
        if not cards:
            return 0.0
            
        result_expenses = await session.execute(
            select(Transaction.cost).where(and_(Transaction.card_number.in_(cards), Transaction.type == TransactionType.EXPENSE))
        )
        expenses = sum(r[0] for r in result_expenses.all())

        result_payments = await session.execute(
            select(Transaction.cost).where(and_(Transaction.card_number.in_(cards), Transaction.type == TransactionType.PAYMENT))
        )
        payments = sum(r[0] for r in result_payments.all())
        
        return expenses - payments

async def get_user_transactions(telegram_id: int, limit: int = 10, offset: int = 0):
    async with async_session() as session:
        cards = await get_all_user_cards(telegram_id)
        if not cards:
            return []
        result = await session.execute(
            select(Transaction)
            .where(Transaction.card_number.in_(cards))
            .order_by(Transaction.date.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

async def count_user_transactions(telegram_id: int):
    async with async_session() as session:
        cards = await get_all_user_cards(telegram_id)
        if not cards:
            return 0
        from sqlalchemy import func
        result = await session.execute(
            select(func.count(Transaction.id)).where(Transaction.card_number.in_(cards))
        )
        return result.scalar()

async def transaction_exists(card_number: str, date, t_type: TransactionType) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(Transaction).where(
                and_(
                    Transaction.card_number == card_number,
                    Transaction.date == date,
                    Transaction.type == t_type
                )
            )
        )
        return result.scalar_one_or_none() is not None

async def add_transaction(data: dict):
    async with async_session() as session:
        transaction = Transaction(**data)
        session.add(transaction)
        await session.commit()

