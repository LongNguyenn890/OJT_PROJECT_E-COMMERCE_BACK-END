from fastapi import Depends, APIRouter, status, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas import UserCreate, UserLogin, UserResponse, TokenResponse
from app.service.auth import create_user, login_account, logout_account
from app.dependencies import get_current_user, get_current_token

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_account(data: UserCreate, db: Session = Depends(get_db)):
    new_user = create_user(db, data)
    
    if new_user == "EXISTED_EMAIL":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã tồn tại"
        )
        
    return new_user


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    result = login_account(data.email, data.password, db)
    
    if result in ("INVALID_EMAIL", "INVALID_PASSWORD"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác",
        )
        
    if result == "ACCOUNT_IS_LOCKED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị khóa",
        )
        
    return {"access_token": result, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout(
    token: str = Depends(get_current_token),
    current_user: User = Depends(get_current_user),
):
    logout_account(token)
    return {"message": "Đăng xuất thành công"}
