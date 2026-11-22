"""Schemas cho chức năng quản lý khách hàng (Customer Management Schemas)."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role, Status
from app.schemas.address import AddressResponse
from app.schemas.order_item import OrderItemResponse


class CustomerOrderSummary(BaseModel):
    """Tóm tắt thông tin đơn hàng của khách hàng."""
    id: int
    order_code: str
    receiver_name: str
    receiver_phone: Optional[str] = None
    shipping_address: Optional[str] = None
    payment_method: Optional[str] = None
    total_amount: int
    status: str
    created_at: datetime
    items: List[OrderItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CustomerListItemResponse(BaseModel):
    """Thông tin khách hàng trong danh sách phân trang kèm thống kê đơn & chi tiêu."""
    id: int
    full_name: str
    email: EmailStr
    phone: str
    avatar: Optional[str] = None
    role: Role
    status: Status
    created_at: Optional[datetime] = None
    total_orders: int = Field(default=0, description="Tổng số đơn hàng đã đặt")
    total_spent: int = Field(default=0, description="Tổng số tiền đã chi tiêu (đơn không hủy)")

    model_config = ConfigDict(from_attributes=True)


class CustomerPaginationResponse(BaseModel):
    """Phản hồi phân trang danh sách khách hàng."""
    total: int = Field(description="Tổng số khách hàng thỏa mãn điều kiện lọc")
    page: int = Field(description="Số trang hiện tại")
    page_size: int = Field(description="Số khách hàng trên mỗi trang")
    items: List[CustomerListItemResponse] = Field(description="Danh sách khách hàng")

    model_config = ConfigDict(from_attributes=True)


class CustomerDetailResponse(BaseModel):
    """Chi tiết hồ sơ khách hàng, danh sách địa chỉ, thống kê và các đơn hàng gần đây."""
    id: int
    full_name: str
    email: EmailStr
    phone: str
    avatar: Optional[str] = None
    role: Role
    status: Status
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    addresses: List[AddressResponse] = []
    total_orders: int = Field(default=0, description="Tổng số đơn hàng đã đặt")
    total_spent: int = Field(default=0, description="Tổng số tiền đã chi tiêu (đơn không hủy)")
    completed_orders: int = Field(default=0, description="Số đơn hàng đã hoàn thành")
    cancelled_orders: int = Field(default=0, description="Số đơn hàng đã bị hủy")
    recent_orders: List[CustomerOrderSummary] = Field(default=[], description="5 đơn hàng gần đây nhất")

    model_config = ConfigDict(from_attributes=True)


class CustomerOrdersPaginationResponse(BaseModel):
    """Phản hồi phân trang lịch sử đơn hàng của khách hàng."""
    total: int = Field(description="Tổng số đơn hàng của khách hàng thỏa điều kiện")
    page: int = Field(description="Số trang hiện tại")
    page_size: int = Field(description="Số đơn hàng trên mỗi trang")
    items: List[CustomerOrderSummary] = Field(description="Danh sách đơn hàng của khách hàng")

    model_config = ConfigDict(from_attributes=True)
