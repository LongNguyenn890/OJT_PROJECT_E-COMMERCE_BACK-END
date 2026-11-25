"""Dịch vụ nghiệp vụ quản lý Đánh giá & Bình luận sản phẩm (Product Review & Comment Service).

Bao gồm:
 - Thêm mới đánh giá có số sao (1-5 sao) và hình ảnh
 - Thêm phản hồi cho bình luận (phản hồi của Người bán / Khách hàng)
 - Tính toán số sao trung bình của sản phẩm và phân bố đánh giá (1-5 sao)
 - Danh sách đánh giá phân trang kèm danh sách phản hồi lồng nhau
 - Kiểm tra điều kiện đánh giá của người dùng
 - Chỉnh sửa / Xóa đánh giá và phản hồi
"""

from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.product import Product
from app.models.review import ProductReview, ReviewReply
from app.models.user import Role, User
from app.schemas.review import (
    AdminReviewItem,
    AdminReviewPageResponse,
    AdminReviewProductInfo,
    AdminReviewStats,
    ProductRatingSummary,
    ProductReviewPageResponse,
    ReviewEligibilityResponse,
    ReviewReplyResponse,
    ReviewResponse,
)


def _format_reply_response(rep: ReviewReply) -> ReviewReplyResponse:
    """Định dạng phản hồi bình luận với tên tác giả phù hợp."""
    author_name = "ShopEase Official" if rep.is_seller else (rep.user.full_name if rep.user else "Khách hàng")
    author_avatar = rep.user.avatar if rep.user else None
    return ReviewReplyResponse(
        id=rep.id,
        review_id=rep.review_id,
        user_id=rep.user_id,
        author_name=author_name,
        author_avatar=author_avatar,
        is_seller=rep.is_seller,
        is_hidden=getattr(rep, "is_hidden", False),
        content=rep.content,
        created_at=rep.created_at,
        updated_at=getattr(rep, "updated_at", None),
    )


def _format_review_response(
    rev: ProductReview, include_hidden_replies: bool = False
) -> ReviewResponse:
    """Định dạng dữ liệu đánh giá sản phẩm kèm danh sách phản hồi."""
    customer_name = rev.user.full_name if rev.user else "Khách hàng"
    customer_avatar = rev.user.avatar if rev.user else None

    raw_replies = rev.replies or []
    if not include_hidden_replies:
        raw_replies = [rep for rep in raw_replies if not getattr(rep, "is_hidden", False)]

    formatted_replies = [_format_reply_response(rep) for rep in raw_replies]

    return ReviewResponse(
        id=rev.id,
        product_id=rev.product_id,
        user_id=rev.user_id,
        customer_name=customer_name,
        customer_avatar=customer_avatar,
        rating=rev.rating,
        comment=rev.comment,
        image_url=rev.image_url,
        is_hidden=getattr(rev, "is_hidden", False),
        created_at=rev.created_at,
        updated_at=rev.updated_at,
        replies=formatted_replies,
    )


def get_product_rating_summary(db: Session, product_id: int) -> ProductRatingSummary:
    """Tính toán số sao trung bình, tổng số lượt đánh giá và phân bố sao của sản phẩm (chỉ tính đánh giá không bị ẩn)."""
    reviews = (
        db.query(ProductReview.rating)
        .filter(
            ProductReview.product_id == product_id,
            ProductReview.is_hidden.is_(False),
        )
        .all()
    )
    count = len(reviews)
    distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}

    if count == 0:
        return ProductRatingSummary(
            average_rating=0.0,
            review_count=0,
            rating_distribution=distribution,
        )

    total_stars = 0
    for r in reviews:
        star = int(r.rating)
        if 1 <= star <= 5:
            distribution[star] = distribution.get(star, 0) + 1
            total_stars += star

    average_rating = round(total_stars / count, 1)

    return ProductRatingSummary(
        average_rating=average_rating,
        review_count=count,
        rating_distribution=distribution,
    )


