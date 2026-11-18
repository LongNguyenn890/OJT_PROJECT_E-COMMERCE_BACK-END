"""Router xác thực và quản lý phiên người dùng (Authentication & Account Router).

Tài liệu đặc tả liên quan:
- FR-001: Đăng ký tài khoản người dùng mới (Mặc định vai trò CUSTOMER, trạng thái ACTIVE).
- FR-002: Đăng nhập hệ thống (Sinh mã JWT Token, kiểm tra tài khoản có bị khóa hay không).
- FR-003: Đăng xuất hệ thống (Hủy bỏ phiên làm việc của JWT token).
- FR-004: Xem thông tin tài khoản hiện tại (/auth/me).
"""
from datetime import datetime, timedelta
import uuid
from typing import List
from fastapi import Depends, APIRouter, status, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    UserUpdate,
    AvatarResponse,
    AddressCreate,
    AddressUpdate,
    AddressResponse,
    VoucherTier,
    RedeemVoucherRequest,
    VoucherResponse,
    RewardPointsInfoResponse,
)
from app.service.auth import (
    create_user,
    login_account,
    logout_account,
    update_user_avatar,
    delete_user_avatar,
    update_user_profile,
)
from app.dependencies import get_current_user, get_current_token

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký tài khoản người dùng mới (FR-001)",
    description=(
        "Đăng ký tài khoản khách hàng mới vào hệ thống.\n"
        "- **Dữ liệu đầu vào**: Họ tên, email hợp lệ, số điện thoại, mật khẩu (tối thiểu 6 ký tự).\n"
        "- **Mặc định**: Vai trò `CUSTOMER`, trạng thái `ACTIVE`.\n"
        "- **Mã lỗi**: `409 Conflict` nếu email đã được đăng ký trước đó; `422 Unprocessable Entity` nếu sai định dạng dữ liệu."
    ),
)
def register_account(data: UserCreate, db: Session = Depends(get_db)):
    """Tạo mới tài khoản người dùng trong cơ sở dữ liệu."""
    new_user = create_user(db, data)
    
    if new_user == "EXISTED_EMAIL":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được sử dụng trong hệ thống",
        )
        
    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Đăng nhập tài khoản (FR-002)",
    description=(
        "Xác thực email và mật khẩu của người dùng, trả về mã định danh JWT Access Token.\n"
        "- **Mã lỗi**:\n"
        "  + `401 Unauthorized`: Sai thông tin email hoặc mật khẩu.\n"
        "  + `403 Forbidden`: Tài khoản đang ở trạng thái bị khóa (`LOCKED`)."
    ),
)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Xác thực thông tin đăng nhập và trả về access token."""
    result = login_account(data.email, data.password, db)
    
    if result == "INVALID_EMAIL":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại",
        )
        
    if result == "INVALID_PASSWORD":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mật khẩu không chính xác",
        )
        
    if result == "ACCOUNT_IS_LOCKED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị khóa, vui lòng liên hệ quản trị viên",
        )
        
    return {"access_token": result, "token_type": "bearer"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Xem thông tin tài khoản hiện tại (FR-004)",
    description=(
        "Lấy toàn bộ thông tin cá nhân của tài khoản đang đăng nhập thông qua Bearer Token.\n"
        "- **Quyền hạn**: Người dùng đã đăng nhập.\n"
        "- **Mã lỗi**: `401 Unauthorized` nếu chưa gửi token hoặc token hết hạn/không hợp lệ."
    ),
)
def get_me(current_user: User = Depends(get_current_user)):
    """Trả về thông tin hồ sơ của người dùng hiện tại."""
    return current_user


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Cập nhật thông tin tài khoản cá nhân",
    description=(
        "Cập nhật thông tin hồ sơ của tài khoản đang đăng nhập (họ tên, số điện thoại, đường dẫn avatar, mật khẩu mới).\n"
        "- **Quyền hạn**: Người dùng đã đăng nhập.\n"
        "- **Mã lỗi**: `400 Bad Request` nếu dữ liệu cập nhật không hợp lệ; `401 Unauthorized` nếu chưa đăng nhập."
    ),
)
def update_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cập nhật thông tin tài khoản của người dùng hiện tại."""
    return update_user_profile(db=db, user=current_user, data=payload)


