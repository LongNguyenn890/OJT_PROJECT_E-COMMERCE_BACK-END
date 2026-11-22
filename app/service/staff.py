"""Service xử lý nghiệp vụ quản lý nhân sự / nhân viên nội bộ (Staff Management Service).

Chức năng:
- Lấy danh sách nhân viên & quản trị viên (STAFF, ADMIN) kèm phân trang, tìm kiếm theo tên/email/SĐT, lọc trạng thái.
- Xem chi tiết hồ sơ tài khoản nhân viên.
- Admin tạo tài khoản nhân viên mới (kiểm tra trùng lặp email, mã hóa mật khẩu).
- Admin cập nhật thông tin nhân viên (họ tên, SĐT, phân quyền vai trò, đổi mật khẩu).
- Admin khóa / mở khóa tài khoản nhân viên (ngăn chặn tự khóa tài khoản của chính mình).
- Admin xóa tài khoản nhân viên.
"""
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_
from fastapi import HTTPException, status

from app.models.user import User, Role, Status
from app.models.order import Order
from app.core.security import hash_password
from app.schemas.staff import StaffCreate


def get_staff_list(
    db: Session,
    keyword: Optional[str] = None,
    status_filter: Optional[str] = None,
    role_filter: Optional[str] = None,
    exclude_user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[int, List[User]]:
    """Lấy danh sách nhân viên & quản trị viên nội bộ kèm phân trang, tìm kiếm và bộ lọc."""
    query = (
        db.query(User)
        .options(selectinload(User.addresses))
    )

    # Chỉ lấy các tài khoản có vai trò nội bộ (STAFF hoặc ADMIN)
    if role_filter and role_filter.strip():
        rf = role_filter.strip().upper()
        if rf == "ADMIN":
            query = query.filter(User.role == Role.ADMIN)
        elif rf == "STAFF":
            query = query.filter(User.role == Role.STAFF)
        else:
            query = query.filter(User.role.in_([Role.STAFF, Role.ADMIN]))
    else:
        query = query.filter(User.role.in_([Role.STAFF, Role.ADMIN]))

    # Lọc theo trạng thái tài khoản nếu có
    if status_filter and status_filter.strip():
        sf = status_filter.strip().upper()
        if sf in ("LOCKED", "LOCK"):
            query = query.filter(or_(User.status == Status.LOCK, User.status == "LOCKED", User.status == "LOCK"))
        else:
            query = query.filter(or_(User.status == Status.ACTIVE, User.status == "ACTIVE"))

    # Tìm kiếm theo họ tên, email hoặc số điện thoại
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                User.full_name.ilike(kw),
                User.email.ilike(kw),
                User.phone.like(kw),
            )
        )

    # Loại trừ tài khoản chỉ định (ví dụ chính Admin đang đăng nhập)
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)

    total = query.count()
    items = (
        query.order_by(User.role.asc(), User.created_at.desc(), User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return total, items


def get_staff_detail(db: Session, staff_id: int) -> User:
    """Lấy chi tiết hồ sơ tài khoản nhân viên theo ID."""
    staff = (
        db.query(User)
        .options(selectinload(User.addresses))
        .filter(User.id == staff_id)
        .first()
    )
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài khoản nhân viên với ID #{staff_id}",
        )
    if staff.role == Role.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tài khoản ID #{staff_id} là tài khoản Khách hàng (CUSTOMER), vui lòng xem tại module Quản lý khách hàng.",
        )
    return staff


def create_staff_member(db: Session, payload: StaffCreate) -> User:
    """Admin tạo tài khoản nhân viên mới."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{payload.email}' đã tồn tại trong hệ thống, vui lòng chọn email khác.",
        )

    target_role = payload.role if payload.role in (Role.STAFF, Role.ADMIN) else Role.STAFF

    new_staff = User(
        full_name=payload.full_name.strip(),
        email=payload.email.strip().lower(),
        phone=payload.phone.strip(),
        password_hash=hash_password(payload.password),
        role=target_role,
        status=Status.ACTIVE,
    )
    db.add(new_staff)
    db.commit()
    db.refresh(new_staff)
    return new_staff


def update_staff_member(
    db: Session,
    staff_id: int,
    full_name: Optional[str] = None,
    phone: Optional[str] = None,
    password: Optional[str] = None,
    role: Optional[Role] = None,
) -> User:
    """Admin cập nhật thông tin nhân viên."""
    staff = get_staff_detail(db, staff_id)

    if full_name and full_name.strip():
        staff.full_name = full_name.strip()
    if phone and phone.strip():
        staff.phone = phone.strip()
    if role:
        staff.role = role
    if password and password.strip():
        staff.password_hash = hash_password(password.strip())

    db.commit()
    db.refresh(staff)
    return staff


def update_staff_status(db: Session, staff_id: int, new_status: Any) -> User:
    """Admin khóa hoặc mở khóa tài khoản nhân viên."""
    staff = get_staff_detail(db, staff_id)

    st_val = getattr(new_status, "value", str(new_status)).strip().upper()
    if st_val in ("LOCKED", "LOCK"):
        staff.status = Status.LOCK
    else:
        staff.status = Status.ACTIVE

    db.commit()
    db.refresh(staff)
    return staff


def delete_staff_member(db: Session, staff_id: int) -> Dict[str, Any]:
    """Admin xóa tài khoản nhân viên."""
    staff = get_staff_detail(db, staff_id)

    # Kiểm tra ràng buộc dữ liệu (ví dụ có xử lý đơn hàng hay lịch sử)
    order_count = db.query(Order).filter(Order.user_id == staff_id).count()
    if order_count > 0:
        staff.status = Status.LOCK
        db.commit()
        return {
            "message": f"Tài khoản nhân viên {staff.full_name} đã có dữ liệu liên kết trong hệ thống. Đã chuyển sang trạng thái KHÓA (LOCKED) thay vì xóa vĩnh viễn.",
            "action": "locked",
            "id": staff_id,
        }

    db.delete(staff)
    db.commit()
    return {
        "message": f"Đã xóa thành công tài khoản nhân viên {staff.full_name} (#{staff_id}) khỏi hệ thống.",
        "action": "deleted",
        "id": staff_id,
    }
