from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import declarative_base
import enum

Base = declarative_base()

class TransactionType(enum.Enum):
    EXPENSE = "expense"
    PAYMENT = "payment"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False) # Remove unique=True
    card_number = Column(String, unique=True, nullable=False)
    is_admin = Column(Boolean, default=False)

class Whitelist(Base):
    __tablename__ = "whitelist"

    id = Column(Integer, primary_key=True)
    card_number = Column(String, unique=True, nullable=False)

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    card_number = Column(String, nullable=False)
    firm = Column(String)
    date = Column(DateTime, nullable=False)
    address = Column(String)
    item_name = Column(String)
    quantity = Column(Float)
    price = Column(Float)
    cost = Column(Float)
    type = Column(Enum(TransactionType), nullable=False)

    # For deduplication: card number, date, and status (type)
    __mapper_args__ = {
        "confirm_deleted_rows": False
    }

