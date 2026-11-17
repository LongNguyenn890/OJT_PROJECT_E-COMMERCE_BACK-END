"""Gói chứa toàn bộ các Service xử lý nghiệp vụ (Business Logic) của ứng dụng backend.

Bao gồm:
- user: Truy vấn và thao tác dữ liệu người dùng.
- auth: Nghiệp vụ đăng ký, đăng nhập và xác thực token JWT.
- cart: Nghiệp vụ giỏ hàng (tính tiền, cộng dồn, kiểm tra tồn kho).
- order_status_histories: Truy vấn đơn hàng và lịch sử trạng thái đơn hàng.
- inventory: Nghiệp vụ quản lý tồn kho, xuất/nhập/điều chỉnh và cảnh báo sắp hết hàng.
- category: Nghiệp vụ quản lý danh mục (thêm, sửa, xóa, kiểm tra BR-13, BR-18).
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
from app.service import category as category_service
from app.service.category import (
    get_all_categories,
    get_category_by_id,
    get_category_by_name,
    create_category,
    update_category,
    delete_category,
)
from app.service import customer as customer_service
from app.service.customer import (
    get_customers_list,
    get_customer_detail,
    get_customer_orders,
    update_customer_status,
)
from app.service import product as product_service
from app.service.product import (
    create_product,
    update_product,
    upload_product_images,
    set_primary_image,
    delete_product_image,
    delete_or_hide_product,
    set_product_visibility,
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
    "category_service",
    "get_all_categories",
    "get_category_by_id",
    "get_category_by_name",
    "create_category",
    "update_category",
    "delete_category",
    "product_service",
    "create_product",
    "update_product",
    "upload_product_images",
    "set_primary_image",
    "delete_product_image",
    "delete_or_hide_product",
    "set_product_visibility",
    "customer_service",
    "get_customers_list",
    "get_customer_detail",
    "get_customer_orders",
    "update_customer_status",
]
