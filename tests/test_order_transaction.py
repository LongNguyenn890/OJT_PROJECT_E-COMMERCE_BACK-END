"""Kiểm thử tự động cho chức năng Tạo đơn hàng trong Transaction (FR-022, FR-023, FR-035).

Bao gồm:
1. Tạo đơn hàng thành công (tính tiền, phí ship, trừ kho, lưu snapshot, tạo log, xóa giỏ).
2. Kiểm tra tính toàn vẹn Transaction (Rollback khi gặp lỗi giữa chừng, không để lại dữ liệu rác).
3. Chặn tạo đơn khi giỏ rỗng hoặc sản phẩm bị ẩn.
4. Test 2 request đồng thời (Concurrent Race Condition):
   - Sản phẩm chỉ còn tồn kho = 1.
   - 2 người cùng đặt hàng tại cùng một thời điểm.
   - Kết quả: Đúng 1 người thành công, 1 người thất bại (409 Conflict), tồn kho = 0, KHÔNG BỊ ÂM KHO.
"""
import sys
from pathlib import Path

# Thêm thư mục gốc của project vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.user import User, Role, Status
from app.models.category import Category
from app.models.product import Product
from app.models.order import Order, OrderStatus, PaymentMethod
from app.models.order_item import OrderItem
from app.models.stock_log import StockLog, ChangeType
from app.models.order_status_histories import OrderStatusHistory
from app.schemas.order import OrderCreate
from app.service import cart as cart_service
from app.service import order as order_service


