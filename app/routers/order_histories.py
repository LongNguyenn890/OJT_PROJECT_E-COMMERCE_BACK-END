"""Router quản lý đơn hàng và lịch sử trạng thái đơn hàng (Order & Order Histories).

Tài liệu đặc tả liên quan:
- FR-025: Xem chi tiết đơn hàng (Sản phẩm, tổng tiền, lịch sử chuyển trạng thái).
- FR-028: Khách hàng xem lịch sử các đơn hàng của mình kèm trạng thái hiện tại.
- Phân quyền:
  + Customer: Chỉ xem danh sách và chi tiết các đơn hàng do chính mình đặt.
  + Admin & Staff: Có quyền xem toàn bộ danh sách đơn hàng của hệ thống và lịch sử chi tiết.
"""
import random
from typing import Optional, List
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.order import Order, OrderStatus, PaymentMethod
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.stock_log import StockLog
from app.models.order_status_histories import OrderStatusHistory
from app.schemas import (
    MyOrdersPaginationResponse,
    OrderDetailResponse,
    CancelOrderRequest,
    UpdateOrderStatusRequest,
    OrderStatusHistoryResponse,
)

from app.service import order_status_histories as crud_order_histories
from app.core.ws import dashboard_ws_manager

router = APIRouter(prefix="/orders", tags=["Orders"])

VALID_TRANSITIONS = {
    "PENDING": ["CONFIRMED"],
    "CONFIRMED": ["SHIPPING"],
    "SHIPPING": ["COMPLETED", "DELIVERED"],
}


