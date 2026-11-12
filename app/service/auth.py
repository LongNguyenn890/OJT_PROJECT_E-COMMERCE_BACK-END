from sqlalchemy.orm import Session
from app.schemas import UserCreate
from app.models import User, Role, Status
from app.core import hash_password, verify_password, create_access_token, blacklist_token
from app.core.config import settings

def create_user(db: Session, user: UserCreate):
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


    