class TestOrderTransaction(unittest.TestCase):
    def setUp(self):
        # Sử dụng SQLite in-memory với StaticPool để chia sẻ giữa các luồng test
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.Session()

        # Seed Người dùng
        self.user1 = User(
            id=1,
            full_name="Nguyễn Văn A",
            email="user1@example.com",
            phone="0912345678",
            password_hash="hashed_pw_1",
            role=Role.CUSTOMER,
            status=Status.ACTIVE,
        )
        self.user2 = User(
            id=2,
            full_name="Trần Thị B",
            email="user2@example.com",
            phone="0987654321",
            password_hash="hashed_pw_2",
            role=Role.CUSTOMER,
            status=Status.ACTIVE,
        )
        self.db.add_all([self.user1, self.user2])

        # Seed Danh mục
        self.cat = Category(id=1, name="Thiết bị điện tử", description="Điện thoại, phụ kiện")
        self.db.add(self.cat)

        # Seed Sản phẩm
        # P1: Tai nghe bluetooth (300.000đ, tồn 10)
        self.p1 = Product(
            id=1,
            category_id=1,
            name="Tai nghe Bluetooth TWS",
            price=Decimal("300000"),
            stock_quantity=10,
            is_visible=1,
        )
        # P2: Loa bluetooth (600.000đ, tồn 5)
        self.p2 = Product(
            id=2,
            category_id=1,
            name="Loa Bluetooth Bass Mini",
            price=Decimal("600000"),
            stock_quantity=5,
            is_visible=1,
        )
        # P3: Cáp sạc (50.000đ, tồn 2 - ít hàng để test thiếu kho)
        self.p3 = Product(
            id=3,
            category_id=1,
            name="Cáp sạc Type-C",
            price=Decimal("50000"),
            stock_quantity=2,
            is_visible=1,
        )
        # P4: Sản phẩm đã ẩn (100.000đ, is_visible=0)
        self.p4 = Product(
            id=4,
            category_id=1,
            name="Sản phẩm ngừng kinh doanh",
            price=Decimal("100000"),
            stock_quantity=10,
            is_visible=0,
        )
        # P5: Sản phẩm cuối cùng duy nhất để test race condition (tồn = 1)
        self.p5 = Product(
            id=5,
            category_id=1,
            name="Phiên bản giới hạn (Còn đúng 1 cái)",
            price=Decimal("1000000"),
            stock_quantity=1,
            is_visible=1,
        )
        self.db.add_all([self.p1, self.p2, self.p3, self.p4, self.p5])
        self.db.commit()

        self.order_payload = OrderCreate(
            receiver_name="Nguyễn Văn A",
            receiver_phone="0912345678",
            shipping_address="Số 123 Đường Cầu Giấy, Hà Nội",
            note="Giao vào giờ hành chính",
            payment_method=PaymentMethod.COD,
        )

    def tearDown(self):
        self.db.close()

    def test_01_create_order_success_with_free_shipping(self):
        """FR-023: Tạo đơn hàng thành công, tạm tính >= 500k -> miễn phí ship, trừ kho và xóa giỏ."""
        # Thêm 1 loa bluetooth (600.000đ) -> subtotal >= 500.000đ
        cart_service.add_item_to_cart(self.db, user_id=1, product_id=2, quantity=1)

        order = order_service.create_order(self.db, user_id=1, data=self.order_payload)

        # 1. Kiểm tra đơn hàng được tạo
        self.assertIsNotNone(order.id)
        self.assertTrue(order.order_code.startswith("DH-"))
        self.assertEqual(order.user_id, 1)
        self.assertEqual(order.receiver_name, "Nguyễn Văn A")
        self.assertEqual(order.receiver_phone, "0912345678")
        self.assertEqual(order.shipping_address, "Số 123 Đường Cầu Giấy, Hà Nội")
        self.assertEqual(order.payment_method, PaymentMethod.COD)
        self.assertEqual(order.status, OrderStatus.PENDING)

        # 2. Kiểm tra tính tiền
        self.assertEqual(order.subtotal_amount, 600000)
        self.assertEqual(order.shipping_fee, 0)  # Miễn phí vận chuyển từ 500k
        self.assertEqual(order.total_amount, 600000)

        # 3. Kiểm tra chi tiết đơn hàng (OrderItem)
        self.assertEqual(len(order.items), 1)
        item = order.items[0]
        self.assertEqual(item.product_id, 2)
        self.assertEqual(item.product_name, "Loa Bluetooth Bass Mini")
        self.assertEqual(item.unit_price, 600000)
        self.assertEqual(item.quantity, 1)
        self.assertEqual(item.subtotal, 600000)

        # 4. Kiểm tra trừ kho sản phẩm (p2 tồn từ 5 -> còn 4)
        p2_db = self.db.get(Product, 2)
        self.assertEqual(p2_db.stock_quantity, 4)

        # 5. Kiểm tra nhật ký tồn kho (StockLog)
        log = self.db.scalar(select(StockLog).where(StockLog.order_id == order.id))
        self.assertIsNotNone(log)
        self.assertEqual(log.change_type, ChangeType.ORDER)
        self.assertEqual(log.quantity_change, -1)
        self.assertEqual(log.stock_before, 5)
        self.assertEqual(log.stock_after, 4)

        # 6. Kiểm tra lịch sử trạng thái đơn hàng (OrderStatusHistory)
        history = self.db.scalar(select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id))
        self.assertIsNotNone(history)
        self.assertEqual(history.new_status, "PENDING")

        # 7. Kiểm tra giỏ hàng đã được xóa sạch (BR-20)
        cart = cart_service.get_cart_by_user(self.db, user_id=1)
        self.assertEqual(len(cart.cart_items), 0)

    def test_02_create_order_under_500k_adds_shipping_fee(self):
        """FR-023 & BR-07: Tạm tính < 500k -> cộng thêm 30.000đ phí vận chuyển."""
        # Thêm 1 tai nghe bluetooth (300.000đ)
        cart_service.add_item_to_cart(self.db, user_id=1, product_id=1, quantity=1)

        order = order_service.create_order(self.db, user_id=1, data=self.order_payload)
        self.assertEqual(order.subtotal_amount, 300000)
        self.assertEqual(order.shipping_fee, 30000)
        self.assertEqual(order.total_amount, 330000)

    def test_03_empty_cart_raises_bad_request(self):
        """FR-023: Giỏ hàng rỗng không thể đặt hàng -> 400 Bad Request."""
        with self.assertRaises(HTTPException) as ctx:
            order_service.create_order(self.db, user_id=1, data=self.order_payload)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("trống", ctx.exception.detail)

    def test_04_hidden_product_in_cart_blocks_order(self):
        """Chặn đặt hàng nếu có sản phẩm trong giỏ bị ẩn -> 400 Bad Request."""
        # Thêm sản phẩm 1 bình thường
        cart_service.add_item_to_cart(self.db, user_id=1, product_id=1, quantity=1)
        # Giả lập admin ẩn sản phẩm 1 sau khi khách đã thêm vào giỏ
        p1 = self.db.get(Product, 1)
        p1.is_visible = 0
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            order_service.create_order(self.db, user_id=1, data=self.order_payload)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("đã bị ẩn", ctx.exception.detail)

    def test_05_transaction_rollback_when_insufficient_stock(self):
        """Transaction Rollback (NFR-019): Lỗi thiếu hàng giữa chừng phải rollback 100% dữ liệu."""
        # Thêm P1 (tồn 10, mua 2) -> Đủ hàng
        cart_service.add_item_to_cart(self.db, user_id=1, product_id=1, quantity=2)
        # Thêm P3 (tồn 2, mua 2) -> Đủ hàng lúc thêm
        cart_service.add_item_to_cart(self.db, user_id=1, product_id=3, quantity=2)

        # Giả sử sau đó tồn kho P3 bị giảm còn 1 (không đủ cho đơn 2 cái)
        p3 = self.db.get(Product, 3)
        p3.stock_quantity = 1
        self.db.commit()

        # Tiến hành đặt hàng -> kỳ vọng fail 409 Conflict
        with self.assertRaises(HTTPException) as ctx:
            order_service.create_order(self.db, user_id=1, data=self.order_payload)
        self.assertEqual(ctx.exception.status_code, 409)

        # KIỂM TRA TÍNH TOÀN VẸN CỦA GIAO DỊCH (ROLLBACK):
        # 1. Tồn kho P1 KHÔNG được bị trừ (vẫn giữ nguyên là 10)
        p1_check = self.db.get(Product, 1)
        self.assertEqual(p1_check.stock_quantity, 10)

        # 2. Không có đơn hàng nào được tạo
        orders_count = self.db.query(Order).count()
        self.assertEqual(orders_count, 0)

        # 3. Không có OrderItem nào được tạo
        items_count = self.db.query(OrderItem).count()
        self.assertEqual(items_count, 0)

        # 4. Giỏ hàng KHÔNG bị xóa (vẫn còn nguyên 2 sản phẩm)
        cart = cart_service.get_cart_by_user(self.db, user_id=1)
        self.assertEqual(len(cart.cart_items), 2)

    def test_06_concurrent_orders_on_last_item_prevents_negative_stock(self):
        """Test 2 request đồng thời mua sản phẩm cuối (P5 tồn = 1).
        
        Kỳ vọng:
        - Đúng 1 request thành công (201 Created).
        - Đúng 1 request thất bại (409 Conflict).
        - Tồn kho sau cùng = 0, KHÔNG BAO GIỜ ÂM!
        - Bảng orders chỉ có đúng 1 đơn hàng.
        """
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            c_engine = create_engine(
                f"sqlite:///{db_path}",
                connect_args={"timeout": 15},
            )
            Base.metadata.create_all(bind=c_engine)
            C_Session = sessionmaker(bind=c_engine, autocommit=False, autoflush=False)

            init_session = C_Session()
            # Seed 2 user và sản phẩm P5 có tồn kho = 1
            u1 = User(id=1, full_name="User 1", email="u1@test.com", phone="0911111111", password_hash="h1", role=Role.CUSTOMER, status=Status.ACTIVE)
            u2 = User(id=2, full_name="User 2", email="u2@test.com", phone="0922222222", password_hash="h2", role=Role.CUSTOMER, status=Status.ACTIVE)
            cat = Category(id=1, name="Test Cat")
            prod = Product(id=5, category_id=1, name="Phiên bản giới hạn", price=Decimal("1000000"), stock_quantity=1, is_visible=1)
            init_session.add_all([u1, u2, cat, prod])
            init_session.commit()

            # Chuẩn bị giỏ hàng cho cả 2 user cùng chứa sản phẩm P5 (số lượng 1)
            cart_service.add_item_to_cart(init_session, user_id=1, product_id=5, quantity=1)
            cart_service.add_item_to_cart(init_session, user_id=2, product_id=5, quantity=1)
            init_session.close()

            payload1 = OrderCreate(
                receiver_name="Khách Hàng 1",
                receiver_phone="0911111111",
                shipping_address="Hà Nội",
                payment_method=PaymentMethod.COD,
            )
            payload2 = OrderCreate(
                receiver_name="Khách Hàng 2",
                receiver_phone="0922222222",
                shipping_address="TP Hồ Chí Minh",
                payment_method=PaymentMethod.COD,
            )

            results = []

            def place_order_worker(user_id: int, payload: OrderCreate):
                # Mỗi thread sử dụng 1 connection session độc lập
                session = C_Session()
                try:
                    order = order_service.create_order(session, user_id=user_id, data=payload)
                    results.append({"status": "SUCCESS", "order_id": order.id, "user_id": user_id})
                except HTTPException as e:
                    results.append({"status": "FAILED", "code": e.status_code, "detail": e.detail, "user_id": user_id})
                except Exception as e:
                    results.append({"status": "ERROR", "error": str(e), "user_id": user_id})
                finally:
                    session.close()

            # Thực thi đồng thời 2 luồng đặt hàng
            with ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(place_order_worker, 1, payload1)
                future2 = executor.submit(place_order_worker, 2, payload2)
                future1.result()
                future2.result()

            success_list = [r for r in results if r["status"] == "SUCCESS"]
            failed_list = [r for r in results if r["status"] == "FAILED"]

            # 1. Đúng 1 người thành công và đúng 1 người thất bại
            self.assertEqual(len(success_list), 1, f"Số đơn thành công: {len(success_list)}, chi tiết: {results}")
            self.assertEqual(len(failed_list), 1, f"Số đơn thất bại: {len(failed_list)}, chi tiết: {results}")

            # 2. Người thất bại nhận mã 409 Conflict vì thiếu hàng
            self.assertEqual(failed_list[0]["code"], 409)
            self.assertIn("không đủ tồn kho", failed_list[0]["detail"])

            # 3. Tồn kho sau cùng của sản phẩm P5 PHẢI BẰNG 0, KHÔNG ĐƯỢC BỊ ÂM
            check_session = C_Session()
            p5_final = check_session.get(Product, 5)
            self.assertEqual(p5_final.stock_quantity, 0, "Tồn kho bị sai lệch hoặc bị âm!")

            # 4. Chỉ có duy nhất 1 đơn hàng được tạo trong toàn hệ thống
            total_orders = check_session.query(Order).count()
            self.assertEqual(total_orders, 1)
            check_session.close()
            c_engine.dispose()
        finally:
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except OSError:
                    pass


if __name__ == "__main__":
    unittest.main()