@router.post(
    "/me/avatar",
    response_model=UserResponse,
    summary="Tải lên và cập nhật ảnh đại diện (Avatar)",
    description=(
        "Người dùng tải lên một file ảnh để làm ảnh đại diện cá nhân.\n"
        "- **Định dạng cho phép**: JPG, JPEG, PNG, WEBP.\n"
        "- **Giới hạn dung lượng**: Tối đa 100MB.\n"
        "- **Xử lý**: Hệ thống tự động lưu file vào thư mục `/uploads/avatars/`, xóa file avatar cũ (nếu có) và cập nhật đường dẫn vào hồ sơ.\n"
        "- **Quyền hạn**: Người dùng đã đăng nhập.\n"
        "- **Mã lỗi**: `400 Bad Request` nếu sai định dạng, file rỗng hoặc vượt quá 100MB; `401 Unauthorized` nếu chưa đăng nhập."
    ),
)
def upload_avatar(
    file: UploadFile = File(..., description="File ảnh đại diện (JPG, PNG, WEBP, tối đa 100MB)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload và cập nhật ảnh đại diện cho người dùng hiện tại."""
    return update_user_avatar(db=db, user=current_user, file=file)


@router.delete(
    "/me/avatar",
    response_model=AvatarResponse,
    summary="Xóa ảnh đại diện cá nhân",
    description=(
        "Xóa bỏ ảnh đại diện hiện tại của người dùng và dọn dẹp file vật lý trên máy chủ.\n"
        "- **Quyền hạn**: Người dùng đã đăng nhập.\n"
        "- **Mã lỗi**: `401 Unauthorized` nếu chưa đăng nhập."
    ),
)
def remove_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa ảnh đại diện của người dùng hiện tại."""
    delete_user_avatar(db=db, user=current_user)
    return AvatarResponse(message="Xóa ảnh đại diện thành công", avatar=None)


@router.post(
    "/logout",
    summary="Đăng xuất tài khoản (FR-003)",
    description=(
        "Đăng xuất khỏi phiên làm việc hiện tại và thu hồi hiệu lực của token trên client/blacklist.\n"
        "- **Quyền hạn**: Người dùng đã đăng nhập."
    ),
)
def logout(
    token: str = Depends(get_current_token),
    current_user: User = Depends(get_current_user),
):
    """Đăng xuất người dùng và hủy phiên token."""
    logout_account(token)
    return {"message": "Đăng xuất thành công"}


# ==========================================================
# CÁC API QUẢN LÝ SỔ ĐỊA CHỈ NHẬN HÀNG (ADDRESS BOOK)
# ==========================================================
@router.get(
    "/me/addresses",
    response_model=List[AddressResponse],
    summary="Lấy danh sách địa chỉ nhận hàng của người dùng",
)
def get_my_addresses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy toàn bộ địa chỉ trong sổ địa chỉ của tài khoản đang đăng nhập."""
    from app.models.address import Address
    return (
        db.query(Address)
        .filter(Address.user_id == current_user.id)
        .order_by(Address.is_default.desc(), Address.id.desc())
        .all()
    )


@router.post(
    "/me/addresses",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm địa chỉ nhận hàng mới",
)
def create_my_address(
    payload: AddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Thêm một địa chỉ mới vào sổ địa chỉ cá nhân."""
    from app.models.address import Address

    existing_count = db.query(Address).filter(Address.user_id == current_user.id).count()
    is_default = payload.is_default

    # Nếu là địa chỉ đầu tiên thì mặc định là default
    if existing_count == 0:
        is_default = 1
    elif is_default == 1:
        # Bỏ mặc định các địa chỉ cũ
        db.query(Address).filter(Address.user_id == current_user.id).update({"is_default": 0})
        db.commit()

    new_addr = Address(
        user_id=current_user.id,
        receiver_name=payload.receiver_name.strip(),
        phone=payload.phone.strip(),
        province=payload.province.strip(),
        ward=payload.ward.strip(),
        street_detail=payload.street_detail.strip() if payload.street_detail else None,
        is_default=is_default,
    )
    db.add(new_addr)
    db.commit()
    db.refresh(new_addr)
    return new_addr


@router.put(
    "/me/addresses/{address_id}",
    response_model=AddressResponse,
    summary="Chỉnh sửa thông tin địa chỉ nhận hàng",
)
def update_my_address(
    address_id: int,
    payload: AddressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cập nhật thông tin một địa chỉ đã có của tài khoản hiện tại."""
    from app.models.address import Address

    addr = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == current_user.id)
        .first()
    )
    if not addr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy địa chỉ trong tài khoản của bạn",
        )

    if payload.is_default == 1:
        db.query(Address).filter(Address.user_id == current_user.id).update({"is_default": 0})
        addr.is_default = 1
    elif payload.is_default == 0:
        # Kiểm tra xem có địa chỉ khác không trước khi bỏ mặc định
        other_exists = db.query(Address).filter(Address.user_id == current_user.id, Address.id != address_id).first()
        if other_exists:
            addr.is_default = 0
            other_exists.is_default = 1

    if payload.receiver_name is not None:
        addr.receiver_name = payload.receiver_name.strip()
    if payload.phone is not None:
        addr.phone = payload.phone.strip()
    if payload.province is not None:
        addr.province = payload.province.strip()
    if payload.ward is not None:
        addr.ward = payload.ward.strip()
    if payload.street_detail is not None:
        addr.street_detail = payload.street_detail.strip()

    db.commit()
    db.refresh(addr)
    return addr


