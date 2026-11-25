"""ROUTER ĐÁNH GIÁ & PHẢN HỒI BÌNH LUẬN SẢN PHẨM (REVIEWS & COMMENTS API)
Cung cấp các API:
 - POST /api/products/{product_id}/reviews : Gửi đánh giá sản phẩm (số sao 1-5, bình luận, ảnh đính kèm)
 - GET  /api/products/{product_id}/reviews : Lấy danh sách đánh giá phân trang, kèm số sao trung bình và phản hồi
 - GET  /api/products/{product_id}/reviews/mine : Xem đánh giá của người dùng hiện tại
 - DELETE /api/products/{product_id}/reviews/mine : Xóa đánh giá của chính mình
 - POST /api/reviews/{review_id}/replies  : Gửi phản hồi cho một bình luận (Người bán hoặc Khách hàng)
 - DELETE /api/reviews/{review_id}       : Xóa đánh giá theo ID (Chủ sở hữu hoặc Quản trị viên)
 - DELETE /api/replies/{reply_id}        : Xóa phản hồi theo ID (Chủ sở hữu hoặc Quản trị viên)
 - Các bí danh tương đương với /comments để tương thích linh hoạt.
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, require_admin_or_staff
from app.models.user import User
from app.schemas.review import (
    AdminReviewPageResponse,
    ProductReviewPageResponse,
    ReviewCreate,
    ReviewEligibilityResponse,
    ReviewReplyCreate,
    ReviewReplyResponse,
    ReviewReplyUpdate,
    ReviewResponse,
)
from app.service import review as review_service

router = APIRouter(tags=["Reviews & Comments"])

UPLOAD_DIR = Path("uploads/reviews")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


async def _save_upload_image(file: UploadFile) -> str:
    """Xác thực và lưu file ảnh đánh giá sản phẩm tải lên."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng ảnh không được hỗ trợ ({ext}). Chỉ chấp nhận JPG, JPEG, PNG, WEBP, GIF.",
        )

    # Đọc nội dung để kiểm tra dung lượng
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dung lượng ảnh vượt quá 5MB. Vui lòng chọn ảnh nhỏ hơn.",
        )

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = UPLOAD_DIR / unique_filename

    with open(dest_path, "wb") as f:
        f.write(contents)

    return f"uploads/reviews/{unique_filename}"


# ==============================================================
# 1. API QUẢN LÝ TỔNG HỢP ĐÁNH GIÁ (DÀNH CHO ADMIN & STAFF)
# ==============================================================

