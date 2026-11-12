import enum
from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship
from app.db.session import Base

class PaymentMethod(str, enum.Enum):
    COD = "COD"
    BANK_TRANSFER = "chuyển khoản"

class OrderStatus(str, enum.Enum):
    PENDING = "Chờ xác nhận"
    CONFIRMED = "Đã xác nhận"
    SHIPPING = "Đang giao"
    COMPLETED = "Hoàn thành"
    CANCELLED = "Hủy"

class Order(Base):
    __tablename__ = "orders"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, index=True)
    order_code = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    address_id = Column(BigInteger, ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True)
    
    # Thông tin người nhận
    receiver_name = Column(String(100), nullable=False)
    receiver_phone = Column(String(15), nullable=False)
    shipping_address = Column(String(500), nullable=False)
    note = Column(String(500), nullable=True)
    
    # Thanh toán & Tiền tệ
    payment_method = Column(Enum(PaymentMethod), nullable=False, default=PaymentMethod.COD)
    subtotal_amount = Column(BigInteger, nullable=False, default=0)
    shipping_fee = Column(BigInteger, nullable=False, default=0)
    total_amount = Column(BigInteger, nullable=False)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    cancel_reason = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    user = relationship("User", back_populates="orders")
