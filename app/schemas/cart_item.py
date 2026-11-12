from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# Dữ liệu Frontend gửi lên khi thêm sản phẩm vào giỏ (FR-018)
class CartItemCreate(BaseModel):
    product_id: int = Field(..., gt=0, description="ID sản phẩm phải lớn hơn 0")
    quantity: int = Field(1, ge=1, description="Số lượng thêm vào giỏ ít nhất là 1")


# Dữ liệu Frontend gửi lên khi sửa số lượng (FR-019)
class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1, description="Số lượng cập nhật ít nhất là 1")


# Dữ liệu API trả về cho 1 dòng giỏ hàng (FR-021)
class CartItemResponse(BaseModel):
    id: int
    cart_id: int
    product_id: int
    product_name: str
    product_price: int = Field(description="Đơn giá hiện hành tại server")
    price_at_add: int = Field(description="Đơn giá tại thời điểm thêm vào giỏ hàng")
    quantity: int
    subtotal: int = Field(description="Thành tiền = đơn giá hiện hành x số lượng")
    stock_quantity: int = Field(description="Số lượng tồn kho hiện tại")
    is_visible: bool = Field(True, description="Sản phẩm đang hiển thị hay đã bị ẩn")
    price_changed: bool = Field(False, description="Đánh dấu giá hiện tại đã thay đổi so với lúc thêm")
    out_of_stock: bool = Field(False, description="Hết hàng hoặc số lượng trong giỏ vượt tồn kho")
    warning: str | None = Field(None, description="Cảnh báo thay đổi giá hoặc tồn kho (nếu có)")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
