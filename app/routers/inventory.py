from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import Product, StockLog, User, Category
from app.models.stock_log import ChangeType
from app.dependencies.auth import require_admin_or_staff
from app.schemas.stock_log import DEFAULT_LOW_STOCK_THRESHOLD

router = APIRouter(prefix="/admin/inventory", tags=["Inventory"])


# --- SCHEMAS ---

class StockImportRequest(BaseModel):
    quantity_to_add: int = Field(
        ..., gt=0, description="Số lượng nhập thêm phải lớn hơn 0"
    )
    note: Optional[str] = Field(None, description="Lý do hoặc ghi chú nhập hàng")


class StockAdjustRequest(BaseModel):
    new_stock_quantity: int = Field(
        ..., ge=0, description="Số lượng tồn kho mới sau kiểm kê (>= 0)"
    )
    note: Optional[str] = Field(None, description="Lý do điều chỉnh kho")


class StockUpdateRequest(BaseModel):
    """Schema cập nhật tồn kho linh hoạt theo FR-034."""
    quantity_to_add: Optional[int] = Field(
        None, gt=0, description="Số lượng nhập thêm (nếu nhập hàng)"
    )
    new_stock_quantity: Optional[int] = Field(
        None, ge=0, description="Số lượng tồn kho mới sau kiểm kê (nếu đặt lại số lượng)"
    )
    note: Optional[str] = Field(None, description="Ghi chú / lý do cập nhật tồn kho")


class StockLogItemResponse(BaseModel):
    id: int
    product_id: int
    order_id: Optional[int] = None
    created_by: Optional[int] = None
    change_type: str
    quantity_change: int
    stock_before: int
    stock_after: int
    note: Optional[str] = None
    created_at: Optional[datetime] = None


# --- CÁC HÀM XỬ LÝ DÙNG CHUNG (Dành cho module Đặt hàng và Đơn hàng gọi) ---

def decrease_stock(
    db: Session,
    product_id: int,
    quantity: int,
    order_id: int | None = None,
    user_id: int | None = None,
    note: str | None = None,
) -> StockLog:
    """Hàm trừ kho dùng chung cho module Đặt hàng (FR-035, BR-10).

    Chạy trong transaction hiện tại của DB. Không cho phép tồn âm.
    Pessimistic locking (with_for_update) chống race condition.
    """
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số lượng trừ kho phải lớn hơn 0",
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

    # Ghi log biến động kho vào stock_logs
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
    """Hàm hoàn kho/tăng kho dùng chung (khi hủy đơn hàng hoặc nhập kho, v.v.).

    Chạy trong transaction hiện tại.
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


# --- CÁC API QUẢN LÝ KHO DÀNH CHO ADMIN / STAFF (FR-033, FR-034, FR-036) ---

@router.get("", summary="Theo dõi số lượng tồn kho (FR-033, FR-036)")
def get_inventory_list(
    keyword: Optional[str] = Query(None, description="Tìm theo tên sản phẩm"),
    category_id: Optional[int] = Query(None, description="Lọc theo danh mục"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Lọc theo tình trạng: IN_STOCK (Còn hàng), LOW_STOCK (Sắp hết), OUT_OF_STOCK (Hết hàng)",
    ),
    threshold: int = Query(
        DEFAULT_LOW_STOCK_THRESHOLD,
        ge=0,
        description="Ngưỡng cảnh báo sắp hết hàng (mặc định 5)",
    ),
    page: int = Query(1, ge=1, description="Trang hiện tại"),
    page_size: int = Query(20, ge=1, le=100, description="Số lượng mỗi trang"),
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Admin/Nhân viên xem tồn kho của tất cả sản phẩm (kể cả sản phẩm đang ẩn) (FR-033).

    Hỗ trợ tìm kiếm theo tên, lọc theo danh mục, lọc theo tình trạng tồn kho và cảnh báo sắp hết hàng (FR-036).
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


@router.get("/low-stock", summary="Cảnh báo sản phẩm sắp hết hàng (FR-036)")
def get_low_stock_alerts(
    threshold: int = Query(
        DEFAULT_LOW_STOCK_THRESHOLD,
        ge=0,
        description="Ngưỡng cảnh báo sắp hết hàng",
    ),
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Lấy danh sách các sản phẩm có tồn kho thấp hơn hoặc bằng ngưỡng cảnh báo (FR-036)."""
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


