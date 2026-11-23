"""Dịch vụ tổng hợp báo cáo bán hàng, doanh thu và thống kê hiệu suất kinh doanh (Report Service).

Đáp ứng đầy đủ các chỉ số:
 - Tổng số đơn hàng
 - Tổng doanh thu (đơn DELIVERED và bán tại quầy POS)
 - Doanh thu tách riêng: Đơn online giao thành công vs Đơn bán tại quầy
 - Số lượng sản phẩm đã bán thành công
 - Thống kê đơn theo trạng thái (DELIVERED, POS, PENDING, CONFIRMED, SHIPPING, CANCELLED)
 - Top 10 sản phẩm bán chạy nhất (theo số lượng bán và doanh thu)
 - Biến động doanh thu và đơn hàng theo từng ngày
 - Lọc linh hoạt theo khoảng thời gian tùy chỉnh hoặc preset (today, 7days, 30days, this_month,...)
"""

from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.schemas.report import (
    DailyRevenueReportItem,
    FilterApplied,
    OrderStatusReportItem,
    ReportSummary,
    SalesReportResponse,
    TopProductReportItem,
)


def _is_pos_order(order: Order) -> bool:
    """Xác định đơn hàng có phải là đơn bán trực tiếp tại quầy hay không."""
    code = (order.order_code or "").strip().upper()
    if code.startswith("POS"):
        return True
    addr = (order.shipping_address or "").lower()
    if "tại quầy" in addr or "truc tiep tai quay" in addr:
        return True
    note = (order.note or "").lower()
    if "bán tại quầy" in note or "ban tai quay" in note:
        return True
    return False


def _normalize_order_status(status_val: Any) -> str:
    """Chuẩn hóa trạng thái đơn hàng thành mã trạng thái tiêu chuẩn."""
    if hasattr(status_val, "value"):
        s = str(status_val.value).strip().upper()
    else:
        s = str(status_val or "").strip().upper()

    if s in ("HOÀN THÀNH", "ĐÃ GIAO", "COMPLETED", "DELIVERED"):
        return "DELIVERED"
    if s in ("CHỜ XÁC NHẬN", "CHO XAC NHAN", "PENDING"):
        return "PENDING"
    if s in ("ĐÃ XÁC NHẬN", "DA XAC NHAN", "CONFIRMED"):
        return "CONFIRMED"
    if s in ("ĐANG GIAO", "DANG GIAO", "ĐANG GIAO HÀNG", "SHIPPING"):
        return "SHIPPING"
    if s in ("HỦY", "HUY", "ĐÃ HỦY", "CANCELLED", "CANCELED"):
        return "CANCELLED"
    return s


