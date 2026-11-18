from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, SmallInteger, String, func
from sqlalchemy.orm import relationship

from app.db.session import Base

if TYPE_CHECKING:
    from .user import User


class Voucher(Base):
    __tablename__ = "vouchers"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(100), nullable=False)
    discount_amount = Column(BigInteger, nullable=False)
    min_order_value = Column(BigInteger, nullable=False, default=0)
    points_spent = Column(Integer, nullable=False, default=0)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_used = Column(SmallInteger, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="vouchers")
