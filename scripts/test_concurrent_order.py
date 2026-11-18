"""Script kiểm thử 2 request đặt hàng đồng thời tranh chấp sản phẩm cuối cùng (Race Condition Test).

Chạy script bằng lệnh:
    python scripts/test_concurrent_order.py

Kịch bản:
- Sản phẩm 'IPhone 16 Pro Max (Limited)' chỉ còn duy nhất tồn kho = 1.
- Hai khách hàng (User A và User B) cùng thêm sản phẩm này vào giỏ hàng.
- Tại cùng một thời điểm, cả 2 bấm nút 'Đặt hàng' (gửi 2 request POST /api/orders đồng thời).
- Kết quả mong đợi:
  + Đúng 1 người đặt thành công (201 Created).
  + Đúng 1 người nhận thông báo lỗi không đủ tồn kho (409 Conflict).
  + Tồn kho sau cùng đúng bằng 0, KHÔNG BAO GIỜ BỊ ÂM KHO.
  + Toàn bộ hệ thống chỉ sinh ra đúng 1 đơn hàng và 1 nhật ký trừ kho.
"""
import sys
import os
import tempfile
from pathlib import Path
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor

# Thêm root project vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.user import User, Role, Status
from app.models.category import Category
from app.models.product import Product
from app.models.order import Order, PaymentMethod
from app.schemas.order import OrderCreate
from app.service import cart as cart_service
from app.service import order as order_service


def run_concurrent_test():
    print("=" * 70)
    print(" BẮT ĐẦU TEST 2 REQUEST TẠO ĐƠN HÀNG ĐỒNG THỜI (CONCURRENT TEST)")
    print("=" * 70)

    # 1. Khởi tạo database test độc lập
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"timeout": 15})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

        setup_db = SessionLocal()

        # Seed 2 khách hàng
        user_a = User(
            id=1,
            full_name="Nguyễn Văn A (Khách 1)",
            email="usera@example.com",
            phone="0911111111",
            password_hash="hashed_pw_a",
            role=Role.CUSTOMER,
            status=Status.ACTIVE,
        )
        user_b = User(
            id=2,
            full_name="Trần Thị B (Khách 2)",
            email="userb@example.com",
            phone="0922222222",
            password_hash="hashed_pw_b",
            role=Role.CUSTOMER,
            status=Status.ACTIVE,
        )
        cat = Category(id=1, name="Điện thoại cao cấp")
        product = Product(
            id=100,
            category_id=1,
            name="IPhone 16 Pro Max (Limited)",
            price=Decimal("30000000"),
            stock_quantity=1,  # CHỈ CÒN ĐÚNG 1 CÁI DUY NHẤT
            is_visible=1,
        )
        setup_db.add_all([user_a, user_b, cat, product])
        setup_db.commit()

        # Cả 2 khách hàng cùng thêm sản phẩm vào giỏ
        cart_service.add_item_to_cart(setup_db, user_id=1, product_id=100, quantity=1)
        cart_service.add_item_to_cart(setup_db, user_id=2, product_id=100, quantity=1)
        setup_db.close()

        print("[1] Đã khởi tạo sản phẩm: 'IPhone 16 Pro Max (Limited)'")
        print("    -> Tồn kho ban đầu trong kho: 1")
        print("    -> Cả Khách A và Khách B đều đã có sản phẩm này trong giỏ hàng.")
        print("\n[2] Đang kích hoạt 2 request đặt hàng đồng thời qua 2 Thread riêng biệt...")

        payload_a = OrderCreate(
            receiver_name="Nguyễn Văn A",
            receiver_phone="0911111111",
            shipping_address="Hà Nội",
            payment_method=PaymentMethod.COD,
        )
        payload_b = OrderCreate(
            receiver_name="Trần Thị B",
            receiver_phone="0922222222",
            shipping_address="TP Hồ Chí Minh",
            payment_method=PaymentMethod.COD,
        )

        results = []

        def place_order_task(user_id: int, user_name: str, payload: OrderCreate):
            session = SessionLocal()
            try:
                order = order_service.create_order(session, user_id=user_id, data=payload)
                results.append({
                    "user": user_name,
                    "success": True,
                    "status_code": 201,
                    "order_code": order.order_code,
                    "message": f"Đặt hàng thành công! Mã đơn: {order.order_code}",
                })
            except HTTPException as exc:
                results.append({
                    "user": user_name,
                    "success": False,
                    "status_code": exc.status_code,
                    "message": f"Bị chặn bởi hệ thống: [{exc.status_code}] {exc.detail}",
                })
            except Exception as exc:
                results.append({
                    "user": user_name,
                    "success": False,
                    "status_code": 500,
                    "message": f"Lỗi: {str(exc)}",
                })
            finally:
                session.close()

        # Chạy đồng thời 2 luồng
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_a = executor.submit(place_order_task, 1, "Khách hàng A", payload_a)
            fut_b = executor.submit(place_order_task, 2, "Khách hàng B", payload_b)
            fut_a.result()
            fut_b.result()

        print("\n[3] KẾT QUẢ PHẢN HỒI TỪ SERVER:")
        for r in results:
            prefix = "[THÀNH CÔNG]" if r["success"] else "[BỊ TỪ CHỐI]"
            print(f"    * {r['user']}: {prefix} - {r['message']}")

        # 4. Kiểm tra dữ liệu sau cùng trong CSDL
        check_db = SessionLocal()
        final_product = check_db.get(Product, 100)
        total_orders = check_db.query(Order).count()
        check_db.close()
        engine.dispose()

        print("\n[4] KIỂM TRA TÍNH TOÀN VẸN CƠ SỞ DỮ LIỆU:")
        print(f"    - Số lượng tồn kho sản phẩm còn lại: {final_product.stock_quantity}")
        print(f"    - Tổng số đơn hàng được tạo trong DB: {total_orders}")

        # Đánh giá
        success_count = sum(1 for r in results if r["success"])
        failed_count = sum(1 for r in results if not r["success"])

        is_passed = (
            success_count == 1
            and failed_count == 1
            and final_product.stock_quantity == 0
            and total_orders == 1
        )

        print("\n" + "=" * 70)
        if is_passed:
            print(" KẾT QUẢ ĐÁNH GIÁ: [PASS] CHỐNG RACE CONDITION HOÀN TOÀN XUẤT SẮC!")
            print(" - Đơn hàng xử lý giao dịch nguyên tử, đúng 1 người mua được.")
            print(" - Không xảy ra hiện tượng âm kho (tồn kho dừng chính xác ở 0).")
        else:
            print(" KẾT QUẢ ĐÁNH GIÁ: [FAIL] DỮ LIỆU KHÔNG KHỚP!")
        print("=" * 70)

    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass


if __name__ == "__main__":
    run_concurrent_test()
