from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime

from app.schemas.order_item import OrderItemResponse


# Schema cho lịch sử trạng thái
class OrderStatusHistoryResponse(BaseModel):
    id: int
    old_status: Optional[str] = None
    new_status: str
    note: Optional[str] = None
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema hiển thị danh sách đơn (ngắn gọn)
class OrderListResponse(BaseModel):
    id: int
    order_code: str
    receiver_name: str
    total_amount: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema phản hồi phân trang danh sách đơn
class MyOrdersPaginationResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[OrderListResponse]

    model_config = ConfigDict(from_attributes=True)


# Schema hiển thị chi tiết một đơn
class OrderDetailResponse(BaseModel):
    id: int
    order_code: str
    receiver_name: str
    receiver_phone: str
    shipping_address: str
    note: Optional[str] = None
    payment_method: str
    total_amount: int
    status: str
    cancel_reason: Optional[str] = None
    created_at: datetime
    items: List[OrderItemResponse] = []
    histories: List[OrderStatusHistoryResponse] = []

    model_config = ConfigDict(from_attributes=True)

class CancelOrderRequest(BaseModel):
    cancel_reason: str = Field(..., min_length=1, max_length=255, description="Lý do hủy đơn hàng")