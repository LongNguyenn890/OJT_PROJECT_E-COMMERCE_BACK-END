# Import mọi model ở đây để Base.metadata.create_all() "nhìn thấy" và tạo bảng.
# Thêm model mới -> nhớ thêm 1 dòng import vào file này.
from app.models.item import Item  # noqa: F401
from app.models.user import User, Role, Status  # noqa: F401
from app.models.address import Address  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.cart import Cart  # noqa: F401
from app.models.cart_item import CartItem  # noqa: F401
from app.models.order import Order, PaymentMethod, OrderStatus  # noqa: F401
from app.models.order_item import OrderItem  # noqa: F401
# Thêm model mới -> nhớ thêm dòng import vào file này.

from app.models.user import User, Role, Status
from app.models.address import Address
from app.models.category import Category
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.order import Order, PaymentMethod, OrderStatus
from app.models.order_item import OrderItem
from app.models.order_status_histories import OrderStatusHistory
from app.models.stock_log import StockLog, ChangeType
