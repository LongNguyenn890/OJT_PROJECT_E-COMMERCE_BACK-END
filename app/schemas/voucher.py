from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class VoucherTier(BaseModel):
    tier_id: str = Field(..., description="Mã định danh gói quy đổi")
    title: str = Field(..., description="Tiêu đề voucher")
    points_required: int = Field(..., description="Số điểm thưởng cần có")
    discount_amount: int = Field(..., description="Số tiền giảm giá (VNĐ)")
    min_order_value: int = Field(0, description="Giá trị đơn hàng tối thiểu áp dụng")


class RedeemVoucherRequest(BaseModel):
    tier_id: str = Field(..., description="Mã gói quy đổi: VOUCHER_20K, VOUCHER_50K, VOUCHER_100K, VOUCHER_150K")


class VoucherResponse(BaseModel):
    id: int
    code: str
    title: str
    discount_amount: int
    min_order_value: int = 0
    points_spent: int = 0
    is_used: int = 0
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RewardPointsInfoResponse(BaseModel):
    reward_points: int = Field(..., description="Số điểm thưởng hiện tại của người dùng")
    available_tiers: List[VoucherTier] = Field(..., description="Các gói voucher có thể đổi")
    vouchers: List[VoucherResponse] = Field(default=[], description="Danh sách các voucher đã đổi của người dùng")
