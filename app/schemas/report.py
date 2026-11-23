from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReportSummary(BaseModel):
    """Tổng quan số liệu báo cáo bán hàng."""
    total_orders: int = Field(..., description="Tổng số đơn hàng phát sinh trong khoảng thời gian")
    total_revenue: int = Field(..., description="Tổng doanh thu từ đơn DELIVERED (hoàn thành) và bán tại quầy (POS)")
    
    delivered_online_revenue: int = Field(..., description="Doanh thu từ các đơn online giao thành công (DELIVERED)")
    delivered_online_orders_count: int = Field(..., description="Số đơn hàng online giao thành công")
    
    pos_revenue: int = Field(..., description="Doanh thu từ các đơn bán trực tiếp tại quầy (POS)")
    pos_orders_count: int = Field(..., description="Số đơn hàng bán trực tiếp tại quầy (POS)")
    
    total_items_sold: int = Field(..., description="Tổng số lượng sản phẩm đã bán thành công")
    average_order_value: float = Field(..., description="Giá trị trung bình của một đơn hàng thành công")
    
    pending_orders_count: int = Field(0, description="Số đơn hàng chờ xác nhận")
    confirmed_orders_count: int = Field(0, description="Số đơn hàng đã xác nhận")
    shipping_orders_count: int = Field(0, description="Số đơn hàng đang giao")
    cancelled_orders_count: int = Field(0, description="Số đơn hàng bị hủy")


class OrderStatusReportItem(BaseModel):
    """Thống kê chi tiết đơn hàng theo trạng thái."""
    status_code: str = Field(..., description="Mã trạng thái (DELIVERED, POS, PENDING, CONFIRMED, SHIPPING, CANCELLED)")
    status_name: str = Field(..., description="Tên trạng thái tiếng Việt")
    order_count: int = Field(..., description="Số lượng đơn hàng")
    total_amount: int = Field(..., description="Tổng giá trị đơn hàng thuộc trạng thái này")
    percentage: float = Field(..., description="Tỷ lệ % trên tổng số đơn hàng")


class TopProductReportItem(BaseModel):
    """Thông tin sản phẩm trong top bán chạy."""
    product_id: int = Field(..., description="ID sản phẩm")
    product_name: str = Field(..., description="Tên sản phẩm")
    sku: Optional[str] = Field(None, description="Mã SKU sản phẩm")
    category_name: Optional[str] = Field(None, description="Tên ngành hàng / danh mục")
    image_url: Optional[str] = Field(None, description="Ảnh đại diện sản phẩm")
    quantity_sold: int = Field(..., description="Số lượng sản phẩm đã bán được")
    revenue: int = Field(..., description="Tổng doanh thu thu được từ sản phẩm này")
    orders_count: int = Field(..., description="Số đơn hàng có chứa sản phẩm này")


class DailyRevenueReportItem(BaseModel):
    """Doanh thu và biến động bán hàng theo từng ngày."""
    date: str = Field(..., description="Ngày ghi nhận (định dạng YYYY-MM-DD)")
    total_revenue: int = Field(..., description="Tổng doanh thu trong ngày (DELIVERED + POS)")
    delivered_revenue: int = Field(..., description="Doanh thu đơn online giao thành công trong ngày")
    pos_revenue: int = Field(..., description="Doanh thu bán tại quầy trong ngày")
    order_count: int = Field(..., description="Tổng số đơn hàng tạo mới trong ngày")
    completed_orders_count: int = Field(..., description="Số đơn hàng hoàn thành/giao thành công trong ngày")
    items_sold: int = Field(..., description="Số lượng sản phẩm bán ra trong ngày")


class FilterApplied(BaseModel):
    """Khoảng thời gian và bộ lọc được áp dụng trong báo cáo."""
    from_date: Optional[str] = Field(None, description="Thời điểm bắt đầu lọc")
    to_date: Optional[str] = Field(None, description="Thời điểm kết thúc lọc")
    preset: Optional[str] = Field(None, description="Tên khoảng thời gian thiết lập sẵn")


class SalesReportResponse(BaseModel):
    """Dữ liệu trả về đầy đủ của API báo cáo bán hàng."""
    success: bool = True
    filter: FilterApplied
    summary: ReportSummary
    orders_by_status: List[OrderStatusReportItem]
    top_products: List[TopProductReportItem]
    daily_revenue: List[DailyRevenueReportItem]
