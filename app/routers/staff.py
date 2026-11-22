"""Router quản lý nhân viên nội bộ dành riêng cho Quản trị viên (Staff Management Router).

Đặc tả nghiệp vụ:
- Danh sách nhân viên nội bộ (ADMIN, STAFF) phân trang, tìm kiếm đa năng theo họ tên, email, SĐT.
- Tạo mới tài khoản nhân viên nội bộ (chỉ Quản trị viên).
- Xem chi tiết thông tin hồ sơ nhân viên.
- Chỉnh sửa thông tin nhân viên, đổi mật khẩu, phân quyền vai trò.
- Khóa / Mở khóa tài khoản nhân viên (chống tự khóa chính mình).
- Xóa tài khoản nhân viên (chống tự xóa chính mình).
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, Status, Role
from app.dependencies.auth import require_admin, require_admin_or_staff
from app.schemas.user import UserResponse
from app.schemas.staff import (
    StaffCreate,
    StaffUpdate,
    StaffStatusUpdate,
    StaffPaginationResponse,
)
from app.service import staff as staff_service

router = APIRouter(prefix="/staff", tags=["Staff"])


@router.get(
    "",
    response_model=StaffPaginationResponse,
    summary="Danh sách nhân viên & quản trị viên phân trang",
    description=(
        "Lấy danh sách nhân viên nội bộ (`STAFF` và `ADMIN`) kèm phân trang, tìm kiếm và bộ lọc trạng thái.\n"
        "- **Tìm kiếm (`keyword`)**: Tìm kiếm theo họ tên, email hoặc số điện thoại.\n"
        "- **Bộ lọc vai trò (`role`)**: `STAFF`, `ADMIN`, hoặc để trống để lấy tất cả nhân sự.\n"
        "- **Bộ lọc trạng thái (`status`)**: `ACTIVE` hoặc `LOCKED`.\n"
        "- **Loại trừ chính mình (`exclude_self`)**: Bỏ qua tài khoản đang đăng nhập khỏi danh sách.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`."
    ),
)
def get_staff_members(
    keyword: Optional[str] = Query(None, description="Tìm kiếm theo họ tên, email hoặc số điện thoại"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: ACTIVE hoặc LOCKED"),
    role: Optional[str] = Query(None, description="Lọc theo vai trò: STAFF hoặc ADMIN"),
    exclude_self: bool = Query(False, description="Loại trừ tài khoản đang đăng nhập"),
    page: int = Query(1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Số nhân viên hiển thị mỗi trang"),
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Admin hoặc Staff xem danh sách nhân sự nội bộ."""
    total, items = staff_service.get_staff_list(
        db=db,
        keyword=keyword,
        status_filter=status,
        role_filter=role,
        exclude_user_id=current_user.id if exclude_self else None,
        page=page,
        page_size=page_size,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin tạo tài khoản nhân viên mới (STAFF)",
    description=(
        "Chỉ Quản trị viên (ADMIN) mới có quyền tạo tài khoản nhân viên nội bộ.\n"
        "- **Dữ liệu đầu vào**: Họ tên, email, số điện thoại, mật khẩu khởi tạo, vai trò (`STAFF`/`ADMIN`).\n"
        "- Tài khoản được tạo tự động kích hoạt trạng thái `ACTIVE`.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN`.\n"
        "- **Mã lỗi**: `403 Forbidden` nếu không phải Admin; `409 Conflict` nếu email đã tồn tại."
    ),
)
def create_staff(
    payload: StaffCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin tạo tài khoản nhân viên mới."""
    return staff_service.create_staff_member(db=db, payload=payload)


@router.get(
    "/{id}",
    response_model=UserResponse,
    summary="Xem chi tiết tài khoản nhân viên",
    description="Xem thông tin chi tiết hồ sơ của một nhân viên hoặc quản trị viên theo ID.",
)
def get_staff_detail(
    id: int,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Admin hoặc Staff xem thông tin chi tiết nhân viên theo ID."""
    return staff_service.get_staff_detail(db=db, staff_id=id)


@router.put(
    "/{id}",
    response_model=UserResponse,
    summary="Admin cập nhật thông tin nhân viên",
    description="Admin chỉnh sửa họ tên, số điện thoại, phân quyền vai trò (STAFF/ADMIN) hoặc đổi mật khẩu.",
)
def update_staff(
    id: int,
    payload: StaffUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin cập nhật thông tin tài khoản nhân viên."""
    return staff_service.update_staff_member(
        db=db,
        staff_id=id,
        full_name=payload.full_name,
        phone=payload.phone,
        password=payload.password,
        role=payload.role,
    )


@router.patch(
    "/{id}/status",
    response_model=UserResponse,
    summary="Khóa hoặc mở khóa tài khoản nhân viên",
    description=(
        "Chuyển đổi trạng thái tài khoản nhân viên giữa `ACTIVE` (hoạt động) và `LOCKED` (khóa).\n"
        "- Tài khoản bị khóa sẽ không thể đăng nhập vào hệ thống.\n"
        "- Hệ thống tự động ngăn chặn Admin tự khóa tài khoản của chính mình."
    ),
)
def update_staff_status(
    id: int,
    payload: StaffStatusUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin khóa hoặc mở khóa tài khoản nhân viên."""
    st_val = str(payload.status).strip().upper()
    if current_user.id == id and st_val in ("LOCKED", "LOCK"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự khóa tài khoản quản trị của chính bạn đang đăng nhập",
        )
    return staff_service.update_staff_status(
        db=db,
        staff_id=id,
        new_status=payload.status,
    )


@router.delete(
    "/{id}",
    summary="Admin xóa tài khoản nhân viên",
    description=(
        "Chỉ Quản trị viên (ADMIN) mới có quyền xóa tài khoản nhân viên.\n"
        "- Tự động ngăn chặn Admin tự xóa tài khoản của chính mình.\n"
        "- Nếu nhân viên đã có dữ liệu liên kết, hệ thống chuyển sang `LOCKED` để bảo tồn dữ liệu kiểm toán."
    ),
)
def delete_staff(
    id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin xóa tài khoản nhân viên."""
    if current_user.id == id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự xóa tài khoản quản trị của chính bạn đang đăng nhập",
        )
    return staff_service.delete_staff_member(db=db, staff_id=id)
