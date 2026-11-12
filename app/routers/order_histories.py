from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User

from app.schemas import (
    MyOrdersPaginationResponse,
    OrderDetailResponse,
)
from app.service import order_status_histories as crud_order_histories

router = APIRouter(prefix="/orders", tags=["Order Histories"])

VALID_STATUSES = ["PENDING", "CONFIRMED", "SHIPPING", "DELIVERED", "COMPLETED", "CANCELLED"]


@router.get("/my", response_model=MyOrdersPaginationResponse)
def read_my_orders(
    status_filter: Optional[str] = Query(None, alias="status", description="Lọc theo trạng thái"),
    page: int = Query(1, ge=1, description="Trang hiện tại"),
    page_size: int = Query(10, ge=1, le=50, description="Số lượng mỗi trang"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Khách hàng xem danh sách đơn hàng của mình (FR-028)."""
    if status_filter and status_filter.upper() not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Trạng thái đơn hàng không hợp lệ",
        )

    total, orders = crud_order_histories.get_orders_by_user(
        db=db,
        user_id=current_user.id,
        status=status_filter,
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
