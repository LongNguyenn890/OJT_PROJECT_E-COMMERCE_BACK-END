"""Gói chứa toàn bộ các Pydantic Schemas phục vụ request validation và response serialization.

Bao gồm:
- user: Schemas đăng ký, đăng nhập, thông tin người dùng và token JWT.
- address: Schemas quản lý địa chỉ nhận hàng của khách hàng.
- category: Schemas danh mục sản phẩm.
- product: Schemas sản phẩm công khai và quản trị.
- product_image: Schemas hình ảnh sản phẩm.
- cart & cart_item: Schemas giỏ hàng và mặt hàng trong giỏ.
- order & order_item: Schemas tạo đơn, chi tiết đơn hàng và mặt hàng.
- order_histories: Schemas danh sách và lịch sử trạng thái đơn hàng.
- stock_log: Schemas quản lý tồn kho, nhập hàng, kiểm kê và cảnh báo sắp hết hàng.
"""
from app.schemas.user import (
    UserCreate,
    TokenResponse,
    UserLogin,
    UserResponse,
    UserStatusUpdate,
    UserUpdate,
)
from app.schemas.address import (
    AddressCreate,
    AddressResponse,
    AddressUpdate,
)
from app.schemas.category import (
    CategoryBase,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
)
from app.schemas.product import (
    ProductBase,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    PublicProductResponse,
    PublicProductDetailResponse,
    PublicProductPageResponse,
)
from app.schemas.product_image import (
    ProductImageBase,
    ProductImageCreate,
    ProductImageResponse,
    ProductImageUpdate,
)
from app.schemas.cart_item import (
    CartItemCreate,
    CartItemUpdate,
    CartItemResponse,
)
from app.schemas.cart import (
    CartResponse,
)
from app.schemas.order import (
    OrderCreate,
    OrderStatusUpdate,
    OrderResponse,
)
from app.schemas.order_item import (
    OrderItemResponse,
)
from app.schemas.order_histories import (
    OrderStatusHistoryResponse,
    OrderListResponse,
    MyOrdersPaginationResponse,
    OrderDetailResponse,
)
from app.schemas.stock_log import (
    DEFAULT_LOW_STOCK_THRESHOLD,
    ChangeType,
    StockLogBase,
    StockLogCreate,
    StockLogResponse,
    StockImportRequest,
    StockAdjustRequest,
    StockUpdateRequest,
    StockOperationResponse,
    StockLogsPageResponse,
    InventoryItemResponse,
    InventoryListResponse,
    LowStockFilter,
    LowStockProductItem,
    LowStockAlertResponse,
)

__all__ = [
    "UserCreate",
    "TokenResponse",
    "UserLogin",
    "UserResponse",
    "UserStatusUpdate",
    "UserUpdate",
    "AddressCreate",
    "AddressResponse",
    "AddressUpdate",
    "CategoryBase",
    "CategoryCreate",
    "CategoryResponse",
    "CategoryUpdate",
    "ProductBase",
    "ProductCreate",
    "ProductResponse",
    "ProductUpdate",
    "PublicProductResponse",
    "PublicProductDetailResponse",
    "PublicProductPageResponse",
    "ProductImageBase",
    "ProductImageCreate",
    "ProductImageResponse",
    "ProductImageUpdate",
    "CartItemCreate",
    "CartItemUpdate",
    "CartItemResponse",
    "CartResponse",
    "OrderCreate",
    "OrderStatusUpdate",
    "OrderResponse",
    "OrderItemResponse",
    "OrderStatusHistoryResponse",
    "OrderListResponse",
    "MyOrdersPaginationResponse",
    "OrderDetailResponse",
    "DEFAULT_LOW_STOCK_THRESHOLD",
    "ChangeType",
    "StockLogBase",
    "StockLogCreate",
    "StockLogResponse",
    "StockImportRequest",
    "StockAdjustRequest",
    "StockUpdateRequest",
    "StockOperationResponse",
    "StockLogsPageResponse",
    "InventoryItemResponse",
    "InventoryListResponse",
    "LowStockFilter",
    "LowStockProductItem",
    "LowStockAlertResponse",
]
