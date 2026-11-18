"""Router sản phẩm công khai dành cho khách hàng (Public Products Router).

Tài liệu đặc tả liên quan:
- FR-013: Xem danh sách sản phẩm (Chỉ hiển thị các sản phẩm đang hoạt động is_visible=1).
- FR-014: Xem danh sách sản phẩm theo danh mục.
- FR-015: Xem chi tiết sản phẩm kèm danh sách ảnh và sản phẩm gợi ý cùng danh mục.
- Public: Khách hàng vãng lai không cần đăng nhập vẫn có thể duyệt và xem thông tin sản phẩm.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.dependencies.auth import require_admin_or_staff
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
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
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, min_length=1, description="Search product name"),
    category_id: int | None = Query(None, ge=1, description="Filter by category ID"),
    category_ids: str | None = Query(None, description="Filter by multiple category IDs (comma-separated, e.g. 7,8,9)"),
    min_price: float | None = Query(None, ge=0, description="Minimum price"),
    max_price: float | None = Query(None, ge=0, description="Maximum price"),
    in_stock: bool | None = Query(None, description="true: còn hàng, false: hết hàng"),
    sort: str = Query("newest", pattern="^(price_asc|price_desc|newest|best_selling)$", description="price_asc, price_desc, newest, best_selling"),
    db: Session = Depends(get_db),
):
    """Search, filter, sort and paginate visible products."""
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail="min_price must be less than or equal to max_price")

    query = _active_products_query(db)
    if search and search.strip():
        query = query.filter(Product.name.ilike(f"%{search.strip()}%"))
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
