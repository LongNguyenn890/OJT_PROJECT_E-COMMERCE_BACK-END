"""Schemas cho phân hệ Quản lý kho, Nhật ký tồn kho và Cảnh báo sắp hết hàng (Inventory Schemas).

Tài liệu đặc tả liên quan:
- FR-033: Theo dõi số lượng tồn kho (InventoryItemResponse, InventoryListResponse).
- FR-034: Cập nhật số lượng tồn kho (StockImportRequest, StockAdjustRequest, StockUpdateRequest, StockOperationResponse).
- FR-036: Cảnh báo sản phẩm sắp hết hàng (LowStockFilter, LowStockProductItem, LowStockAlertResponse).
- BR-14: Ngưỡng cảnh báo sắp hết hàng mặc định là 5.
"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.models.stock_log import ChangeType

# Ngưỡng cảnh báo sắp hết hàng mặc định là 5
DEFAULT_LOW_STOCK_THRESHOLD: int = 5


class StockLogBase(BaseModel):
    product_id: int = Field(..., ge=1, description="ID của sản phẩm", examples=[1])
    change_type: ChangeType = Field(..., description="Loại thay đổi tồn kho", examples=[ChangeType.IMPORT])
    quantity_change: int = Field(
        ...,
        description="Số lượng thay đổi: số dương (+) khi nhập thêm/hoàn kho, số âm (-) khi bán/giảm",
        examples=[10],
    )
    note: str | None = Field(default=None, description="Ghi chú lý do thay đổi tồn kho", examples=["Nhập kho đợt 1"])


class StockLogCreate(BaseModel):
    """Schema gửi lên khi nhân viên/thủ kho tạo bản ghi nhập kho hoặc điều chỉnh tồn kho thủ công."""
    product_id: int = Field(..., ge=1, description="ID của sản phẩm", examples=[1])
    change_type: ChangeType = Field(
        default=ChangeType.ADJUST,
        description="Loại điều chỉnh: IMPORT, ADJUST, v.v.",
        examples=[ChangeType.ADJUST],
    )
    quantity_change: int = Field(
        ...,
        description="Số lượng thay đổi: số dương (+) để tăng kho, số âm (-) để giảm kho",
        examples=[5],
    )
    note: str | None = Field(default=None, description="Ghi chú giải trình điều chỉnh", examples=["Kiểm kê kho định kỳ"])


class StockLogResponse(BaseModel):
    """Schema dữ liệu chi tiết log biến động kho trả về cho client."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    order_id: int | None = None
    created_by: int | None = None
    change_type: ChangeType | str
    quantity_change: int
    stock_before: int
    stock_after: int
    note: str | None = None
    created_at: datetime | None = None


# -------------------------------------------------------------
# Schemas yêu cầu cập nhật kho (FR-034)
# -------------------------------------------------------------
class StockImportRequest(BaseModel):
    quantity_to_add: int = Field(
        ..., gt=0, description="Số lượng nhập thêm phải lớn hơn 0", examples=[10]
    )
    note: str | None = Field(default=None, description="Lý do hoặc ghi chú nhập hàng", examples=["Nhập hàng đợt mới"])


class StockAdjustRequest(BaseModel):
    new_stock_quantity: int = Field(
        ..., ge=0, description="Số lượng tồn kho mới sau kiểm kê (>= 0)", examples=[20]
    )
    note: str | None = Field(default=None, description="Lý do điều chỉnh kho", examples=["Kiểm kê kho định kỳ"])


class StockUpdateRequest(BaseModel):
    """Schema cập nhật tồn kho linh hoạt theo FR-034."""
    quantity_to_add: int | None = Field(
        default=None, gt=0, description="Số lượng nhập thêm (nếu nhập hàng)"
    )
    new_stock_quantity: int | None = Field(
        default=None, ge=0, description="Số lượng tồn kho mới sau kiểm kê (nếu đặt lại số lượng)"
    )
    note: str | None = Field(default=None, description="Ghi chú / lý do cập nhật tồn kho")


class StockOperationResponse(BaseModel):
    """Schema phản hồi kết quả sau khi nhập kho hoặc điều chỉnh kho."""
    message: str
    product_id: int
    added_quantity: int | None = None
    quantity_change: int | None = None
    stock_before: int
    stock_after: int


class StockLogsPageResponse(BaseModel):
    """Schema phản hồi danh sách nhật ký biến động kho có phân trang."""
    product_id: int
    product_name: str
    current_stock: int
    total: int
    page: int
    page_size: int
    items: list[StockLogResponse] = []


# -------------------------------------------------------------
# Schemas theo dõi kho và cảnh báo tồn kho (FR-033, FR-036)
# -------------------------------------------------------------
class InventoryItemResponse(BaseModel):
    """Thông tin tồn kho của từng sản phẩm."""
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    name: str
    category_id: int
    category_name: str | None = None
    price: Decimal | float | int
    stock_quantity: int
    is_visible: int | bool
    status: str
    status_code: str
    threshold: int


class InventoryListResponse(BaseModel):
    """Danh sách theo dõi tồn kho có phân trang kèm thống kê cảnh báo."""
    total: int
    page: int
    page_size: int
    threshold: int
    low_stock_count: int
    out_of_stock_count: int
    items: list[InventoryItemResponse] = []


class LowStockFilter(BaseModel):
    """Schema query params khi lọc danh sách sản phẩm sắp hết hàng."""
    threshold: int = Field(
        default=DEFAULT_LOW_STOCK_THRESHOLD,
        ge=0,
        description="Ngưỡng tồn kho để xác định sản phẩm sắp hết hàng (mặc định: 5)",
        examples=[DEFAULT_LOW_STOCK_THRESHOLD],
    )


class LowStockProductItem(BaseModel):
    """Thông tin tóm tắt sản phẩm sắp hết hàng."""
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    category_name: str | None = None
    current_stock: int
    threshold: int = Field(default=DEFAULT_LOW_STOCK_THRESHOLD, description="Ngưỡng cảnh báo áp dụng")
    is_out_of_stock: bool = Field(default=False, description="True nếu tồn kho = 0")
    is_low_stock: bool = Field(default=True, description="True nếu 0 < tồn kho <= threshold")


class LowStockAlertResponse(BaseModel):
    """Kết quả trả về danh sách cảnh báo tồn kho."""
    threshold: int = Field(default=DEFAULT_LOW_STOCK_THRESHOLD, description="Ngưỡng kiểm tra đã dùng")
    total_low_stock_products: int = Field(default=0, description="Tổng số sản phẩm chạm ngưỡng cảnh báo")
    items: list[LowStockProductItem] = []
