"""Tầng xử lý dữ liệu và nghiệp vụ cho Đơn hàng và Lịch sử trạng thái (Order & Histories Service).

Tài liệu đặc tả liên quan:
- FR-025: Xem chi tiết đơn hàng (Sản phẩm, tổng tiền, lịch sử chuyển trạng thái).
- FR-028: Xem danh sách đơn hàng của khách hàng (hoặc toàn bộ đơn hàng cho Admin/Staff).
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_status_histories import OrderStatusHistory


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
        query = query.filter(Order.status == status)

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
