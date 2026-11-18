"""Tầng xử lý nghiệp vụ cho Danh mục sản phẩm (Category Service).

Tài liệu đặc tả liên quan:
- FR-014: Thêm danh mục (Kiểm tra tên duy nhất BR-18).
- FR-015: Cập nhật danh mục (Sửa tên, mô tả; kiểm tra tên duy nhất BR-18).
- FR-016: Xóa danh mục (Chặn xóa nếu danh mục còn sản phẩm BR-13).
- FR-017: Xem danh sách danh mục và sản phẩm theo danh mục.
- BR-13: Không được xóa danh mục còn sản phẩm.
- BR-18: Tên danh mục là duy nhất trong toàn hệ thống.
"""
from __future__ import annotations

from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.schemas.category import CategoryCreate, CategoryUpdate


def get_all_categories(
    db: Session,
    keyword: Optional[str] = None,
) -> List[Category]:
    """Lấy danh sách tất cả danh mục sản phẩm (FR-017), có thể tìm kiếm theo tên.

    Args:
        db: Database session.
        keyword: Từ khóa tìm kiếm theo tên danh mục (nếu có).

    Returns:
        Danh sách các đối tượng Category kèm số lượng sản phẩm, số lượng đã bán và số người mua.
    """
    query = db.query(Category)
    if keyword and keyword.strip():
        query = query.filter(Category.name.ilike(f"%{keyword.strip()}%"))

    categories = query.order_by(Category.id.asc()).all()

    # Tính toán số lượng sản phẩm, số lượng đã bán và số người mua cho từng danh mục
    for cat in categories:
        cat.product_count = db.query(Product).filter(Product.category_id == cat.id).count()
        sold_qty = (
            db.query(func.coalesce(func.sum(OrderItem.quantity), 0))
            .join(Product, OrderItem.product_id == Product.id)
            .join(Order, OrderItem.order_id == Order.id)
            .filter(Product.category_id == cat.id, Order.status != OrderStatus.CANCELLED)
            .scalar()
        )
        cat.sold_count = int(sold_qty or 0)
        buyers = (
            db.query(func.count(func.distinct(Order.user_id)))
            .join(OrderItem, Order.id == OrderItem.order_id)
            .join(Product, OrderItem.product_id == Product.id)
            .filter(Product.category_id == cat.id, Order.status != OrderStatus.CANCELLED)
            .scalar()
        )
        cat.buyer_count = int(buyers or 0)

    return categories


