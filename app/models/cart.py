from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import relationship
from app.db.session import Base

class Cart(Base):
    __tablename__ = "carts"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="cart")
    cart_items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan", lazy="selectin")

    @property
    def subtotal(self) -> int:
        return sum(item.subtotal for item in self.cart_items)

    @property
    def shipping_fee(self) -> int:
        # Miễn phí vận chuyển theo BR-07, A-02
        return 0

    @property
    def total_amount(self) -> int:
        return self.subtotal + self.shipping_fee    

    @property
    def can_checkout(self) -> bool:
        if not self.cart_items:
            return False
        return not any(item.out_of_stock for item in self.cart_items)

    @property
    def warnings(self) -> list[str]:
        res = []
        for item in self.cart_items:
            if item.warning:
                res.append(f"{item.product_name}: {item.warning}")
        return res
