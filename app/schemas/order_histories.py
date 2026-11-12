from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Schema cho từng món hàng trong đơn
class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    unit_price: int
    quantity: int
    subtotal: int

    class Config:
        from_attributes = True

# Schema cho lịch sử trạng thái
class OrderStatusHistoryResponse(BaseModel):
    id: int
    old_status: Optional[str] = None
    new_status: str
    note: Optional[str] = None
    changed_at: datetime

    class Config:
        from_attributes = True

# Schema hiển thị danh sách đơn (ngắn gọn)
class OrderListResponse(BaseModel):
    id: int
    order_code: str
    receiver_name: str
    total_amount: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Schema phản hồi phân trang danh sách đơn
class MyOrdersPaginationResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[OrderListResponse]

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

    class Config:
        from_attributes = True