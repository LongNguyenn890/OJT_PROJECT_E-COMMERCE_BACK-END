from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.order import PaymentMethod, OrderStatus
from app.schemas.order_item import OrderItemResponse


# Dữ liệu Frontend gửi lên khi tạo đơn hàng (FR-022, FR-023)
class OrderCreate(BaseModel):
    receiver_name: str = Field(..., min_length=1, max_length=100, description="Tên người nhận hàng")
    receiver_phone: str = Field(..., pattern=r"^0\d{9}$", description="SĐT người nhận (10 chữ số, bắt đầu bằng 0 - BR-19)")
    shipping_address: str = Field(..., min_length=1, max_length=500, description="Địa chỉ giao hàng chi tiết")
    note: str | None = Field(None, max_length=500, description="Ghi chú đơn hàng (nếu có)")
    payment_method: PaymentMethod = Field(default=PaymentMethod.COD, description="Phương thức thanh toán: COD hoặc chuyển khoản")


# Dữ liệu cập nhật trạng thái đơn hàng (FR-026)
class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    cancel_reason: str | None = None


# Dữ liệu API trả về chi tiết đơn hàng (FR-025, FR-028)
class OrderResponse(BaseModel):
    id: int
    order_code: str
    user_id: int
    receiver_name: str
    receiver_phone: str
    shipping_address: str
    note: str | None = None
    payment_method: PaymentMethod
    subtotal_amount: int = Field(description="Tạm tính tổng tiền hàng")
    shipping_fee: int = Field(description="Phí vận chuyển")
    total_amount: int = Field(description="Tổng tiền thanh toán")
    status: OrderStatus
    cancel_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    items: list[OrderItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
