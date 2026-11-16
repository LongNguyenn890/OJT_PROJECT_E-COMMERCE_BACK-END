from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from datetime import date, datetime
from sqlalchemy import func, or_

from app.models.order import Order
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

def cancel_order(db: Session, order: Order, user_id: int, cancel_reason: str) -> Order:
    """Hủy đơn hàng, ghi lịch sử và hoàn lại tồn kho."""
    old_status = str(order.status.value if hasattr(order.status, "value") else order.status)
    # 1. Cập nhật trạng thái đơn hàng sang CANCELLED
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
    old_status = str(order.status.value if hasattr(order.status, "value") else order.status)
    # Cập nhật trạng thái mới
    order.status = new_status
    # Nếu hoàn thành thì lưu thời điểm hoàn thành
    if new_status == "COMPLETED":
        order.completed_at = datetime.now()
    # Ghi lại 1 dòng lịch sử chuyển đổi trạng thái
    history = OrderStatusHistory(
        order_id=order.id,
        changed_by=user_id,
        old_status=old_status,
        new_status=new_status,
        note=note,
    )
    db.add(history)
    db.commit()
    db.refresh(order)
    return order