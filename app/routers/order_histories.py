"""Router quản lý đơn hàng và lịch sử trạng thái đơn hàng (Order & Order Histories).

Tài liệu đặc tả liên quan:
- FR-025: Xem chi tiết đơn hàng (Sản phẩm, tổng tiền, lịch sử chuyển trạng thái).
- FR-028: Khách hàng xem lịch sử các đơn hàng của mình kèm trạng thái hiện tại.
- Phân quyền:
  + Customer: Chỉ xem danh sách và chi tiết các đơn hàng do chính mình đặt.
  + Admin & Staff: Có quyền xem toàn bộ danh sách đơn hàng của hệ thống và lịch sử chi tiết.
"""
from typing import Optional, List
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas import (
    MyOrdersPaginationResponse,
    OrderDetailResponse,
    OrderStatusHistoryResponse,
)
from app.service import order_status_histories as crud_order_histories

router = APIRouter(prefix="/orders", tags=["Order Histories"])


class OrderStatusFilter(str, Enum):
    """Bộ lọc trạng thái đơn hàng phục vụ API tìm kiếm/phân loại."""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    SHIPPING = "SHIPPING"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@router.get(
    "",
    response_model=MyOrdersPaginationResponse,
    summary="Xem tất cả đơn hàng hệ thống (Dành cho Admin & Staff)",
    description=(
        "Lấy danh sách tất cả các đơn hàng trong toàn bộ hệ thống kèm phân trang và lọc theo trạng thái.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`.\n"
        "- **Hỗ trợ lọc**: Theo trạng thái đơn hàng (`PENDING`, `CONFIRMED`, `SHIPPING`, `DELIVERED`, `COMPLETED`, `CANCELLED`).\n"
        "- **Mã lỗi**: `401 Unauthorized` nếu chưa đăng nhập; `403 Forbidden` nếu người dùng là Customer thông thường."
    ),
)
def read_all_orders(
    status_filter: Optional[OrderStatusFilter] = Query(
        None,
        alias="status",
        description="Lọc theo trạng thái đơn hàng (ví dụ: PENDING, SHIPPING, COMPLETED)",
    ),
    page: int = Query(1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(10, ge=1, le=50, description="Số đơn hàng trên mỗi trang (tối đa 50)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin hoặc Staff xem danh sách tất cả đơn hàng kèm phân trang."""
    # Kiểm tra quyền: Chỉ tài khoản Admin hoặc Staff mới được xem toàn bộ đơn hàng
    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role not in ("ADMIN", "STAFF"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem toàn bộ đơn hàng (chỉ dành cho Admin/Staff)",
        )

    status_val = status_filter.value if status_filter else None
    total, orders = crud_order_histories.get_all_orders(
        db=db,
        status=status_val,
        page=page,
        page_size=page_size,
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": orders,
    }


@router.get(
    "/my",
    response_model=MyOrdersPaginationResponse,
    summary="Khách hàng xem danh sách đơn hàng của mình (FR-028)",
    description=(
        "Khách hàng lấy danh sách các đơn hàng đã đặt của chính mình, sắp xếp theo thời gian tạo mới nhất.\n"
        "- **Quyền hạn yêu cầu**: Khách hàng đã đăng nhập (`Customer`, `Staff`, hoặc `Admin`).\n"
        "- **Hỗ trợ lọc**: Theo trạng thái đơn hàng và phân trang (`page`, `page_size`).\n"
        "- **Mã lỗi**: `401 Unauthorized` nếu chưa đăng nhập hoặc token hết hạn."
    ),
)
def read_my_orders(
    status_filter: Optional[OrderStatusFilter] = Query(
        None,
        alias="status",
        description="Lọc danh sách theo trạng thái đơn hàng",
    ),
    page: int = Query(1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(10, ge=1, le=50, description="Số đơn hàng hiển thị mỗi trang (tối đa 50)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Khách hàng xem lịch sử đơn hàng của chính mình (FR-028)."""
    status_val = status_filter.value if status_filter else None

    total, orders = crud_order_histories.get_orders_by_user(
        db=db,
        user_id=current_user.id,
        status=status_val,
        page=page,
        page_size=page_size,
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": orders,
    }


@router.get(
    "/{id}",
    response_model=OrderDetailResponse,
    summary="Xem chi tiết đơn hàng (FR-025)",
    description=(
        "Xem thông tin chi tiết một đơn hàng cụ thể, bao gồm thông tin người nhận, danh sách sản phẩm, thanh toán và toàn bộ lịch sử trạng thái giao hàng.\n"
        "- **Quyền hạn yêu cầu**: Khách hàng sở hữu đơn hàng đó HOẶC người dùng có quyền `ADMIN`/`STAFF`.\n"
        "- **Mã lỗi**:\n"
        "  + `404 Not Found`: Không tìm thấy đơn hàng với ID cung cấp.\n"
        "  + `403 Forbidden`: Khách hàng cố tình xem đơn hàng của người khác."
    ),
)
def read_order_detail(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xem chi tiết đơn hàng kèm danh sách sản phẩm và lịch sử trạng thái (FR-025)."""
    order = crud_order_histories.get_order_by_id(db=db, order_id=id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Đơn hàng không tồn tại",
        )

    # Chặn khách thường xem đơn của người khác; Admin và Staff có quyền xem
    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if order.user_id != current_user.id and user_role not in ("ADMIN", "STAFF"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem đơn hàng này",
        )

    items = crud_order_histories.get_order_items(db=db, order_id=id)
    histories = crud_order_histories.get_order_histories(db=db, order_id=id)

    return OrderDetailResponse(
        id=order.id,
        order_code=order.order_code,
        receiver_name=order.receiver_name,
        receiver_phone=order.receiver_phone,
        shipping_address=order.shipping_address,
        note=order.note,
        payment_method=str(order.payment_method.value if hasattr(order.payment_method, "value") else order.payment_method),
        total_amount=order.total_amount,
        status=str(order.status.value if hasattr(order.status, "value") else order.status),
        cancel_reason=order.cancel_reason,
        created_at=order.created_at,
        items=items,
        histories=histories,
    )


@router.get(
    "/{id}/histories",
    response_model=List[OrderStatusHistoryResponse],
    summary="Xem lịch sử chuyển đổi trạng thái đơn hàng (FR-025, FR-028)",
    description=(
        "Lấy toàn bộ dòng thời gian (timeline) thay đổi trạng thái của đơn hàng (VD: Chờ xác nhận -> Đã xác nhận -> Đang giao -> Hoàn thành).\n"
        "- **Quyền hạn yêu cầu**: Chủ sở hữu đơn hàng hoặc người dùng có role `ADMIN`/`STAFF`.\n"
        "- **Mã lỗi**: `404 Not Found` nếu đơn không tồn tại; `403 Forbidden` nếu không có quyền truy cập."
    ),
)
def read_order_status_histories(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách các mốc thay đổi trạng thái của đơn hàng."""
    order = crud_order_histories.get_order_by_id(db=db, order_id=id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Đơn hàng không tồn tại",
        )

    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if order.user_id != current_user.id and user_role not in ("ADMIN", "STAFF"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem lịch sử của đơn hàng này",
        )

    return crud_order_histories.get_order_histories(db=db, order_id=id)
