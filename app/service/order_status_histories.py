"""Tầng xử lý dữ liệu và nghiệp vụ cho Đơn hàng và Lịch sử trạng thái (Order & Histories Service).

Tài liệu đặc tả liên quan:
- FR-025: Xem chi tiết đơn hàng (Sản phẩm, tổng tiền, lịch sử chuyển trạng thái).
- FR-028: Xem danh sách đơn hàng của khách hàng (hoặc toàn bộ đơn hàng cho Admin/Staff).
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from datetime import date, datetime
from sqlalchemy import func, or_

from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.order_status_histories import OrderStatusHistory
from app.models.product import Product
from app.models.stock_log import StockLog


def get_orders_by_user(
    db: Session,
    user_id: int,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[int, List[Order]]:
    """Lấy danh sách đơn hàng của một người dùng cụ thể kèm phân trang (FR-028).

    Args:
        db: Database session.
        user_id: ID khách hàng.
        status: Bộ lọc trạng thái đơn hàng (nếu có).
        page: Số trang hiện tại.
        page_size: Số lượng đơn hàng mỗi trang.

    Returns:
        Tuple (tổng số đơn hàng thỏa điều kiện, danh sách đơn hàng).
    """
    query = db.query(Order).filter(Order.user_id == user_id)
    if status:
        st_clean = str(status).strip().upper()
        candidates = [status, st_clean]
        if hasattr(OrderStatus, st_clean):
            member = getattr(OrderStatus, st_clean)
            candidates.extend([member, member.value])
        if st_clean in ("COMPLETED", "DELIVERED"):
            candidates.extend(["Hoàn thành", "Đã giao", "DELIVERED", "COMPLETED", OrderStatus.COMPLETED])
        elif st_clean == "PENDING":
            candidates.extend(["Chờ xác nhận", OrderStatus.PENDING])
        elif st_clean == "CONFIRMED":
            candidates.extend(["Đã xác nhận", OrderStatus.CONFIRMED])
        elif st_clean == "SHIPPING":
            candidates.extend(["Đang giao", "Đang giao hàng", OrderStatus.SHIPPING])
        elif st_clean == "CANCELLED":
            candidates.extend(["Hủy", "Đã hủy", OrderStatus.CANCELLED])
        query = query.filter(Order.status.in_(list(set(candidates))))

    total = query.count()
    orders = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, orders


def get_all_orders(
    db: Session,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[int, List[Order]]:
    """Lấy danh sách tất cả đơn hàng trong hệ thống (dành cho Admin/Staff) kèm phân trang.

    Args:
        db: Database session.
        status: Bộ lọc trạng thái đơn hàng (nếu có).
        page: Số trang.
        page_size: Số lượng mỗi trang.

    Returns:
        Tuple (tổng số đơn hàng trong hệ thống, danh sách đơn hàng).
    """
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)

    total = query.count()
    orders = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, orders


def get_order_by_id(db: Session, order_id: int) -> Optional[Order]:
    """Lấy thông tin một đơn hàng theo ID.

    Args:
        db: Database session.
        order_id: ID đơn hàng cần tìm.

    Returns:
        Đối tượng Order nếu tìm thấy, ngược lại None.
    """
    return db.query(Order).filter(Order.id == order_id).first()


def get_order_items(db: Session, order_id: int) -> List[OrderItem]:
    """Lấy danh sách các mặt hàng chi tiết trong một đơn hàng (FR-025).

    Args:
        db: Database session.
        order_id: ID đơn hàng.

    Returns:
        Danh sách OrderItem thuộc về đơn hàng đó.
    """
    return db.query(OrderItem).filter(OrderItem.order_id == order_id).all()


def get_order_histories(db: Session, order_id: int) -> List[OrderStatusHistory]:
    """Lấy toàn bộ lịch sử chuyển đổi trạng thái của một đơn hàng theo thời gian (FR-025, FR-028).

    Args:
        db: Database session.
        order_id: ID đơn hàng.

    Returns:
        Danh sách OrderStatusHistory sắp xếp từ mới nhất tới cũ nhất.
    """
    return (
        db.query(OrderStatusHistory)
        .filter(OrderStatusHistory.order_id == order_id)
        .order_by(OrderStatusHistory.changed_at.desc())
        .all()
    )

def _normalize_history_code(val) -> str:
    if hasattr(val, "name"):
        return val.name
    s = str(val.value if hasattr(val, "value") else val).strip().lower()
    if "chờ" in s or "pending" in s:
        return "PENDING"
    if "xác nhận" in s or "confirmed" in s:
        return "CONFIRMED"
    if "giao" in s or "shipping" in s:
        return "SHIPPING"
    if any(k in s for k in ["hoàn thành", "completed", "delivered", "thành công", "đã giao"]):
        return "DELIVERED"
    if "hủy" in s or "cancel" in s:
        return "CANCELLED"
    return "PENDING"


def cancel_order(db: Session, order: Order, user_id: int, cancel_reason: str) -> Order:
    """Hủy đơn hàng, ghi lịch sử và hoàn lại tồn kho."""
    old_status = _normalize_history_code(order.status)
    # 1. Cập nhật trạng thái đơn hàng sang CANCELLED / Hủy
    try:
        order.status = OrderStatus.CANCELLED
    except Exception:
        order.status = "CANCELLED"
    order.cancel_reason = cancel_reason
    # 2. Ghi 1 dòng lịch sử thay đổi trạng thái
    history = OrderStatusHistory(
        order_id=order.id,
        changed_by=user_id,
        old_status=old_status,
        new_status="CANCELLED",
        note=cancel_reason,
    )
    db.add(history)
    # 3. Hoàn lại tồn kho cho từng sản phẩm và ghi nhật ký kho
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            stock_before = product.stock_quantity
            product.stock_quantity += item.quantity
            stock_after = product.stock_quantity
            # Ghi nhật ký biến động kho (stock_logs)
            stock_log = StockLog(
                product_id=product.id,
                order_id=order.id,
                created_by=user_id,
                change_type="CANCEL",
                quantity_change=item.quantity,  # số dương là cộng hoàn lại
                stock_before=stock_before,
                stock_after=stock_after,
                note=f"Hoàn tồn kho do hủy đơn {order.order_code}",
            )
            db.add(stock_log)

    # 3.1 Hoàn lại voucher nếu đơn hàng có áp dụng voucher
    if order.note and "[Voucher " in order.note and order.user_id:
        import re
        match = re.search(r"\[Voucher\s+([A-Za-z0-9_-]+):", order.note)
        if match:
            vcode = match.group(1).strip().upper()
            from app.models.voucher import Voucher
            voucher = db.query(Voucher).filter(
                Voucher.code == vcode,
                Voucher.user_id == order.user_id
            ).first()
            if voucher and voucher.is_used == 1:
                voucher.is_used = 0

    # 3.2 Thu hồi điểm thưởng nếu đơn hàng đã từng được tích điểm khi Admin duyệt
    if old_status in ["CONFIRMED", "SHIPPING", "COMPLETED", "DELIVERED"]:
        total_amount = int(order.total_amount or 0)
        if total_amount > 500_000 and order.user_id:
            points_earned = int((total_amount - 500_000) // 10_000)
            if points_earned > 0:
                from app.models.user import User
                customer = db.query(User).filter(User.id == order.user_id).first()
                if customer and customer.reward_points:
                    customer.reward_points = max(0, customer.reward_points - points_earned)

    # 4. Lưu toàn bộ thay đổi trong 1 giao dịch
    db.commit()
    db.refresh(order)
    return order

def get_all_orders_admin(
    db: Session,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[int, List[Order]]:
    """Lấy danh sách tất cả đơn hàng cho Admin có lọc và phân trang (FR-024)."""
    query = db.query(Order)
    # Lọc theo trạng thái
    if status:
        query = query.filter(Order.status == status)
    # Lọc theo khoảng ngày tạo đơn
    if from_date:
        query = query.filter(func.date(Order.created_at) >= from_date)
    if to_date:
        query = query.filter(func.date(Order.created_at) <= to_date)
    # Tìm kiếm theo mã đơn hoặc số điện thoại
    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Order.order_code.like(kw),
                Order.receiver_phone.like(kw),
            )
        )
    total = query.count()
    orders = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, orders
def update_order_status_admin(
    db: Session,
    order: Order,
    new_status: str,
    user_id: int,
    note: Optional[str] = None,
) -> Order:
    """Cập nhật trạng thái đơn hàng và ghi lại lịch sử (FR-026)."""
    old_status_code = _normalize_history_code(order.status)
    new_status_code = _normalize_history_code(new_status)

    # 1. Cập nhật Order.status (chuẩn hóa enum tiếng Việt trong Order model)
    order_enum_map = {
        "PENDING": OrderStatus.PENDING,
        "CONFIRMED": OrderStatus.CONFIRMED,
        "SHIPPING": OrderStatus.SHIPPING,
        "COMPLETED": OrderStatus.COMPLETED,
        "DELIVERED": OrderStatus.COMPLETED,
        "CANCELLED": OrderStatus.CANCELLED,
    }
    target_status = order_enum_map.get(new_status_code, OrderStatus.CONFIRMED)
    try:
        order.status = target_status
    except Exception:
        order.status = new_status

    # 2. Nếu hoàn thành thì lưu thời điểm hoàn thành
    if new_status_code in ["COMPLETED", "DELIVERED"]:
        order.completed_at = datetime.now()

    # 2.1 Tích lũy điểm thưởng khi Admin duyệt đơn (PENDING -> CONFIRMED / SHIPPING / COMPLETED)
    # Quy tắc: Đơn hàng chi tiêu trên 500k, mỗi 10k vượt 500k nhận 1 điểm (Ví dụ: 490k -> 0đ, 510k -> 1đ)
    if old_status_code == "PENDING" and new_status_code in ["CONFIRMED", "SHIPPING", "COMPLETED"]:
        total_amount = int(order.total_amount or 0)
        if total_amount > 500_000 and order.user_id:
            points_earned = int((total_amount - 500_000) // 10_000)
            if points_earned > 0:
                from app.models.user import User
                customer = db.query(User).filter(User.id == order.user_id).first()
                if customer:
                    customer.reward_points = (customer.reward_points or 0) + points_earned
                    points_text = f" (+{points_earned} điểm thưởng)"
                    note = f"{(note or 'Admin duyệt đơn')}{points_text}"

    # 3. Ghi lại 1 dòng lịch sử chuyển đổi trạng thái (chuẩn hóa enum tiếng Anh trong OrderStatusHistory)
    history = OrderStatusHistory(
        order_id=order.id,
        changed_by=user_id,
        old_status=old_status_code,
        new_status=new_status_code,
        note=note,
    )
    db.add(history)
    db.commit()
    db.refresh(order)
    return order