from datetime import datetime
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
    """Schema dữ liệu trả về cho client."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    order_id: int | None = None
    created_by: int | None = None
    change_type: ChangeType
    quantity_change: int
    stock_before: int
    stock_after: int
    note: str | None = None
    created_at: datetime | None = None


# -------------------------------------------------------------
# Schemas phục vụ tính năng cảnh báo tồn kho / Sắp hết hàng
# -------------------------------------------------------------
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
    current_stock: int
    threshold: int = Field(default=DEFAULT_LOW_STOCK_THRESHOLD, description="Ngưỡng cảnh báo áp dụng")
    is_out_of_stock: bool = Field(default=False, description="True nếu tồn kho = 0")
    is_low_stock: bool = Field(default=True, description="True nếu 0 < tồn kho <= threshold")


class LowStockAlertResponse(BaseModel):
    """Kết quả trả về danh sách cảnh báo tồn kho."""
    threshold: int = Field(default=DEFAULT_LOW_STOCK_THRESHOLD, description="Ngưỡng kiểm tra đã dùng")
    total_low_stock_products: int = Field(default=0, description="Tổng số sản phẩm chạm ngưỡng cảnh báo")
    items: list[LowStockProductItem] = []
