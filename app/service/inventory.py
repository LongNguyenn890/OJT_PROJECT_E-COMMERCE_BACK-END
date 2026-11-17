"""Tầng xử lý nghiệp vụ Quản lý kho và Nhật ký tồn kho (Inventory Service).

Tài liệu đặc tả liên quan:
- FR-033: Theo dõi số lượng tồn kho (Danh sách sản phẩm, trạng thái còn/hết/sắp hết).
- FR-034: Cập nhật tồn kho (Nhập hàng IMPORT, Điều chỉnh kiểm kê ADJUST).
- FR-035: Kiểm tra tồn kho trước khi đặt hàng (Trừ kho nguyên tử, không âm).
- FR-036: Cảnh báo sản phẩm sắp hết hàng (Theo ngưỡng cấu hình).
- BR-05: Tồn kho phải là số nguyên >= 0.
- BR-10: Trừ tồn kho khi tạo đơn, hoàn tồn kho khi hủy đơn, xử lý nguyên tử chống race condition.
- BR-14: Ngưỡng cảnh báo sắp hết hàng mặc định là 5 (Admin có thể truyền threshold tùy chỉnh).
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models import Product, StockLog, Category
from app.models.stock_log import ChangeType
from app.schemas.stock_log import DEFAULT_LOW_STOCK_THRESHOLD


# ==============================================================================
# 1. CÁC HÀM XỬ LÝ DÙNG CHUNG CHO TRANSACTION KHO (Dùng cho Order, Cart, Admin)
# ==============================================================================

def decrease_stock(
    db: Session,
    product_id: int,
    quantity: int,
    order_id: int | None = None,
    user_id: int | None = None,
    note: str | None = None,
) -> StockLog:
    """Hàm trừ kho dùng chung cho module Đặt hàng (FR-035, BR-10).

    Args:
        db: SQLAlchemy database session trong transaction hiện tại.
        product_id: ID sản phẩm cần trừ kho.
        quantity: Số lượng cần trừ (phải > 0).
        order_id: ID đơn hàng liên quan (nếu có).
        user_id: ID người thực hiện (nếu có).
        note: Ghi chú lý do trừ kho.

    Returns:
        Bản ghi StockLog vừa được tạo (chưa commit, chờ transaction chung).

    Raises:
        HTTPException 400: Nếu số lượng <= 0.
        HTTPException 404: Nếu không tìm thấy sản phẩm.
        HTTPException 409: Nếu số lượng tồn kho hiện tại không đủ.
    """
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số lượng trừ kho phải lớn hơn 0",
        )

    # Khóa bi quan (Pessimistic Locking) bằng SELECT FOR UPDATE chống race-condition
    product = (
        db.query(Product).filter(Product.id == product_id).with_for_update().first()
    )

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sản phẩm với ID {product_id}",
        )

    stock_before = product.stock_quantity

    # Kiểm tra tồn kho (BR-10, BR-04, FR-035)
    if stock_before < quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Sản phẩm '{product.name}' không đủ tồn kho. Còn lại: {stock_before},"
                f" yêu cầu: {quantity}"
            ),
        )

    stock_after = stock_before - quantity
    product.stock_quantity = stock_after

    # Ghi log biến động kho vào bảng stock_logs
    stock_log = StockLog(
        product_id=product_id,
        order_id=order_id,
        created_by=user_id,
        change_type=ChangeType.ORDER,
        quantity_change=-quantity,
        stock_before=stock_before,
        stock_after=stock_after,
        note=note or (f"Trừ kho cho đơn hàng #{order_id}" if order_id else "Trừ kho"),
    )
    db.add(stock_log)
    return stock_log


def increase_stock(
    db: Session,
    product_id: int,
    quantity: int,
    change_type: ChangeType = ChangeType.CANCEL,
    order_id: int | None = None,
    user_id: int | None = None,
    note: str | None = None,
) -> StockLog:
    """Hàm hoàn kho hoặc tăng kho dùng chung (khi hủy đơn hàng hoặc nhập kho).

    Args:
        db: Database session.
        product_id: ID sản phẩm.
        quantity: Số lượng thêm vào (phải > 0).
        change_type: Loại thay đổi (CANCEL, IMPORT, v.v.).
        order_id: ID đơn hàng liên quan (nếu hủy đơn).
        user_id: ID người thực hiện.
        note: Ghi chú giải trình.

    Returns:
        Bản ghi StockLog vừa tạo.
    """
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số lượng thêm vào kho phải lớn hơn 0",
        )

    product = (
        db.query(Product).filter(Product.id == product_id).with_for_update().first()
    )

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sản phẩm với ID {product_id}",
        )

    stock_before = product.stock_quantity
    stock_after = stock_before + quantity
    product.stock_quantity = stock_after

    # Ghi log biến động kho
    stock_log = StockLog(
        product_id=product_id,
        order_id=order_id,
        created_by=user_id,
        change_type=change_type,
        quantity_change=quantity,
        stock_before=stock_before,
        stock_after=stock_after,
        note=note
        or (
            f"Hoàn kho từ đơn hàng #{order_id}"
            if order_id
            else "Cập nhật tăng kho"
        ),
    )
    db.add(stock_log)
    return stock_log


# ==============================================================================
# 2. NGHIỆP VỤ QUẢN LÝ KHO CHO ADMIN / STAFF (FR-033, FR-034, FR-036)
# ==============================================================================

def get_inventory_list(
    db: Session,
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    threshold: int = DEFAULT_LOW_STOCK_THRESHOLD,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Admin/Nhân viên theo dõi tồn kho tất cả sản phẩm kèm cảnh báo (FR-033, FR-036).

    Args:
        db: Database session.
        keyword: Từ khóa tìm kiếm theo tên sản phẩm.
        category_id: ID danh mục cần lọc.
        status_filter: Trạng thái tồn kho cần lọc (IN_STOCK, LOW_STOCK, OUT_OF_STOCK).
        threshold: Ngưỡng cảnh báo sắp hết hàng (mặc định = 5).
        page: Trang hiện tại.
        page_size: Số lượng mỗi trang.

    Returns:
        Dictionary chứa danh sách sản phẩm phân trang và thống kê số lượng cảnh báo.
    """
    query = db.query(Product).options(joinedload(Product.category))

    if keyword and keyword.strip():
        query = query.filter(Product.name.ilike(f"%{keyword.strip()}%"))

    if category_id is not None:
        query = query.filter(Product.category_id == category_id)

    products = query.order_by(Product.id.asc()).all()

    items = []
    low_stock_count = 0
    out_of_stock_count = 0

    for p in products:
        if p.stock_quantity == 0:
            status_label = "Hết hàng"
            status_code = "OUT_OF_STOCK"
            out_of_stock_count += 1
            low_stock_count += 1
        elif p.stock_quantity <= threshold:
            status_label = "Sắp hết"
            status_code = "LOW_STOCK"
            low_stock_count += 1
        else:
            status_label = "Còn hàng"
            status_code = "IN_STOCK"

        # Lọc theo tình trạng nếu có yêu cầu
        if status_filter:
            sf = status_filter.strip().upper()
            if sf in ("OUT_OF_STOCK", "HẾT HÀNG", "HET HANG") and status_code != "OUT_OF_STOCK":
                continue
            elif sf in ("LOW_STOCK", "SẮP HẾT", "SAP HET") and status_code != "LOW_STOCK":
                continue
            elif sf in ("IN_STOCK", "CÒN HÀNG", "CON HANG") and status_code != "IN_STOCK":
                continue

        category_name = p.category.name if p.category else None

        items.append({
            "product_id": p.id,
            "name": p.name,
            "category_id": p.category_id,
            "category_name": category_name,
            "price": p.price,
            "stock_quantity": p.stock_quantity,
            "is_visible": p.is_visible,
            "status": status_label,
            "status_code": status_code,
            "threshold": threshold,
        })

    total = len(items)
    start = (page - 1) * page_size
    paginated_items = items[start:start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "threshold": threshold,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "items": paginated_items,
    }


