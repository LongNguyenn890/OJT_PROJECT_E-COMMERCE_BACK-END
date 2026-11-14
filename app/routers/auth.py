"""Router xác thực và quản lý phiên người dùng (Authentication & Account Router).

Tài liệu đặc tả liên quan:
- FR-001: Đăng ký tài khoản người dùng mới (Mặc định vai trò CUSTOMER, trạng thái ACTIVE).
- FR-002: Đăng nhập hệ thống (Sinh mã JWT Token, kiểm tra tài khoản có bị khóa hay không).
- FR-003: Đăng xuất hệ thống (Hủy bỏ phiên làm việc của JWT token).
- FR-004: Xem thông tin tài khoản hiện tại (/auth/me).
"""
from fastapi import Depends, APIRouter, status, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas import UserCreate, UserLogin, UserResponse, TokenResponse
from app.service.auth import create_user, login_account, logout_account
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
    
    if result in ("INVALID_EMAIL", "INVALID_PASSWORD"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác",
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