def create_product_review(
    db: Session,
    product_id: int,
    user: User,
    rating: int,
    comment: str,
    image_url: Optional[str] = None,
) -> ReviewResponse:
    """Tạo mới hoặc cập nhật đánh giá sản phẩm của người dùng."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sản phẩm có ID {product_id}.",
        )

    if not (1 <= rating <= 5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Số sao đánh giá phải từ 1 đến 5 sao.",
        )

    comment_clean = (comment or "").strip()

    # Kiểm tra xem người dùng đã từng đánh giá sản phẩm này chưa
    existing = (
        db.query(ProductReview)
        .filter(ProductReview.product_id == product_id, ProductReview.user_id == user.id)
        .first()
    )

    if existing:
        # Cập nhật lại đánh giá hiện có
        existing.rating = rating
        existing.comment = comment_clean
        if image_url is not None:
            existing.image_url = image_url
        db.commit()
        db.refresh(existing)
        return _format_review_response(existing)

    new_review = ProductReview(
        product_id=product_id,
        user_id=user.id,
        rating=rating,
        comment=comment_clean,
        image_url=image_url,
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)
    return _format_review_response(new_review)


def get_product_reviews(
    db: Session,
    product_id: int,
    page: int = 1,
    page_size: int = 20,
    rating_filter: Optional[int] = None,
) -> ProductReviewPageResponse:
    """Lấy danh sách đánh giá & bình luận sản phẩm phân trang kèm tóm tắt điểm sao."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sản phẩm có ID {product_id}.",
        )

    summary = get_product_rating_summary(db, product_id)

    query = db.query(ProductReview).filter(
        ProductReview.product_id == product_id,
        ProductReview.is_hidden.is_(False),
    )
    if rating_filter and 1 <= rating_filter <= 5:
        query = query.filter(ProductReview.rating == rating_filter)

    total = query.count()
    reviews = (
        query.order_by(desc(ProductReview.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [_format_review_response(r, include_hidden_replies=False) for r in reviews]

    return ProductReviewPageResponse(
        total=total,
        page=page,
        page_size=page_size,
        review_count=summary.review_count,
        average_rating=summary.average_rating,
        rating_distribution=summary.rating_distribution,
        items=items,
    )


def get_user_review_eligibility(
    db: Session, product_id: int, user: User
) -> ReviewEligibilityResponse:
    """Kiểm tra người dùng hiện tại có đủ điều kiện hoặc đã đánh giá sản phẩm hay chưa."""
    existing = (
        db.query(ProductReview)
        .filter(ProductReview.product_id == product_id, ProductReview.user_id == user.id)
        .first()
    )

    if existing:
        return ReviewEligibilityResponse(
            eligible=True,
            review=_format_review_response(existing),
        )

    # Người dùng đã đăng nhập có thể đánh giá sản phẩm
    return ReviewEligibilityResponse(
        eligible=True,
        review=None,
    )


def delete_user_product_review(
    db: Session, product_id: int, user: User
) -> Dict[str, Any]:
    """Xóa đánh giá của chính người dùng đối với sản phẩm cụ thể (Chỉ ADMIN/STAFF có quyền)."""
    user_role = (user.role.value if hasattr(user.role, "value") else str(user.role)).upper()
    if user_role not in ["ADMIN", "STAFF"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ có Quản trị viên (ADMIN) hoặc Nhân viên (STAFF) mới có quyền xóa bình luận đánh giá.",
        )

    review = (
        db.query(ProductReview)
        .filter(ProductReview.product_id == product_id, ProductReview.user_id == user.id)
        .first()
    )
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bạn chưa có đánh giá nào cho sản phẩm này.",
        )

    db.delete(review)
    db.commit()
    return {"message": "Đã xóa đánh giá sản phẩm thành công.", "product_id": product_id}


def delete_review_by_id(db: Session, review_id: int, user: User) -> Dict[str, Any]:
    """Xóa đánh giá theo ID (Chỉ ADMIN/STAFF có quyền)."""
    user_role = (user.role.value if hasattr(user.role, "value") else str(user.role)).upper()
    if user_role not in ["ADMIN", "STAFF"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ có Quản trị viên (ADMIN) hoặc Nhân viên (STAFF) mới có quyền xóa bình luận đánh giá.",
        )

    review = db.query(ProductReview).filter(ProductReview.id == review_id).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy đánh giá với ID {review_id}.",
        )

    db.delete(review)
    db.commit()
    return {"message": "Đã xóa bình luận đánh giá thành công.", "review_id": review_id}


def create_review_reply(
    db: Session,
    review_id: int,
    user: User,
    content: str,
) -> ReviewReplyResponse:
    """Tạo mới một phản hồi cho đánh giá/bình luận đã có."""
    review = db.query(ProductReview).filter(ProductReview.id == review_id).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bình luận đánh giá có ID {review_id} để phản hồi.",
        )

    content_clean = content.strip()
    if not content_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nội dung phản hồi không được để trống.",
        )

    user_role = (user.role.value if hasattr(user.role, "value") else str(user.role)).upper()
    is_seller = user_role in ["ADMIN", "STAFF"]

    new_reply = ReviewReply(
        review_id=review_id,
        user_id=user.id,
        content=content_clean,
        is_seller=is_seller,
    )
    db.add(new_reply)
    db.commit()
    db.refresh(new_reply)

    return _format_reply_response(new_reply)


