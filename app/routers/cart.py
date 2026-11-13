from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_customer
from app.models.user import User
from app.schemas.cart import CartResponse
from app.schemas.cart_item import CartItemCreate, CartItemResponse, CartItemUpdate
from app.service import cart as cart_service

router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get("", response_model=CartResponse, summary="Xem giỏ hàng và tổng tiền (FR-021)")
def get_cart(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """
    Xem toàn bộ giỏ hàng của chính mình (FR-021):
    - Tính thành tiền từng dòng, tạm tính và tổng thanh toán.
    - Kèm các cảnh báo nếu sản phẩm đổi giá hoặc hết hàng/ẩn.
    """
    return cart_service.get_cart_by_user(db, current_user.id)


@router.post(
    "/items",
    response_model=CartItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm sản phẩm vào giỏ hàng (FR-018)",
)
def add_item_to_cart(
    data: CartItemCreate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """
    Thêm sản phẩm vào giỏ hàng (FR-018):
    - Thêm trùng thì cộng dồn số lượng.
    - Số lượng cộng dồn không vượt quá tồn kho.
    - Chặn sản phẩm đã bị ẩn hoặc hết hàng.
    - Chỉ thao tác trên giỏ hàng của chính mình.
    """
    return cart_service.add_item_to_cart(
        db=db,
        user_id=current_user.id,
        product_id=data.product_id,
        quantity=data.quantity,
    )


@router.put(
    "/items/{product_id}",
    response_model=CartItemResponse,
    summary="Cập nhật số lượng sản phẩm trong giỏ (FR-019)",
)
def update_cart_item(
    product_id: int,
    data: CartItemUpdate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """
    Cập nhật số lượng sản phẩm trong giỏ hàng (FR-019):
    - Số lượng tối thiểu là 1.
    - Số lượng không được vượt quá tồn kho.
    - Chặn cập nhật sản phẩm đã bị ẩn.
    - Chỉ thao tác trên giỏ hàng của chính mình.
    """
    return cart_service.update_cart_item_quantity(
        db=db,
        user_id=current_user.id,
        product_id=product_id,
        quantity=data.quantity,
    )


@router.delete(
    "/items/{product_id}",
    summary="Xóa sản phẩm khỏi giỏ hàng (FR-020)",
)
def delete_cart_item(
    product_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """
    Xóa sản phẩm khỏi giỏ hàng (FR-020):
    - Chỉ xóa trong giỏ hàng của chính mình.
    """
    cart_service.delete_cart_item(
        db=db,
        user_id=current_user.id,
        product_id=product_id,
    )
    return {"message": "Đã xóa sản phẩm khỏi giỏ hàng thành công"}
