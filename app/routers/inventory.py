from datetime import datetime
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db
from models import Product, StockLog, User

router = APIRouter(prefix="/api/admin/inventory", tags=["Inventory"])

# --- ENUMS & SCHEMAS ---
class ChangeTypeEnum(str, Enum):
  INITIAL = "INITIAL"
  IMPORT = "IMPORT"
  ADJUST = "ADJUST"
  ORDER = "ORDER"
  CANCEL = "CANCEL"

class StockImportRequest(BaseModel):
  quantity_to_add: int = Field(
      ..., gt=0, description="Số lượng nhập thêm phải lớn hơn 0"
  )
  note: str | None = Field(None, description="Lý do hoặc ghi chú nhập hàng")


class StockAdjustRequest(BaseModel):
  new_stock_quantity: int = Field(
      ..., ge=0, description="Số lượng tồn kho mới sau kiểm kê (>= 0)"
  )
  note: str | None = Field(None, description="Lý do điều chỉnh kho")


# --- CÁC HÀM XỬ LÝ DÙNG CHUNG (Dành cho module Đặt hàng và Đơn hàng gọi) ---


def decrease_stock(
    db: Session,
    product_id: int,
    quantity: int,
    order_id: int | None = None,
    user_id: int | None = None,
):
  """Hàm trừ kho dùng chung cho module Đặt hàng (FR-035, BR-10).

  Chạy trong transaction hiện tại của DB. Không cho phép tồn âm.
  """
  # Khóa dòng sản phẩm trong CSDL để tránh xung đột đồng thời (Race Condition / Pessimistic Locking)
  product = (
      db.query(Product).filter(Product.id == product_id).with_for_update().first()
  )

  if not product:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Không tìm thấy sản phẩm với ID {product_id}",
    )

  stock_before = product.stock_quantity

  # Kiểm tra tồn kho (BR-10, BR-04)
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
      change_type=ChangeTypeEnum.ORDER,
      quantity_change=-quantity,
      stock_before=stock_before,
      stock_after=stock_after,
      note=f"Trừ kho cho đơn hàng #{order_id}" if order_id else "Trừ kho",
  )
  db.add(stock_log)
  # Lưu ý: db.commit() sẽ do hàm gọi ở tầng cao hơn (hoặc transaction chung của tạo đơn) thực hiện.


def increase_stock(
    db: Session,
    product_id: int,
    quantity: int,
    change_type: ChangeTypeEnum = ChangeTypeEnum.CANCEL,
    order_id: int | None = None,
    user_id: int | None = None,
    note: str | None = None,
):
  """Hàm hoàn kho/tăng kho dùng chung (khi hủy đơn hàng hoặc nhập kho, v.v.).

  Chạy trong transaction hiện tại.
  """
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


# --- CÁC API QUẢN LÝ KHO DÀNH CHO ADMIN (FR-033, FR-034) ---


@router.get("", summary="Theo dõi số lượng tồn kho (FR-033)")
def get_inventory_list(db: Session = Depends(get_db)):
  """Admin xem tồn kho của tất cả sản phẩm (kể cả sản phẩm đang ẩn)."""
  products = db.query(Product).all()
  result = []
  for p in products:
    # Xác định trạng thái tồn kho dựa theo quy tắc cảnh báo (BR-14: ngưỡng mặc định = 10)
    threshold = 10
    if p.stock_quantity == 0:
      status_label = "Hết hàng"
    elif p.stock_quantity <= threshold:
      status_label = "Sắp hết"
    else:
      status_label = "Còn hàng"

    result.append({
        "product_id": p.id,
        "name": p.name,
        "category_id": p.category_id,
        "price": p.price,
        "stock_quantity": p.stock_quantity,
        "is_visible": p.is_visible,
        "status": status_label,
    })
  return {"total": len(result), "items": result}


@router.put("/{product_id}/import", summary="Nhập thêm hàng cho sản phẩm (FR-034)")
def import_stock(
    product_id: int,
    payload: StockImportRequest,
    # current_admin: User = Depends(get_current_admin), # Thêm xác thực Admin theo FR-006
    db: Session = Depends(get_db),
):
  """Admin cộng thêm số lượng nhập vào kho.

  Luôn ghi nhận StockLog với loại IMPORT.
  """
  try:
    # Gọi hàm tăng kho trong transaction
    increase_stock(
        db=db,
        product_id=product_id,
        quantity=payload.quantity_to_add,
        change_type=ChangeTypeEnum.IMPORT,
        user_id=1,  # Thay thế bằng ID của Admin thực tế từ token
        note=payload.note or "Nhập thêm hàng",
    )
    db.commit()
    return {
        "message": "Nhập hàng thành công",
        "product_id": product_id,
        "added_quantity": payload.quantity_to_add,
    }
  except Exception as e:
    db.rollback()
    if isinstance(e, HTTPException):
      raise e
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
    )


@router.put(
    "/{product_id}/adjust", summary="Điều chỉnh tồn kho có lý do / kiểm kê (FR-034)"
)
def adjust_stock(
    product_id: int,
    payload: StockAdjustRequest,
    db: Session = Depends(get_db),
):
  """Admin đặt lại số lượng tồn kho mới sau khi kiểm kê (đảm bảo không âm)."""
  try:
    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .with_for_update()
        .first()
    )
    if not product:
      raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sản phẩm"
      )

    stock_before = product.stock_quantity
    new_stock = payload.new_stock_quantity
    quantity_change = new_stock - stock_before

    if quantity_change == 0:
      return {"message": "Số lượng tồn kho không thay đổi", "stock": stock_before}

    product.stock_quantity = new_stock

    # Ghi log điều chỉnh (ADJUST)
    stock_log = StockLog(
        product_id=product_id,
        created_by=1,  # ID Admin
        change_type=ChangeTypeEnum.ADJUST,
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
    }
  except Exception as e:
    db.rollback()
    if isinstance(e, HTTPException):
      raise e
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
    )