def delete_reply_by_id(db: Session, reply_id: int, user: User) -> Dict[str, Any]:
    """Xóa phản hồi bình luận (Chỉ ADMIN/STAFF có quyền)."""
    user_role = (user.role.value if hasattr(user.role, "value") else str(user.role)).upper()
    if user_role not in ["ADMIN", "STAFF"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ có Quản trị viên (ADMIN) hoặc Nhân viên (STAFF) mới có quyền xóa phản hồi bình luận.",
        )

    reply = db.query(ReviewReply).filter(ReviewReply.id == reply_id).first()
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phản hồi với ID {reply_id}.",
        )

    db.delete(reply)
    db.commit()
    return {"message": "Đã xóa phản hồi thành công.", "reply_id": reply_id}


def update_review_reply(
    db: Session,
    reply_id: int,
    user: User,
    content: Optional[str] = None,
    is_hidden: Optional[bool] = None,
) -> ReviewReplyResponse:
    """Chỉnh sửa nội dung hoặc trạng thái ẩn/hiện của phản hồi (Người tạo có quyền sửa nội dung, chỉ ADMIN/STAFF mới được ẩn/hiện)."""
    reply = db.query(ReviewReply).filter(ReviewReply.id == reply_id).first()
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phản hồi với ID {reply_id}.",
        )

    user_role = (user.role.value if hasattr(user.role, "value") else str(user.role)).upper()
    is_admin_or_staff = user_role in ["ADMIN", "STAFF"]

    if not is_admin_or_staff and reply.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền chỉnh sửa phản hồi của người dùng khác.",
        )

    if content is not None:
        c_clean = content.strip()
        if not c_clean:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Nội dung phản hồi không được để trống.",
            )
        reply.content = c_clean

    if is_hidden is not None:
        if not is_admin_or_staff:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ có Quản trị viên (ADMIN) hoặc Nhân viên (STAFF) mới có quyền ẩn/hiện phản hồi.",
            )
        reply.is_hidden = is_hidden

    db.commit()
    db.refresh(reply)
    return _format_reply_response(reply)


def toggle_reply_visibility(db: Session, reply_id: int, user: User) -> ReviewReplyResponse:
    """Bật / Tắt trạng thái ẩn của phản hồi (Chỉ ADMIN/STAFF có quyền)."""
    user_role = (user.role.value if hasattr(user.role, "value") else str(user.role)).upper()
    if user_role not in ["ADMIN", "STAFF"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ có Quản trị viên (ADMIN) hoặc Nhân viên (STAFF) mới có quyền ẩn/hiện phản hồi bình luận.",
        )

    reply = db.query(ReviewReply).filter(ReviewReply.id == reply_id).first()
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy phản hồi với ID {reply_id}.",
        )

    reply.is_hidden = not getattr(reply, "is_hidden", False)
    db.commit()
    db.refresh(reply)
    return _format_reply_response(reply)


def toggle_review_visibility(db: Session, review_id: int, user: User) -> Dict[str, Any]:
    """Bật / Tắt trạng thái ẩn của bình luận đánh giá (Chỉ ADMIN/STAFF có quyền)."""
    user_role = (user.role.value if hasattr(user.role, "value") else str(user.role)).upper()
    if user_role not in ["ADMIN", "STAFF"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ có Quản trị viên (ADMIN) hoặc Nhân viên (STAFF) mới có quyền ẩn/hiện bình luận đánh giá.",
        )

    review = db.query(ProductReview).filter(ProductReview.id == review_id).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy đánh giá với ID {review_id}.",
        )

    review.is_hidden = not getattr(review, "is_hidden", False)
    db.commit()
    db.refresh(review)
    return {
        "message": f"Đã {'ẩn' if review.is_hidden else 'bỏ ẩn'} đánh giá thành công.",
        "review_id": review_id,
        "is_hidden": review.is_hidden,
    }


