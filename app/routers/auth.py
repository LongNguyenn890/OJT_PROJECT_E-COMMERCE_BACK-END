"""Router xác thực và quản lý phiên người dùng (Authentication & Account Router).

Tài liệu đặc tả liên quan:
- FR-001: Đăng ký tài khoản người dùng mới (Mặc định vai trò CUSTOMER, trạng thái ACTIVE).
- FR-002: Đăng nhập hệ thống (Sinh mã JWT Token, kiểm tra tài khoản có bị khóa hay không).
- FR-003: Đăng xuất hệ thống (Hủy bỏ phiên làm việc của JWT token).
- FR-004: Xem thông tin tài khoản hiện tại (/auth/me).
"""
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
