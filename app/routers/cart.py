"""Router quản lý giỏ hàng của khách hàng (Shopping Cart Router).

Tài liệu đặc tả liên quan:
- FR-018: Thêm sản phẩm vào giỏ hàng (Kiểm tra tồn kho, cộng dồn số lượng, chặn sản phẩm ẩn).
- FR-019: Cập nhật số lượng sản phẩm trong giỏ hàng (Kiểm tra giới hạn tồn kho).
- FR-020: Xóa sản phẩm khỏi giỏ hàng.
- FR-021: Xem giỏ hàng và tổng tiền (Tính tạm tính, phí ship, tổng tiền và các cảnh báo).
- BR-20: Mỗi tài khoản Customer sở hữu duy nhất 1 giỏ hàng tại một thời điểm.
- Phân quyền: Toàn bộ API giỏ hàng chỉ dành riêng cho tài khoản Khách hàng (vai trò CUSTOMER).
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_customer
from app.models.user import User
from app.schemas.cart import CartResponse
from app.schemas.cart_item import CartItemCreate, CartItemResponse, CartItemUpdate
from app.service import cart as cart_service

router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get(
    "",
    response_model=CartResponse,
    summary="Xem chi tiết giỏ hàng và tổng tiền (FR-021)",
    description=(
        "Khách hàng xem toàn bộ các sản phẩm hiện có trong giỏ hàng của mình.\n"
        "- **Tính toán tự động**: Tạm tính từng dòng, tổng tiền hàng, phí vận chuyển (mặc định 0đ theo chính sách).\n"
        "- **Cảnh báo tích hợp** (`warnings`): Tự động phát hiện nếu sản phẩm bị đổi giá, sản phẩm hết hàng hoặc bị ẩn.\n"
        "- **Kiểm tra thanh toán** (`can_checkout`): Chỉ cho phép tiến hành đặt hàng khi tất cả sản phẩm trong giỏ còn hàng.\n"
        "- **Quyền hạn**: Chỉ dành cho tài khoản `CUSTOMER`."
    ),
)
def get_cart(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Lấy thông tin giỏ hàng của khách hàng hiện tại."""
    return cart_service.get_cart_by_user(db, current_user.id)


@router.post(
    "/items",
    response_model=CartItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm sản phẩm vào giỏ hàng (FR-018)",
    description=(
        "Thêm một sản phẩm với số lượng mong muốn vào giỏ hàng của khách hàng.\n"
        "- **Quy tắc nghiệp vụ**:\n"
        "  + Số lượng thêm phải >= 1.\n"
        "  + Chặn không cho thêm nếu sản phẩm đã bị ẩn (`is_visible=0`) hoặc tồn kho = 0.\n"
        "  + Nếu sản phẩm đã tồn tại trong giỏ: Tự động cộng dồn số lượng mới vào số lượng cũ.\n"
        "  + Tổng số lượng sau khi cộng dồn không được vượt quá số lượng tồn kho hiện tại.\n"
        "- **Quyền hạn**: Chỉ dành cho `CUSTOMER`.\n"
        "- **Mã lỗi**: `400 Bad Request` nếu không đủ hàng hoặc sản phẩm đã ẩn; `404 Not Found` nếu ID không tồn tại."
    ),
)
def add_item_to_cart(
    data: CartItemCreate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Thêm sản phẩm vào giỏ hàng của khách hàng."""
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
    description=(
        "Điều chỉnh số lượng của một mặt hàng đã có sẵn trong giỏ hàng.\n"
        "- **Quy tắc**:\n"
        "  + Số lượng mới phải >= 1.\n"
        "  + Số lượng mới không được vượt quá tồn kho thực tế của sản phẩm.\n"
        "- **Quyền hạn**: Chỉ dành cho `CUSTOMER`.\n"
        "- **Mã lỗi**: `400 Bad Request` nếu vượt quá tồn kho; `404 Not Found` nếu mặt hàng không có trong giỏ."
    ),
)
def update_cart_item(
    product_id: int,
    data: CartItemUpdate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Cập nhật số lượng sản phẩm trong giỏ."""
    return cart_service.update_cart_item_quantity(
        db=db,
        user_id=current_user.id,
        product_id=product_id,
        quantity=data.quantity,
    )


@router.delete(
    "/items/{product_id}",
    status_code=status.HTTP_200_OK,
    summary="Xóa sản phẩm khỏi giỏ hàng (FR-020)",
    description=(
        "Xóa bỏ hoàn toàn một sản phẩm ra khỏi giỏ hàng của khách hàng.\n"
        "- **Quyền hạn**: Chỉ dành cho `CUSTOMER`.\n"
        "- **Mã lỗi**: `404 Not Found` nếu sản phẩm không có trong giỏ hàng."
    ),
)
def delete_cart_item(
    product_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Xóa sản phẩm khỏi giỏ hàng."""
    cart_service.delete_cart_item(
        db=db,
        user_id=current_user.id,
        product_id=product_id,
    )
    return {"message": "Đã xoá sản phẩm khỏi giỏ hàng thành công"}
