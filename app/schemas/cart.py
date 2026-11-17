from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.cart_item import CartItemResponse


# Dữ liệu API trả về cho toàn bộ giỏ hàng và thanh toán (FR-021)
class CartResponse(BaseModel):
    id: int
    user_id: int
    cart_items: list[CartItemResponse] = []
    subtotal: int = Field(0, description="Tạm tính: tổng thành tiền các dòng sản phẩm")
    shipping_fee: int = Field(0, description="Phí vận chuyển (0đ nếu tạm tính >= 500.000đ, ngược lại 30.000đ)")
    total_amount: int = Field(0, description="Tổng tiền thanh toán = Tạm tính + Phí vận chuyển")
    can_checkout: bool = Field(True, description="Điều kiện đặt hàng: False nếu giỏ rỗng hoặc có sản phẩm hết hàng/ẩn")
    warnings: list[str] = Field(default_factory=list, description="Danh sách cảnh báo giá hoặc tồn kho")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
