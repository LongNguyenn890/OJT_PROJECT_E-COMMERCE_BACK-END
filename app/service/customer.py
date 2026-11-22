"""Service xử lý dữ liệu và nghiệp vụ quản lý khách hàng (Customer Management Service).

Chức năng:
- Danh sách khách hàng phân trang, tìm kiếm theo tên/email/SĐT, thống kê tổng số đơn và tổng chi tiêu.
- Xem chi tiết thông tin khách hàng, sổ địa chỉ, thống kê đơn hoàn thành, đơn hủy, các đơn gần đây.
- Lịch sử mua hàng của khách hàng (phân trang, lọc theo trạng thái đơn hàng).
- Cập nhật trạng thái khách hàng (khóa/mở khóa tài khoản).
- Xóa tài khoản khách hàng (khóa bảo tồn dữ liệu nếu đã có đơn hàng).
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

    # Nghiệp vụ Khách hàng: Luôn luôn chỉ lấy tài khoản có vai trò CUSTOMER
    query = (
        db.query(
            User,
            func.coalesce(order_stats.c.total_orders, 0).label("total_orders"),
            func.coalesce(order_stats.c.total_spent, 0).label("total_spent"),
        )
        .outerjoin(order_stats, order_stats.c.user_id == User.id)
        .filter(User.role == Role.CUSTOMER)
    )

    # Lọc theo trạng thái tài khoản nếu có
    if status_filter and status_filter.strip():
        sf = status_filter.strip().upper()
        if sf in ("LOCKED", "LOCK"):
            query = query.filter(or_(User.status == Status.LOCK, User.status == "LOCKED", User.status == "LOCK"))
        else:
            query = query.filter(or_(User.status == Status.ACTIVE, User.status == "ACTIVE"))

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
        .filter(User.id == customer_id, User.role == Role.CUSTOMER)
        .first()
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng với ID #{customer_id}",
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
    customer = db.query(User.id).filter(User.id == customer_id, User.role == Role.CUSTOMER).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng với ID #{customer_id}",
        )

    query = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.user_id == customer_id)
    )

    if status_filter and status_filter.strip():
        sf = status_filter.strip()
        query = query.filter(
            or_(
                Order.status == sf,
                Order.status == sf.upper(),
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
    new_status: Any,
) -> User:
    """Cập nhật trạng thái tài khoản khách hàng (khóa hoặc kích hoạt)."""
    customer = db.query(User).filter(User.id == customer_id, User.role == Role.CUSTOMER).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng với ID #{customer_id}",
        )
    st_val = getattr(new_status, "value", str(new_status)).strip().upper()
    if st_val in ("LOCKED", "LOCK"):
        customer.status = Status.LOCK
    else:
        customer.status = Status.ACTIVE
    db.commit()
    db.refresh(customer)
    return customer


def delete_customer(db: Session, customer_id: int) -> Dict[str, Any]:
    """Xóa tài khoản khách hàng (chuyển sang LOCKED nếu đã có đơn hàng để bảo toàn lịch sử giao dịch)."""
    customer = db.query(User).filter(User.id == customer_id, User.role == Role.CUSTOMER).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy khách hàng với ID #{customer_id}",
        )

    # Kiểm tra xem khách hàng đã có đơn hàng trong hệ thống hay chưa
    order_count = db.query(Order).filter(Order.user_id == customer_id).count()
    if order_count > 0:
        customer.status = Status.LOCK
        db.commit()
        return {
            "message": f"Khách hàng {customer.full_name} đã có {order_count} đơn hàng trong lịch sử. Hệ thống đã khóa tài khoản thay vì xóa vĩnh viễn để bảo tồn dữ liệu báo cáo.",
            "action": "locked",
            "id": customer_id,
        }

    db.delete(customer)
    db.commit()
    return {
        "message": f"Đã xóa thành công tài khoản khách hàng {customer.full_name} (#{customer_id}) khỏi hệ thống.",
        "action": "deleted",
        "id": customer_id,
    }
