from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class AddressCreate(BaseModel):
    receiver_name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=10, max_length=15)
    province: str = Field(..., min_length=1, description="Nhập tỉnh/thành phố")
    ward: str = Field(..., min_length=1, description="Nhập xã/quận/phường")
    street_detail: Optional[str] = Field(default=None, min_length=1, description="Nhập số nhà, tên đường")
    is_default: int = Field(default=0, ge=0, le=1)


class AddressUpdate(BaseModel):
    receiver_name: Optional[str] = Field(default=None, min_length=1)
    phone: Optional[str] = Field(default=None, min_length=10, max_length=15)
    province: Optional[str] = Field(default=None, min_length=1)
    ward: Optional[str] = Field(default=None, min_length=1)
    street_detail: Optional[str] = Field(default=None, min_length=1)
    is_default: Optional[int] = Field(default=None, ge=0, le=1)



class AddressResponse(BaseModel):
    id: int
    user_id: int
    receiver_name: str
    phone: str
    province: str
    ward: str
    street_detail: Optional[str] = None
    is_default: int = 0

    model_config = ConfigDict(from_attributes=True)