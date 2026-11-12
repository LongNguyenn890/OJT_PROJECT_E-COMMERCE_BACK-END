from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.category import CategoryResponse
from app.schemas.product_image import ProductImageResponse


class ProductBase(BaseModel):
    category_id: int = Field(..., examples=[1], description="ID của danh mục")
    name: str = Field(..., min_length=1, max_length=200, examples=["iPhone 15 Pro Max"])
    description: str | None = Field(default=None, examples=["Flagship mới nhất của Apple"])
    price: Decimal = Field(default=Decimal("0.00"), ge=0, examples=[29990000])
    stock_quantity: int = Field(default=0, ge=0, examples=[50], description="Số lượng tồn kho")
    is_visible: int = Field(default=1, ge=0, le=1, description="1: Hiển thị, 0: Ẩn")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    category_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    stock_quantity: int | None = Field(default=None, ge=0)
    is_visible: int | None = Field(default=None, ge=0, le=1)


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    category: CategoryResponse | None = None
    product_images: list[ProductImageResponse] = []
