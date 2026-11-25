"""Kết nối MySQL bằng SQLAlchemy."""
import certifi
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

connect_args = {}
if settings.DB_SSL or "tidbcloud.com" in settings.DB_HOST:
    connect_args["ssl"] = {"ca": certifi.where()}

# engine: "đường ống" tới MySQL. pool_pre_ping giúp tự nối lại khi MySQL ngắt kết nối cũ.
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)

# SessionLocal(): mỗi lần gọi tạo ra 1 phiên làm việc với DB
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Mọi model (bảng) đều kế thừa từ Base."""


def get_db():
    """Dependency cho FastAPI: mở session cho mỗi request và luôn đóng lại sau đó.

    Dùng trong router:  db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
