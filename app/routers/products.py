from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.category import Category
from app.models.product import Product
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.schemas.product import (
    PublicProductDetailResponse,
    PublicProductPageResponse,
    PublicProductResponse,
)

router = APIRouter(prefix="/products", tags=["Products"])


def _active_products_query(db: Session):
    return db.query(Product).filter(Product.is_visible == 1)


@router.get("", response_model=PublicProductPageResponse)
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, min_length=1, description="Search product name"),
    category_id: int | None = Query(None, ge=1, description="Filter by category ID"),
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
    if category_id is not None:
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


@router.get("/category/{category_id}", response_model=PublicProductPageResponse)
def list_products_by_category(
    category_id: int,
    page: int = Query(1, ge=1, description="Trang hiện tại"),
    page_size: int = Query(10, ge=1, le=100, description="Số sản phẩm mỗi trang"),
    db: Session = Depends(get_db),
):
    """Danh sách sản phẩm đang hoạt động thuộc một danh mục."""
    if db.query(Category.id).filter(Category.id == category_id).first() is None:
        raise HTTPException(status_code=404, detail="Danh mục không tồn tại")

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


@router.get("/{product_id}", response_model=PublicProductDetailResponse)
def get_product_detail(product_id: int, db: Session = Depends(get_db)):
    """Chi tiết sản phẩm đang hoạt động, gồm ảnh và sản phẩm cùng danh mục."""
    product = (
        _active_products_query(db)
        .filter(Product.id == product_id)
        .options(selectinload(Product.category), selectinload(Product.product_images))
        .first()
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")

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
