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
from datetime import date

from app.db.session import get_db
from app.dependencies import require_customer
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas import (
    MyOrdersPaginationResponse,
    OrderDetailResponse,
    CancelOrderRequest,
    UpdateOrderStatusRequest,
    OrderStatusHistoryResponse,
)
from app.schemas.order import OrderCreate, OrderResponse

from app.service import order_status_histories as crud_order_histories
from app.service import order as order_service

router = APIRouter(prefix="/orders", tags=["Orders"])

VALID_TRANSITIONS = {
    "PENDING": ["CONFIRMED"],
    "CONFIRMED": ["SHIPPING"],
    "SHIPPING": ["COMPLETED"],
}

class OrderStatusFilter(str, Enum):
    """Bộ lọc trạng thái đơn hàng phục vụ API tìm kiếm/phân loại."""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    SHIPPING = "SHIPPING"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo đơn hàng từ giỏ hàng trong Transaction (FR-022, FR-023, FR-035)",
    description=(
        "Khách hàng xác nhận thông tin giao hàng và tạo đơn hàng chính thức từ giỏ hàng.\n"
        "- **Quy trình Transaction nguyên tử**:\n"
        "  1. Kiểm tra giỏ hàng: Giỏ không được rỗng, không chứa sản phẩm bị ẩn.\n"
        "  2. Tính toán tiền hàng ở server: Tạm tính, phí ship (miễn phí từ 500k), tổng thanh toán.\n"
        "  3. Trừ tồn kho thông qua module Kho (`decrease_stock` với SELECT FOR UPDATE chống race condition).\n"
        "  4. Tạo đơn hàng và chi tiết đơn hàng (lưu snapshot giá và tên lúc đặt).\n"
        "  5. Ghi nhận lịch sử trạng thái ban đầu (`PENDING`).\n"
        "  6. Xóa sạch giỏ hàng.\n"
        "- **Rollback**: Bất kỳ lỗi nào (như thiếu tồn kho) sẽ hoàn tác 100% dữ liệu.\n"
        "- **Quyền hạn yêu cầu**: Khách hàng đã đăng nhập (`CUSTOMER`).\n"
        "- **Mã trạng thái**: `201 Created` kèm thông tin đơn hàng; `400 Bad Request` nếu giỏ rỗng/sản phẩm ẩn; `409 Conflict` nếu không đủ tồn kho."
    ),
)
def create_order_endpoint(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_customer),
):
    """Khách hàng tạo đơn hàng mới từ giỏ hàng (FR-022, FR-023, FR-035)."""
    return order_service.create_order(
        db=db,
        user_id=current_user.id,
        data=data,
    )


