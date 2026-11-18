from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.session import Base

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, index=True)
    order_id = Column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    
    product_name = Column(String(200), nullable=False)  # Bản sao tên sản phẩm lúc đặt
    unit_price = Column(BigInteger, nullable=False)       # Đơn giá tại thời điểm đặt (BR-06)
    quantity = Column(Integer, nullable=False)
    subtotal = Column(BigInteger, nullable=False)        # unit_price * quantity
    image_url = Column(String(255), nullable=True)       # Ảnh sản phẩm tại thời điểm đặt
    category_name = Column(String(100), nullable=True)   # Tên ngành hàng
    sku = Column(String(100), nullable=True)             # Mã SKU sản phẩm

    __table_args__ = (UniqueConstraint("order_id", "product_id", name="uq_order_product"),)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")
