"""Schemas cho chức năng quản lý nhân viên nội bộ (Staff Management Schemas)."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role, Status
from app.schemas.address import AddressResponse
from app.schemas.user import UserResponse


class StaffCreate(BaseModel):
    """Schema tạo mới tài khoản nhân viên."""
    full_name: str = Field(..., min_length=2, max_length=100, description="Họ và tên nhân viên", examples=["Nguyễn Văn Nhân Viên"])
    email: EmailStr = Field(..., description="Email nhân viên", examples=["staff.new@example.com"])
    phone: str = Field(..., min_length=9, max_length=15, description="Số điện thoại", examples=["0912345678"])
    password: str = Field(..., min_length=6, description="Mật khẩu khởi tạo (tối thiểu 6 ký tự)", examples=["password123"])
    role: Optional[Role] = Field(default=Role.STAFF, description="Vai trò: STAFF hoặc ADMIN")


class StaffUpdate(BaseModel):
    """Schema cập nhật thông tin nhân viên."""
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100, description="Họ và tên nhân viên")
    phone: Optional[str] = Field(default=None, min_length=9, max_length=15, description="Số điện thoại")
    password: Optional[str] = Field(default=None, min_length=6, description="Mật khẩu mới (bỏ trống nếu không đổi)")
    role: Optional[Role] = Field(default=None, description="Vai trò: STAFF hoặc ADMIN")


class StaffStatusUpdate(BaseModel):
    """Schema cập nhật trạng thái tài khoản nhân viên."""
    status: str = Field(..., description="Trạng thái tài khoản: ACTIVE hoặc LOCKED / LOCK")


class StaffPaginationResponse(BaseModel):
    """Phản hồi danh sách nhân viên phân trang."""
    total: int = Field(description="Tổng số nhân viên thỏa mãn điều kiện")
    page: int = Field(description="Số trang hiện tại")
    page_size: int = Field(description="Số nhân viên mỗi trang")
    items: List[UserResponse] = Field(description="Danh sách nhân viên & quản trị viên")

    model_config = ConfigDict(from_attributes=True)
