from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.product import Product


def get_or_create_cart(db: Session, user_id: int) -> Cart:
    """Lấy giỏ hàng của user hoặc tạo mới nếu chưa có (BR-20: mỗi user 1 giỏ)."""
    cart = db.scalar(
        select(Cart)
        .options(selectinload(Cart.cart_items).joinedload(CartItem.product))
        .where(Cart.user_id == user_id)
    )
    if cart is None:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def get_cart_by_user(db: Session, user_id: int) -> Cart:
    """Lấy toàn bộ thông tin giỏ hàng của user (FR-021)."""
    return get_or_create_cart(db, user_id)


def add_item_to_cart(db: Session, user_id: int, product_id: int, quantity: int = 1) -> CartItem:
    """
    Thêm sản phẩm vào giỏ hàng (FR-018):
    - Kiểm tra số lượng hợp lệ (>= 1).
    - Chặn sản phẩm đã ẩn (is_visible=False) hoặc hết hàng.
    - Thêm trùng thì cộng dồn số lượng.
    - Số lượng cộng dồn không vượt quá tồn kho.
    - Chỉ thao tác trên giỏ của chính user.
    """
    if quantity < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số lượng sản phẩm thêm vào giỏ phải lớn hơn hoặc bằng 1.",
        )

    # 1. Kiểm tra sản phẩm tồn tại
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm với ID {product_id} không tồn tại.",
        )

    # 2. Chặn sản phẩm đã ẩn (BR-12, FR-018 E3)
    if not product.is_visible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sản phẩm đã bị ẩn hoặc ngừng kinh doanh, không thể thêm vào giỏ.",
        )

    # 3. Kiểm tra còn hàng hay không
    if product.stock_quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sản phẩm hiện đã hết hàng.",
        )

    # 4. Lấy giỏ hàng của chính user
    cart = get_or_create_cart(db, user_id)

    # 5. Kiểm tra sản phẩm đã có trong giỏ chưa
    cart_item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
    )

    current_qty = cart_item.quantity if cart_item else 0
    new_total_qty = current_qty + quantity

    # 6. Kiểm tra không vượt tồn kho (BR-04, FR-035)
    if new_total_qty > product.stock_quantity:
        max_can_add = max(0, product.stock_quantity - current_qty)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Số lượng yêu cầu vượt quá tồn kho. "
                f"Tồn kho còn {product.stock_quantity}, trong giỏ đã có {current_qty}, "
                f"chỉ có thể thêm tối đa {max_can_add} sản phẩm."
            ),
        )

    # 7. Thêm mới hoặc cộng dồn
    if cart_item:
        cart_item.quantity = new_total_qty
    else:
        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product.id,
            quantity=quantity,
            price_at_add=product.price,
        )
        db.add(cart_item)

    db.commit()
    db.refresh(cart_item)
    return cart_item


def update_cart_item_quantity(db: Session, user_id: int, product_id: int, quantity: int) -> CartItem:
    """
    Cập nhật số lượng sản phẩm trong giỏ hàng (FR-019):
    - Kiểm tra số lượng hợp lệ (>= 1).
    - Kiểm tra sản phẩm có trong giỏ của user không.
    - Chặn sản phẩm đã bị ẩn.
    - Không cho phép số lượng vượt quá tồn kho hiện tại.
    """
    if quantity < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số lượng sản phẩm trong giỏ phải lớn hơn hoặc bằng 1.",
        )

    cart = get_or_create_cart(db, user_id)

    cart_item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
    )
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sản phẩm không có trong giỏ hàng của bạn.",
        )

    product = cart_item.product
    if product is None or not product.is_visible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sản phẩm đã bị ẩn hoặc không còn tồn tại.",
        )

    if quantity > product.stock_quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Số lượng yêu cầu ({quantity}) vượt quá tồn kho hiện có ({product.stock_quantity}). "
                f"Vui lòng điều chỉnh lại."
            ),
        )

    cart_item.quantity = quantity
    db.commit()
    db.refresh(cart_item)
    return cart_item


def delete_cart_item(db: Session, user_id: int, product_id: int) -> None:
    """
    Xóa sản phẩm khỏi giỏ hàng (FR-020):
    - Kiểm tra sản phẩm có trong giỏ của user không.
    - Xóa dòng cart_item tương ứng.
    """
    cart = get_or_create_cart(db, user_id)

    cart_item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
    )
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sản phẩm không có trong giỏ hàng của bạn.",
        )

    db.delete(cart_item)
    db.commit()
