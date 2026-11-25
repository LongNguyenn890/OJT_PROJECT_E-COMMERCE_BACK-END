from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    """Yêu cầu gửi đánh giá & bình luận sản phẩm mới."""
    rating: int = Field(..., ge=1, le=5, examples=[5], description="Số sao đánh giá (từ 1 đến 5 sao)")
    comment: Optional[str] = Field(None, max_length=2000, examples=["Sản phẩm rất tốt, giao hàng nhanh!"], description="Nội dung bình luận nhận xét (không bắt buộc)")
    image_url: Optional[str] = Field(None, description="URL ảnh đính kèm (nếu có)")


class ReviewUpdate(BaseModel):
    """Chỉnh sửa nội dung đánh giá sản phẩm."""
    rating: Optional[int] = Field(None, ge=1, le=5, description="Số sao đánh giá mới (1-5)")
    comment: Optional[str] = Field(None, max_length=2000, description="Nội dung bình luận mới")
    image_url: Optional[str] = Field(None, description="URL ảnh đính kèm mới")


class ReviewReplyCreate(BaseModel):
    """Yêu cầu gửi phản hồi cho một bình luận."""
    content: str = Field(..., min_length=1, max_length=1000, examples=["Cảm ơn bạn đã tin tưởng ủng hộ ShopEase!"], description="Nội dung phản hồi")


class ReviewReplyUpdate(BaseModel):
    """Chỉnh sửa nội dung hoặc trạng thái ẩn/hiện của phản hồi."""
    content: Optional[str] = Field(None, min_length=1, max_length=1000, description="Nội dung phản hồi mới")
    is_hidden: Optional[bool] = Field(None, description="Trạng thái ẩn/hiện phản hồi (True: ẩn, False: hiện)")


class ReviewReplyResponse(BaseModel):
    """Thông tin phản hồi bình luận."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    review_id: int
    user_id: int
    author_name: str
    author_avatar: Optional[str] = None
    is_seller: bool = False
    is_hidden: bool = False
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class ReviewResponse(BaseModel):
    """Thông tin chi tiết một đánh giá sản phẩm kèm các phản hồi liên quan."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    user_id: int
    customer_name: str
    customer_avatar: Optional[str] = None
    rating: int
    comment: Optional[str] = None
    image_url: Optional[str] = None
    is_hidden: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    replies: List[ReviewReplyResponse] = []


class ProductRatingSummary(BaseModel):
    """Tóm tắt điểm số sao đánh giá của sản phẩm."""
    average_rating: float = Field(0.0, description="Số sao trung bình (làm tròn 1 chữ số thập phân)")
    review_count: int = Field(0, description="Tổng số lượt đánh giá của sản phẩm")
    rating_distribution: Dict[int, int] = Field(
        default_factory=lambda: {5: 0, 4: 0, 3: 0, 2: 0, 1: 0},
        description="Phân bố số lượng đánh giá theo từng mức sao 1-5"
    )


class ProductReviewPageResponse(BaseModel):
    """Danh sách đánh giá & bình luận sản phẩm phân trang kèm tóm tắt số sao."""
    total: int = Field(..., description="Tổng số đánh giá thỏa điều kiện")
    page: int = Field(1, description="Trang hiện tại")
    page_size: int = Field(20, description="Số lượng đánh giá trên mỗi trang")
    review_count: int = Field(0, description="Tổng số lượt đánh giá của sản phẩm")
    average_rating: float = Field(0.0, description="Số sao trung bình của sản phẩm")
    rating_distribution: Dict[int, int] = Field(
        default_factory=lambda: {5: 0, 4: 0, 3: 0, 2: 0, 1: 0},
        description="Số lượng đánh giá theo mức 1, 2, 3, 4, 5 sao"
    )
    items: List[ReviewResponse] = Field(default_factory=list, description="Danh sách các đánh giá")


class ReviewEligibilityResponse(BaseModel):
    """Kiểm tra quyền đánh giá sản phẩm của người dùng hiện tại."""
    eligible: bool = Field(..., description="True nếu người dùng có thể gửi đánh giá")
    review: Optional[ReviewResponse] = Field(None, description="Đánh giá đã gửi của người dùng (nếu có)")


class AdminReviewProductInfo(BaseModel):
    """Thông tin tóm tắt sản phẩm trong danh sách quản lý đánh giá."""
    id: int
    name: str
    sku: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[float] = None


class AdminReviewItem(BaseModel):
    """Chi tiết đánh giá dành cho Quản trị viên & Nhân viên quản lý và phản hồi."""
    id: int
    product_id: int
    product: AdminReviewProductInfo
    user_id: int
    customer_name: str
    customer_email: Optional[str] = None
    customer_avatar: Optional[str] = None
    rating: int
    comment: str
    image_url: Optional[str] = None
    is_hidden: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    replies: List[ReviewReplyResponse] = []
    has_seller_reply: bool = False
    reply_count: int = 0


class AdminReviewStats(BaseModel):
    """Thống kê tổng quan phục vụ trang quản lý đánh giá."""
    total_reviews: int = Field(0, description="Tổng số lượt đánh giá toàn hệ thống")
    unreplied_count: int = Field(0, description="Số đánh giá chưa có phản hồi từ Người bán")
    replied_count: int = Field(0, description="Số đánh giá đã có phản hồi từ Người bán")
    average_rating: float = Field(0.0, description="Điểm đánh giá trung bình toàn hệ thống")
    positive_percentage: float = Field(0.0, description="Tỷ lệ đánh giá tích cực (4-5 sao)")


class AdminReviewPageResponse(BaseModel):
    """Danh sách đánh giá phân trang dành cho trang quản lý Admin/Staff."""
    total: int
    page: int
    page_size: int
    stats: AdminReviewStats
    items: List[AdminReviewItem]

