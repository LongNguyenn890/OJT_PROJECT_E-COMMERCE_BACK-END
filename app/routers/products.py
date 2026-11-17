"""Router sản phẩm công khai dành cho khách hàng (Public Products Router).

Tài liệu đặc tả liên quan:
- FR-013: Xem danh sách sản phẩm (Chỉ hiển thị các sản phẩm đang hoạt động is_visible=1).
- FR-014: Xem danh sách sản phẩm theo danh mục.
- FR-015: Xem chi tiết sản phẩm kèm danh sách ảnh và sản phẩm gợi ý cùng danh mục.
- Public: Khách hàng vãng lai không cần đăng nhập vẫn có thể duyệt và xem thông tin sản phẩm.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.category import Category
from app.models.product import Product
from app.schemas.product import (
    PublicProductDetailResponse,
    PublicProductPageResponse,
    PublicProductResponse,
)

router = APIRouter(prefix="/products", tags=["Products"])


def _active_products_query(db: Session):
    """Truy vấn cơ bản chỉ lọc các sản phẩm đang được bật hiển thị (is_visible = 1)."""
    return db.query(Product).filter(Product.is_visible == 1)


@router.get(
    "",
    response_model=PublicProductPageResponse,
    summary="Xem danh sách sản phẩm công khai (FR-013)",
    description=(
        "Lấy danh sách các sản phẩm đang hoạt động (`is_visible=1`) phục vụ trang chủ hoặc trang danh sách sản phẩm của người dùng.\n"
        "- **Phân trang**: Hỗ trợ `page` và `page_size`.\n"
        "- **Dữ liệu kèm theo**: Bao gồm thông tin danh mục và danh sách ảnh của sản phẩm.\n"
        "- **Quyền hạn**: Công khai (không yêu cầu đăng nhập)."
    ),
)
def list_products(
    page: int = Query(1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Số sản phẩm hiển thị trên mỗi trang"),
    db: Session = Depends(get_db),
):
    """Lấy danh sách sản phẩm đang hiển thị kèm phân trang."""
    query = _active_products_query(db).options(
        selectinload(Product.category), selectinload(Product.product_images)
    )
    total = query.count()
    products = (
        query.order_by(Product.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "page": page, "page_size": page_size, "items": products}


@router.get(
    "/category/{category_id}",
    response_model=PublicProductPageResponse,
    summary="Xem danh sách sản phẩm theo danh mục (FR-014)",
    description=(
        "Lọc danh sách các sản phẩm đang hoạt động thuộc về một danh mục cụ thể (`category_id`).\n"
        "- **Kiểm tra**: Trả về `404 Not Found` nếu ID danh mục không tồn tại trong hệ thống.\n"
        "- **Phân trang**: Hỗ trợ `page` và `page_size`.\n"
        "- **Quyền hạn**: Công khai."
    ),
)
def list_products_by_category(
    category_id: int,
    page: int = Query(1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Số sản phẩm trên mỗi trang"),
    db: Session = Depends(get_db),
):
    """Lọc danh sách sản phẩm theo mã danh mục."""
    if db.query(Category.id).filter(Category.id == category_id).first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Danh mục không tồn tại",
        )

    query = _active_products_query(db).filter(Product.category_id == category_id).options(
        selectinload(Product.category), selectinload(Product.product_images)
    )
    total = query.count()
    products = (
        query.order_by(Product.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "page": page, "page_size": page_size, "items": products}


@router.get(
    "/{product_id}",
    response_model=PublicProductDetailResponse,
    summary="Xem chi tiết sản phẩm và sản phẩm liên quan (FR-015)",
    description=(
        "Xem thông tin chi tiết của một sản phẩm cụ thể, bao gồm toàn bộ hình ảnh sản phẩm và tối đa 8 sản phẩm liên quan cùng danh mục.\n"
        "- **Kiểm tra**: Nếu sản phẩm bị ẩn (`is_visible=0`) hoặc không tồn tại, trả về `404 Not Found`.\n"
        "- **Quyền hạn**: Công khai."
    ),
)
def get_product_detail(product_id: int, db: Session = Depends(get_db)):
    """Lấy chi tiết một sản phẩm đang hiển thị kèm danh sách sản phẩm liên quan."""
    product = (
        _active_products_query(db)
        .filter(Product.id == product_id)
        .options(selectinload(Product.category), selectinload(Product.product_images))
        .first()
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sản phẩm không tồn tại hoặc đã bị ẩn",
        )

    related_products = (
        _active_products_query(db)
        .filter(Product.category_id == product.category_id, Product.id != product.id)
        .options(selectinload(Product.category), selectinload(Product.product_images))
        .order_by(Product.id)
        .limit(8)
        .all()
    )
    product_data = PublicProductResponse.model_validate(product).model_dump()
    product_data["related_products"] = related_products
    return product_data