def normalize_status_code(status_obj) -> str:
    """Chuẩn hóa trạng thái đơn hàng về mã code PENDING, CONFIRMED, SHIPPING, COMPLETED, CANCELLED."""
    if hasattr(status_obj, "name"):
        return status_obj.name
    val = str(status_obj.value if hasattr(status_obj, "value") else status_obj).strip()
    norm = val.lower()
    if "chờ" in norm or "pending" in norm:
        return "PENDING"
    if "xác nhận" in norm or "confirmed" in norm:
        return "CONFIRMED"
    if "giao" in norm or "shipping" in norm:
        return "SHIPPING"
    if "hoàn thành" in norm or "completed" in norm or "delivered" in norm or "đã giao" in norm:
        return "COMPLETED"
    if "hủy" in norm or "cancel" in norm:
        return "CANCELLED"
    return val.upper()

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
    page_size: int = Query(10, ge=1, le=500, description="Số đơn hàng trên mỗi trang (tối đa 500)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin hoặc Staff xem danh sách tất cả đơn hàng kèm phân trang và tìm kiếm/lọc."""
    # Kiểm tra quyền: Chỉ tài khoản Admin hoặc Staff mới được xem toàn bộ đơn hàng
    user_role = (current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)).upper()
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

    result_items = []
    for o in orders:
        items_payload = []
        for it in (o.items or []):
            prod = it.product
            primary_img = None
            category_name = None
            sku = None
            if prod:
                sku = prod.sku or f"SP-{prod.id}"
                if prod.category:
                    category_name = prod.category.name
                if prod.product_images:
                    for img in prod.product_images:
                        if img.is_primary:
                            primary_img = img.image_url
                            break
                    if not primary_img and prod.product_images:
                        primary_img = prod.product_images[0].image_url
            items_payload.append({
                "id": it.id,
                "order_id": it.order_id,
                "product_id": it.product_id,
                "product_name": it.product_name,
                "unit_price": it.unit_price,
                "quantity": it.quantity,
                "subtotal": it.subtotal,
                "image_url": primary_img,
                "category_name": category_name,
                "sku": sku,
            })
        order_dict = {
            "id": o.id,
            "order_code": o.order_code,
            "receiver_name": o.receiver_name,
            "receiver_phone": o.receiver_phone,
            "shipping_address": o.shipping_address,
            "note": o.note,
            "payment_method": str(o.payment_method.value if hasattr(o.payment_method, "value") else o.payment_method),
            "subtotal_amount": o.subtotal_amount or (o.total_amount - (o.shipping_fee or 0)),
            "shipping_fee": o.shipping_fee or 0,
            "total_amount": o.total_amount,
            "status": normalize_status_code(o.status),
            "cancel_reason": o.cancel_reason,
            "created_at": o.created_at,
            "completed_at": o.completed_at,
            "items": items_payload,
        }
        result_items.append(order_dict)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": result_items,
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
    items_payload = []
    for it in items:
        prod = it.product
        primary_img = None
        category_name = None
        sku = None
        if prod:
            sku = prod.sku or f"SP-{prod.id}"
            if prod.category:
                category_name = prod.category.name
            if prod.product_images:
                for img in prod.product_images:
                    if img.is_primary:
                        primary_img = img.image_url
                        break
                if not primary_img and prod.product_images:
                    primary_img = prod.product_images[0].image_url
        items_payload.append({
            "id": it.id,
            "order_id": it.order_id,
            "product_id": it.product_id,
            "product_name": it.product_name,
            "unit_price": it.unit_price,
            "quantity": it.quantity,
            "subtotal": it.subtotal,
            "image_url": primary_img,
            "category_name": category_name,
            "sku": sku,
        })

    histories = crud_order_histories.get_order_histories(db=db, order_id=id)
    histories_payload = []
    for h in histories:
        histories_payload.append({
            "id": h.id,
            "old_status": normalize_status_code(h.old_status) if h.old_status else None,
            "new_status": normalize_status_code(h.new_status),
            "note": h.note,
            "changed_at": h.changed_at,
        })

    return OrderDetailResponse(
        id=order.id,
        order_code=order.order_code,
        receiver_name=order.receiver_name,
        receiver_phone=order.receiver_phone,
        shipping_address=order.shipping_address,
        note=order.note,
        payment_method=str(order.payment_method.value if hasattr(order.payment_method, "value") else order.payment_method),
        subtotal_amount=order.subtotal_amount or (order.total_amount - (order.shipping_fee or 0)),
        shipping_fee=order.shipping_fee or 0,
        total_amount=order.total_amount,
        status=normalize_status_code(order.status),
        cancel_reason=order.cancel_reason,
        created_at=order.created_at,
        completed_at=order.completed_at,
        items=items_payload,
        histories=histories_payload,
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
async def update_order_status(
    id: int,
    request: UpdateOrderStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin cập nhật trạng thái đơn hàng theo đúng luồng (FR-026)."""
    user_role = (current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)).upper()
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
    current_status = normalize_status_code(order.status)
    new_status = normalize_status_code(request.status)
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
    # 4. Phát tín hiệu cập nhật thời gian thực qua WebSocket
    try:
        await dashboard_ws_manager.broadcast({
            "type": "ORDER_UPDATED",
            "order_id": updated_order.id,
            "order_code": updated_order.order_code,
            "old_status": current_status,
            "new_status": normalize_status_code(updated_order.status),
        })
    except Exception:
        pass

    return {
        "message": "Cập nhật trạng thái đơn hàng thành công",
        "order_id": updated_order.id,
        "order_code": updated_order.order_code,
        "old_status": current_status,
        "new_status": normalize_status_code(updated_order.status),
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
async def cancel_order_endpoint(
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
    user_role = (current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)).upper()
    current_status = normalize_status_code(order.status)
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
    # 4. Phát tín hiệu cập nhật thời gian thực qua WebSocket
    try:
        await dashboard_ws_manager.broadcast({
            "type": "ORDER_UPDATED",
            "order_id": cancelled_order.id,
            "order_code": cancelled_order.order_code,
            "old_status": current_status,
            "new_status": "CANCELLED",
        })
    except Exception:
        pass

    return {
        "message": "Hủy đơn hàng thành công",
        "order_id": cancelled_order.id,
        "order_code": cancelled_order.order_code,
        "status": normalize_status_code(cancelled_order.status),
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


class PosOrderItemRequest(BaseModel):
    product_id: int
    quantity: int = 1


class PosOrderCreateRequest(BaseModel):
    customer_name: Optional[str] = "Khách lẻ tại quầy"
    customer_phone: Optional[str] = "0900000000"
    payment_method: Optional[str] = "COD"
    cash_received: Optional[int] = 0
    note: Optional[str] = "Bán tại quầy (POS)"
    items: List[PosOrderItemRequest]


@router.post(
    "/pos",
    summary="Tạo đơn hàng bán tại quầy (POS) & trừ kho ngay lập tức",
    description="Nhân viên hoặc Admin tạo đơn tại quầy, khách trả tiền mặt/chuyển khoản, đơn hoàn tất ngay và tự động trừ kho sản phẩm.",
)
async def create_pos_order(
    request: PosOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Nhân viên tạo đơn tại quầy (tìm sản phẩm, nhập số lượng, khách trả tiền mặt), đơn hoàn tất ngay và trừ kho."""
    user_role = (current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)).upper()
    if user_role not in ["ADMIN", "STAFF"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Nhân viên hoặc Quản trị viên mới có quyền tạo đơn bán tại quầy",
        )

    if not request.items or len(request.items) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn hàng phải có ít nhất 1 sản phẩm",
        )

    # 1. Kiểm tra từng sản phẩm và tính tổng tiền
    items_to_process = []
    total_amount = 0

    for it in request.items:
        if it.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số lượng sản phẩm mua phải lớn hơn 0",
            )
        product = db.query(Product).filter(Product.id == it.product_id).first()
        if not product or product.is_visible == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sản phẩm ID {it.product_id} không tồn tại hoặc đã ngừng kinh doanh",
            )
        if product.stock_quantity < it.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sản phẩm '{product.name}' không đủ tồn kho (chỉ còn {product.stock_quantity} món, yêu cầu {it.quantity})",
            )

        unit_price = int(product.promotional_price) if (product.promotional_price is not None and product.promotional_price > 0) else int(product.price)
        subtotal = unit_price * it.quantity
        total_amount += subtotal

        primary_img = None
        if product.product_images:
            for img in product.product_images:
                if img.is_primary:
                    primary_img = img.image_url
                    break
            if not primary_img:
                primary_img = product.product_images[0].image_url

        items_to_process.append({
            "product": product,
            "quantity": it.quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
            "image_url": primary_img,
            "category_name": product.category.name if product.category else "Chính hãng",
            "sku": product.sku or f"SP-{product.id}",
        })

    # 2. Sinh mã đơn hàng duy nhất cho POS
    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d%H%M%S")
    rand_suffix = f"{random.randint(10, 99)}"
    order_code = f"POS{timestamp_str}{rand_suffix}"

    # 3. Tạo đơn hàng với trạng thái COMPLETED
    pm_raw = (request.payment_method or "COD").upper()
    pm_enum = PaymentMethod.BANK_TRANSFER if ("BANK" in pm_raw or "CHUYỂN" in pm_raw) else PaymentMethod.COD

    order = Order(
        order_code=order_code,
        user_id=current_user.id,
        receiver_name=(request.customer_name or "Khách lẻ tại quầy").strip(),
        receiver_phone=(request.customer_phone or "0900000000").strip(),
        shipping_address="Mua trực tiếp tại quầy ShopEase",
        note=(request.note or "Bán hàng tại quầy (POS)").strip(),
        payment_method=pm_enum,
        subtotal_amount=total_amount,
        shipping_fee=0,
        total_amount=total_amount,
        status=OrderStatus.COMPLETED,
        created_at=now,
        completed_at=now,
    )
    db.add(order)
    db.flush()

    # 4. Lưu từng OrderItem và Trừ kho sản phẩm (ghi nhận StockLog)
    response_items = []
    for p_item in items_to_process:
        prod = p_item["product"]
        qty = p_item["quantity"]

        order_item = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            product_name=prod.name,
            unit_price=p_item["unit_price"],
            quantity=qty,
            subtotal=p_item["subtotal"],
            image_url=p_item["image_url"],
            category_name=p_item["category_name"],
            sku=p_item["sku"],
        )
        db.add(order_item)

        stock_before = prod.stock_quantity
        prod.stock_quantity -= qty
        stock_after = prod.stock_quantity

        stock_log = StockLog(
            product_id=prod.id,
            order_id=order.id,
            created_by=current_user.id,
            change_type="ORDER",
            quantity_change=-qty,
            stock_before=stock_before,
            stock_after=stock_after,
            note=f"Xuất kho bán tại quầy cho đơn {order.order_code}",
            created_at=now,
        )
        db.add(stock_log)

        response_items.append({
            "product_id": prod.id,
            "product_name": prod.name,
            "sku": p_item["sku"],
            "category_name": p_item["category_name"],
            "image_url": p_item["image_url"],
            "unit_price": p_item["unit_price"],
            "quantity": qty,
            "subtotal": p_item["subtotal"],
        })

    # 5. Ghi lịch sử trạng thái đơn hàng
    pm_text = "Chuyển khoản" if pm_enum == PaymentMethod.BANK_TRANSFER else "Tiền mặt"
    history = OrderStatusHistory(
        order_id=order.id,
        changed_by=current_user.id,
        old_status=None,
        new_status="DELIVERED",
        note=f"Tạo đơn bán tại quầy - Đã thanh toán {pm_text} và hoàn thành đơn",
        changed_at=now,
    )
    db.add(history)

    db.commit()
    db.refresh(order)

    # 6. Phát tín hiệu thời gian thực WebSocket
    try:
        await dashboard_ws_manager.broadcast({
            "type": "NEW_ORDER",
            "order_id": order.id,
            "order_code": order.order_code,
            "status": "COMPLETED",
            "total_amount": total_amount,
        })
    except Exception:
        pass

    cash_received = request.cash_received or total_amount
    cash_change = max(0, cash_received - total_amount)

    return {
        "id": order.id,
        "order_code": order.order_code,
        "receiver_name": order.receiver_name,
        "receiver_phone": order.receiver_phone,
        "shipping_address": order.shipping_address,
        "payment_method": "Tiền mặt (Tại quầy)" if pm_enum == PaymentMethod.COD else "Chuyển khoản",
        "subtotal_amount": order.subtotal_amount,
        "shipping_fee": 0,
        "total_amount": order.total_amount,
        "cash_received": cash_received,
        "cash_change": cash_change,
        "status": "COMPLETED",
        "created_at": order.created_at,
        "completed_at": order.completed_at,
        "cashier_name": current_user.full_name or current_user.email,
        "items": response_items,
    }
