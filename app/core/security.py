from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        plain_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(plain_bytes, hash_bytes)
    except (ValueError, TypeError):
        return False


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta | int] = None) -> str:
    to_encode = data.copy()
    if isinstance(expires_delta, int):
        expire = datetime.now(timezone.utc) + timedelta(minutes=expires_delta)
    elif isinstance(expires_delta, timedelta):
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


BLACKLISTED_TOKENS: set[str] = set()


def blacklist_token(token: str) -> None:
    BLACKLISTED_TOKENS.add(token)


def is_token_blacklisted(token: str) -> bool:
    return token in BLACKLISTED_TOKENS


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    if is_token_blacklisted(token):
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
