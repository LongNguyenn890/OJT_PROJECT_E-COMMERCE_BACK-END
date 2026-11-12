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
    """Lấy danh sách đơn hàng của người dùng kèm phân trang."""
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


def get_order_by_id(db: Session, order_id: int) -> Optional[Order]:
    """Lấy thông tin đơn hàng theo ID."""
    return db.query(Order).filter(Order.id == order_id).first()


def get_order_items(db: Session, order_id: int) -> List[OrderItem]:
    """Lấy danh sách sản phẩm trong đơn hàng."""
    return db.query(OrderItem).filter(OrderItem.order_id == order_id).all()


def get_order_histories(db: Session, order_id: int) -> List[OrderStatusHistory]:
    """Lấy danh sách lịch sử chuyển đổi trạng thái của đơn hàng."""
    return (
        db.query(OrderStatusHistory)
        .filter(OrderStatusHistory.order_id == order_id)
        .order_by(OrderStatusHistory.changed_at.desc())
        .all()
    )
