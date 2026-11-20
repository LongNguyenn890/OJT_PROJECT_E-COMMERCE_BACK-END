from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.category import CategoryResponse
from app.schemas.product_image import ProductImageResponse


class ProductBase(BaseModel):
    category_id: int = Field(..., examples=[1], description="ID của danh mục")
    name: str = Field(..., min_length=1, max_length=200, examples=["iPhone 15 Pro Max"])
    sku: str | None = Field(default=None, max_length=100, examples=["IP15PM-256-BLK"], description="Mã SKU (duy nhất)")
    description: str | None = Field(default=None, examples=["Flagship mới nhất của Apple"])
    price: Decimal = Field(default=Decimal("0.00"), examples=[29990000], description="Giá gốc sản phẩm (> 0)")
    promotional_price: Decimal | None = Field(default=None, examples=[27990000], description="Giá khuyến mãi (< giá gốc)")
    stock_quantity: int = Field(default=0, ge=0, examples=[50], description="Số lượng tồn kho")
    is_visible: int = Field(default=1, ge=0, le=1, description="1: Hiển thị, 0: Ẩn")


class ProductCreate(BaseModel):
    category_id: int = Field(..., ge=1, examples=[1], description="ID của danh mục")
    name: str = Field(..., min_length=1, max_length=200, examples=["iPhone 15 Pro Max"], description="Tên sản phẩm")
    sku: str = Field(..., min_length=1, max_length=100, examples=["IP15PM-256-BLK"], description="Mã SKU duy nhất")
    description: str | None = Field(default=None, examples=["Flagship mới nhất của Apple"])
    price: Decimal = Field(..., examples=[29990000], description="Giá gốc sản phẩm (> 0)")
    promotional_price: Decimal | None = Field(default=None, examples=[27990000], description="Giá khuyến mãi (< giá gốc)")
    stock_quantity: int = Field(default=0, ge=0, examples=[50], description="Số lượng tồn kho ban đầu")
    is_visible: int = Field(default=1, ge=0, le=1, description="1: Hiển thị, 0: Ẩn")
    image_urls: list[str] | None = Field(default=None, description="Danh sách URL ảnh sản phẩm")


class ProductUpdate(BaseModel):
    category_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    price: Decimal | None = Field(default=None)
    promotional_price: Decimal | None = Field(default=None)
    stock_quantity: int | None = Field(default=None, ge=0)
    is_visible: int | None = Field(default=None, ge=0, le=1)
    image_urls: list[str] | None = None


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    category: CategoryResponse | None = None
    product_images: list[ProductImageResponse] = []


class PublicProductResponse(BaseModel):
    """Thông tin sản phẩm dùng cho API danh mục công khai và quản trị."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    name: str
    sku: str | None = None
    description: str | None = None
    price: Decimal
    promotional_price: Decimal | None = None
    stock_quantity: int
    in_stock: bool
    is_visible: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None
    category: CategoryResponse | None = None
    product_images: list[ProductImageResponse] = []


class PublicProductDetailResponse(PublicProductResponse):
    related_products: list[PublicProductResponse] = []


class PublicProductPageResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PublicProductResponse]


class ProductDeleteOrHideResponse(BaseModel):
    message: str
    action: str = Field(..., description="HIDDEN nếu sản phẩm có trong đơn hàng, DELETED nếu xóa vĩnh viễn")
    product_id: int
    is_visible: int | None = None


class ProductVisibilityRequest(BaseModel):
    is_visible: int = Field(..., ge=0, le=1, description="1: Hiển thị, 0: Ẩn")


class ProductImageDeleteResponse(BaseModel):
    message: str
    deleted_image_id: int
