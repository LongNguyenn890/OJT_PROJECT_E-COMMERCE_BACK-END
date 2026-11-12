from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, Text, func, Enum as SQL_Enum, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

class ChangeType(str, Enum):
    INITIAL = "INITIAL" # Thêm mới ban dầu
    IMPORT = "IMPORT" # Nhập thêm
    ADJUST = "ADJUST" # Điều chỉnh
    ORDER = "ORDER" # Tạo đơn
    CANCEL = "CANCEL" # Trả tồn kho khi hủy


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