def parse_date_range(
    from_date_str: Optional[str] = None,
    to_date_str: Optional[str] = None,
    preset: Optional[str] = None,
) -> Tuple[Optional[datetime], Optional[datetime], str]:
    """Phân tích và trả về khoảng thời gian (start_dt, end_dt, preset_name)."""
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59, 999999)

    preset_clean = (preset or "").strip().lower()

    if preset_clean == "today":
        return today_start, today_end, "today"

    if preset_clean == "yesterday":
        y_start = today_start - timedelta(days=1)
        y_end = datetime(y_start.year, y_start.month, y_start.day, 23, 59, 59, 999999)
        return y_start, y_end, "yesterday"

    if preset_clean in ("7days", "7_days", "week"):
        start = today_start - timedelta(days=6)
        return start, today_end, "7days"

    if preset_clean in ("30days", "30_days", "month"):
        start = today_start - timedelta(days=29)
        return start, today_end, "30days"

    if preset_clean in ("this_month", "current_month"):
        start = datetime(now.year, now.month, 1, 0, 0, 0)
        return start, today_end, "this_month"

    if preset_clean in ("last_month", "prev_month"):
        first_day_current_month = datetime(now.year, now.month, 1)
        last_day_prev_month = first_day_current_month - timedelta(days=1)
        first_day_prev_month = datetime(last_day_prev_month.year, last_day_prev_month.month, 1, 0, 0, 0)
        end_prev_month = datetime(
            last_day_prev_month.year, last_day_prev_month.month, last_day_prev_month.day, 23, 59, 59, 999999
        )
        return first_day_prev_month, end_prev_month, "last_month"

    if preset_clean in ("this_year", "year"):
        start = datetime(now.year, 1, 1, 0, 0, 0)
        return start, today_end, "this_year"

    if preset_clean == "all":
        return None, None, "all"

    # Xử lý from_date_str và to_date_str tùy chỉnh
    start_dt = None
    end_dt = None

    if from_date_str:
        f_clean = from_date_str.strip()
        try:
            if len(f_clean) == 10:  # YYYY-MM-DD
                start_dt = datetime.strptime(f_clean, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
            elif "T" in f_clean:
                start_dt = datetime.fromisoformat(f_clean)
            else:
                start_dt = datetime.strptime(f_clean, "%Y-%m-%d %H:%M:%S")
        except Exception:
            start_dt = None

    if to_date_str:
        t_clean = to_date_str.strip()
        try:
            if len(t_clean) == 10:  # YYYY-MM-DD
                end_dt = datetime.strptime(t_clean, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
            elif "T" in t_clean:
                end_dt = datetime.fromisoformat(t_clean)
            else:
                end_dt = datetime.strptime(t_clean, "%Y-%m-%d %H:%M:%S")
        except Exception:
            end_dt = None

    applied_preset = "custom" if (start_dt or end_dt) else "all"
    return start_dt, end_dt, applied_preset


def get_sales_report(
    db: Session,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    preset: Optional[str] = None,
) -> SalesReportResponse:
    """Tính toán và tổng hợp báo cáo bán hàng chi tiết từ cơ sở dữ liệu."""
    start_dt, end_dt, applied_preset = parse_date_range(from_date, to_date, preset)

    # 1. Truy vấn các đơn hàng trong khoảng thời gian
    query = db.query(Order)
    if start_dt:
        query = query.filter(Order.created_at >= start_dt)
    if end_dt:
        query = query.filter(Order.created_at <= end_dt)

    orders: List[Order] = query.order_by(Order.created_at.asc()).all()

    total_orders = len(orders)
    total_revenue = 0
    delivered_online_revenue = 0
    delivered_online_orders_count = 0
    pos_revenue = 0
    pos_orders_count = 0

    pending_count = 0
    confirmed_count = 0
    shipping_count = 0
    cancelled_count = 0

    completed_order_ids: List[int] = []

    # Bản đồ thống kê theo ngày (YYYY-MM-DD)
    daily_stats: Dict[str, Dict[str, int]] = {}

    # Bản đồ thống kê theo trạng thái
    status_summary: Dict[str, Dict[str, Any]] = {
        "DELIVERED": {"name": "Đơn online giao thành công", "count": 0, "amount": 0},
        "POS": {"name": "Bán trực tiếp tại quầy", "count": 0, "amount": 0},
        "SHIPPING": {"name": "Đang giao hàng", "count": 0, "amount": 0},
        "CONFIRMED": {"name": "Đã xác nhận", "count": 0, "amount": 0},
        "PENDING": {"name": "Chờ xác nhận", "count": 0, "amount": 0},
        "CANCELLED": {"name": "Đã hủy", "count": 0, "amount": 0},
    }

    # Nếu khoảng thời gian có giới hạn cụ thể (<= 31 ngày), khởi tạo trước các ngày để biểu đồ liền mạch
    if start_dt and end_dt:
        delta_days = (end_dt.date() - start_dt.date()).days
        if 0 <= delta_days <= 31:
            cur_day = start_dt.date()
            while cur_day <= end_dt.date():
                ds_str = cur_day.strftime("%Y-%m-%d")
                daily_stats[ds_str] = {
                    "total_revenue": 0,
                    "delivered_revenue": 0,
                    "pos_revenue": 0,
                    "order_count": 0,
                    "completed_orders_count": 0,
                    "items_sold": 0,
                }
                cur_day += timedelta(days=1)

    for order in orders:
        norm_status = _normalize_order_status(order.status)
        is_pos = _is_pos_order(order)
        order_amount = int(order.total_amount or 0)
        order_date_str = (
            order.created_at.strftime("%Y-%m-%d") if order.created_at else datetime.now().strftime("%Y-%m-%d")
        )

        if order_date_str not in daily_stats:
            daily_stats[order_date_str] = {
                "total_revenue": 0,
                "delivered_revenue": 0,
                "pos_revenue": 0,
                "order_count": 0,
                "completed_orders_count": 0,
                "items_sold": 0,
            }

        daily_stats[order_date_str]["order_count"] += 1

        if is_pos and norm_status != "CANCELLED":
            # Đơn bán tại quầy (POS) thành công
            pos_orders_count += 1
            pos_revenue += order_amount
            total_revenue += order_amount
            completed_order_ids.append(order.id)

            status_summary["POS"]["count"] += 1
            status_summary["POS"]["amount"] += order_amount

            daily_stats[order_date_str]["pos_revenue"] += order_amount
            daily_stats[order_date_str]["total_revenue"] += order_amount
            daily_stats[order_date_str]["completed_orders_count"] += 1

        elif norm_status == "DELIVERED":
            # Đơn online giao thành công
            delivered_online_orders_count += 1
            delivered_online_revenue += order_amount
            total_revenue += order_amount
            completed_order_ids.append(order.id)

            status_summary["DELIVERED"]["count"] += 1
            status_summary["DELIVERED"]["amount"] += order_amount

            daily_stats[order_date_str]["delivered_revenue"] += order_amount
            daily_stats[order_date_str]["total_revenue"] += order_amount
            daily_stats[order_date_str]["completed_orders_count"] += 1

        elif norm_status == "CANCELLED":
            cancelled_count += 1
            status_summary["CANCELLED"]["count"] += 1
            status_summary["CANCELLED"]["amount"] += order_amount

        elif norm_status == "SHIPPING":
            shipping_count += 1
            status_summary["SHIPPING"]["count"] += 1
            status_summary["SHIPPING"]["amount"] += order_amount

        elif norm_status == "CONFIRMED":
            confirmed_count += 1
            status_summary["CONFIRMED"]["count"] += 1
            status_summary["CONFIRMED"]["amount"] += order_amount

        else:  # PENDING hoặc trạng thái khác
            pending_count += 1
            status_summary["PENDING"]["count"] += 1
            status_summary["PENDING"]["amount"] += order_amount

    # 2. Tính tổng số sản phẩm đã bán và Top 10 sản phẩm bán chạy nhất
    total_items_sold = 0
    top_products_list: List[TopProductReportItem] = []

    if completed_order_ids:
        # Tổng số lượng sản phẩm từ các đơn hoàn thành
        sum_items_sold = (
            db.query(func.coalesce(func.sum(OrderItem.quantity), 0))
            .filter(OrderItem.order_id.in_(completed_order_ids))
            .scalar()
        )
        total_items_sold = int(sum_items_sold or 0)

        # Cập nhật số sản phẩm bán theo từng ngày
        items_by_day = (
            db.query(func.date(Order.created_at).label("day"), func.sum(OrderItem.quantity).label("qty"))
            .join(Order, OrderItem.order_id == Order.id)
            .filter(Order.id.in_(completed_order_ids))
            .group_by("day")
            .all()
        )
        for row in items_by_day:
            day_str = str(row.day)
            if day_str in daily_stats:
                daily_stats[day_str]["items_sold"] = int(row.qty or 0)

        # Top 10 sản phẩm bán chạy nhất
        top_rows = (
            db.query(
                OrderItem.product_id,
                OrderItem.product_name,
                OrderItem.sku,
                OrderItem.category_name,
                OrderItem.image_url,
                func.sum(OrderItem.quantity).label("qty_sold"),
                func.sum(OrderItem.subtotal).label("total_rev"),
                func.count(func.distinct(OrderItem.order_id)).label("order_cnt"),
            )
            .filter(OrderItem.order_id.in_(completed_order_ids))
            .group_by(
                OrderItem.product_id,
                OrderItem.product_name,
                OrderItem.sku,
                OrderItem.category_name,
                OrderItem.image_url,
            )
            .order_by(desc("qty_sold"), desc("total_rev"))
            .limit(10)
            .all()
        )

        for r in top_rows:
            top_products_list.append(
                TopProductReportItem(
                    product_id=r.product_id,
                    product_name=r.product_name,
                    sku=r.sku,
                    category_name=r.category_name,
                    image_url=r.image_url,
                    quantity_sold=int(r.qty_sold or 0),
                    revenue=int(r.total_rev or 0),
                    orders_count=int(r.order_cnt or 0),
                )
            )

    # 3. Tính toán giá trị đơn hàng trung bình (AOV - Average Order Value)
    completed_orders_total = delivered_online_orders_count + pos_orders_count
    avg_order_value = (
        round(total_revenue / completed_orders_total, 2) if completed_orders_total > 0 else 0.0
    )

    # 4. Chuẩn bị danh sách thống kê trạng thái
    orders_by_status: List[OrderStatusReportItem] = []
    for code, info in status_summary.items():
        pct = round((info["count"] / total_orders * 100), 2) if total_orders > 0 else 0.0
        orders_by_status.append(
            OrderStatusReportItem(
                status_code=code,
                status_name=info["name"],
                order_count=info["count"],
                total_amount=info["amount"],
                percentage=pct,
            )
        )

    # 5. Chuẩn bị danh sách doanh thu theo ngày (sắp xếp tăng dần theo thời gian)
    daily_revenue_list: List[DailyRevenueReportItem] = []
    for d_str in sorted(daily_stats.keys()):
        d_val = daily_stats[d_str]
        daily_revenue_list.append(
            DailyRevenueReportItem(
                date=d_str,
                total_revenue=d_val["total_revenue"],
                delivered_revenue=d_val["delivered_revenue"],
                pos_revenue=d_val["pos_revenue"],
                order_count=d_val["order_count"],
                completed_orders_count=d_val["completed_orders_count"],
                items_sold=d_val["items_sold"],
            )
        )

    # 6. Đóng gói kết quả báo cáo
    summary = ReportSummary(
        total_orders=total_orders,
        total_revenue=total_revenue,
        delivered_online_revenue=delivered_online_revenue,
        delivered_online_orders_count=delivered_online_orders_count,
        pos_revenue=pos_revenue,
        pos_orders_count=pos_orders_count,
        total_items_sold=total_items_sold,
        average_order_value=avg_order_value,
        pending_orders_count=pending_count,
        confirmed_orders_count=confirmed_count,
        shipping_orders_count=shipping_count,
        cancelled_orders_count=cancelled_count,
    )

    filter_applied = FilterApplied(
        from_date=start_dt.strftime("%Y-%m-%d %H:%M:%S") if start_dt else None,
        to_date=end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt else None,
        preset=applied_preset,
    )

    return SalesReportResponse(
        success=True,
        filter=filter_applied,
        summary=summary,
        orders_by_status=orders_by_status,
        top_products=top_products_list,
        daily_revenue=daily_revenue_list,
    )