def get_low_stock_alerts(
    db: Session,
    threshold: int = DEFAULT_LOW_STOCK_THRESHOLD,
) -> Dict[str, Any]:
    """Lấy danh sách các sản phẩm có tồn kho thấp hơn hoặc bằng ngưỡng cảnh báo (FR-036).

    Args:
        db: Database session.
        threshold: Ngưỡng cảnh báo.

    Returns:
        Dictionary chứa tổng số sản phẩm chạm ngưỡng và danh sách chi tiết.
    """
    products = (
        db.query(Product)
        .options(joinedload(Product.category))
        .filter(Product.stock_quantity <= threshold)
        .order_by(Product.stock_quantity.asc())
        .all()
    )

    items = []
    for p in products:
        items.append({
            "product_id": p.id,
            "product_name": p.name,
            "category_name": p.category.name if p.category else None,
            "current_stock": p.stock_quantity,
            "threshold": threshold,
            "is_out_of_stock": p.stock_quantity == 0,
            "is_low_stock": 0 < p.stock_quantity <= threshold,
        })

    return {
        "threshold": threshold,
        "total_low_stock_products": len(items),
        "items": items,
    }


def import_stock(
    db: Session,
    product_id: int,
    quantity_to_add: int,
    note: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Nghiệp vụ nhập thêm hàng vào kho cho một sản phẩm (FR-034).

    Args:
        db: Database session.
        product_id: ID sản phẩm.
        quantity_to_add: Số lượng nhập thêm (> 0).
        note: Ghi chú / lý do nhập hàng.
        user_id: ID người thực hiện (Admin/Staff).

    Returns:
        Thông tin kết quả nhập hàng và số lượng tồn mới.
    """
    try:
        stock_log = increase_stock(
            db=db,
            product_id=product_id,
            quantity=quantity_to_add,
            change_type=ChangeType.IMPORT,
            user_id=user_id,
            note=note or "Nhập thêm hàng",
        )
        db.commit()
        return {
            "message": "Nhập hàng thành công",
            "product_id": product_id,
            "added_quantity": quantity_to_add,
            "stock_before": stock_log.stock_before,
            "stock_after": stock_log.stock_after,
        }
    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


def adjust_stock(
    db: Session,
    product_id: int,
    new_stock_quantity: int,
    note: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Nghiệp vụ điều chỉnh tồn kho có lý do / kiểm kê (FR-034).

    Args:
        db: Database session.
        product_id: ID sản phẩm.
        new_stock_quantity: Số lượng tồn kho mới sau kiểm kê (>= 0).
        note: Lý do điều chỉnh kiểm kê.
        user_id: ID người thực hiện.

    Returns:
        Thông tin kết quả điều chỉnh và độ chênh lệch.
    """
    if new_stock_quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số lượng tồn kho mới không được âm (>= 0)",
        )

    try:
        product = (
            db.query(Product)
            .filter(Product.id == product_id)
            .with_for_update()
            .first()
        )
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy sản phẩm với ID {product_id}",
            )

        stock_before = product.stock_quantity
        quantity_change = new_stock_quantity - stock_before

        if quantity_change == 0:
            return {
                "message": "Số lượng tồn kho không thay đổi",
                "product_id": product_id,
                "stock_before": stock_before,
                "stock_after": new_stock_quantity,
                "quantity_change": 0,
            }

        product.stock_quantity = new_stock_quantity

        # Ghi log điều chỉnh (ADJUST)
        stock_log = StockLog(
            product_id=product_id,
            created_by=user_id,
            change_type=ChangeType.ADJUST,
            quantity_change=quantity_change,
            stock_before=stock_before,
            stock_after=new_stock_quantity,
            note=note or "Điều chỉnh tồn kho do kiểm kê",
        )
        db.add(stock_log)
        db.commit()

        return {
            "message": "Cập nhật tồn kho thành công",
            "product_id": product_id,
            "stock_before": stock_before,
            "stock_after": new_stock_quantity,
            "quantity_change": quantity_change,
        }
    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


def get_product_stock_logs(
    db: Session,
    product_id: int,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Lấy danh sách nhật ký thay đổi tồn kho của một sản phẩm có phân trang.

    Args:
        db: Database session.
        product_id: ID sản phẩm.
        page: Số trang.
        page_size: Số dòng mỗi trang.

    Returns:
        Dictionary chứa tổng số bản ghi và danh sách log chi tiết.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sản phẩm với ID {product_id}",
        )

    query = db.query(StockLog).filter(StockLog.product_id == product_id)
    total = query.count()
    logs = (
        query.order_by(StockLog.created_at.desc(), StockLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        {
            "id": log.id,
            "product_id": log.product_id,
            "order_id": log.order_id,
            "created_by": log.created_by,
            "change_type": log.change_type.value if hasattr(log.change_type, "value") else str(log.change_type),
            "quantity_change": log.quantity_change,
            "stock_before": log.stock_before,
            "stock_after": log.stock_after,
            "note": log.note,
            "created_at": log.created_at,
        }
        for log in logs
    ]

    return {
        "product_id": product_id,
        "product_name": product.name,
        "current_stock": product.stock_quantity,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }
