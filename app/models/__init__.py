# Import mọi model ở đây để Base.metadata.create_all() "nhìn thấy" và tạo bảng.
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