from __future__ import annotations
from sqlalchemy import BigInteger, String, SmallInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import TYPE_CHECKING


from app.db.session import Base

if TYPE_CHECKING:
    from .user import User

class Address(Base):
    __tablename__ = "addresses"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    receiver_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    ward: Mapped[str] = mapped_column(String(100), nullable=False)
    street_detail: Mapped[str] = mapped_column(String(255))
    is_default: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    
    user: Mapped["User"] = relationship("User", back_populates="addresses")