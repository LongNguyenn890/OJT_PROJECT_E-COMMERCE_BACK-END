from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.db.session import Base

class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, index=True)
    cart_id = Column(BigInteger, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    price_at_add = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),)

    cart = relationship("Cart", back_populates="cart_items")
    product = relationship("Product", lazy="joined")

    @property
    def product_name(self) -> str:
        return self.product.name if self.product else ""

    @property
    def product_price(self) -> int:
        return int(self.product.price) if self.product and self.product.price is not None else 0

    @property
    def stock_quantity(self) -> int:
        return self.product.stock_quantity if self.product else 0

    @property
    def is_visible(self) -> bool:
        return bool(self.product.is_visible) if self.product else False

    @property
    def image_url(self) -> str | None:
        if not self.product or not getattr(self.product, "product_images", None):
            return None
        for img in self.product.product_images:
            if getattr(img, "is_primary", 0) == 1:
                return img.image_url
        return self.product.product_images[0].image_url if self.product.product_images else None

    @property
    def subtotal(self) -> int:
        return self.product_price * self.quantity

    @property
    def price_changed(self) -> bool:
        return self.price_at_add != 0 and int(self.price_at_add) != self.product_price

    @property
    def out_of_stock(self) -> bool:
        if not self.is_visible:
            return True
        return self.quantity > self.stock_quantity

    @property
    def warning(self) -> str | None:
        warnings = []
        if not self.is_visible:
            warnings.append("Sản phẩm đã bị ẩn hoặc ngừng kinh doanh")
        elif self.stock_quantity <= 0:
            warnings.append("Sản phẩm hiện đã hết hàng")
        elif self.quantity > self.stock_quantity:
            warnings.append(f"Số lượng trong giỏ ({self.quantity}) vượt quá tồn kho hiện có ({self.stock_quantity})")
        
        if self.price_changed:
            if self.product_price > self.price_at_add:
                warnings.append(f"Giá sản phẩm đã tăng từ {self.price_at_add:,}đ lên {self.product_price:,}đ")
            else:
                warnings.append(f"Giá sản phẩm đã giảm từ {self.price_at_add:,}đ xuống {self.product_price:,}đ")

        return "; ".join(warnings) if warnings else None
