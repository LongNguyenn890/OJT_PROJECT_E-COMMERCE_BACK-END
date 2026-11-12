from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, Numeric, String, Text, func, BigInteger, ForeignKey, Integer, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from .category import Category
    from .product_image import ProductImage
    from .stock_log import StockLog


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_visible: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    category: Mapped["Category"] = relationship(back_populates="products")
    product_images: Mapped[List["ProductImage"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    stock_logs: Mapped[List["StockLog"]] = relationship(back_populates="product", cascade="all, delete-orphan")

    @property
    def in_stock(self) -> bool:
        return self.stock_quantity > 0
