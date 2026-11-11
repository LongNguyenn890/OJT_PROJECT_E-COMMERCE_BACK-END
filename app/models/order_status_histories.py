from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text, func, BigInteger, ForeignKey, VARCHAR, Enum
from typing import Optional
from enum import Enum
from sqlalchemy.orm import Mapped, mapped_column
import enum
from sqlalchemy import Enum as SQLEnum

from app.db.session import Base

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
    # order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    # changed_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
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