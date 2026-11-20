"""Router quản lý khách hàng dành cho Admin & Nhân viên (Customer Management Router).

Tài liệu đặc tả và tính năng:
- Xem danh sách khách hàng phân trang, hỗ trợ tìm kiếm đa năng theo họ tên, email hoặc số điện thoại.
- Thống kê tự động trên từng khách hàng: Tổng số đơn hàng (`total_orders`) và tổng chi tiêu thực tế (`total_spent`).
- Xem thông tin chi tiết khách hàng: Hồ sơ, danh sách sổ địa chỉ, phân tích đơn hoàn thành / đơn hủy, danh sách đơn hàng gần đây.
- Lịch sử mua hàng của khách hàng: Phân trang chi tiết các đơn hàng của khách, hỗ trợ lọc theo trạng thái đơn hàng.
- Khóa / Kích hoạt tài khoản khách hàng (chuyển đổi trạng thái ACTIVE / LOCKED).
- Phân quyền: Toàn bộ API trong module này yêu cầu quyền Quản trị viên (ADMIN) hoặc Nhân viên (STAFF).
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, Status, Role
from app.dependencies.auth import require_admin, require_admin_or_staff
from app.schemas.customer import (
    CustomerPaginationResponse,
    CustomerDetailResponse,
    CustomerOrdersPaginationResponse,
)
from app.schemas.user import UserStatusUpdate, UserResponse, StaffCreate, StaffUpdate
from app.service import customer as customer_service
from app.service.auth import create_user

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get(
    "",
    response_model=CustomerPaginationResponse,
    summary="Danh sách khách hàng phân trang & tìm kiếm",
    description=(
        "Lấy danh sách khách hàng trong hệ thống kèm phân trang và tính toán thống kê tổng số đơn hàng, tổng chi tiêu.\n"
        "- **Tìm kiếm đa năng (`keyword`)**: Tìm kiếm theo họ tên (`full_name`), email (`email`), hoặc số điện thoại (`phone`).\n"
        "- **Bộ lọc trạng thái (`status`)**: Lọc theo trạng thái tài khoản (`ACTIVE`, `LOCKED`).\n"
        "- **Thống kê kèm theo**:\n"
        "  + `total_orders`: Tổng số đơn hàng mà khách đã tạo.\n"
        "  + `total_spent`: Tổng số tiền khách hàng đã thanh toán (không tính các đơn bị hủy).\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`.\n"
        "- **Mã lỗi**: `401 Unauthorized` nếu chưa đăng nhập; `403 Forbidden` nếu người dùng là Customer thông thường."
    ),
)
def get_customers(
    keyword: Optional[str] = Query(None, description="Tìm kiếm theo họ tên, email hoặc số điện thoại khách hàng"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái tài khoản: ACTIVE hoặc LOCKED"),
    role: Optional[str] = Query("CUSTOMER", description="Lọc theo vai trò người dùng (mặc định: CUSTOMER, hoặc ALL)"),
    exclude_self: bool = Query(False, description="Loại trừ tài khoản đang đăng nhập khỏi danh sách"),
    page: int = Query(1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Số khách hàng hiển thị mỗi trang (tối đa 100)"),
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Admin hoặc Staff xem danh sách khách hàng kèm phân trang và tìm kiếm."""
    total, items = customer_service.get_customers_list(
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


@router.get(
    "/{id}",
    response_model=CustomerDetailResponse,
    summary="Xem thông tin chi tiết khách hàng",
    description=(
        "Xem toàn bộ hồ sơ chi tiết của một khách hàng cụ thể theo ID.\n"
        "- **Dữ liệu trả về**:\n"
        "  + Thông tin cá nhân: ID, họ tên, email, số điện thoại, avatar, trạng thái, ngày tạo tài khoản.\n"
        "  + Sổ địa chỉ nhận hàng (`addresses`): Danh sách tất cả địa chỉ của khách.\n"
        "  + Báo cáo thống kê đơn hàng: `total_orders` (tổng số đơn), `total_spent` (tổng chi tiêu), "
        "`completed_orders` (số đơn hoàn thành), `cancelled_orders` (số đơn đã hủy).\n"
        "  + `recent_orders`: Danh sách 5 đơn hàng gần nhất của khách hàng.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`.\n"
        "- **Mã lỗi**: `404 Not Found` nếu không tìm thấy ID khách hàng."
    ),
)
def get_customer_detail(
    id: int,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Admin hoặc Staff xem chi tiết thông tin hồ sơ và thống kê mua sắm của khách hàng."""
    return customer_service.get_customer_detail(db=db, customer_id=id)


@router.get(
    "/{id}/orders",
    response_model=CustomerOrdersPaginationResponse,
    summary="Lịch sử mua hàng của khách hàng kèm phân trang",
    description=(
        "Xem toàn bộ lịch sử các đơn hàng do khách hàng này đặt kèm phân trang và lọc theo trạng thái.\n"
        "- **Hỗ trợ lọc trạng thái (`status`)**: Lọc theo trạng thái đơn hàng (`PENDING`, `CONFIRMED`, `SHIPPING`, `COMPLETED`, `CANCELLED`).\n"
        "- **Chi tiết mỗi đơn**: Mã đơn hàng, ngày đặt, trạng thái hiện tại, địa chỉ giao hàng, phương thức thanh toán, tổng tiền và danh sách sản phẩm.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`.\n"
        "- **Mã lỗi**: `404 Not Found` nếu không tìm thấy khách hàng."
    ),
)
def get_customer_order_history(
    id: int,
    status: Optional[str] = Query(None, description="Lọc theo trạng thái đơn hàng (ví dụ: COMPLETED, CANCELLED, PENDING)"),
    page: int = Query(1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Số đơn hàng mỗi trang"),
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Admin hoặc Staff xem lịch sử mua hàng của khách hàng theo ID."""
    total, items = customer_service.get_customer_orders(
        db=db,
        customer_id=id,
        status_filter=status,
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
    "/staff",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin tạo tài khoản nhân viên mới (STAFF)",
    description=(
        "Chỉ Quản trị viên (ADMIN) mới có quyền tạo tài khoản nhân viên nội bộ.\n"
        "- **Dữ liệu đầu vào**: Họ tên, email, số điện thoại, mật khẩu.\n"
        "- Tài khoản tạo xong sẽ có vai trò `STAFF` và trạng thái `ACTIVE`.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN`.\n"
        "- **Mã lỗi**: `403 Forbidden` nếu không phải ADMIN; `409 Conflict` nếu email đã tồn tại."
    ),
)
def create_staff_account(
    payload: StaffCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin tạo tài khoản nhân viên mới."""
    new_staff = create_user(db, payload)
    if new_staff in ("EXISTED_EMAIL", "EMAIL_ALREADY_EXISTS"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được sử dụng trong hệ thống",
        )
    return new_staff


@router.put(
    "/staff/{id}",
    response_model=UserResponse,
    summary="Admin cập nhật thông tin nhân viên",
    description="Cập nhật họ tên, số điện thoại, vai trò hoặc đổi mật khẩu cho nhân viên.",
)
def update_staff_account(
    id: int,
    payload: StaffUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin cập nhật thông tin tài khoản nhân viên."""
    return customer_service.update_staff_member(
        db=db,
        staff_id=id,
        full_name=payload.full_name,
        phone=payload.phone,
        password=payload.password,
        role=payload.role,
    )


@router.delete(
    "/{id}",
    summary="Admin xóa tài khoản người dùng hoặc nhân viên",
    description=(
        "Chỉ Quản trị viên (ADMIN) mới có quyền xóa tài khoản.\n"
        "- Nếu người dùng đã có đơn hàng trong hệ thống, chuyển sang trạng thái LOCKED để bảo toàn dữ liệu.\n"
        "- Nếu chưa có đơn hàng, xóa vĩnh viễn khỏi hệ thống."
    ),
)
def delete_user_account(
    id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin xóa tài khoản người dùng hoặc nhân viên."""
    if current_user.id == id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự xóa tài khoản của chính bạn đang đăng nhập",
        )
    return customer_service.delete_user(db=db, user_id=id)


@router.patch(
    "/{id}/status",
    response_model=UserResponse,
    summary="Khóa hoặc mở khóa tài khoản người dùng",
    description=(
        "Cập nhật trạng thái tài khoản thành `ACTIVE` (hoạt động) hoặc `LOCKED` (khóa).\n"
        "- Khi tài khoản bị khóa (`LOCKED`), người dùng sẽ không thể đăng nhập vào hệ thống.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`.\n"
        "- **Mã lỗi**: `400 Bad Request` nếu tự khóa chính mình; `404 Not Found` nếu không tìm thấy người dùng."
    ),
)
def update_customer_status(
    id: int,
    payload: UserStatusUpdate,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Admin hoặc Staff khóa hoặc mở khóa tài khoản người dùng."""
    st_val = str(payload.status).strip().upper()
    if current_user.id == id and st_val in ("LOCKED", "LOCK"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự khóa tài khoản của chính bạn đang đăng nhập",
        )
    return customer_service.update_customer_status(
        db=db,
        customer_id=id,
        new_status=payload.status,
    )
