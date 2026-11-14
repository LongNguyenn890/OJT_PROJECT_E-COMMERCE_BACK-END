"""Gói chứa toàn bộ các Router API của ứng dụng backend FastAPI.

Bao gồm:
- auth: Xác thực, đăng ký, đăng nhập, hồ sơ cá nhân và đăng xuất (FR-001 -> FR-004).
- cart: Quản lý giỏ hàng của khách hàng (FR-018 -> FR-021).
- health: Kiểm tra tình trạng server và kết nối MySQL Database.
- inventory: Quản lý tồn kho, nhập hàng, kiểm kê và cảnh báo sắp hết (FR-033, FR-034, FR-036).
- order_histories: Xem danh sách và chi tiết lịch sử đơn hàng (FR-025, FR-028).
- products: Danh sách, phân loại và chi tiết sản phẩm công khai (FR-013 -> FR-015).
"""
from app.routers import auth, cart, health, inventory, order_histories, products

__all__ = ["auth", "cart", "health", "inventory", "order_histories", "products"]
