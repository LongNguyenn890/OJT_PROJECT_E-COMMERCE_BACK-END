"""Gói chứa toàn bộ các Service xử lý nghiệp vụ (Business Logic) của ứng dụng backend.

Bao gồm:
- user: Truy vấn và thao tác dữ liệu người dùng.
- auth: Nghiệp vụ đăng ký, đăng nhập và xác thực token JWT.
- cart: Nghiệp vụ giỏ hàng (tính tiền, cộng dồn, kiểm tra tồn kho).
- order_status_histories: Truy vấn đơn hàng và lịch sử trạng thái đơn hàng.
- inventory: Nghiệp vụ quản lý tồn kho, xuất/nhập/điều chỉnh và cảnh báo sắp hết hàng.
"""
from app.service.user import get_user_by_id, get_user_by_email, get_users
from app.service.auth import create_user, login_account, logout_account
from app.service.cart import (
    get_or_create_cart,
    get_cart_by_user,
    add_item_to_cart,
    update_cart_item_quantity,
    delete_cart_item,
)
from app.service import order_status_histories
from app.service import inventory
from app.service.inventory import (
    decrease_stock,
    increase_stock,
    get_inventory_list,
    get_low_stock_alerts,
    import_stock,
    adjust_stock,
    get_product_stock_logs,
)

__all__ = [
    "get_user_by_id",
    "get_user_by_email",
    "get_users",
    "create_user",
    "login_account",
    "logout_account",
    "get_or_create_cart",
    "get_cart_by_user",
    "add_item_to_cart",
    "update_cart_item_quantity",
    "delete_cart_item",
    "order_status_histories",
    "inventory",
    "decrease_stock",
    "increase_stock",
    "get_inventory_list",
    "get_low_stock_alerts",
    "import_stock",
    "adjust_stock",
    "get_product_stock_logs",
]
