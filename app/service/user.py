from typing import Optional, List
from sqlalchemy.orm import Session, selectinload
from app.models.user import User


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return (
        db.query(User)
        .options(selectinload(User.addresses))
        .filter(User.id == user_id)
        .first()
    )


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return (
        db.query(User)
        .options(selectinload(User.addresses))
        .filter(User.email == email)
        .first()
    )


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()
