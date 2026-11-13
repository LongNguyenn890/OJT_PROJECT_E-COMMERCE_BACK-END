from typing import Optional
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User

from app.schemas import (
    MyOrdersPaginationResponse,
    OrderDetailResponse,
)

from app.schemas import (
    MyOrdersPaginationResponse,
    OrderDetailResponse,
    CancelOrderRequest 
)

from app.service import order_status_histories as crud_order_histories

router = APIRouter(prefix="/orders", tags=["Order Histories"])

class OrderStatusFilter(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    SHIPPING = "SHIPPING"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

@router.get("/my", response_model=MyOrdersPaginationResponse)
def read_my_orders(
    status_filter: Optional[OrderStatusFilter] = Query(None, alias="status", description="Lọc theo trạng thái"),
    page: int = Query(1, ge=1, description="Trang hiện tại"),
    page_size: int = Query(10, ge=1, le=50, description="Số lượng mỗi trang"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Khách hàng xem danh sách đơn hàng của mình (FR-028)."""
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


@router.get("/{id}", response_model=OrderDetailResponse)
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

    # Chặn khách xem đơn của người khác
    if order.user_id != current_user.id and getattr(current_user, "role", "") != "ADMIN":
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

@router.post("/{id}/cancel")
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