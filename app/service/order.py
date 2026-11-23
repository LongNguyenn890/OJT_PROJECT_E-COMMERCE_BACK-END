"""Tầng xử lý nghiệp vụ Đơn hàng và Tạo đơn trong Transaction (Order Service).

Tài liệu đặc tả liên quan:
- FR-022: Xác nhận thông tin giao hàng (Người nhận, SĐT 10 chữ số bắt đầu bằng 0, Địa chỉ nhận hàng).
- FR-023: Tạo đơn hàng (Chuyển đổi giỏ hàng sang đơn hàng, trừ kho, xóa sạch giỏ trong 1 transaction).
- FR-035: Kiểm tra tồn kho trước khi đặt hàng (Trừ kho nguyên tử qua decrease_stock, chống race condition).
- BR-06: Đơn giá và tên sản phẩm được lưu bản sao tại thời điểm đặt (không bị ảnh hưởng khi giá thay đổi sau này).
- BR-07: Tổng tiền đơn hàng = Tạm tính + Phí vận chuyển (Miễn phí vận chuyển từ 500.000đ, dưới 500.000đ là 30.000đ).
- BR-10: Kiểm tra và trừ tồn kho nguyên tử, lỗi giữa chừng phải rollback hoàn toàn.
- BR-20: Giỏ hàng bị xóa sạch sau khi tạo đơn hàng thành công.
"""
from __future__ import annotations

import secrets
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.order import Order, OrderStatus, PaymentMethod
from app.models.order_item import OrderItem
from app.models.order_status_histories import (
    OrderStatusHistory,
    OrderStatus as HistoryOrderStatus,
)
from app.schemas.order import OrderCreate
from app.service.inventory import decrease_stock


def generate_order_code(db: Session) -> str:
    """Sinh mã đơn hàng duy nhất và dễ đọc (ví dụ: DH-20261115-A1B2C3)."""
    today_str = datetime.now().strftime("%Y%m%d")
    while True:
        suffix = secrets.token_hex(3).upper()  # 6 ký tự ngẫu nhiên
        code = f"DH-{today_str}-{suffix}"
        existing = db.scalar(select(Order.id).where(Order.order_code == code))
        if not existing:
            return code


