"""Router quản lý tồn kho và biến động kho (Inventory Management Router).

Tài liệu đặc tả liên quan:
- FR-033: Theo dõi số lượng tồn kho (Xem tất cả sản phẩm, tìm kiếm, lọc danh mục, trạng thái còn/hết/sắp hết).
- FR-034: Cập nhật số lượng tồn kho (Nhập thêm hàng IMPORT hoặc Điều chỉnh sau kiểm kê ADJUST).
- FR-035: Kiểm tra tồn kho trước khi đặt hàng (Không cho phép tồn âm, thực hiện nguyên tử).
- FR-036: Cảnh báo sản phẩm sắp hết hàng (Dựa trên ngưỡng cấu hình, mặc định = 5).
- BR-05, BR-10, BR-14: Quy tắc nghiệp vụ về tính nguyên tử, hoàn kho và ngưỡng cảnh báo.
- Phân quyền: Toàn bộ API trong router này yêu cầu quyền Quản trị viên (ADMIN) hoặc Nhân viên (STAFF).
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.dependencies.auth import require_admin_or_staff
from app.schemas.stock_log import (
    DEFAULT_LOW_STOCK_THRESHOLD,
    StockImportRequest,
    StockAdjustRequest,
    StockUpdateRequest,
    StockOperationResponse,
    StockLogsPageResponse,
    InventoryListResponse,
    LowStockAlertResponse,
)
from app.service import inventory as inventory_service
from app.service.inventory import decrease_stock, increase_stock  # Re-export để các module khác có thể gọi

router = APIRouter(prefix="/admin/inventory", tags=["Inventory"])


@router.get(
    "",
    response_model=InventoryListResponse,
    summary="Theo dõi số lượng tồn kho toàn bộ sản phẩm (FR-033, FR-036)",
    description=(
        "Admin/Nhân viên theo dõi số lượng tồn kho của tất cả sản phẩm trong hệ thống (bao gồm cả sản phẩm đang ẩn).\n"
        "- **Chức năng**:\n"
        "  + Tìm kiếm theo tên sản phẩm (`keyword`).\n"
        "  + Lọc theo danh mục (`category_id`).\n"
        "  + Lọc theo tình trạng tồn kho (`status`: `IN_STOCK`, `LOW_STOCK`, `OUT_OF_STOCK`).\n"
        "  + Đánh giá trạng thái tồn kho dựa trên ngưỡng cảnh báo (`threshold`, mặc định: 5).\n"
        "  + Thống kê nhanh số lượng sản phẩm sắp hết (`low_stock_count`) và hết hàng (`out_of_stock_count`).\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`."
    ),
)
def get_inventory_list(
    keyword: Optional[str] = Query(None, description="Từ khóa tìm kiếm theo tên sản phẩm"),
    category_id: Optional[int] = Query(None, description="Lọc sản phẩm theo ID danh mục"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Lọc theo tình trạng: IN_STOCK (Còn hàng), LOW_STOCK (Sắp hết), OUT_OF_STOCK (Hết hàng)",
    ),
    threshold: int = Query(
        DEFAULT_LOW_STOCK_THRESHOLD,
        ge=0,
        description="Ngưỡng cảnh báo sắp hết hàng (mặc định = 5)",
    ),
    page: int = Query(1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Số lượng sản phẩm trên mỗi trang"),
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Admin/Nhân viên xem tồn kho của tất cả sản phẩm kèm bộ lọc và phân trang (FR-033)."""
    return inventory_service.get_inventory_list(
        db=db,
        keyword=keyword,
        category_id=category_id,
        status_filter=status_filter,
        threshold=threshold,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/low-stock",
    response_model=LowStockAlertResponse,
    summary="Cảnh báo danh sách sản phẩm sắp hết hàng (FR-036)",
    description=(
        "Lấy danh sách các sản phẩm có tồn kho thấp hơn hoặc bằng ngưỡng cảnh báo (`stock_quantity <= threshold`).\n"
        "- **Quy tắc**:\n"
        "  + Tồn kho = 0: Đánh dấu `is_out_of_stock = True` (Hết hàng).\n"
        "  + 0 < Tồn kho <= Ngưỡng: Đánh dấu `is_low_stock = True` (Sắp hết hàng).\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`."
    ),
)
def get_low_stock_alerts(
    threshold: int = Query(
        DEFAULT_LOW_STOCK_THRESHOLD,
        ge=0,
        description="Ngưỡng cảnh báo tồn kho (mặc định = 5)",
    ),
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Lấy danh sách các sản phẩm chạm ngưỡng cảnh báo tồn kho (FR-036)."""
    return inventory_service.get_low_stock_alerts(db=db, threshold=threshold)


@router.put(
    "/{product_id}/import",
    response_model=StockOperationResponse,
    summary="Nhập thêm hàng cho sản phẩm (FR-034)",
    description=(
        "Admin/Nhân viên nhập thêm một lượng hàng vào kho cho một sản phẩm cụ thể.\n"
        "- **Quy tắc**:\n"
        "  + `quantity_to_add` phải là số nguyên dương (> 0).\n"
        "  + Tồn kho mới = Tồn kho cũ + Số lượng nhập thêm.\n"
        "  + Tự động ghi nhật ký biến động kho `StockLog` với loại `IMPORT` và lưu ID người thực hiện.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`.\n"
        "- **Mã lỗi**: `404 Not Found` nếu sản phẩm không tồn tại; `400 Bad Request` nếu số lượng không hợp lệ."
    ),
)
def import_stock(
    product_id: int,
    payload: StockImportRequest,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Thực hiện nhập thêm hàng vào kho cho sản phẩm."""
    return inventory_service.import_stock(
        db=db,
        product_id=product_id,
        quantity_to_add=payload.quantity_to_add,
        note=payload.note,
        user_id=current_user.id,
    )


@router.put(
    "/{product_id}/adjust",
    response_model=StockOperationResponse,
    summary="Điều chỉnh tồn kho sau kiểm kê (FR-034)",
    description=(
        "Admin/Nhân viên đặt lại chính xác số lượng tồn kho thực tế sau khi kiểm kê kho định kỳ.\n"
        "- **Quy tắc**:\n"
        "  + `new_stock_quantity` phải là số nguyên không âm (>= 0).\n"
        "  + Độ chênh lệch `quantity_change = new_stock_quantity - stock_before`.\n"
        "  + Tự động ghi nhận `StockLog` với loại `ADJUST` kèm lý do giải trình.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`.\n"
        "- **Mã lỗi**: `404 Not Found` nếu sản phẩm không tồn tại; `400 Bad Request` nếu số lượng < 0."
    ),
)
def adjust_stock(
    product_id: int,
    payload: StockAdjustRequest,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Điều chỉnh lại số lượng tồn kho theo kết quả kiểm kê thực tế."""
    return inventory_service.adjust_stock(
        db=db,
        product_id=product_id,
        new_stock_quantity=payload.new_stock_quantity,
        note=payload.note,
        user_id=current_user.id,
    )


@router.put(
    "/{product_id}",
    response_model=StockOperationResponse,
    summary="Cập nhật tồn kho linh hoạt theo chuẩn SRS (FR-034)",
    description=(
        "Endpoint tổng hợp cập nhật tồn kho theo bảng đặc tả SRS: `PUT /api/admin/inventory/{product_id}`.\n"
        "- Hỗ trợ 2 chế độ tự động phân nhánh:\n"
        "  1. **Nhập thêm hàng**: Truyền trường `quantity_to_add` (> 0) -> Chuyển sang xử lý `IMPORT`.\n"
        "  2. **Kiểm kê kho**: Truyền trường `new_stock_quantity` (>= 0) -> Chuyển sang xử lý `ADJUST`.\n"
        "- **Mã lỗi**: `400 Bad Request` nếu không cung cấp một trong hai trường trên."
    ),
)
def update_stock(
    product_id: int,
    payload: StockUpdateRequest,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Cập nhật số lượng tồn kho linh hoạt (hỗ trợ cả nhập hàng và kiểm kê)."""
    if payload.quantity_to_add is not None:
        return inventory_service.import_stock(
            db=db,
            product_id=product_id,
            quantity_to_add=payload.quantity_to_add,
            note=payload.note,
            user_id=current_user.id,
        )
    elif payload.new_stock_quantity is not None:
        return inventory_service.adjust_stock(
            db=db,
            product_id=product_id,
            new_stock_quantity=payload.new_stock_quantity,
            note=payload.note,
            user_id=current_user.id,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp 'quantity_to_add' để nhập thêm hàng hoặc 'new_stock_quantity' để điều chỉnh kho",
        )


@router.get(
    "/{product_id}/logs",
    response_model=StockLogsPageResponse,
    summary="Xem lịch sử biến động kho của sản phẩm (FR-034, Audit Trail)",
    description=(
        "Xem toàn bộ nhật ký lịch sử thay đổi tồn kho của một sản phẩm (các lần nhập hàng, tạo đơn trừ kho, hủy đơn hoàn kho, kiểm kê).\n"
        "- **Sắp xếp**: Mới nhất lên đầu (`created_at DESC`).\n"
        "- **Hỗ trợ phân trang**: `page`, `page_size`.\n"
        "- **Quyền hạn yêu cầu**: `ADMIN` hoặc `STAFF`."
    ),
)
def get_product_stock_logs(
    product_id: int,
    page: int = Query(1, ge=1, description="Số trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Số dòng nhật ký mỗi trang"),
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Xem danh sách các lần biến động tồn kho của một sản phẩm kèm phân trang."""
    return inventory_service.get_product_stock_logs(
        db=db,
        product_id=product_id,
        page=page,
        page_size=page_size,
    )
