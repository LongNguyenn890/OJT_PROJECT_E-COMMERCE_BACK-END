from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum as SQL_Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from .address import Address
    from .cart import Cart
    from .order import Order


class Role(str, Enum):
    ADMIN = "ADMIN"
    CUSTOMER = "CUSTOMER"
    STAFF = "STAFF"


class Status(str, Enum):
    ACTIVE = "ACTIVE"
    LOCK = "LOCKED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(SQL_Enum(Role), nullable=False, default=Role.CUSTOMER)
    status: Mapped[str] = mapped_column(SQL_Enum(Status), nullable=False, default=Status.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Quan hệ liên kết
    addresses: Mapped[List["Address"]] = relationship(
        "Address", back_populates="user", cascade="all, delete-orphan"
    )
    cart: Mapped[Optional["Cart"]] = relationship(
        "Cart", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="user")