def get_category_by_id(db: Session, category_id: int) -> Category:
    """Lấy thông tin chi tiết một danh mục theo ID.

    Args:
        db: Database session.
        category_id: ID danh mục cần tìm.

    Returns:
        Đối tượng Category nếu tìm thấy.

    Raises:
        HTTPException 404: Nếu không tìm thấy danh mục.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Danh mục với ID {category_id} không tồn tại",
        )

    category.product_count = db.query(Product).filter(Product.category_id == category.id).count()
    sold_qty = (
        db.query(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Product, OrderItem.product_id == Product.id)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Product.category_id == category.id, Order.status != OrderStatus.CANCELLED)
        .scalar()
    )
    category.sold_count = int(sold_qty or 0)
    buyers = (
        db.query(func.count(func.distinct(Order.user_id)))
        .join(OrderItem, Order.id == OrderItem.order_id)
        .join(Product, OrderItem.product_id == Product.id)
        .filter(Product.category_id == category.id, Order.status != OrderStatus.CANCELLED)
        .scalar()
    )
    category.buyer_count = int(buyers or 0)
    return category


def get_category_by_name(
    db: Session,
    name: str,
    exclude_id: Optional[int] = None,
) -> Optional[Category]:
    """Tìm danh mục theo tên (không phân biệt chữ hoa / thường, hỗ trợ tiếng Việt có dấu).

    Args:
        db: Database session.
        name: Tên danh mục.
        exclude_id: ID danh mục loại trừ khi kiểm tra (dùng cho cập nhật).

    Returns:
        Đối tượng Category nếu có, ngược lại None.
    """
    name_clean = name.strip().lower()
    query = db.query(Category)
    if exclude_id is not None:
        query = query.filter(Category.id != exclude_id)

    # Thử so sánh trực tiếp bằng SQL
    candidate = query.filter(func.lower(Category.name) == name_clean).first()
    if candidate:
        return candidate

    # So sánh Unicode tiếng Việt trong Python (đảm bảo chạy tốt trên cả SQLite và MySQL)
    all_cats = query.all()
    for cat in all_cats:
        if cat.name.strip().lower() == name_clean:
            return cat
    return None


def create_category(db: Session, data: CategoryCreate) -> Category:
    """Tạo mới một danh mục sản phẩm (FR-014).

    Quy tắc nghiệp vụ:
    - Tên danh mục không được để trống (BR-18).
    - Tên danh mục là duy nhất trong hệ thống (BR-18).

    Args:
        db: Database session.
        data: Dữ liệu tạo danh mục (tên, mô tả).

    Returns:
        Đối tượng Category vừa được tạo trong CSDL.

    Raises:
        HTTPException 409: Nếu tên danh mục đã tồn tại.
    """
    name_clean = data.name.strip()

    # Kiểm tra ràng buộc BR-18: Tên danh mục là duy nhất
    existing = get_category_by_name(db, name_clean)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tên danh mục '{name_clean}' đã tồn tại trong hệ thống",
        )

    new_category = Category(
        name=name_clean,
        description=data.description.strip() if data.description else None,
    )
    db.add(new_category)
    db.commit()
    db.refresh(new_category)

    new_category.product_count = 0
    return new_category


def update_category(
    db: Session,
    category_id: int,
    data: CategoryUpdate,
) -> Category:
    """Cập nhật thông tin danh mục sản phẩm (FR-015).

    Quy tắc nghiệp vụ:
    - Danh mục phải tồn tại trong CSDL.
    - Nếu thay đổi tên danh mục, tên mới phải là duy nhất (BR-18).

    Args:
        db: Database session.
        category_id: ID danh mục cần cập nhật.
        data: Dữ liệu cập nhật (tên mới, mô tả mới).

    Returns:
        Đối tượng Category sau khi cập nhật.

    Raises:
        HTTPException 404: Nếu không tìm thấy danh mục.
        HTTPException 409: Nếu tên mới trùng với danh mục khác đã có.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Danh mục với ID {category_id} không tồn tại",
        )

    # Nếu cập nhật tên, kiểm tra trùng lặp với danh mục khác (BR-18)
    if data.name is not None:
        name_clean = data.name.strip()
        existing = get_category_by_name(db, name_clean, exclude_id=category_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tên danh mục '{name_clean}' đã tồn tại trên một danh mục khác",
            )
        category.name = name_clean

    if data.description is not None:
        category.description = data.description.strip() if data.description else None

    db.commit()
    db.refresh(category)

    category.product_count = db.query(Product).filter(Product.category_id == category.id).count()
    return category


def delete_category(db: Session, category_id: int) -> int:
    """Xóa danh mục sản phẩm (FR-016).

    Quy tắc nghiệp vụ:
    - Danh mục phải tồn tại.
    - BR-13: Không được xóa danh mục khi vẫn còn sản phẩm thuộc danh mục này.

    Args:
        db: Database session.
        category_id: ID danh mục cần xóa.

    Returns:
        ID của danh mục vừa bị xóa.

    Raises:
        HTTPException 404: Nếu danh mục không tồn tại.
        HTTPException 400: Nếu danh mục vẫn còn sản phẩm (vi phạm BR-13).
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Danh mục với ID {category_id} không tồn tại",
        )

    # Kiểm tra ràng buộc BR-13: Không được xóa danh mục còn sản phẩm
    product_count = db.query(Product).filter(Product.category_id == category_id).count()
    if product_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Không thể xóa danh mục '{category.name}' vì vẫn còn {product_count} sản phẩm "
                f"thuộc danh mục này. Vui lòng chuyển hoặc xóa sản phẩm trước (BR-13)."
            ),
        )

    db.delete(category)
    db.commit()
    return category_id
