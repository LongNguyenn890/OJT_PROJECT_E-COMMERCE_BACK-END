"""File seed dữ liệu mẫu cho cơ sở dữ liệu.
Bao gồm:
- 1 Admin
- 1 Nhân viên (STAFF)
- 5 Khách hàng (CUSTOMER)

Chạy file:
    python app/seed.py
hoặc:
    python -m app.seed
"""
import sys
from pathlib import Path

# Đảm bảo import được module app khi chạy file trực tiếp
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import bcrypt
from sqlalchemy.orm import Session
from app.db.session import Base, SessionLocal, engine
from app.models.user import User, Role, Status
from app.models.address import Address
from app import models  # noqa: F401 - đảm bảo toàn bộ model được nạp


def hash_password(password: str) -> str:
    """Mã hoá mật khẩu bằng bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# Mật khẩu chung mặc định để dễ dàng kiểm thử
DEFAULT_PASSWORD = "password123"

USERS_SEED_DATA = [
    # 1 Admin
    {
        "full_name": "Quản Trị Viên",
        "email": "admin@example.com",
        "phone": "0901234567",
        "password": DEFAULT_PASSWORD,
        "role": Role.ADMIN,
        "status": Status.ACTIVE,
        "address": {
            "receiver_name": "Quản Trị Viên",
            "phone": "0901234567",
            "province": "Hà Nội",
            "ward": "Phường Cầu Giấy",
            "street_detail": "Số 1 Duy Tân",
            "is_default": 1,
        },
    },
    # 1 Nhân viên
    {
        "full_name": "Nguyễn Văn Nhân Viên",
        "email": "staff@example.com",
        "phone": "0902345678",
        "password": DEFAULT_PASSWORD,
        "role": Role.STAFF,
        "status": Status.ACTIVE,
        "address": {
            "receiver_name": "Nguyễn Văn Nhân Viên",
            "phone": "0902345678",
            "province": "Hà Nội",
            "ward": "Phường Mỹ Đình",
            "street_detail": "Số 18 Phạm Hùng",
            "is_default": 1,
        },
    },
    # 5 Khách hàng
    {
        "full_name": "Nguyễn Văn An",
        "email": "customer1@example.com",
        "phone": "0912345001",
        "password": DEFAULT_PASSWORD,
        "role": Role.CUSTOMER,
        "status": Status.ACTIVE,
        "address": {
            "receiver_name": "Nguyễn Văn An",
            "phone": "0912345001",
            "province": "Hà Nội",
            "ward": "Phường Dịch Vọng",
            "street_detail": "Số 10 Xuân Thủy",
            "is_default": 1,
        },
    },
    {
        "full_name": "Trần Thị Bình",
        "email": "customer2@example.com",
        "phone": "0912345002",
        "password": DEFAULT_PASSWORD,
        "role": Role.CUSTOMER,
        "status": Status.ACTIVE,
        "address": {
            "receiver_name": "Trần Thị Bình",
            "phone": "0912345002",
            "province": "Đà Nẵng",
            "ward": "Phường Hải Châu 1",
            "street_detail": "Số 25 Bạch Đằng",
            "is_default": 1,
        },
    },
    {
        "full_name": "Lê Hoàng Cường",
        "email": "customer3@example.com",
        "phone": "0912345003",
        "password": DEFAULT_PASSWORD,
        "role": Role.CUSTOMER,
        "status": Status.ACTIVE,
        "address": {
            "receiver_name": "Lê Hoàng Cường",
            "phone": "0912345003",
            "province": "Hồ Chí Minh",
            "ward": "Phường Bến Nghé",
            "street_detail": "Số 50 Lê Lợi, Quận 1",
            "is_default": 1,
        },
    },
    {
        "full_name": "Phạm Thị Dung",
        "email": "customer4@example.com",
        "phone": "0912345004",
        "password": DEFAULT_PASSWORD,
        "role": Role.CUSTOMER,
        "status": Status.ACTIVE,
        "address": {
            "receiver_name": "Phạm Thị Dung",
            "phone": "0912345004",
            "province": "Hồ Chí Minh",
            "ward": "Phường Thảo Điền",
            "street_detail": "Số 12 Nguyễn Văn Hưởng, TP Thủ Đức",
            "is_default": 1,
        },
    },
    {
        "full_name": "Vũ Đức Em",
        "email": "customer5@example.com",
        "phone": "0912345005",
        "password": DEFAULT_PASSWORD,
        "role": Role.CUSTOMER,
        "status": Status.ACTIVE,
        "address": {
            "receiver_name": "Vũ Đức Em",
            "phone": "0912345005",
            "province": "Hải Phòng",
            "ward": "Phường Hoàng Văn Thụ",
            "street_detail": "Số 88 Lạch Tray",
            "is_default": 1,
        },
    },
]


def seed_database():
    """Tự động tạo bảng nếu chưa có và thêm dữ liệu người dùng mẫu."""
    print("=== BẮT ĐẦU SEED DỮ LIỆU ===")
    
    # 1. Đảm bảo bảng đã tồn tại
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        created_count = 0
        skipped_count = 0

        for item in USERS_SEED_DATA:
            existing_user = db.query(User).filter(User.email == item["email"]).first()
            if existing_user:
                print(f"[BỎ QUA] Email đã tồn tại: {item['email']} ({item['role'].value})")
                skipped_count += 1
                continue

            # Tạo user mới
            user = User(
                full_name=item["full_name"],
                email=item["email"],
                phone=item["phone"],
                password_hash=hash_password(item["password"]),
                role=item["role"],
                status=item["status"],
            )

            # Thêm địa chỉ kèm theo nếu có
            if "address" in item:
                addr_data = item["address"]
                address = Address(
                    receiver_name=addr_data["receiver_name"],
                    phone=addr_data["phone"],
                    province=addr_data["province"],
                    ward=addr_data["ward"],
                    street_detail=addr_data.get("street_detail"),
                    is_default=addr_data.get("is_default", 1),
                )
                user.addresses.append(address)

            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[THÀNH CÔNG] Đã tạo user id={user.id}: {user.email} [{user.role.value}] - {user.full_name}")
            created_count += 1

        print("--------------------------------------------------")
        print(f"Tổng kết: Đã tạo mới {created_count} user, bỏ qua {skipped_count} user đã có.")
        print(f"Mật khẩu mặc định cho tất cả tài khoản mẫu: {DEFAULT_PASSWORD}")
        print("==================================================")

    except Exception as e:
        db.rollback()
        print(f"[LỖI] Xảy ra lỗi khi seed dữ liệu: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
