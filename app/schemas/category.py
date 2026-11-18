"""Schemas cho phân hệ Quản lý danh mục sản phẩm (Category Schemas).

Tài liệu đặc tả liên quan:
- FR-014: Thêm danh mục (CategoryCreate: tên duy nhất BR-18, mô tả).
- FR-015: Cập nhật danh mục (CategoryUpdate).
- FR-016: Xóa danh mục (CategoryDeleteResponse).
- FR-017: Xem danh sách danh mục (CategoryResponse).
- BR-18: Tên danh mục là duy nhất và không được rỗng.
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Tên danh mục", examples=["Điện thoại"])
    description: str | None = Field(default=None, description="Mô tả danh mục", examples=["Các dòng điện thoại thông minh"])

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip() if v else ""
        if not trimmed:
            raise ValueError("Tên danh mục không được để trống hoặc chỉ chứa khoảng trắng")
        return trimmed


class CategoryCreate(CategoryBase):
    """Schema dữ liệu đầu vào khi tạo mới danh mục (FR-014)."""
    pass


class CategoryUpdate(BaseModel):
    """Schema dữ liệu đầu vào khi cập nhật danh mục (FR-015)."""
    name: str | None = Field(default=None, min_length=1, max_length=100, description="Tên danh mục mới")
    description: str | None = Field(default=None, description="Mô tả danh mục mới")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Tên danh mục không được để trống hoặc chỉ chứa khoảng trắng")
            return trimmed
        return v


class CategoryResponse(CategoryBase):
    """Schema dữ liệu phản hồi thông tin danh mục cho client."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    product_count: int | None = Field(default=None, description="Số lượng sản phẩm thuộc danh mục này")
    sold_count: int | None = Field(default=0, description="Tổng số lượng sản phẩm đã bán trong danh mục")
    buyer_count: int | None = Field(default=0, description="Tổng số khách hàng/lượt mua của danh mục")


class CategoryDeleteResponse(BaseModel):
    """Schema dữ liệu phản hồi sau khi xóa danh mục thành công."""
    message: str
    id: int
