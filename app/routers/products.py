from fastapi import APIRouter, Depends, HTTPException, Query
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
    return db.query(Product).filter(Product.is_visible == 1)


@router.get("", response_model=PublicProductPageResponse)
def list_products(
    page: int = Query(1, ge=1, description="Trang hiện tại"),
    page_size: int = Query(10, ge=1, le=100, description="Số sản phẩm mỗi trang"),
    db: Session = Depends(get_db),
):
    """Danh sách sản phẩm đang hoạt động, có phân trang."""
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
