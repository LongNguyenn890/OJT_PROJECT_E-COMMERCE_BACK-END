"""Router sản phẩm công khai dành cho khách hàng (Public Products Router).

Tài liệu đặc tả liên quan:
- FR-013: Xem danh sách sản phẩm (Chỉ hiển thị các sản phẩm đang hoạt động is_visible=1).
- FR-014: Xem danh sách sản phẩm theo danh mục.
- FR-015: Xem chi tiết sản phẩm kèm danh sách ảnh và sản phẩm gợi ý cùng danh mục.
- Public: Khách hàng vãng lai không cần đăng nhập vẫn có thể duyệt và xem thông tin sản phẩm.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from pathlib import Path
from uuid import uuid4
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.dependencies.auth import require_admin_or_staff, require_customer
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.product_review import ProductReview
from app.schemas.product_review import (
    MyProductReviewResponse,
    ProductReviewListResponse,
    ProductReviewResponse,
)
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    PublicProductDetailResponse,
    PublicProductPageResponse,
    PublicProductResponse,
    ProductDeleteOrHideResponse,
    ProductVisibilityRequest,
    ProductImageDeleteResponse,
)
from app.schemas.product_image import ProductImageResponse
from app.service import product as product_service

router = APIRouter(prefix="/products", tags=["Products"])
REVIEW_UPLOAD_DIR = Path("uploads/reviews")
REVIEW_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_REVIEW_IMAGE_TYPES = {
    ".jpg": {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
}
MAX_REVIEW_IMAGE_SIZE = 5 * 1024 * 1024


def _active_products_query(db: Session):
    """Truy vấn cơ bản chỉ lọc các sản phẩm đang được bật hiển thị (is_visible = 1)."""
    return db.query(Product).filter(Product.is_visible == 1)


def _review_stats(db: Session, products: list[Product]) -> dict[int, dict[str, float | int]]:
    product_ids = [product.id for product in products]
    if not product_ids:
        return {}

    rows = (
        db.query(
            ProductReview.product_id,
            func.avg(ProductReview.rating).label("average_rating"),
            func.count(ProductReview.id).label("review_count"),
        )
        .filter(ProductReview.product_id.in_(product_ids))
        .group_by(ProductReview.product_id)
        .all()
    )
    return {
        row.product_id: {
            "average_rating": round(float(row.average_rating or 0), 1),
            "review_count": int(row.review_count or 0),
        }
        for row in rows
    }


def _public_product_data(db: Session, products: list[Product]) -> list[dict]:
    stats = _review_stats(db, products)
    return [
        {
            **PublicProductResponse.model_validate(product).model_dump(),
            **stats.get(product.id, {"average_rating": 0, "review_count": 0}),
        }
        for product in products
    ]


def _is_delivered(order: Order) -> bool:
    status_value = getattr(order.status, "name", None) or getattr(order.status, "value", order.status)
    return str(status_value).strip().upper() in {"COMPLETED", "DELIVERED"}


def _eligible_order(db: Session, product_id: int, user_id: int) -> Order | None:
    orders = (
        db.query(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(Order.user_id == user_id, OrderItem.product_id == product_id)
        .all()
    )
    return next((order for order in orders if _is_delivered(order)), None)


def _review_response(review: ProductReview) -> dict:
    return {
        "id": review.id,
        "rating": review.rating,
        "comment": review.comment,
        "image_url": review.image_url,
        "created_at": review.created_at,
        "customer_name": review.user.full_name,
    }


def _remove_review_image(path: Path | None) -> None:
    if path and path.is_file():
        try:
            path.unlink()
        except OSError:
            pass


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
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, min_length=1, description="Search product name"),
    category_id: int | None = Query(None, ge=1, description="Filter by category ID"),
    category_ids: str | None = Query(None, description="Filter by multiple category IDs (comma-separated, e.g. 7,8,9)"),
    min_price: float | None = Query(None, ge=0, description="Minimum price"),
    max_price: float | None = Query(None, ge=0, description="Maximum price"),
    in_stock: bool | None = Query(None, description="true: còn hàng, false: hết hàng"),
    is_visible: int | None = Query(None, description="1: Hiển thị, 0: Ẩn, -1: Tất cả trạng thái"),
    sort: str = Query("newest", pattern="^(price_asc|price_desc|newest|best_selling)$", description="price_asc, price_desc, newest, best_selling"),
    db: Session = Depends(get_db),
):
    """Search, filter, sort and paginate visible products."""
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail="min_price must be less than or equal to max_price")

    if is_visible is None:
        query = _active_products_query(db)
    elif is_visible == -1:
        query = db.query(Product)
    else:
        query = db.query(Product).filter(Product.is_visible == is_visible)

    if search and search.strip():
        s = search.strip()
        from sqlalchemy import or_
        query = query.filter(or_(Product.name.ilike(f"%{s}%"), Product.sku.ilike(f"%{s}%")))
    if category_ids and category_ids.strip():
        parsed_ids = [int(x.strip()) for x in category_ids.split(",") if x.strip().isdigit()]
        if parsed_ids:
            query = query.filter(Product.category_id.in_(parsed_ids))
    elif category_id is not None:
        query = query.filter(Product.category_id == category_id)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if in_stock is True:
        query = query.filter(Product.stock_quantity > 0)
    elif in_stock is False:
        query = query.filter(Product.stock_quantity <= 0)

    if sort == "price_asc":
        query = query.order_by(Product.price.asc(), Product.id.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc(), Product.id.desc())
    elif sort == "best_selling":
        sales = (
            db.query(OrderItem.product_id, func.sum(OrderItem.quantity).label("sold_quantity"))
            .join(Order, Order.id == OrderItem.order_id)
            .filter(Order.status == OrderStatus.COMPLETED)
            .group_by(OrderItem.product_id)
            .subquery()
        )
        query = query.outerjoin(sales, sales.c.product_id == Product.id)
        query = query.order_by(func.coalesce(sales.c.sold_quantity, 0).desc(), Product.id.asc())
    else:
        query = query.order_by(Product.created_at.desc(), Product.id.desc())

    query = query.options(selectinload(Product.category), selectinload(Product.product_images))
    total = query.count()
    products = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": _public_product_data(db, products),
    }


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
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": _public_product_data(db, products),
    }


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
    product_data = _public_product_data(db, [product])[0]
    product_data["related_products"] = _public_product_data(db, related_products)
    return product_data


@router.get(
    "/{product_id}/reviews",
    response_model=ProductReviewListResponse,
    summary="Xem điểm trung bình và đánh giá sản phẩm",
)
def list_product_reviews(
    product_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if not _active_products_query(db).filter(Product.id == product_id).first():
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại hoặc đã bị ẩn")

    aggregate = db.query(
        func.avg(ProductReview.rating).label("average_rating"),
        func.count(ProductReview.id).label("review_count"),
    ).filter(ProductReview.product_id == product_id).first()
    distribution_rows = (
        db.query(ProductReview.rating, func.count(ProductReview.id))
        .filter(ProductReview.product_id == product_id)
        .group_by(ProductReview.rating)
        .all()
    )
    distribution = {rating: 0 for rating in range(1, 6)}
    distribution.update({int(rating): int(count) for rating, count in distribution_rows})
    reviews = (
        db.query(ProductReview)
        .options(selectinload(ProductReview.user))
        .filter(ProductReview.product_id == product_id)
        .order_by(ProductReview.created_at.desc(), ProductReview.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "average_rating": round(float(aggregate.average_rating or 0), 1),
        "review_count": int(aggregate.review_count or 0),
        "rating_distribution": distribution,
        "items": [_review_response(review) for review in reviews],
    }


@router.get(
    "/{product_id}/reviews/mine",
    response_model=MyProductReviewResponse,
    summary="Kiểm tra quyền đánh giá của khách hàng cho sản phẩm",
)
def get_my_product_review(
    product_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    if not _active_products_query(db).filter(Product.id == product_id).first():
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại hoặc đã bị ẩn")

    review = (
        db.query(ProductReview)
        .options(selectinload(ProductReview.user))
        .filter(ProductReview.product_id == product_id, ProductReview.user_id == current_user.id)
        .first()
    )
    return {
        "eligible": _eligible_order(db, product_id, current_user.id) is not None,
        "review": _review_response(review) if review else None,
    }


@router.delete(
    "/{product_id}/reviews/mine",
    summary="Xóa đánh giá của khách hàng hiện tại",
)
def delete_my_product_review(
    product_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    review = (
        db.query(ProductReview)
        .filter(ProductReview.product_id == product_id, ProductReview.user_id == current_user.id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đánh giá của bạn cho sản phẩm này")

    image_path = None
    if review.image_url and review.image_url.startswith("/uploads/reviews/"):
        image_path = Path(".") / review.image_url.lstrip("/")
    db.delete(review)
    db.commit()
    _remove_review_image(image_path)
    return {"message": "Đã xóa đánh giá sản phẩm"}


@router.post(
    "/{product_id}/reviews",
    response_model=ProductReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đánh giá sản phẩm đã giao thành công",
)
def create_product_review(
    product_id: int,
    rating: int = Form(..., ge=1, le=5),
    comment: str = Form(..., min_length=1, max_length=1000),
    image: UploadFile | None = File(None, description="Ảnh đánh giá tùy chọn (JPG, PNG hoặc WEBP, tối đa 5MB)"),
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    product = _active_products_query(db).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại hoặc đã bị ẩn")

    order = _eligible_order(db, product_id, current_user.id)
    if order is None:
        raise HTTPException(status_code=403, detail="Bạn chỉ có thể đánh giá sản phẩm trong đơn hàng đã giao thành công")

    existing = db.query(ProductReview.id).filter(
        ProductReview.product_id == product_id,
        ProductReview.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Bạn đã đánh giá sản phẩm này rồi")

    normalized_comment = comment.strip()
    if not normalized_comment:
        raise HTTPException(status_code=422, detail="Vui lòng nhập nhận xét")

    image_url = None
    saved_image_path = None
    if image and image.filename:
        extension = Path(image.filename).suffix.lower()
        allowed_types = ALLOWED_REVIEW_IMAGE_TYPES.get(extension)
        if not allowed_types or (image.content_type and image.content_type.lower() not in allowed_types):
            raise HTTPException(status_code=400, detail="Ảnh đánh giá phải có định dạng JPG, PNG hoặc WEBP")

        image_content = image.file.read(MAX_REVIEW_IMAGE_SIZE + 1)
        if len(image_content) > MAX_REVIEW_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail="Ảnh đánh giá không được vượt quá 5MB")
        if not image_content:
            raise HTTPException(status_code=400, detail="Ảnh đánh giá không hợp lệ")

        file_name = f"{uuid4().hex}{extension}"
        saved_image_path = REVIEW_UPLOAD_DIR / file_name
        saved_image_path.write_bytes(image_content)
        image_url = f"/uploads/reviews/{file_name}"

    review = ProductReview(
        product_id=product_id,
        user_id=current_user.id,
        order_id=order.id,
        rating=rating,
        comment=normalized_comment,
        image_url=image_url,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _remove_review_image(saved_image_path)
        raise HTTPException(status_code=409, detail="Bạn đã đánh giá sản phẩm này rồi")
    except Exception:
        db.rollback()
        _remove_review_image(saved_image_path)
        raise
    db.refresh(review)
    review.user = current_user
    return _review_response(review)


# ==============================================================================
# QUẢN TRỊ VIÊN & NHÂN VIÊN (ADMIN & STAFF) - THÊM & CẬP NHẬT SẢN PHẨM (FR-011, FR-012)
# ==============================================================================

@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm sản phẩm mới (FR-011)",
    description=(
        "Tạo sản phẩm mới trong hệ thống.\n"
        "- **Quyền hạn**: Bắt buộc tài khoản có quyền `ADMIN` hoặc `STAFF`.\n"
        "- **Quy tắc nghiệp vụ**:\n"
        "  + Mã SKU là bắt buộc, không được để trống và không được trùng với sản phẩm khác (trả `409 Conflict`).\n"
        "  + Giá gốc (`price`) phải là số lớn hơn 0 (trả `400 Bad Request`).\n"
        "  + Giá khuyến mãi (`promotional_price`, nếu có) phải nhỏ hơn giá gốc và >= 0 (trả `400 Bad Request`).\n"
        "  + Danh mục (`category_id`) phải tồn tại trong CSDL (trả `400 Bad Request`).\n"
        "- **Mã lỗi**:\n"
        "  + `400 Bad Request`: Lỗi dữ liệu không hợp lệ (giá <= 0, giá KM >= giá gốc, danh mục không tồn tại).\n"
        "  + `401 Unauthorized`: Chưa cung cấp token hoặc token không hợp lệ.\n"
        "  + `403 Forbidden`: Người dùng không có quyền Admin hoặc Staff.\n"
        "  + `409 Conflict`: Mã SKU đã tồn tại."
    ),
)
def create_product(
    payload: ProductCreate,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Tạo sản phẩm mới (dành cho Admin & Staff)."""
    return product_service.create_product(db=db, data=payload, user_id=current_user.id)


