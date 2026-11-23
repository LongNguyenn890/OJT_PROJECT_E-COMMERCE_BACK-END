from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=1, max_length=1000)

    @field_validator("comment")
    @classmethod
    def comment_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Vui lòng nhập nhận xét")
        return value


class ProductReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rating: int
    comment: str
    image_url: str | None = None
    created_at: datetime
    customer_name: str


class ProductReviewListResponse(BaseModel):
    average_rating: float = 0
    review_count: int = 0
    rating_distribution: dict[int, int] = Field(default_factory=dict)
    items: list[ProductReviewResponse] = Field(default_factory=list)


class MyProductReviewResponse(BaseModel):
    eligible: bool
    review: ProductReviewResponse | None = None
