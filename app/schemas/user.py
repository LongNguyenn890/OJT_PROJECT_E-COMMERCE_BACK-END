from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role, Status
from app.schemas.address import AddressResponse


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=5, max_length=100, examples=["Nguyễn Văn A"])
    email: EmailStr = Field(..., examples=["nguyenvana@gmail.com"])
    phone: str = Field(..., min_length=10, max_length=15, examples=["0912345678"])
    password: str = Field(..., min_length=6, examples=["123456"])



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
    password: Optional[str] = Field(default=None, min_length=6)


class UserStatusUpdate(BaseModel):
    status: Status = Field(..., description="Trạng thái tài khoản: ACTIVE hoặc LOCK")


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: str
    role: Role
    status: Status
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    addresses: List[AddressResponse] = []

    model_config = ConfigDict(from_attributes=True)