@router.put(
    "/{id}",
    response_model=ProductResponse,
    summary="Cập nhật thông tin sản phẩm (FR-012)",
    description=(
        "Cập nhật thông tin sản phẩm đã tồn tại trong hệ thống.\n"
        "- **Quyền hạn**: Bắt buộc tài khoản có quyền `ADMIN` hoặc `STAFF`.\n"
        "- **Quy tắc nghiệp vụ**:\n"
        "  + Sản phẩm phải tồn tại trong hệ thống (trả `404 Not Found`).\n"
        "  + Nếu đổi mã SKU: mã SKU không được trùng với sản phẩm khác (trả `409 Conflict`).\n"
        "  + Nếu cập nhật giá gốc: giá gốc phải > 0 (trả `400 Bad Request`).\n"
        "  + Giá khuyến mãi sau cập nhật phải nhỏ hơn giá gốc và >= 0 (trả `400 Bad Request`).\n"
        "  + Nếu cập nhật danh mục: danh mục phải tồn tại (trả `400 Bad Request`).\n"
        "- **Mã lỗi**:\n"
        "  + `400 Bad Request`: Dữ liệu vi phạm quy tắc nghiệp vụ.\n"
        "  + `401 Unauthorized`: Chưa cung cấp token.\n"
        "  + `403 Forbidden`: Người dùng không có quyền Admin hoặc Staff.\n"
        "  + `404 Not Found`: Sản phẩm không tồn tại.\n"
        "  + `409 Conflict`: Mã SKU đã bị trùng với sản phẩm khác."
    ),
)
def update_product(
    id: int,
    payload: ProductUpdate,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Cập nhật sản phẩm (dành cho Admin & Staff)."""
    return product_service.update_product(
        db=db, product_id=id, data=payload, user_id=current_user.id
    )


@router.post(
    "/{id}/images",
    response_model=list[ProductImageResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload nhiều ảnh cho sản phẩm",
    description=(
        "Tải lên một hoặc nhiều hình ảnh cho một sản phẩm cụ thể.\n"
        "- **Quyền hạn**: Bắt buộc tài khoản có quyền `ADMIN` hoặc `STAFF`.\n"
        "- **Ràng buộc**:\n"
        "  + Định dạng hợp lệ: JPG, JPEG, PNG (trả `400 Bad Request` nếu sai định dạng).\n"
        "  + Giới hạn dung lượng: Tối đa 100MB mỗi ảnh (trả `400 Bad Request` nếu vượt quá).\n"
        "  + Nếu sản phẩm chưa có ảnh đại diện nào, ảnh đầu tiên được tải lên sẽ tự động thành ảnh đại diện (`is_primary=1`)."
    ),
)
def upload_images(
    id: int,
    files: list[UploadFile] = File(..., description="Danh sách các file ảnh tải lên (JPG/PNG <= 100MB)"),
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Upload nhiều ảnh cho sản phẩm (JPG/PNG, tối đa 100MB mỗi file)."""
    return product_service.upload_product_images(db=db, product_id=id, files=files)


@router.put(
    "/{id}/images/{image_id}/primary",
    response_model=ProductImageResponse,
    summary="Chọn ảnh đại diện cho sản phẩm",
    description=(
        "Đặt một hình ảnh cụ thể làm ảnh đại diện (`is_primary=1`) của sản phẩm.\n"
        "- Tất cả các ảnh khác của sản phẩm này sẽ tự động chuyển về `is_primary=0`.\n"
        "- **Quyền hạn**: Bắt buộc tài khoản có quyền `ADMIN` hoặc `STAFF`.\n"
        "- **Mã lỗi**: `404 Not Found` nếu sản phẩm hoặc ảnh không tồn tại."
    ),
)
def set_primary_image(
    id: int,
    image_id: int,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Chọn ảnh đại diện cho sản phẩm (Admin / Staff)."""
    return product_service.set_primary_image(db=db, product_id=id, image_id=image_id)


@router.delete(
    "/{id}/images/{image_id}",
    response_model=ProductImageDeleteResponse,
    summary="Xóa một ảnh của sản phẩm",
    description=(
        "Xóa một hình ảnh khỏi sản phẩm và dọn dẹp file vật lý trên máy chủ.\n"
        "- Nếu ảnh bị xóa đang là ảnh đại diện (`is_primary=1`), hệ thống sẽ tự động chuyển quyền đại diện cho ảnh còn lại đầu tiên.\n"
        "- **Quyền hạn**: Bắt buộc tài khoản có quyền `ADMIN` hoặc `STAFF`.\n"
        "- **Mã lỗi**: `404 Not Found` nếu không tìm thấy ảnh thuộc sản phẩm này."
    ),
)
def delete_image(
    id: int,
    image_id: int,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Xóa ảnh của sản phẩm (Admin / Staff)."""
    return product_service.delete_product_image(db=db, product_id=id, image_id=image_id)


@router.patch(
    "/{id}/visibility",
    summary="Ẩn hoặc hiện sản phẩm",
    description=(
        "Chuyển đổi trạng thái hiển thị của sản phẩm (`is_visible`: 1 là hiển thị, 0 là ẩn).\n"
        "- Sản phẩm bị ẩn sẽ không hiển thị trên danh sách và tìm kiếm công khai của khách hàng.\n"
        "- **Quyền hạn**: Bắt buộc tài khoản có quyền `ADMIN` hoặc `STAFF`."
    ),
)
def toggle_visibility(
    id: int,
    payload: ProductVisibilityRequest,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Ẩn hoặc hiện sản phẩm (Admin / Staff)."""
    return product_service.set_product_visibility(db=db, product_id=id, is_visible=payload.is_visible)


@router.delete(
    "/{id}",
    response_model=ProductDeleteOrHideResponse,
    summary="Xóa hoặc ẩn sản phẩm (FR-013 & BR-12)",
    description=(
        "Thực hiện xóa hoặc ẩn sản phẩm theo ràng buộc dữ liệu toàn vẹn:\n"
        "- **BR-12**: Nếu sản phẩm đã phát sinh trong bất kỳ đơn hàng nào (`order_items`), hệ thống **CHỈ ẨN (`is_visible=0`), KHÔNG XÓA CỨNG** khỏi CSDL.\n"
        "- Nếu sản phẩm chưa từng có trong đơn hàng nào: Cho phép xóa vĩnh viễn khỏi CSDL và dọn dẹp file ảnh vật lý.\n"
        "- **Quyền hạn**: Bắt buộc tài khoản có quyền `ADMIN` hoặc `STAFF`.\n"
        "- **Mã lỗi**: `404 Not Found` nếu sản phẩm không tồn tại."
    ),
)
def delete_product(
    id: int,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Xóa sản phẩm (nếu có trong đơn hàng thì chỉ ẩn, chưa có thì xóa cứng)."""
    return product_service.delete_or_hide_product(db=db, product_id=id)
