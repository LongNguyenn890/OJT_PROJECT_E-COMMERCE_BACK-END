"""Router quản lý danh mục sản phẩm (Category Router).

Tài liệu đặc tả liên quan:
- FR-014: Thêm danh mục (Chỉ Admin và Staff; tên không rỗng, tên duy nhất BR-18).
- FR-015: Cập nhật danh mục (Chỉ Admin và Staff; kiểm tra tên duy nhất BR-18).
- FR-016: Xóa danh mục (Chỉ Admin và Staff; chặn xóa nếu danh mục còn sản phẩm BR-13).
- FR-017: Xem danh mục sản phẩm (Công khai cho mọi người dùng).
- Phân quyền:
  + Các thao tác thay đổi (Thêm, Sửa, Xóa): Bắt buộc tài khoản có quyền `ADMIN` hoặc `STAFF`.
  + Thao tác xem (GET): Công khai (khách hàng chưa đăng nhập vẫn xem được).
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import require_admin_or_staff
from app.models.user import User
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryDeleteResponse,
)
from app.service import category as category_service

router = APIRouter(prefix="/categories", tags=["Categories"])


# ==============================================================================
# 1. API CÔNG KHAI - XEM DANH MỤC (FR-017)
# ==============================================================================

@router.get(
    "",
    response_model=List[CategoryResponse],
    summary="Xem danh sách danh mục sản phẩm (FR-017)",
    description=(
        "Lấy toàn bộ danh sách danh mục sản phẩm trong hệ thống kèm số lượng sản phẩm (`product_count`).\n"
        "- **Hỗ trợ tìm kiếm**: Theo tên danh mục qua tham số query `keyword`.\n"
        "- **Quyền hạn**: Công khai (không yêu cầu đăng nhập)."
    ),
)
def get_categories(
    keyword: Optional[str] = Query(None, description="Từ khóa tìm kiếm theo tên danh mục"),
    db: Session = Depends(get_db),
):
    """Lấy danh sách tất cả các danh mục sản phẩm."""
    return category_service.get_all_categories(db=db, keyword=keyword)


@router.get(
    "/{id}",
    response_model=CategoryResponse,
    summary="Xem chi tiết một danh mục sản phẩm",
    description=(
        "Lấy thông tin chi tiết của một danh mục sản phẩm theo ID kèm số lượng sản phẩm thuộc danh mục đó.\n"
        "- **Mã lỗi**: `404 Not Found` nếu không tìm thấy ID danh mục.\n"
        "- **Quyền hạn**: Công khai."
    ),
)
def get_category_detail(
    id: int,
    db: Session = Depends(get_db),
):
    """Lấy thông tin chi tiết một danh mục theo ID."""
    return category_service.get_category_by_id(db=db, category_id=id)


# ==============================================================================
# 2. API QUẢN TRỊ - THÊM, SỬA, XÓA DANH MỤC (DÀNH CHO ADMIN & STAFF)
# ==============================================================================

@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm danh mục sản phẩm mới (FR-014)",
    description=(
        "Tạo mới một danh mục sản phẩm trong hệ thống.\n"
        "- **Quyền hạn**: Chỉ dành cho `ADMIN` hoặc `STAFF`.\n"
        "- **Quy tắc nghiệp vụ**:\n"
        "  + Tên danh mục không được để trống (BR-18).\n"
        "  + Tên danh mục là duy nhất trong hệ thống (BR-18).\n"
        "- **Mã lỗi**:\n"
        "  + `401 Unauthorized`: Chưa đăng nhập token.\n"
        "  + `403 Forbidden`: Người dùng là Customer thông thường.\n"
        "  + `409 Conflict`: Tên danh mục đã tồn tại trong CSDL."
    ),
)
def create_category(
    payload: CategoryCreate,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Tạo mới danh mục sản phẩm (yêu cầu quyền Admin hoặc Staff)."""
    return category_service.create_category(db=db, data=payload)


@router.put(
    "/{id}",
    response_model=CategoryResponse,
    summary="Cập nhật thông tin danh mục (FR-015)",
    description=(
        "Cập nhật tên hoặc mô tả của một danh mục sản phẩm hiện có.\n"
        "- **Quyền hạn**: Chỉ dành cho `ADMIN` hoặc `STAFF`.\n"
        "- **Quy tắc nghiệp vụ**:\n"
        "  + Danh mục phải tồn tại trong CSDL.\n"
        "  + Tên danh mục mới không được trùng với tên của danh mục khác (BR-18).\n"
        "- **Mã lỗi**:\n"
        "  + `404 Not Found`: Không tìm thấy danh mục với ID yêu cầu.\n"
        "  + `409 Conflict`: Tên mới bị trùng với danh mục khác đã tồn tại."
    ),
)
def update_category(
    id: int,
    payload: CategoryUpdate,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Cập nhật tên, mô tả danh mục (yêu cầu quyền Admin hoặc Staff)."""
    return category_service.update_category(db=db, category_id=id, data=payload)


@router.delete(
    "/{id}",
    response_model=CategoryDeleteResponse,
    summary="Xóa danh mục sản phẩm (FR-016)",
    description=(
        "Xóa một danh mục sản phẩm khỏi cơ sở dữ liệu.\n"
        "- **Quyền hạn**: Chỉ dành cho `ADMIN` hoặc `STAFF`.\n"
        "- **Quy tắc nghiệp vụ quan trọng**:\n"
        "  + **BR-13: Không được xóa danh mục còn sản phẩm**.\n"
        "  + Nếu danh mục vẫn còn sản phẩm liên kết, hệ thống sẽ từ chối và báo lỗi để bảo vệ toàn vẹn dữ liệu.\n"
        "- **Mã lỗi**:\n"
        "  + `404 Not Found`: Không tìm thấy danh mục.\n"
        "  + `400 Bad Request`: Danh mục còn sản phẩm (vi phạm BR-13).\n"
        "  + `403 Forbidden`: Người gọi không có quyền Admin hoặc Staff."
    ),
)
def delete_category(
    id: int,
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Xóa danh mục sản phẩm (yêu cầu quyền Admin hoặc Staff, chặn nếu còn sản phẩm)."""
    category_id = category_service.delete_category(db=db, category_id=id)
    return {
        "message": "Đã xóa danh mục thành công",
        "id": category_id,
    }
