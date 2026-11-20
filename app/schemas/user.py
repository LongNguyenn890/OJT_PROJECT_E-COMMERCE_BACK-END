from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role, Status
from app.schemas.address import AddressResponse


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, examples=["Nguyễn Văn A"])
    email: EmailStr = Field(..., examples=["nguyenvana@gmail.com"])
    phone: str = Field(..., min_length=9, max_length=15, examples=["0912345678"])
    password: str = Field(..., min_length=6, examples=["123456"])


class StaffCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Họ và tên nhân viên")
    email: EmailStr = Field(..., description="Email nhân viên")
    phone: str = Field(..., min_length=9, max_length=15, description="Số điện thoại")
    password: str = Field(..., min_length=6, description="Mật khẩu khởi tạo (tối thiểu 6 ký tự)")
    role: Optional[Role] = Field(default=Role.STAFF, description="Vai trò: STAFF hoặc ADMIN")


class StaffUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100, description="Họ và tên nhân viên")
    phone: Optional[str] = Field(default=None, min_length=9, max_length=15, description="Số điện thoại")
    password: Optional[str] = Field(default=None, min_length=6, description="Mật khẩu mới (bỏ trống nếu không đổi)")
    role: Optional[Role] = Field(default=None, description="Vai trò: STAFF hoặc ADMIN")


class UserLogin(BaseModel):
    email: EmailStr = Field(...)
    password: str = Field(...)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1)
    email: Optional[EmailStr] = Field(default=None)
    phone: Optional[str] = Field(default=None, min_length=10, max_length=15)
    avatar: Optional[str] = Field(default=None, description="Đường dẫn hoặc URL ảnh đại diện")
    password: Optional[str] = Field(default=None, min_length=6)


class UserStatusUpdate(BaseModel):
    status: str = Field(..., description="Trạng thái tài khoản: ACTIVE hoặc LOCKED / LOCK")


class AvatarResponse(BaseModel):
    message: str = "Cập nhật ảnh đại diện thành công"
    avatar: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: str
    avatar: Optional[str] = None
    reward_points: int = 0
    role: Role
    status: Status
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    addresses: List[AddressResponse] = []

    model_config = ConfigDict(from_attributes=True)
