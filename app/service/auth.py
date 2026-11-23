import uuid
from pathlib import Path
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from app.schemas import UserCreate, UserUpdate
from app.models import User, Role, Status
from app.core import hash_password, verify_password, create_access_token, blacklist_token
from app.core.config import settings

ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_AVATAR_SIZE = 100 * 1024 * 1024  # 100MB
AVATAR_DIR = Path("uploads/avatars")
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

def create_user(db: Session, user: UserCreate):
    if any(c.isspace() for c in user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu không được chứa khoảng trắng",
        )

    existing_email = db.query(User).filter(User.email == user.email).first()
    
    if existing_email:
        return "EXISTED_EMAIL"
    
    hashed_password = hash_password(user.password)
    
    new_user = User(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        password_hash=hashed_password,
        role=getattr(user, "role", None) or Role.CUSTOMER,
        status=getattr(user, "status", None) or Status.ACTIVE,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

def login_account(email: str, password: str, db: Session) -> str:
    user_db = db.query(User).filter(User.email == email).first()
    
    if not user_db:
        return "INVALID_EMAIL"
    
    if user_db.status in (Status.LOCK, "LOCKED"):
        return "ACCOUNT_IS_LOCKED"
    
    if not verify_password(password, user_db.password_hash):
        return "INVALID_PASSWORD"
    
    token_data = {
        "id": user_db.id,
        "full_name": user_db.full_name,
        "email": user_db.email,
        "phone": user_db.phone,
        "avatar": user_db.avatar,
        "role": user_db.role.value if hasattr(user_db.role, "value") else str(user_db.role),
        "status": user_db.status.value if hasattr(user_db.status, "value") else str(user_db.status),
    }
    
    access_token = create_access_token(token_data)
    
    return access_token


def logout_account(token: str) -> bool:
    if token:
        blacklist_token(token)
        return True
    return False


def update_user_avatar(db: Session, user: User, file: UploadFile) -> User:
    """Tải lên và cập nhật ảnh đại diện (avatar) cho người dùng."""
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn file ảnh để tải lên",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{file.filename}' không đúng định dạng. Hệ thống chỉ hỗ trợ JPG, JPEG, PNG, WEBP.",
        )

    content = file.file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ảnh tải lên không có dữ liệu (rỗng)",
        )

    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File có dung lượng ({len(content) / (1024 * 1024):.2f}MB) vượt quá giới hạn tối đa cho phép là 100MB.",
        )

    # Dọn dẹp file avatar cũ trên ổ đĩa nếu trước đó đã có
    if user.avatar and user.avatar.startswith("/uploads/avatars/"):
        old_filename = Path(user.avatar).name
        old_file_path = AVATAR_DIR / old_filename
        if old_file_path.exists() and old_file_path.is_file():
            try:
                old_file_path.unlink()
            except Exception:
                pass

    # Lưu file vật lý mới
    unique_filename = f"avatar_{user.id}_{uuid.uuid4().hex[:8]}{ext}"
    saved_path = AVATAR_DIR / unique_filename
    saved_path.write_bytes(content)

    # Cập nhật thông tin avatar trong CSDL
    user.avatar = f"/uploads/avatars/{unique_filename}"
    db.commit()
    db.refresh(user)

    return user


def delete_user_avatar(db: Session, user: User) -> User:
    """Xóa ảnh đại diện hiện tại của người dùng."""
    if user.avatar:
        if user.avatar.startswith("/uploads/avatars/"):
            old_filename = Path(user.avatar).name
            old_file_path = AVATAR_DIR / old_filename
            if old_file_path.exists() and old_file_path.is_file():
                try:
                    old_file_path.unlink()
                except Exception:
                    pass
        user.avatar = None
        db.commit()
        db.refresh(user)

    return user


def update_user_profile(db: Session, user: User, data: UserUpdate) -> User:
    """Cập nhật thông tin hồ sơ người dùng (họ tên, sđt, avatar url, mật khẩu)."""
    if data.full_name is not None:
        name = data.full_name.strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Họ tên không được để trống",
            )
        user.full_name = name

    if data.phone is not None:
        phone = data.phone.strip()
        if len(phone) < 10 or len(phone) > 15:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Số điện thoại phải từ 10 đến 15 ký tự",
            )
        user.phone = phone

    if data.avatar is not None:
        avatar_val = data.avatar.strip()
        user.avatar = avatar_val if avatar_val else None

    if data.password is not None:
        new_pwd = data.password
        if any(c.isspace() for c in new_pwd):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu mới không được chứa khoảng trắng",
            )
        if len(new_pwd.strip()) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu mới phải có ít nhất 6 ký tự",
            )

        # Bắt buộc phải có mật khẩu hiện tại để xác thực
        current_pwd = getattr(data, "current_password", None)
        if not current_pwd or not current_pwd.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vui lòng nhập mật khẩu hiện tại để xác thực đổi mật khẩu",
            )

        if any(c.isspace() for c in current_pwd):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu hiện tại không được chứa khoảng trắng",
            )

        from app.core.security import verify_password
        if not verify_password(current_pwd, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu hiện tại không chính xác",
            )

        if current_pwd == new_pwd:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu mới không được trùng với mật khẩu hiện tại",
            )

        user.password_hash = hash_password(new_pwd)

    db.commit()
    db.refresh(user)

    return user


    