@router.put("/{product_id}/import", summary="Nhập thêm hàng cho sản phẩm (FR-034)")
def import_stock(
    product_id: int,
    payload: StockImportRequest,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Admin/Nhân viên cộng thêm số lượng nhập vào kho (FR-034).

    Luôn ghi nhận StockLog với loại IMPORT và mã người thực hiện.
    """
    try:
        stock_log = increase_stock(
            db=db,
            product_id=product_id,
            quantity=payload.quantity_to_add,
            change_type=ChangeType.IMPORT,
            user_id=current_user.id,
            note=payload.note or "Nhập thêm hàng",
        )
        db.commit()
        return {
            "message": "Nhập hàng thành công",
            "product_id": product_id,
            "added_quantity": payload.quantity_to_add,
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


@router.put("/{product_id}/adjust", summary="Điều chỉnh tồn kho có lý do / kiểm kê (FR-034)")
def adjust_stock(
    product_id: int,
    payload: StockAdjustRequest,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Admin/Nhân viên đặt lại số lượng tồn kho mới sau khi kiểm kê (đảm bảo không âm) (FR-034)."""
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
        new_stock = payload.new_stock_quantity
        quantity_change = new_stock - stock_before

        if quantity_change == 0:
            return {
                "message": "Số lượng tồn kho không thay đổi",
                "product_id": product_id,
                "stock_before": stock_before,
                "stock_after": new_stock,
                "quantity_change": 0,
            }

        product.stock_quantity = new_stock

        # Ghi log điều chỉnh (ADJUST)
        stock_log = StockLog(
            product_id=product_id,
            created_by=current_user.id,
            change_type=ChangeType.ADJUST,
            quantity_change=quantity_change,
            stock_before=stock_before,
            stock_after=new_stock,
            note=payload.note or "Điều chỉnh tồn kho do kiểm kê",
        )
        db.add(stock_log)
        db.commit()

        return {
            "message": "Cập nhật tồn kho thành công",
            "product_id": product_id,
            "stock_before": stock_before,
            "stock_after": new_stock,
            "quantity_change": quantity_change,
        }
    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{product_id}", summary="Cập nhật tồn kho linh hoạt (FR-034)")
def update_stock(
    product_id: int,
    payload: StockUpdateRequest,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Endpoint cập nhật tồn kho chung theo đặc tả SRS (PUT /api/admin/inventory/{product_id}).

    Hỗ trợ cả 2 chế độ:
    - Nhập thêm hàng: truyền `quantity_to_add`
    - Điều chỉnh kiểm kê: truyền `new_stock_quantity`
    """
    if payload.quantity_to_add is not None:
        import_req = StockImportRequest(
            quantity_to_add=payload.quantity_to_add,
            note=payload.note,
        )
        return import_stock(
            product_id=product_id,
            payload=import_req,
            current_user=current_user,
            db=db,
        )
    elif payload.new_stock_quantity is not None:
        adjust_req = StockAdjustRequest(
            new_stock_quantity=payload.new_stock_quantity,
            note=payload.note,
        )
        return adjust_stock(
            product_id=product_id,
            payload=adjust_req,
            current_user=current_user,
            db=db,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp 'quantity_to_add' để nhập thêm hàng hoặc 'new_stock_quantity' để điều chỉnh kho",
        )


@router.get("/{product_id}/logs", summary="Xem lịch sử biến động kho của sản phẩm (FR-034)")
def get_product_stock_logs(
    product_id: int,
    page: int = Query(1, ge=1, description="Trang hiện tại"),
    page_size: int = Query(20, ge=1, le=100, description="Số lượng mỗi trang"),
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Xem toàn bộ nhật ký thay đổi số lượng tồn kho của một sản phẩm."""
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
        StockLogItemResponse(
            id=log.id,
            product_id=log.product_id,
            order_id=log.order_id,
            created_by=log.created_by,
            change_type=log.change_type.value if hasattr(log.change_type, "value") else str(log.change_type),
            quantity_change=log.quantity_change,
            stock_before=log.stock_before,
            stock_after=log.stock_after,
            note=log.note,
            created_at=log.created_at,
        )
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