def create_order(
    db: Session,
    user_id: int,
    data: OrderCreate,
) -> Order:
    """Tạo đơn hàng từ giỏ hàng của khách hàng trong một TRANSACTION NGUYÊN TỬ (FR-022, FR-023, FR-035).

    Quy trình xử lý:
    1. Kiểm tra giỏ hàng: Giỏ không được rỗng, không chứa sản phẩm bị ẩn.
    2. Tính toán tiền hàng ở server: Tạm tính, phí ship (miễn phí từ 500k), tổng thanh toán.
    3. Mở Transaction:
       - Sinh mã đơn hàng duy nhất.
       - Lưu bản ghi Order.
       - Trừ kho bằng hàm `decrease_stock` của module Kho (SELECT FOR UPDATE chống race condition).
       - Lưu từng bản ghi OrderItem (bản sao tên và đơn giá tại thời điểm đặt - BR-06).
       - Ghi lịch sử trạng thái ban đầu OrderStatusHistory (PENDING).
       - Xóa sạch giỏ hàng của khách hàng (BR-20).
       - Commit toàn bộ thay đổi.
    4. Rollback toàn bộ nếu có bất kỳ lỗi nào giữa chừng (NFR-019).
    """
    # 1. Lấy thông tin giỏ hàng của user
    cart = db.scalar(
        select(Cart)
        .options(
            selectinload(Cart.cart_items).joinedload(CartItem.product)
        )
        .where(Cart.user_id == user_id)
    )

    if not cart or not cart.cart_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giỏ hàng của bạn đang trống, không thể tiến hành đặt hàng.",
        )

    # 1.1 Lọc danh sách mặt hàng được khách hàng tích chọn mua
    if data.selected_product_ids:
        selected_ids_set = set(data.selected_product_ids)
        items_to_order = [it for it in cart.cart_items if it.product_id in selected_ids_set]
    else:
        items_to_order = list(cart.cart_items)

    if not items_to_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn ít nhất một sản phẩm trong giỏ hàng để tiến hành đặt hàng.",
        )

    # 2. Kiểm tra tính hợp lệ của từng sản phẩm được chọn đặt
    for item in items_to_order:
        if not item.product or not bool(item.product.is_visible):
            product_name = item.product.name if item.product else f"ID {item.product_id}"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sản phẩm '{product_name}' đã bị ẩn hoặc ngừng kinh doanh. Vui lòng xóa khỏi giỏ trước khi đặt hàng.",
            )

    # 3. Tính toán tiền hàng ở server chỉ trên các sản phẩm được tích chọn
    def get_effective_price(p):
        if p and p.promotional_price is not None and p.promotional_price >= 0 and (p.price is None or p.promotional_price < p.price):
            return int(p.promotional_price)
        return int(p.price) if p and p.price is not None else 0

    subtotal_amount = sum(
        get_effective_price(item.product) * item.quantity for item in items_to_order
    )
    # Phí ship: Miễn phí từ 500.000đ, dưới 500.000đ là 30.000đ
    shipping_fee = 0 if subtotal_amount >= 500_000 else 30_000

    # 3.1 Xử lý Voucher giảm giá nếu khách áp dụng mã (Chỉ áp dụng voucher do User đổi điểm sở hữu)
    discount_amount = 0
    voucher_applied_code = None
    applied_voucher_obj = None
    if getattr(data, "voucher_code", None):
        vcode = str(data.voucher_code).strip().upper()
        # Kiểm tra trong kho voucher của User (phải đổi bằng điểm thưởng mới có)
        from app.models.voucher import Voucher
        voucher_db = db.scalar(
            select(Voucher).where(
                Voucher.code == vcode,
                Voucher.user_id == user_id,
                Voucher.is_used == 0,
            )
        )
        if voucher_db and subtotal_amount >= int(voucher_db.min_order_value or 0):
            vtype = str(getattr(voucher_db, "voucher_type", "fixed") or "fixed").lower()
            if vtype == "freeship":
                discount_amount = min(shipping_fee, int(voucher_db.discount_amount or 30000))
            elif vtype == "percent":
                pct = int(getattr(voucher_db, "percent", 0) or 0)
                max_d = int(getattr(voucher_db, "max_discount", 0) or 0)
                pct_discount = int(subtotal_amount * pct / 100)
                if max_d > 0:
                    pct_discount = min(pct_discount, max_d)
                discount_amount = pct_discount
            else:
                discount_amount = min(subtotal_amount, int(voucher_db.discount_amount or 0))

            voucher_applied_code = vcode
            applied_voucher_obj = voucher_db

    total_amount = max(0, subtotal_amount + shipping_fee - discount_amount)

    order_note = data.note or ""
    if voucher_applied_code and discount_amount > 0:
        order_note = f"{order_note} [Voucher {voucher_applied_code}: -{discount_amount:,}đ]".strip()

    # 4. Thực hiện toàn bộ quy trình trong TRANSACTION CSDL
    try:
        # 4.1. Sinh mã đơn hàng
        order_code = generate_order_code(db)

        # 4.2. Tạo đối tượng Order
        order = Order(
            order_code=order_code,
            user_id=user_id,
            address_id=getattr(data, "address_id", None),
            receiver_name=data.receiver_name,
            receiver_phone=data.receiver_phone,
            shipping_address=data.shipping_address,
            note=order_note if order_note else None,
            payment_method=data.payment_method,
            subtotal_amount=subtotal_amount,
            shipping_fee=shipping_fee,
            total_amount=total_amount,
            status=OrderStatus.PENDING,
        )
        db.add(order)
        db.flush()  # Sinh order.id để liên kết các bảng phụ thuộc

        # Đánh dấu voucher của user đã sử dụng (nếu là voucher cá nhân)
        if applied_voucher_obj:
            applied_voucher_obj.is_used = 1

        # 4.3. Trừ tồn kho bằng hàm decrease_stock của module Kho & tạo OrderItem cho các món được chọn
        for item in items_to_order:
            item_effective_price = get_effective_price(item.product)
            # Hàm decrease_stock dùng SELECT FOR UPDATE để khóa hàng, chống 2 người mua làm âm kho
            decrease_stock(
                db=db,
                product_id=item.product_id,
                quantity=item.quantity,
                order_id=order.id,
                user_id=user_id,
                note=f"Trừ kho khi tạo đơn hàng {order_code}",
            )

            # Bản sao chi tiết mặt hàng tại thời điểm đặt hàng (BR-06)
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                product_name=item.product.name,
                unit_price=item_effective_price,
                quantity=item.quantity,
                subtotal=item_effective_price * item.quantity,
            )
            db.add(order_item)

        # 4.4. Ghi lịch sử trạng thái ban đầu vào order_status_histories
        status_history = OrderStatusHistory(
            order_id=order.id,
            changed_by=user_id,
            old_status=None,
            new_status=HistoryOrderStatus.PENDING,
            note="Khách hàng đặt hàng thành công",
        )
        db.add(status_history)

        # 4.5. Chỉ xóa các sản phẩm ĐÃ ĐẶT HÀNG khỏi giỏ (các sản phẩm chưa chọn vẫn giữ nguyên cho lần sau)
        for item in items_to_order:
            db.delete(item)

        # 4.6. Commit toàn bộ transaction
        db.commit()

        # Eager load items để trả về đầy đủ response
        created_order = db.scalar(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order.id)
        )
        return created_order

    except Exception as exc:
        db.rollback()
        # Nếu là HTTPException (ví dụ HTTP 409 từ decrease_stock do thiếu tồn kho) -> re-raise
        if isinstance(exc, HTTPException):
            raise exc
        # Lỗi hệ thống ngoài ý muốn -> ném 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xử lý giao dịch tạo đơn hàng: {str(exc)}",
        )