@router.get(
    "",
    response_model=MyOrdersPaginationResponse,
    summary="Xem tất cả đơn hàng hệ thống (Dành cho Admin & Staff) (FR-024)",
    description=(
        "Lấy danh sách tất cả các đơn hàng trong toàn bộ hệ thống kèm phân trang và lọc đa tiêu chí.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`.\n"
        "- **Hỗ trợ lọc**: Theo trạng thái đơn hàng (`PENDING`, `CONFIRMED`, `SHIPPING`, `DELIVERED`, `COMPLETED`, `CANCELLED`), "
        "khoảng ngày tạo đơn (`from_date`, `to_date`), hoặc tìm kiếm từ khóa mã đơn / SĐT người nhận (`keyword`).\n"
        "- **Mã lỗi**: `401 Unauthorized` nếu chưa đăng nhập; `403 Forbidden` nếu người dùng là Customer thông thường; "
        "`422 Unprocessable Entity` nếu `from_date > to_date`."
    ),
)
def read_all_orders(
    status_filter: Optional[OrderStatusFilter] = Query(
        None,
        alias="status",
        description="Lọc theo trạng thái đơn hàng (ví dụ: PENDING, SHIPPING, COMPLETED)",
    ),
    from_date: Optional[date] = Query(None, description="Từ ngày tạo đơn (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Đến ngày tạo đơn (YYYY-MM-DD)"),
    keyword: Optional[str] = Query(None, description="Tìm theo mã đơn hoặc SĐT người nhận"),
    page: int = Query(1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(10, ge=1, le=50, description="Số đơn hàng trên mỗi trang (tối đa 50)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin hoặc Staff xem danh sách tất cả đơn hàng kèm phân trang và tìm kiếm/lọc."""
    # Kiểm tra quyền: Chỉ tài khoản Admin hoặc Staff mới được xem toàn bộ đơn hàng
    user_role = str(getattr(current_user, "role", "")).upper()
    if user_role not in ["ADMIN", "STAFF"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem toàn bộ đơn hàng (chỉ dành cho Admin/Staff)",
        )

    # Kiểm tra ngày hợp lệ
    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ngày bắt đầu (from_date) không được lớn hơn ngày kết thúc (to_date)",
        )

    status_val = status_filter.value if status_filter else None
    total, orders = crud_order_histories.get_all_orders_admin(
        db=db,
        status=status_val,
        from_date=from_date,
        to_date=to_date,
        keyword=keyword,
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


@router.put(
    "/{id}/status",
    summary="Cập nhật trạng thái đơn hàng (Dành cho Admin & Staff) (FR-026)",
    description=(
        "Admin hoặc Nhân viên cập nhật trạng thái đơn hàng theo đúng luồng chuyển trạng thái hợp lệ.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`.\n"
        "- **Quy tắc luồng trạng thái**: PENDING -> CONFIRMED -> SHIPPING -> COMPLETED.\n"
        "- **Lưu ý**: Để hủy đơn hàng và hoàn kho, vui lòng dùng API `POST /orders/{id}/cancel`."
    ),
)
def update_order_status(
    id: int,
    request: UpdateOrderStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin cập nhật trạng thái đơn hàng theo đúng luồng (FR-026)."""
    user_role = str(getattr(current_user, "role", "")).upper()
    if user_role not in ["ADMIN", "STAFF"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thực hiện thao tác này",
        )
    order = crud_order_histories.get_order_by_id(db=db, order_id=id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Đơn hàng không tồn tại",
        )
    current_status = str(order.status.value if hasattr(order.status, "value") else order.status).upper()
    new_status = request.status.upper()
    # 1. Chặn nếu cố chuyển sang CANCELLED (phải dùng API cancel để hoàn kho)
    if new_status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể chuyển sang trạng thái Hủy ở đây. Vui lòng dùng chức năng Hủy đơn hàng để có lý do và hoàn kho",
        )
    # 2. Kiểm tra trạng thái hiện tại có được phép chuyển tiếp không
    allowed_next_statuses = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed_next_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chuyển trạng thái không hợp lệ! Không thể chuyển từ {current_status} sang {new_status}",
        )
    # 3. Cập nhật trạng thái
    updated_order = crud_order_histories.update_order_status_admin(
        db=db,
        order=order,
        new_status=new_status,
        user_id=current_user.id,
        note=request.note,
    )
    return {
        "message": "Cập nhật trạng thái đơn hàng thành công",
        "order_id": updated_order.id,
        "order_code": updated_order.order_code,
        "old_status": current_status,
        "new_status": str(updated_order.status.value if hasattr(updated_order.status, "value") else updated_order.status),
    }


@router.post(
    "/{id}/cancel",
    summary="Hủy đơn hàng (FR-027)",
    description=(
        "Hủy đơn hàng theo điều kiện ràng buộc.\n"
        "- **Khách hàng**: Chỉ được hủy khi đơn ở trạng thái `PENDING`.\n"
        "- **Admin/Staff**: Có thể hủy khi đơn ở trạng thái `PENDING` hoặc `CONFIRMED`.\n"
        "- Đơn hàng hủy sẽ tự động hoàn số lượng sản phẩm lại vào tồn kho."
    ),
)
def cancel_order_endpoint(
    id: int,
    request: CancelOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hủy đơn hàng theo điều kiện (FR-027)."""
    order = crud_order_histories.get_order_by_id(db=db, order_id=id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Đơn hàng không tồn tại",
        )
    # Lấy role của người dùng hiện tại (chuyển về dạng string in hoa)
    user_role = str(getattr(current_user, "role", "")).upper()
    current_status = str(order.status.value if hasattr(order.status, "value") else order.status).upper()
    # 1. Chặn nếu đơn đã ở trạng thái kết thúc hoặc đang giao
    if current_status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Đơn hàng này đã được hủy trước đó",
        )
    if current_status in ["SHIPPING", "COMPLETED"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể hủy đơn hàng đang giao hoặc đã hoàn thành",
        )
    # 2. Kiểm tra điều kiện theo từng vai trò
    if user_role not in ["ADMIN", "STAFF"]:
        # Khách hàng chỉ được hủy đơn của chính mình
        if order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền hủy đơn hàng này",
            )
        # Khách chỉ được hủy khi đơn còn PENDING
        if current_status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Khách hàng chỉ được hủy đơn khi đơn ở trạng thái Chờ xác nhận (PENDING)",
            )
    else:
        # Admin / Staff được hủy khi đơn ở PENDING hoặc CONFIRMED
        if current_status not in ["PENDING", "CONFIRMED"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ có thể hủy đơn hàng trước khi chuyển sang giao hàng",
            )
    # 3. Thực hiện hủy đơn và hoàn kho
    cancelled_order = crud_order_histories.cancel_order(
        db=db,
        order=order,
        user_id=current_user.id,
        cancel_reason=request.cancel_reason,
    )
    return {
        "message": "Hủy đơn hàng thành công",
        "order_id": cancelled_order.id,
        "order_code": cancelled_order.order_code,
        "status": str(cancelled_order.status.value if hasattr(cancelled_order.status, "value") else cancelled_order.status),
        "cancel_reason": cancelled_order.cancel_reason,
    }


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
