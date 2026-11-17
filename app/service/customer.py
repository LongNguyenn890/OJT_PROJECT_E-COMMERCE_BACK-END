"""Service xử lý dữ liệu và nghiệp vụ quản lý khách hàng (Customer Management Service).

Chức năng:
- Danh sách khách hàng phân trang, tìm kiếm theo tên/email/SĐT, thống kê tổng số đơn và tổng chi tiêu.
- Xem chi tiết thông tin khách hàng, thống kê đơn hoàn thành, đơn hủy, các đơn gần đây.
- Lịch sử mua hàng của khách hàng (phân trang, lọc theo trạng thái).
- Cập nhật trạng thái khách hàng (khóa/mở khóa tài khoản).
"""
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, or_, case
from fastapi import HTTPException, status

from app.models.user import User, Role, Status
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem


def get_customers_list(
    db: Session,
    keyword: Optional[str] = None,
    status_filter: Optional[str] = None,
    role_filter: Optional[str] = "CUSTOMER",
    page: int = 1,
    page_size: int = 10,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Lấy danh sách khách hàng phân trang kèm tìm kiếm và thống kê tổng số đơn & tổng chi tiêu."""
    # Subquery tính tổng số đơn và tổng tiền chi tiêu (chỉ cộng tiền đơn không bị hủy)
    order_stats = (
        db.query(
            Order.user_id,
            func.count(Order.id).label("total_orders"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            Order.status.in_(
                                [
                                    "CANCELLED",
                                    "Hủy",
                                    OrderStatus.CANCELLED,
                                    getattr(OrderStatus.CANCELLED, "value", "Hủy"),
                                ]
                            ),
                            0,
                        ),
                        else_=Order.total_amount,
                    )
                ),
                0,
            ).label("total_spent"),
        )
        .group_by(Order.user_id)
        .subquery()
    )

    query = (
        db.query(
            User,
            func.coalesce(order_stats.c.total_orders, 0).label("total_orders"),
            func.coalesce(order_stats.c.total_spent, 0).label("total_spent"),
        )
        .outerjoin(order_stats, order_stats.c.user_id == User.id)
    )

    # Lọc theo vai trò (mặc định là CUSTOMER nếu không chỉ định ALL)
    if role_filter and role_filter.upper() != "ALL":
        query = query.filter(User.role == role_filter)

    # Lọc theo trạng thái tài khoản nếu có
    if status_filter:
        query = query.filter(User.status == status_filter)

    # Tìm kiếm theo tên, email, số điện thoại
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                User.full_name.ilike(kw),
                User.email.ilike(kw),
                User.phone.like(kw),
            )
        )

    total = query.count()
    results = (
        query.order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for user_obj, total_orders, total_spent in results:
        items.append(
            {
                "id": user_obj.id,
                "full_name": user_obj.full_name,
                "email": user_obj.email,
                "phone": user_obj.phone,
                "avatar": user_obj.avatar,
                "role": user_obj.role,
                "status": user_obj.status,
                "created_at": user_obj.created_at,
                "total_orders": int(total_orders),
                "total_spent": int(total_spent),
            }
        )

    return total, items


def get_customer_detail(db: Session, customer_id: int) -> Dict[str, Any]:
    """Lấy chi tiết hồ sơ khách hàng, danh sách địa chỉ, thống kê đơn & chi tiêu và đơn gần đây."""
    customer = (
        db.query(User)
        .options(selectinload(User.addresses))
        .filter(User.id == customer_id)
        .first()
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Khách hàng với ID {customer_id} không tồn tại",
        )

    orders = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.user_id == customer_id)
        .order_by(Order.created_at.desc())
        .all()
    )

    total_orders = len(orders)
    total_spent = 0
    completed_orders = 0
    cancelled_orders = 0

    for ord in orders:
        st = str(ord.status.value if hasattr(ord.status, "value") else ord.status).upper()
        if st in ("CANCELLED", "HỦY"):
            cancelled_orders += 1
        else:
            total_spent += ord.total_amount
            if st in ("COMPLETED", "HOÀN THÀNH"):
                completed_orders += 1

    recent_orders = []
    for ord in orders[:5]:
        status_str = str(ord.status.value if hasattr(ord.status, "value") else ord.status)
        pm_str = str(ord.payment_method.value if hasattr(ord.payment_method, "value") else ord.payment_method)
        recent_orders.append(
            {
                "id": ord.id,
                "order_code": ord.order_code,
                "receiver_name": ord.receiver_name,
                "receiver_phone": ord.receiver_phone,
                "shipping_address": ord.shipping_address,
                "payment_method": pm_str,
                "total_amount": ord.total_amount,
                "status": status_str,
                "created_at": ord.created_at,
                "items": ord.items,
            }
        )

    return {
        "id": customer.id,
        "full_name": customer.full_name,
        "email": customer.email,
        "phone": customer.phone,
        "avatar": customer.avatar,
        "role": customer.role,
        "status": customer.status,
        "created_at": customer.created_at,
        "updated_at": customer.updated_at,
        "addresses": customer.addresses,
        "total_orders": total_orders,
        "total_spent": total_spent,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "recent_orders": recent_orders,
    }


def get_customer_orders(
    db: Session,
    customer_id: int,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Lấy danh sách lịch sử mua hàng của khách hàng kèm phân trang và lọc trạng thái."""
    customer = db.query(User.id).filter(User.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Khách hàng với ID {customer_id} không tồn tại",
        )

    query = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.user_id == customer_id)
    )

    if status_filter:
        query = query.filter(
            or_(
                Order.status == status_filter,
                Order.status == status_filter.upper(),
            )
        )

    total = query.count()
    orders = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for ord in orders:
        status_str = str(ord.status.value if hasattr(ord.status, "value") else ord.status)
        pm_str = str(ord.payment_method.value if hasattr(ord.payment_method, "value") else ord.payment_method)
        items.append(
            {
                "id": ord.id,
                "order_code": ord.order_code,
                "receiver_name": ord.receiver_name,
                "receiver_phone": ord.receiver_phone,
                "shipping_address": ord.shipping_address,
                "payment_method": pm_str,
                "total_amount": ord.total_amount,
                "status": status_str,
                "created_at": ord.created_at,
                "items": ord.items,
            }
        )

    return total, items


def update_customer_status(
    db: Session,
    customer_id: int,
    new_status: Status,
) -> User:
    """Cập nhật trạng thái tài khoản khách hàng (khóa hoặc kích hoạt)."""
    customer = db.query(User).filter(User.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Khách hàng với ID {customer_id} không tồn tại",
        )
    customer.status = new_status
    db.commit()
    db.refresh(customer)
    return customer
