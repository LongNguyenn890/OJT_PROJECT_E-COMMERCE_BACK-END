from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProductImageBase(BaseModel):
    image_url: str = Field(..., max_length=255, examples=["https://images.unsplash.com/photo-1511707171634-5f897ff02aa9"])
    is_primary: int = Field(default=0, ge=0, le=1, description="1 nếu là ảnh chính, 0 nếu là ảnh phụ")
    sort_order: int = Field(default=0, ge=0, description="Thứ tự hiển thị ảnh")


class ProductImageCreate(ProductImageBase):
    product_id: int | None = Field(default=None, description="ID sản phẩm (nếu tạo lẻ)")


class ProductImageUpdate(BaseModel):
    image_url: str | None = Field(default=None, max_length=255)
    is_primary: int | None = Field(default=None, ge=0, le=1)
    sort_order: int | None = Field(default=None, ge=0)


class ProductImageResponse(ProductImageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    created_at: datetime | None = None