def get_all_reviews_admin(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    rating: Optional[int] = None,
    has_replies: Optional[bool] = None,
    keyword: Optional[str] = None,
    product_id: Optional[int] = None,
) -> AdminReviewPageResponse:
    """Lấy danh sách đánh giá toàn hệ thống kèm thống kê phản hồi dành cho Quản trị viên & Nhân viên."""
    # 1. Thống kê tổng quan toàn bộ đánh giá trong hệ thống
    all_reviews_ratings = db.query(ProductReview.id, ProductReview.rating).all()
    total_reviews = len(all_reviews_ratings)
    total_stars = sum(int(r.rating) for r in all_reviews_ratings)
    average_rating = round(total_stars / total_reviews, 1) if total_reviews > 0 else 0.0
    positive_count = sum(1 for r in all_reviews_ratings if int(r.rating) >= 4)
    positive_pct = round(positive_count * 100.0 / total_reviews, 1) if total_reviews > 0 else 0.0

    # Đếm số lượng đánh giá đã có phản hồi từ Người bán (Seller / Shop)
    replied_query = db.query(ProductReview.id).filter(
        ProductReview.replies.any(ReviewReply.is_seller == True)
    )
    replied_count = replied_query.count()
    unreplied_count = max(0, total_reviews - replied_count)

    stats = AdminReviewStats(
        total_reviews=total_reviews,
        unreplied_count=unreplied_count,
        replied_count=replied_count,
        average_rating=average_rating,
        positive_percentage=positive_pct,
    )

    # 2. Xây dựng truy vấn danh sách có lọc & tìm kiếm
    query = (
        db.query(ProductReview)
        .options(
            selectinload(ProductReview.user),
            selectinload(ProductReview.product).selectinload(Product.product_images),
            selectinload(ProductReview.replies).selectinload(ReviewReply.user),
        )
    )

    if product_id:
        query = query.filter(ProductReview.product_id == product_id)

    if rating and 1 <= rating <= 5:
        query = query.filter(ProductReview.rating == rating)

    if has_replies is True:
        query = query.filter(ProductReview.replies.any(ReviewReply.is_seller == True))
    elif has_replies is False:
        query = query.filter(~ProductReview.replies.any(ReviewReply.is_seller == True))

    if keyword and keyword.strip():
        k = f"%{keyword.strip()}%"
        query = (
            query.join(ProductReview.product)
            .outerjoin(ProductReview.user)
            .filter(
                or_(
                    ProductReview.comment.ilike(k),
                    Product.name.ilike(k),
                    Product.sku.ilike(k),
                    User.full_name.ilike(k),
                    User.email.ilike(k),
                )
            )
        )

    total_filtered = query.count()
    reviews = (
        query.order_by(desc(ProductReview.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: List[AdminReviewItem] = []
    for r in reviews:
        # Ảnh sản phẩm đại diện
        prod_img: Optional[str] = None
        if r.product and r.product.product_images:
            prod_img = r.product.product_images[0].image_url

        prod_info = AdminReviewProductInfo(
            id=r.product.id if r.product else r.product_id,
            name=r.product.name if r.product else "Sản phẩm không xác định",
            sku=r.product.sku if r.product else None,
            image_url=prod_img,
            price=float(r.product.price) if (r.product and r.product.price) else None,
        )

        rep_list = r.replies or []
        formatted_replies = [_format_reply_response(rep) for rep in rep_list]
        has_seller_rep = any(rep.is_seller for rep in rep_list)

        items.append(
            AdminReviewItem(
                id=r.id,
                product_id=r.product_id,
                product=prod_info,
                user_id=r.user_id,
                customer_name=r.user.full_name if r.user else "Khách hàng",
                customer_email=r.user.email if r.user else None,
                customer_avatar=r.user.avatar if r.user else None,
                rating=r.rating,
                comment=r.comment or "",
                image_url=r.image_url,
                is_hidden=getattr(r, "is_hidden", False),
                created_at=r.created_at,
                updated_at=r.updated_at,
                replies=formatted_replies,
                has_seller_reply=has_seller_rep,
                reply_count=len(rep_list),
            )
        )

    return AdminReviewPageResponse(
        total=total_filtered,
        page=page,
        page_size=page_size,
        stats=stats,
        items=items,
    )

