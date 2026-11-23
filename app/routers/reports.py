"""ROUTER BÁO CÁO BÁN HÀNG VÀ THỐNG KÊ DOANH THU (REPORTS API)
Dành cho Quản trị viên (ADMIN) và Nhân viên nội bộ (STAFF).

Các chỉ số cung cấp:
 - Tổng số đơn hàng trong kỳ
 - Tổng doanh thu (tổng hợp từ đơn online giao thành công DELIVERED và bán tại quầy POS)
 - Doanh thu tách riêng: Online DELIVERED vs Bán tại quầy POS
 - Số lượng sản phẩm đã bán thành công
 - Thống kê đơn theo trạng thái (DELIVERED, POS, PENDING, CONFIRMED, SHIPPING, CANCELLED)
 - Top 10 sản phẩm bán chạy nhất
 - Thống kê biến động doanh thu theo từng ngày
 - Hỗ trợ lọc theo khoảng thời gian linh hoạt (from_date, to_date) hoặc preset nhanh
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import require_admin_or_staff
from app.models.user import User
from app.schemas.report import SalesReportResponse
from app.service.report import get_sales_report, parse_date_range

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/sales",
    response_model=SalesReportResponse,
    summary="Báo cáo bán hàng & doanh thu chi tiết",
    description=(
        "Tổng hợp số liệu bán hàng toàn hệ thống:\n"
        "- **Tổng số đơn hàng** và **doanh thu thực tế** (tính từ đơn giao thành công DELIVERED và bán tại quầy POS).\n"
        "- **Số lượng sản phẩm đã bán** và **giá trị trung bình đơn hàng** (AOV).\n"
        "- **Thống kê đơn theo trạng thái**: DELIVERED, POS, PENDING, CONFIRMED, SHIPPING, CANCELLED.\n"
        "- **Top 10 sản phẩm bán chạy nhất** (theo số lượng bán và doanh thu).\n"
        "- **Biến động doanh thu theo ngày** (kèm số đơn và số lượng sản phẩm).\n"
        "- **Lọc theo khoảng thời gian**: `from_date`, `to_date` (định dạng `YYYY-MM-DD`) hoặc `preset` (`today`, `yesterday`, `7days`, `30days`, `this_month`, `last_month`, `this_year`, `all`)."
    ),
)
def read_sales_report(
    from_date: Optional[str] = Query(None, description="Từ ngày (định dạng YYYY-MM-DD, ví dụ: 2026-11-01)"),
    to_date: Optional[str] = Query(None, description="Đến ngày (định dạng YYYY-MM-DD, ví dụ: 2026-11-30)"),
    preset: Optional[str] = Query(
        None,
        description="Khoảng thời gian nhanh: today, yesterday, 7days, 30days, this_month, last_month, this_year, all",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff),
):
    """Lấy dữ liệu báo cáo bán hàng tổng hợp theo khoảng thời gian."""
    # Kiểm tra tính hợp lệ của khoảng ngày tùy chỉnh
    start_dt, end_dt, _ = parse_date_range(from_date, to_date, preset)
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ngày bắt đầu (from_date) không được lớn hơn ngày kết thúc (to_date).",
        )

    return get_sales_report(db=db, from_date=from_date, to_date=to_date, preset=preset)


@router.get(
    "/sales-overview",
    response_model=SalesReportResponse,
    summary="Báo cáo bán hàng tổng quan (Alias của /reports/sales)",
    description="Endpoint thay thế tiện ích cho /reports/sales để tích hợp thuận tiện với các module Dashboard và Analytics.",
)
def read_sales_overview(
    from_date: Optional[str] = Query(None, description="Từ ngày (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Đến ngày (YYYY-MM-DD)"),
    preset: Optional[str] = Query(None, description="Khoảng thời gian nhanh: today, 7days, 30days, this_month, all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff),
):
    """Endpoint tiện ích gọi đồng bộ với /reports/sales."""
    return read_sales_report(from_date=from_date, to_date=to_date, preset=preset, db=db, current_user=current_user)
