from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Integer, Text, func, Enum as SQL_Enum, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from .product import Product
    from .order import Order
    from .user import User

class ChangeType(str, Enum):
    INITIAL = "INITIAL"  # Thêm mới ban đầu
    IMPORT = "IMPORT"    # Nhập thêm
    ADJUST = "ADJUST"    # Điều chỉnh
    ORDER = "ORDER"      # Tạo đơn
    CANCEL = "CANCEL"    # Trả tồn kho khi hủy


class StockLog(Base):
    __tablename__ = "stock_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_type: Mapped[str] = mapped_column(SQL_Enum(ChangeType), nullable=False)
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_before: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_after: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Quan hệ liên kết
    product: Mapped["Product"] = relationship("Product", back_populates="stock_logs")
    order: Mapped[Optional["Order"]] = relationship("Order")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