@router.get(
    "/reviews",
    response_model=AdminReviewPageResponse,
    summary="Quản lý toàn bộ đánh giá & phản hồi (Admin/Staff)",
    description=(
        "API dành cho Quản trị viên và Nhân viên để xem danh sách toàn bộ đánh giá trong hệ thống.\n"
        "- Hỗ trợ lọc theo số sao (`rating`: 1..5)\n"
        "- Lọc theo trạng thái phản hồi (`has_replies`: true = Đã phản hồi, false = Chưa phản hồi)\n"
        "- Lọc theo sản phẩm (`product_id`)\n"
        "- Tìm kiếm đa năng theo từ khóa (`keyword`): tên khách hàng, email, nội dung bình luận, tên sản phẩm, mã SKU\n"
        "- Đi kèm các chỉ số thống kê (`stats`): Tổng số đánh giá, chưa phản hồi, đã phản hồi, điểm trung bình, tỷ lệ tích cực."
    ),
)
def list_all_reviews_admin(
    page: int = Query(1, ge=1, description="Số trang (bắt đầu từ 1)"),
    page_size: int = Query(15, ge=1, le=100, description="Số lượng đánh giá mỗi trang"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Lọc theo mức số sao (1-5)"),
    has_replies: Optional[bool] = Query(None, description="Lọc theo trạng thái: true (đã phản hồi), false (chưa phản hồi)"),
    keyword: Optional[str] = Query(None, description="Tìm theo tên khách, email, nhận xét hoặc sản phẩm"),
    product_id: Optional[int] = Query(None, description="Lọc theo ID sản phẩm"),
    current_user: User = Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    """Lấy danh sách đánh giá toàn hệ thống kèm thống kê dành cho Admin & Staff."""
    return review_service.get_all_reviews_admin(
        db=db,
        page=page,
        page_size=page_size,
        rating=rating,
        has_replies=has_replies,
        keyword=keyword,
        product_id=product_id,
    )


# ==============================================================
# 2. API ĐÁNH GIÁ SẢN PHẨM (REVIEWS / COMMENTS)
# ==============================================================

@router.get(
    "/products/{product_id}/reviews",
    response_model=ProductReviewPageResponse,
    summary="Lấy danh sách đánh giá & bình luận của sản phẩm",
    description=(
        "Lấy toàn bộ đánh giá phân trang của sản phẩm kèm theo:\n"
        "- **Số sao trung bình** (`average_rating`, e.g. 4.8 / 5.0)\n"
        "- **Tổng số lượt đánh giá** (`review_count`)\n"
        "- **Phân bố số sao** (`rating_distribution`: số lượng đánh giá 1, 2, 3, 4, 5 sao)\n"
        "- **Danh sách phản hồi lồng nhau** (`replies`) cho từng bình luận.\n"
        "- Hỗ trợ lọc theo số sao cụ thể (`rating` = 1..5)."
    ),
)
@router.get("/products/{product_id}/comments", response_model=ProductReviewPageResponse, include_in_schema=False)
def get_product_reviews(
    product_id: int,
    page: int = Query(1, ge=1, description="Số trang (bắt đầu từ 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Số lượng đánh giá mỗi trang"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Lọc theo mức số sao (1-5)"),
    db: Session = Depends(get_db),
):
    """Lấy danh sách đánh giá công khai của sản phẩm."""
    return review_service.get_product_reviews(
        db=db,
        product_id=product_id,
        page=page,
        page_size=page_size,
        rating_filter=rating,
    )


@router.post(
    "/products/{product_id}/reviews",
    response_model=ReviewResponse,
    summary="Gửi đánh giá & bình luận sản phẩm (kèm số sao 1-5)",
    description=(
        "Khách hàng đã đăng nhập gửi đánh giá cho sản phẩm.\n"
        "- Hỗ trợ cả định dạng JSON (`application/json`) lẫn tải ảnh kèm (`multipart/form-data`).\n"
        "- `rating`: Số sao đánh giá từ 1 đến 5 sao.\n"
        "- `comment`: Nội dung nhận xét, trải nghiệm về sản phẩm.\n"
        "- `image` / `image_url`: Ảnh chụp sản phẩm thực tế đính kèm (tùy chọn)."
    ),
)
@router.post("/products/{product_id}/comments", response_model=ReviewResponse, include_in_schema=False)
async def create_product_review(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tạo mới hoặc cập nhật đánh giá sản phẩm (hỗ trợ cả JSON và Multipart Form)."""
    content_type = request.headers.get("content-type", "").lower()
    saved_image_url: Optional[str] = None
    rating: int = 5
    comment: str = ""

    if "multipart/form-data" in content_type:
        form_data = await request.form()
        try:
            rating = int(form_data.get("rating") or 5)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Số sao đánh giá (rating) không hợp lệ, phải là số nguyên từ 1 đến 5.",
            )
        comment = str(form_data.get("comment") or "").strip()

        # Kiểm tra file ảnh tải lên
        file_obj = form_data.get("image")
        if isinstance(file_obj, UploadFile) and file_obj.filename:
            saved_image_url = await _save_upload_image(file_obj)
        elif form_data.get("image_url"):
            saved_image_url = str(form_data.get("image_url")).strip()
    else:
        # Nhận dữ liệu dạng JSON
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dữ liệu gửi lên không đúng định dạng JSON hoặc Form-data.",
            )
        try:
            rating = int(body.get("rating") or 5)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Số sao đánh giá phải là số nguyên từ 1 đến 5.",
            )
        comment = str(body.get("comment") or body.get("content") or "").strip()
        saved_image_url = body.get("image_url")

    return review_service.create_product_review(
        db=db,
        product_id=product_id,
        user=current_user,
        rating=rating,
        comment=comment,
        image_url=saved_image_url,
    )


@router.get(
    "/products/{product_id}/reviews/mine",
    response_model=ReviewEligibilityResponse,
    summary="Kiểm tra trạng thái đánh giá sản phẩm của người dùng hiện tại",
    description="Trả về đánh giá đã gửi của người dùng (nếu có) và trạng thái hợp lệ để đánh giá.",
)
def get_my_review_status(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xem đánh giá của chính người dùng hiện tại."""
    return review_service.get_user_review_eligibility(
        db=db, product_id=product_id, user=current_user
    )


@router.delete(
    "/products/{product_id}/reviews/mine",
    summary="Xóa đánh giá của chính người dùng trên sản phẩm này",
    description="Chỉ Quản trị viên (ADMIN) hoặc Nhân viên (STAFF) có quyền xóa.",
)
def delete_my_product_review(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff),
):
    """Xóa đánh giá của người dùng hiện tại trên sản phẩm."""
    return review_service.delete_user_product_review(
        db=db, product_id=product_id, user=current_user
    )


@router.delete(
    "/reviews/{review_id}",
    summary="Xóa một đánh giá / bình luận theo ID",
    description="Chỉ Quản trị viên (ADMIN) hoặc Nhân viên (STAFF) có quyền xóa.",
)
@router.delete("/comments/{review_id}", include_in_schema=False)
def delete_review_by_id(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff),
):
    """Xóa đánh giá sản phẩm theo ID."""
    return review_service.delete_review_by_id(
        db=db, review_id=review_id, user=current_user
    )


# ==============================================================
# 2. API PHẢN HỒI BÌNH LUẬN (REPLY COMMENTS)
# ==============================================================

@router.post(
    "/reviews/{review_id}/replies",
    response_model=ReviewReplyResponse,
    summary="Gửi phản hồi cho một bình luận / đánh giá",
    description=(
        "Gửi phản hồi thảo luận cho bình luận đánh giá.\n"
        "- Nếu người gửi là `ADMIN` hoặc `STAFF`, hệ thống sẽ gắn nhãn **ShopEase Official (Người bán)**.\n"
        "- Nếu người gửi là `CUSTOMER`, hệ thống sẽ hiển thị tên khách hàng."
    ),
)
@router.post("/comments/{review_id}/replies", response_model=ReviewReplyResponse, include_in_schema=False)
def create_review_reply(
    review_id: int,
    payload: ReviewReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gửi phản hồi cho một đánh giá bình luận."""
    return review_service.create_review_reply(
        db=db,
        review_id=review_id,
        user=current_user,
        content=payload.content,
    )


@router.delete(
    "/replies/{reply_id}",
    summary="Xóa phản hồi bình luận theo ID",
    description="Chỉ Quản trị viên (ADMIN) hoặc Nhân viên (STAFF) có quyền xóa.",
)
def delete_reply_by_id(
    reply_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff),
):
    """Xóa phản hồi bình luận theo ID."""
    return review_service.delete_reply_by_id(
        db=db, reply_id=reply_id, user=current_user
    )


@router.put(
    "/replies/{reply_id}",
    response_model=ReviewReplyResponse,
    summary="Chỉnh sửa nội dung hoặc trạng thái phản hồi",
    description="Chủ sở hữu phản hồi hoặc Quản trị viên (ADMIN/STAFF) có thể chỉnh sửa nội dung phản hồi.",
)
@router.patch("/replies/{reply_id}", response_model=ReviewReplyResponse, include_in_schema=False)
def update_reply_by_id(
    reply_id: int,
    payload: ReviewReplyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chỉnh sửa phản hồi bình luận."""
    return review_service.update_review_reply(
        db=db,
        reply_id=reply_id,
        user=current_user,
        content=payload.content,
        is_hidden=payload.is_hidden,
    )


@router.patch(
    "/replies/{reply_id}/visibility",
    response_model=ReviewReplyResponse,
    summary="Bật / Tắt trạng thái ẩn phản hồi",
    description="Chỉ Quản trị viên (ADMIN) hoặc Nhân viên (STAFF) có thể ẩn hoặc bỏ ẩn phản hồi.",
)
@router.put("/replies/{reply_id}/hide", response_model=ReviewReplyResponse, include_in_schema=False)
def toggle_reply_visibility(
    reply_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff),
):
    """Bật / Tắt trạng thái ẩn phản hồi."""
    return review_service.toggle_reply_visibility(
        db=db, reply_id=reply_id, user=current_user
    )


@router.patch(
    "/reviews/{review_id}/visibility",
    summary="Bật / Tắt trạng thái ẩn bình luận đánh giá",
    description="Chỉ Quản trị viên (ADMIN) hoặc Nhân viên (STAFF) có thể ẩn hoặc bỏ ẩn đánh giá.",
)
@router.put("/reviews/{review_id}/hide", include_in_schema=False)
def toggle_review_visibility(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff),
):
    """Bật / Tắt trạng thái ẩn bình luận đánh giá."""
    return review_service.toggle_review_visibility(
        db=db, review_id=review_id, user=current_user
    )
