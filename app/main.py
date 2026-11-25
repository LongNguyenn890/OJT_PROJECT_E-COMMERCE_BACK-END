"""Điểm khởi động của backend.

Chạy:  uvicorn app.main:app --reload
Tài liệu API tự sinh: http://127.0.0.1:8000/docs
"""
import sys
from pathlib import Path

# Đảm bảo môi trường .venv luôn được ưu tiên nạp khi người dùng chạy uvicorn từ Python toàn cục
_BASE_DIR = Path(__file__).resolve().parent.parent
_VENV_PACKAGES = _BASE_DIR / ".venv" / "Lib" / "site-packages"
if _VENV_PACKAGES.exists() and str(_VENV_PACKAGES) not in sys.path:
    sys.path.insert(0, str(_VENV_PACKAGES))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app import models  # noqa: F401 - import để SQLAlchemy biết các bảng
from app.core.config import settings
from app.db.session import Base, engine
from app.routers import (
    auth,
    cart,
    categories,
    customers,
    health,
    inventory,
    order_histories,
    products,
    staff,
    reports,
    reviews,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tự tạo các bảng còn thiếu khi server khởi động (bảng đã có thì bỏ qua).
    # Lưu ý: create_all KHÔNG sửa bảng đã tồn tại. Đổi cột -> sửa bằng SQL hoặc xoá bảng tạo lại.
    try:
        Base.metadata.create_all(bind=engine)
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if "products" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("products")]
            with engine.connect() as conn:
                if "sku" not in columns:
                    conn.execute(text("ALTER TABLE products ADD COLUMN sku VARCHAR(100) UNIQUE NULL"))
                    conn.commit()
                if "promotional_price" not in columns:
                    conn.execute(text("ALTER TABLE products ADD COLUMN promotional_price DECIMAL(12, 2) NULL"))
                    conn.commit()
        if "users" in inspector.get_table_names():
            user_columns = [c["name"] for c in inspector.get_columns("users")]
            with engine.connect() as conn:
                if "avatar" not in user_columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN avatar VARCHAR(255) NULL"))
                    conn.commit()
                if "reward_points" not in user_columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN reward_points INT NOT NULL DEFAULT 0"))
                    conn.commit()
        if "vouchers" in inspector.get_table_names():
            voucher_cols = [c["name"] for c in inspector.get_columns("vouchers")]
            with engine.connect() as conn:
                if "voucher_type" not in voucher_cols:
                    conn.execute(text("ALTER TABLE vouchers ADD COLUMN voucher_type VARCHAR(20) NOT NULL DEFAULT 'fixed'"))
                    conn.commit()
                if "percent" not in voucher_cols:
                    conn.execute(text("ALTER TABLE vouchers ADD COLUMN percent INT NULL DEFAULT 0"))
                    conn.commit()
                if "max_discount" not in voucher_cols:
                    conn.execute(text("ALTER TABLE vouchers ADD COLUMN max_discount BIGINT NULL DEFAULT 0"))
                    conn.commit()
        if "orders" in inspector.get_table_names():
            order_cols = [c["name"] for c in inspector.get_columns("orders")]
            with engine.connect() as conn:
                if "subtotal_amount" not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN subtotal_amount BIGINT NOT NULL DEFAULT 0"))
                    conn.commit()
                if "shipping_fee" not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN shipping_fee BIGINT NOT NULL DEFAULT 0"))
                    conn.commit()
                if "cancel_reason" not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN cancel_reason VARCHAR(255) NULL"))
                    conn.commit()
                if "completed_at" not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN completed_at DATETIME NULL"))
                    conn.commit()
                if "note" not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN note VARCHAR(500) NULL"))
                    conn.commit()
        if "order_items" in inspector.get_table_names():
            item_cols = [c["name"] for c in inspector.get_columns("order_items")]
            with engine.connect() as conn:
                if "image_url" not in item_cols:
                    conn.execute(text("ALTER TABLE order_items ADD COLUMN image_url VARCHAR(255) NULL"))
                    conn.commit()
                if "category_name" not in item_cols:
                    conn.execute(text("ALTER TABLE order_items ADD COLUMN category_name VARCHAR(100) NULL"))
                    conn.commit()
                if "sku" not in item_cols:
                    conn.execute(text("ALTER TABLE order_items ADD COLUMN sku VARCHAR(100) NULL"))
                    conn.commit()
        if "product_reviews" in inspector.get_table_names():
            pr_cols = [c["name"] for c in inspector.get_columns("product_reviews")]
            with engine.connect() as conn:
                if "is_hidden" not in pr_cols:
                    conn.execute(text("ALTER TABLE product_reviews ADD COLUMN is_hidden BOOLEAN NOT NULL DEFAULT FALSE"))
                    conn.commit()
        if "review_replies" in inspector.get_table_names():
            rr_cols = [c["name"] for c in inspector.get_columns("review_replies")]
            with engine.connect() as conn:
                if "is_hidden" not in rr_cols:
                    conn.execute(text("ALTER TABLE review_replies ADD COLUMN is_hidden BOOLEAN NOT NULL DEFAULT FALSE"))
                    conn.commit()
        print(f"[DB] Đã kết nối MySQL {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    except OperationalError as error:
        print("[DB] KHÔNG kết nối được MySQL! Kiểm tra MySQL đã bật chưa và file .env.")
        if "Unknown database" in str(error.orig):
            print("[DB] Chưa có database -> mở MySQL Workbench, chạy file sql/init.sql")
        print(f"[DB] Chi tiết: {error.orig}")
    yield


tags_metadata = [
    {
        "name": "Auth",
        "description": "Xác thực, đăng ký, đăng nhập, thông tin tài khoản, avatar và đăng xuất (FR-001 -> FR-004).",
    },
    {
        "name": "Products",
        "description": "Quản lý sản phẩm, tìm kiếm, lọc, chi tiết, upload ảnh và ẩn/xóa sản phẩm (FR-013 -> FR-015).",
    },
    {
        "name": "Categories",
        "description": "Quản lý danh mục sản phẩm (xem công khai, thêm/sửa/xóa dành cho Admin/Staff).",
    },
    {
        "name": "Cart",
        "description": "Quản lý giỏ hàng của khách hàng (xem, thêm, cập nhật số lượng, xóa sản phẩm).",
    },
    {
        "name": "Orders",
        "description": "Quản lý đơn hàng, xem đơn hàng của tôi, xem toàn bộ đơn hệ thống, lịch sử trạng thái và cập nhật.",
    },
    {
        "name": "Customers",
        "description": "Quản lý khách hàng dành cho Admin & Staff: danh sách, tìm kiếm, chi tiết, lịch sử mua hàng, thống kê chi tiêu.",
    },
    {
        "name": "Staff",
        "description": "Quản lý nhân viên nội bộ dành riêng cho Quản trị viên (Staff Management): danh sách, tạo mới, chỉnh sửa, phân quyền và khóa tài khoản.",
    },
    {
        "name": "Inventory",
        "description": "Quản lý kho hàng: theo dõi tồn kho, cảnh báo sắp hết hàng, nhập hàng, kiểm kê và nhật ký biến động kho.",
    },
    {
        "name": "Reports",
        "description": "Báo cáo bán hàng, doanh thu (DELIVERED & bán tại quầy), số sản phẩm đã bán, top 10 bán chạy và doanh thu theo ngày (Admin/Staff).",
    },
    {
        "name": "Reviews & Comments",
        "description": "Đánh giá và bình luận sản phẩm, phản hồi bình luận, số sao và số sao trung bình của sản phẩm.",
    },
    {
        "name": "Health",
        "description": "Kiểm tra tình trạng hoạt động của hệ thống backend và kết nối MySQL Database.",
    },
]

app = FastAPI(
    title=settings.APP_NAME,
    description="Hệ thống API Backend quản lý thương mại điện tử (E-Commerce Platform)",
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

# CORS: cho phép trang FE (khác cổng/khác domain) gọi được API này
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Thư mục lưu trữ tệp tĩnh (ảnh tải lên)
UPLOAD_DIR = Path("uploads")
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / "avatars").mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / "products").mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / "reviews").mkdir(parents=True, exist_ok=True)
except OSError:
    pass  # Bỏ qua nếu môi trường chỉ đọc (Serverless)
if UPLOAD_DIR.exists():
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Mọi API đều bắt đầu bằng /api. Sắp xếp router theo luồng nghiệp vụ chuẩn:
app.include_router(auth.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(order_histories.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(staff.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(health.router, prefix="/api")

from fastapi import WebSocket, WebSocketDisconnect
from app.core.ws import dashboard_ws_manager

@app.websocket("/api/ws/dashboard")
async def ws_dashboard_endpoint(websocket: WebSocket):
    await dashboard_ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        dashboard_ws_manager.disconnect(websocket)
    except Exception:
        dashboard_ws_manager.disconnect(websocket)


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} đang chạy. Xem tài liệu API tại /docs"}
