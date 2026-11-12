from __future__ import annotations
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from enum import Enum
import enum

from sqlalchemy import DateTime, String, func, BigInteger, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from .order import Order
    from .user import User

# PENDING -> CONFIRMED -> SHIPPING -> DELIVERED và CANCELLED
class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    SHIPPING = "SHIPPING"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class OrderStatusHistory(Base):
    __tablename__ = "order_status_histories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    changed_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    old_status: Mapped[Optional[OrderStatus]] = mapped_column(
        SQLEnum(OrderStatus, name="order_status_enum"),
        nullable=True
    )

    new_status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus, name="order_status_enum"),
        nullable=False
    )
    
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Liên kết khóa ngoại
    order: Mapped["Order"] = relationship("Order", back_populates="histories")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[changed_by])


    # Liên kết khóa ngoại
    order: Mapped["Order"] = relationship("Order", back_populates="histories")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[changed_by])