@router.delete(
    "/me/addresses/{address_id}",
    summary="Xóa địa chỉ nhận hàng",
)
def delete_my_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa một địa chỉ khỏi sổ địa chỉ cá nhân."""
    from app.models.address import Address

    addr = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == current_user.id)
        .first()
    )
    if not addr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy địa chỉ để xóa",
        )

    was_default = addr.is_default
    db.delete(addr)
    db.commit()

    # Nếu xóa địa chỉ mặc định, tự động gán địa chỉ còn lại đầu tiên làm mặc định
    if was_default:
        remaining = (
            db.query(Address)
            .filter(Address.user_id == current_user.id)
            .first()
        )
        if remaining:
            remaining.is_default = 1
            db.commit()

    return {"message": "Xóa địa chỉ thành công", "deleted_id": address_id}


@router.patch(
    "/me/addresses/{address_id}/default",
    response_model=AddressResponse,
    summary="Thiết lập địa chỉ làm mặc định",
)
def set_default_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đặt địa chỉ làm địa chỉ nhận hàng mặc định."""
    from app.models.address import Address

    addr = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == current_user.id)
        .first()
    )
    if not addr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy địa chỉ",
        )

    db.query(Address).filter(Address.user_id == current_user.id).update({"is_default": 0})
    addr.is_default = 1
    db.commit()
    db.refresh(addr)
    return addr


# ==========================================================
# CÁC API QUẢN LÝ ĐIỂM THƯỞNG & QUY ĐỔI MÃ GIẢM GIÁ (VOUCHERS)
# ==========================================================
AVAILABLE_VOUCHER_TIERS = [
    {
        "tier_id": "VOUCHER_20K",
        "title": "Voucher giảm 20.000₫",
        "points_required": 100,
        "discount_amount": 20000,
        "min_order_value": 100000,
    },
    {
        "tier_id": "VOUCHER_50K",
        "title": "Voucher giảm 50.000₫",
        "points_required": 200,
        "discount_amount": 50000,
        "min_order_value": 250000,
    },
    {
        "tier_id": "VOUCHER_100K",
        "title": "Voucher giảm 100.000₫",
        "points_required": 350,
        "discount_amount": 100000,
        "min_order_value": 500000,
    },
    {
        "tier_id": "VOUCHER_150K",
        "title": "Voucher giảm 150.000₫",
        "points_required": 500,
        "discount_amount": 150000,
        "min_order_value": 700000,
    },
]


@router.get(
    "/me/reward-points",
    response_model=RewardPointsInfoResponse,
    summary="Xem số điểm thưởng và các gói quy đổi mã giảm giá",
)
def get_my_reward_points(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy số điểm thưởng hiện tại, danh sách các gói voucher có thể đổi và voucher đã sở hữu."""
    from app.models.voucher import Voucher

    vouchers = (
        db.query(Voucher)
        .filter(Voucher.user_id == current_user.id)
        .order_by(Voucher.id.desc())
        .all()
    )
    return {
        "reward_points": getattr(current_user, "reward_points", 0) or 0,
        "available_tiers": AVAILABLE_VOUCHER_TIERS,
        "vouchers": vouchers,
    }


@router.post(
    "/me/redeem-voucher",
    response_model=VoucherResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Quy đổi điểm thưởng lấy mã giảm giá",
)
def redeem_voucher(
    payload: RedeemVoucherRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quy đổi điểm thưởng của tài khoản để nhận mã giảm giá áp dụng khi thanh toán."""
    from app.models.voucher import Voucher

    tier = next((t for t in AVAILABLE_VOUCHER_TIERS if t["tier_id"] == payload.tier_id), None)
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gói voucher '{payload.tier_id}' không hợp lệ hoặc đã hết hạn áp dụng.",
        )

    current_points = getattr(current_user, "reward_points", 0) or 0
    required_points = tier["points_required"]

    if current_points < required_points:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bạn không đủ điểm thưởng để quy đổi gói này. Bạn hiện có {current_points} điểm (cần {required_points} điểm).",
        )

    # Trừ điểm thưởng của tài khoản
    current_user.reward_points = current_points - required_points

    # Sinh mã voucher ngẫu nhiên độc nhất
    code_suffix = uuid.uuid4().hex[:6].upper()
    discount_k = tier["discount_amount"] // 1000
    voucher_code = f"SE{discount_k}K-{code_suffix}"

    # Hạn sử dụng: 30 ngày kể từ lúc quy đổi
    expires_at = datetime.now() + timedelta(days=30)

    new_voucher = Voucher(
        code=voucher_code,
        title=tier["title"],
        discount_amount=tier["discount_amount"],
        min_order_value=tier["min_order_value"],
        points_spent=required_points,
        user_id=current_user.id,
        is_used=0,
        expires_at=expires_at,
    )
    db.add(new_voucher)
    db.commit()
    db.refresh(new_voucher)
    db.refresh(current_user)

    return new_voucher


@router.get(
    "/me/vouchers",
    response_model=List[VoucherResponse],
    summary="Danh sách mã giảm giá đã quy đổi của người dùng",
)
def get_my_vouchers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy toàn bộ danh sách mã giảm giá mà người dùng hiện tại đã quy đổi."""
    from app.models.voucher import Voucher

    return (
        db.query(Voucher)
        .filter(Voucher.user_id == current_user.id)
        .order_by(Voucher.id.desc())
        .all()
    )


