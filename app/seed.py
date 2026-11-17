"""File seed dữ liệu tổng hợp toàn bộ cơ sở dữ liệu.

Bao gồm:
- 1 Admin, 1 Nhân viên (STAFF), 5 Khách hàng (CUSTOMER)
- 7 Địa chỉ nhận hàng (Addresses)
- 6 Danh mục sản phẩm (Categories)
- 40 Sản phẩm công nghệ có ảnh (Products & ProductImages)
- Lịch sử biến động tồn kho (StockLogs)
- Giỏ hàng & Sản phẩm trong giỏ (Carts & CartItems)
- 5 Đơn hàng mẫu ở các trạng thái (Orders, OrderItems, OrderStatusHistories):
  + PENDING (Chờ xác nhận)
  + CONFIRMED (Đã xác nhận)
  + SHIPPING (Đang giao)
  + COMPLETED (Hoàn thành)
  + CANCELLED (Đã hủy)

Chạy file:
    python app/seed.py
hoặc:
    python -m app.seed
"""
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Đảm bảo import được module app khi chạy trực tiếp file này
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import bcrypt
from sqlalchemy.orm import Session

from app.db.session import Base, SessionLocal, engine
from app.models.user import User, Role, Status
from app.models.address import Address
from app.models.category import Category
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.order import Order, PaymentMethod, OrderStatus as OrderModelStatus
from app.models.order_item import OrderItem
from app.models.order_status_histories import OrderStatusHistory, OrderStatus as HistoryStatus
from app.models.stock_log import StockLog, ChangeType
from app import models  # noqa: F401 - đảm bảo toàn bộ model được nạp


def hash_password(password: str) -> str:
    """Mã hoá mật khẩu bằng bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


DEFAULT_PASSWORD = "password123"

# ==============================================================================
# 1. DỮ LIỆU SEED NGƯỜI DÙNG & ĐỊA CHỈ
# ==============================================================================
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

# ==============================================================================
# 2. DỮ LIỆU SEED DANH MỤC (6 DANH MỤC)
# ==============================================================================
CATEGORIES_SEED_DATA = [
    {
        "name": "Điện thoại & Tablet",
        "description": "Điện thoại thông minh, máy tính bảng hàng đầu từ Apple, Samsung, Xiaomi...",
    },
    {
        "name": "Laptop & Máy tính",
        "description": "Laptop văn phòng, gaming, đồ họa chuyên nghiệp từ Apple MacBook, Dell, Asus, Lenovo...",
    },
    {
        "name": "Tai nghe & Âm thanh",
        "description": "Tai nghe không dây chống ồn, tai nghe chụp tai, loa Bluetooth chất lượng cao...",
    },
    {
        "name": "Đồng hồ thông minh",
        "description": "Smartwatch theo dõi sức khỏe, tập luyện thể thao từ Apple Watch, Garmin, Galaxy Watch...",
    },
    {
        "name": "Phụ kiện công nghệ",
        "description": "Củ sạc nhanh GaN, cáp sạc, sạc dự phòng, bàn phím cơ, chuột không dây...",
    },
    {
        "name": "Thiết bị thông minh & Smarthome",
        "description": "Camera an ninh, robot hút bụi, máy lọc không khí cho ngôi nhà hiện đại...",
    },
]

# ==============================================================================
# 3. DỮ LIỆU SEED SẢN PHẨM & ẢNH (40 SẢN PHẨM)
# ==============================================================================
PRODUCTS_SEED_DATA = [
    # ---------------- 1. Điện thoại & Tablet (7 sản phẩm) ----------------
    {
        "category_name": "Điện thoại & Tablet",
        "name": "iPhone 15 Pro Max 256GB",
        "description": "Khung titan siêu bền, chip Apple A17 Pro mạnh mẽ, camera tiềm vọng zoom quang 5x.",
        "price": Decimal("29490000"),
        "stock_quantity": 45,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1695048133142-1a20484d2569", "is_primary": 1, "sort_order": 0},
            {"image_url": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab", "is_primary": 0, "sort_order": 1},
        ],
    },
    {
        "category_name": "Điện thoại & Tablet",
        "name": "Samsung Galaxy S24 Ultra 5G",
        "description": "Màn hình Dynamic AMOLED 2X, tích hợp Galaxy AI đột phá, bút S-Pen quyền năng.",
        "price": Decimal("27990000"),
        "stock_quantity": 38,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c", "is_primary": 1, "sort_order": 0},
            {"image_url": "https://images.unsplash.com/photo-1580910051074-3eb694886505", "is_primary": 0, "sort_order": 1},
        ],
    },
    {
        "category_name": "Điện thoại & Tablet",
        "name": "Xiaomi 14 Ultra 512GB",
        "description": "Cụm camera Leica đỉnh cao nhiếp ảnh di động, cảm biến 1 inch, chip Snapdragon 8 Gen 3.",
        "price": Decimal("24500000"),
        "stock_quantity": 25,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Điện thoại & Tablet",
        "name": "iPad Pro M4 11 inch Wi-Fi 256GB",
        "description": "Màn hình Ultra Retina XDR OLED kép siêu mỏng, chip Apple M4 đỉnh cao hiệu năng đồ họa.",
        "price": Decimal("26990000"),
        "stock_quantity": 30,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Điện thoại & Tablet",
        "name": "iPad Air M2 11 inch Wi-Fi 128GB",
        "description": "Thiết kế mỏng nhẹ nhiều màu sắc trẻ trung, hiệu năng chip M2 mượt mà mọi tác vụ học tập và sáng tạo.",
        "price": Decimal("16490000"),
        "stock_quantity": 50,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1561154464-82e9adf32764", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Điện thoại & Tablet",
        "name": "Samsung Galaxy Z Fold5 5G",
        "description": "Điện thoại màn hình gập cao cấp, bản lề Flex không kẽ hở, đa nhiệm cực đỉnh.",
        "price": Decimal("31990000"),
        "stock_quantity": 20,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1574944985070-8f3ebc6b79d2", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Điện thoại & Tablet",
        "name": "iPhone 13 128GB",
        "description": "Thời lượng pin ấn tượng, camera góc siêu rộng kép, mức giá tốt nhất phân khúc tầm trung cận cao cấp.",
        "price": Decimal("13490000"),
        "stock_quantity": 60,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5", "is_primary": 1, "sort_order": 0},
        ],
    },

    # ---------------- 2. Laptop & Máy tính (7 sản phẩm) ----------------
    {
        "category_name": "Laptop & Máy tính",
        "name": "MacBook Pro 14 M3 Pro (18GB/512GB)",
        "description": "Màn hình Liquid Retina XDR 120Hz, chip M3 Pro cân mượt dựng phim và lập trình chuyên nghiệp.",
        "price": Decimal("48990000"),
        "stock_quantity": 22,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8", "is_primary": 1, "sort_order": 0},
            {"image_url": "https://images.unsplash.com/photo-1611186871348-b1ce696e52c9", "is_primary": 0, "sort_order": 1},
        ],
    },
    {
        "category_name": "Laptop & Máy tính",
        "name": "MacBook Air 13 M3 (16GB/256GB)",
        "description": "Thiết kế siêu mỏng nhẹ chỉ 1.24kg, pin trâu lên đến 18 giờ liên tục, màn hình sắc nét.",
        "price": Decimal("27490000"),
        "stock_quantity": 40,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1629429408209-1f912961dbd8", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Laptop & Máy tính",
        "name": "Dell XPS 13 9340 Intel Core Ultra 7",
        "description": "Viền màn hình InfinityEdge siêu mỏng, bàn phím phẳng phong cách tương lai, tích hợp AI NPU.",
        "price": Decimal("42500000"),
        "stock_quantity": 18,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1593642632823-8f785ba67e45", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Laptop & Máy tính",
        "name": "Asus ROG Zephyrus G14 RTX 4060",
        "description": "Laptop gaming OLED mỏng nhẹ nhất thế giới, âm thanh 4 loa vòm, cấu hình khủng cho game thủ.",
        "price": Decimal("44990000"),
        "stock_quantity": 15,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Laptop & Máy tính",
        "name": "Lenovo ThinkPad X1 Carbon Gen 12",
        "description": "Đẳng cấp doanh nhân với độ bền chuẩn quân đội, bàn phím gõ êm ái hàng đầu thế giới.",
        "price": Decimal("46800000"),
        "stock_quantity": 12,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Laptop & Máy tính",
        "name": "Asus ZenBook 14 OLED UX3405",
        "description": "Màn hình OLED 3K 120Hz tuyệt đẹp, pin 75Wh dùng cả ngày dài, thiết kế kim loại sang trọng.",
        "price": Decimal("24990000"),
        "stock_quantity": 28,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Laptop & Máy tính",
        "name": "Acer Nitro V 15 Gaming Core i5 13420H",
        "description": "Card đồ họa RTX 2050 4GB, tản nhiệt 2 quạt hiệu quả, mức giá sinh viên dễ tiếp cận.",
        "price": Decimal("17490000"),
        "stock_quantity": 35,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1525547719571-a2d4ac8945e2", "is_primary": 1, "sort_order": 0},
        ],
    },

    # ---------------- 3. Tai nghe & Âm thanh (7 sản phẩm) ----------------
    {
        "category_name": "Tai nghe & Âm thanh",
        "name": "Sony WH-1000XM5 Chống Ồn Cao Cấp",
        "description": "Công nghệ chống ồn chủ động đỉnh cao số 1 thị trường, chất âm Hi-Res sắc nét, pin 30 giờ.",
        "price": Decimal("7890000"),
        "stock_quantity": 55,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e", "is_primary": 1, "sort_order": 0},
            {"image_url": "https://images.unsplash.com/photo-1484704849700-f032a568e944", "is_primary": 0, "sort_order": 1},
        ],
    },
    {
        "category_name": "Tai nghe & Âm thanh",
        "name": "Apple AirPods Pro 2 USB-C (MagSafe)",
        "description": "Khử tiếng ồn chủ động gấp 2 lần thế hệ trước, âm thanh thích ứng và chế độ nhận biết cuộc hội thoại.",
        "price": Decimal("5690000"),
        "stock_quantity": 70,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1600294037681-c80b4cb5b434", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Tai nghe & Âm thanh",
        "name": "Bose QuietComfort Ultra Headphones",
        "description": "Âm thanh không gian Bose Immersive Audio, đệm tai êm ái sang trọng hàng đầu.",
        "price": Decimal("9490000"),
        "stock_quantity": 25,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1546435770-a3e426bf472b", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Tai nghe & Âm thanh",
        "name": "Marshall Stanmore III Bluetooth Speaker",
        "description": "Loa Bluetooth gia đình âm trường rộng hơn, thiết kế phong cách vintage biểu tượng của rock & roll.",
        "price": Decimal("8990000"),
        "stock_quantity": 30,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1545454675-3531b543be5d", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Tai nghe & Âm thanh",
        "name": "JBL Charge 5 Chống Nước IP67",
        "description": "Âm thanh JBL Original Pro Sound sống động, tích hợp sạc dự phòng cho điện thoại, pin 20 giờ.",
        "price": Decimal("3590000"),
        "stock_quantity": 65,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1589003077984-894e133dabab", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Tai nghe & Âm thanh",
        "name": "Sony WF-1000XM5 True Wireless",
        "description": "Tai nghe nhét tai chống ồn nhỏ gọn, chất âm chi tiết tuyệt mỹ và đàm thoại rõ nét.",
        "price": Decimal("5490000"),
        "stock_quantity": 40,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Tai nghe & Âm thanh",
        "name": "Loa Bluetooth Harman Kardon Aura Studio 4",
        "description": "Thiết kế vòm trong suốt độc đáo với ánh sáng kim cương mê hoặc cùng âm trầm mạnh mẽ.",
        "price": Decimal("6490000"),
        "stock_quantity": 20,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad", "is_primary": 1, "sort_order": 0},
        ],
    },

    # ---------------- 4. Đồng hồ thông minh (6 sản phẩm) ----------------
    {
        "category_name": "Đồng hồ thông minh",
        "name": "Apple Watch Ultra 2 GPS + Cellular 49mm",
        "description": "Vỏ titan nhẹ và cứng cáp, màn hình 3000 nits sáng nhất, GPS băng tần kép chuyên nghiệp cho vận động viên.",
        "price": Decimal("19990000"),
        "stock_quantity": 25,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30", "is_primary": 1, "sort_order": 0},
            {"image_url": "https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1", "is_primary": 0, "sort_order": 1},
        ],
    },
    {
        "category_name": "Đồng hồ thông minh",
        "name": "Apple Watch Series 9 GPS 45mm",
        "description": "Tính năng chạm hai lần Double Tap kỳ diệu, theo dõi oxy trong máu và điện tâm đồ ECG chuẩn y tế.",
        "price": Decimal("9890000"),
        "stock_quantity": 50,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1434493789847-2f02dc6ca35d", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Đồng hồ thông minh",
        "name": "Samsung Galaxy Watch6 Classic 47mm",
        "description": "Viền xoay bezel vật lý độc bản, theo dõi giấc ngủ chuyên sâu và phân tích thành phần cơ thể BIA.",
        "price": Decimal("6990000"),
        "stock_quantity": 35,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1579586337278-3befd40fd17a", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Đồng hồ thông minh",
        "name": "Garmin Fenix 7 Pro Solar Sapphire",
        "description": "Kính sạc năng lượng mặt trời cho thời lượng pin lên đến 37 ngày, đèn pin LED tích hợp và bản đồ Topo.",
        "price": Decimal("21990000"),
        "stock_quantity": 15,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1510017803434-a899398421b3", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Đồng hồ thông minh",
        "name": "Huawei Watch GT 4 46mm Dây Da",
        "description": "Thiết kế mặt số bát giác cổ điển, pin siêu khủng 14 ngày, tương thích hoàn hảo cả iOS lẫn Android.",
        "price": Decimal("4990000"),
        "stock_quantity": 40,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Đồng hồ thông minh",
        "name": "Xiaomi Smart Band 8 Pro",
        "description": "Màn hình AMOLED 1.74 inch sắc nét, hỗ trợ hơn 150 chế độ thể thao, định vị độc lập GNSS.",
        "price": Decimal("1690000"),
        "stock_quantity": 80,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1575311373937-040b8e1fd5b6", "is_primary": 1, "sort_order": 0},
        ],
    },

    # ---------------- 5. Phụ kiện công nghệ (7 sản phẩm) ----------------
    {
        "category_name": "Phụ kiện công nghệ",
        "name": "Bàn Phím Cơ Không Dây Keychron K2 Pro",
        "description": "Hỗ trợ QMK/VIA tùy biến phím dễ dàng, switch cơ học gõ êm mượt, kết nối cùng lúc 3 thiết bị Bluetooth.",
        "price": Decimal("2450000"),
        "stock_quantity": 60,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3", "is_primary": 1, "sort_order": 0},
            {"image_url": "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef", "is_primary": 0, "sort_order": 1},
        ],
    },
    {
        "category_name": "Phụ kiện công nghệ",
        "name": "Chuột Không Dây Logitech MX Master 3S",
        "description": "Nút bấm Silent giảm 90% tiếng ồn, cuộn siêu tốc MagSpeed 1000 dòng/giây, cảm biến 8000 DPI trên mọi bề mặt.",
        "price": Decimal("2190000"),
        "stock_quantity": 75,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Phụ kiện công nghệ",
        "name": "Củ Sạc Nhanh Anker Prime 67W GaN (3 Cổng)",
        "description": "Công nghệ GaN III thu nhỏ kích thước tối đa, sạc nhanh đồng thời điện thoại, máy tính bảng và laptop.",
        "price": Decimal("1190000"),
        "stock_quantity": 90,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Phụ kiện công nghệ",
        "name": "Pin Dự Phòng Ugreen 25000mAh 145W 2 Cổng Type-C",
        "description": "Công suất siêu khủng 145W sạc được cho cả MacBook Pro, màn hình LED thông minh báo pin chính xác.",
        "price": Decimal("1750000"),
        "stock_quantity": 40,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1609592424369-10659556bf68", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Phụ kiện công nghệ",
        "name": "Cáp Sạc Nhanh Type-C to Type-C 100W Bọc Dù 2m",
        "description": "Đầu cáp bọc hợp kim nhôm tản nhiệt tốt, thân dây bọc dù chống đứt gãy gập gãy thử nghiệm 30.000 lần.",
        "price": Decimal("190000"),
        "stock_quantity": 150,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1585338107529-13afc5f02586", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Phụ kiện công nghệ",
        "name": "Giá Đỡ Laptop Nhôm Công Thái Học Tùy Chỉnh Độ Cao",
        "description": "Chất liệu hợp kim nhôm nguyên khối chắc chắn, tản nhiệt tự nhiên cho máy, chống mỏi cổ vai gáy.",
        "price": Decimal("350000"),
        "stock_quantity": 85,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Phụ kiện công nghệ",
        "name": "Hub Chuyển Đổi USB-C 8 trong 1 4K HDMI 100W PD",
        "description": "Mở rộng 1 cổng Type-C thành HDMI 4K@60Hz, 3 cổng USB 3.0, khe thẻ SD/TF và cổng mạng LAN Gigabit.",
        "price": Decimal("850000"),
        "stock_quantity": 60,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c", "is_primary": 1, "sort_order": 0},
        ],
    },

    # ---------------- 6. Thiết bị thông minh & Smarthome (6 sản phẩm) ----------------
    {
        "category_name": "Thiết bị thông minh & Smarthome",
        "name": "Robot Hút Bụi Lau Nhà Dreame L20 Ultra",
        "description": "Công nghệ cánh tay xòe MopExtend lau sát mép tường, lực hút 7000Pa cực mạnh, trạm sạc tự giặt và sấy giẻ bằng khí nóng.",
        "price": Decimal("18990000"),
        "stock_quantity": 20,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1518770660439-4636190af475", "is_primary": 1, "sort_order": 0},
            {"image_url": "https://images.unsplash.com/photo-1558317374-067fb5f30001", "is_primary": 0, "sort_order": 1},
        ],
    },
    {
        "category_name": "Thiết bị thông minh & Smarthome",
        "name": "Máy Lọc Không Khí Xiaomi Smart Air Purifier 4 Pro",
        "description": "Lọc sạch bụi mịn PM2.5, khử mùi hôi thú cưng, màn hình OLED cảm ứng hiển thị chất lượng không khí theo thời gian thực.",
        "price": Decimal("4490000"),
        "stock_quantity": 35,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1585771724684-38269d6639fd", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Thiết bị thông minh & Smarthome",
        "name": "Camera An Ninh Trong Nhà xoay 360 độ 2K Ezviz C6N",
        "description": "Góc nhìn bao quát toàn phòng, phát hiện chuyển động con người bằng AI, đàm thoại 2 chiều to rõ và quan sát ban đêm có màu.",
        "price": Decimal("590000"),
        "stock_quantity": 100,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1557597774-9d273605dfa9", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Thiết bị thông minh & Smarthome",
        "name": "Khóa Cửa Thông Minh Nhận Diện Khuôn Mặt FaceID Aqara D200i",
        "description": "Mở khóa siêu tốc dưới 1 giây bằng gương mặt 3D, vân tay bán dẫn, mã số ảo và chìa cơ bảo mật.",
        "price": Decimal("12900000"),
        "stock_quantity": 15,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1558002038-1055907df827", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Thiết bị thông minh & Smarthome",
        "name": "Đèn Bàn LED Thông Minh Chống Cận Xiaomi Mijia 1S",
        "description": "Chỉ số hoàn màu Ra90 chân thực, điều chỉnh nhiệt độ màu mượt mà qua núm xoay hoặc app trên điện thoại.",
        "price": Decimal("690000"),
        "stock_quantity": 65,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c", "is_primary": 1, "sort_order": 0},
        ],
    },
    {
        "category_name": "Thiết bị thông minh & Smarthome",
        "name": "Nồi Chiên Không Dầu Điện Tử Philips 6.2L HD9270",
        "description": "Công nghệ luồng khí Rapid Air giảm 90% lượng chất béo, bảng điều khiển cảm ứng với 7 chế độ nấu cài sẵn tiện lợi.",
        "price": Decimal("2590000"),
        "stock_quantity": 40,
        "images": [
            {"image_url": "https://images.unsplash.com/photo-1556911220-e15b29be8c8f", "is_primary": 1, "sort_order": 0},
        ],
    },
]


def seed_database():
    """Tự động tạo bảng nếu chưa có và thêm toàn bộ dữ liệu mẫu cho hệ thống."""
    print("=" * 65)
    print("=== BẮT ĐẦU SEED TOÀN BỘ CƠ SỞ DỮ LIỆU ===")
    print("=" * 65)

    # 1. Đảm bảo cấu trúc bảng trong DB đã được tạo
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # 2. Xóa dữ liệu cũ theo thứ tự ràng buộc khóa ngoại (để có thể chạy lại nhiều lần an toàn)
        print("\n--- 1. Dọn dẹp dữ liệu cũ (nếu có) ---")
        db.query(OrderStatusHistory).delete()
        db.query(OrderItem).delete()
        db.query(Order).delete()
        db.query(CartItem).delete()
        db.query(Cart).delete()
        db.query(StockLog).delete()
        db.query(ProductImage).delete()
        db.query(Product).delete()
        db.query(Category).delete()
        db.query(Address).delete()
        db.query(User).delete()
        db.commit()
        print("-> Đã làm sạch toàn bộ bảng dữ liệu cũ.")

        # 3. Tạo User & Address
        print("\n--- 2. Đang tạo Users & Addresses ---")
        user_map = {}
        address_map = {}
        for item in USERS_SEED_DATA:
            user = User(
                full_name=item["full_name"],
                email=item["email"],
                phone=item["phone"],
                password_hash=hash_password(item["password"]),
                role=item["role"],
                status=item["status"],
            )
            db.add(user)
            db.flush()
            user_map[item["email"]] = user

            if "address" in item:
                addr_data = item["address"]
                address = Address(
                    user_id=user.id,
                    receiver_name=addr_data["receiver_name"],
                    phone=addr_data["phone"],
                    province=addr_data["province"],
                    ward=addr_data["ward"],
                    street_detail=addr_data.get("street_detail"),
                    is_default=addr_data.get("is_default", 1),
                )
                db.add(address)
                db.flush()
                address_map[user.id] = address

            print(f"  + User [ID={user.id}]: {user.email} [{user.role.value}] - {user.full_name}")

        db.commit()
        print(f"-> Hoàn tất tạo {len(user_map)} Users.")

        # 4. Tạo Danh mục (Categories)
        print("\n--- 3. Đang tạo Categories ---")
        category_map = {}
        for cat_data in CATEGORIES_SEED_DATA:
            category = Category(
                name=cat_data["name"],
                description=cat_data.get("description"),
            )
            db.add(category)
            db.flush()
            category_map[cat_data["name"]] = category.id
            print(f"  + Danh mục [ID={category.id}]: {category.name}")

        db.commit()
        print(f"-> Hoàn tất tạo {len(category_map)} Categories.")

        # 5. Tạo Sản phẩm & Ảnh sản phẩm (Products & ProductImages)
        print("\n--- 4. Đang tạo Products & ProductImages ---")
        product_list = []
        total_images = 0
        admin_user = user_map.get("admin@example.com")
        admin_id = admin_user.id if admin_user else None

        for index, prod_data in enumerate(PRODUCTS_SEED_DATA, start=1):
            cat_id = category_map.get(prod_data["category_name"])
            product = Product(
                category_id=cat_id,
                name=prod_data["name"],
                description=prod_data["description"],
                price=prod_data["price"],
                stock_quantity=prod_data["stock_quantity"],
                is_visible=1,
            )
            db.add(product)
            db.flush()
            product_list.append(product)

            # Tạo ảnh cho sản phẩm
            for img_info in prod_data.get("images", []):
                image = ProductImage(
                    product_id=product.id,
                    image_url=img_info["image_url"],
                    is_primary=img_info["is_primary"],
                    sort_order=img_info["sort_order"],
                )
                db.add(image)
                total_images += 1

            # Tạo StockLog ban đầu (INITIAL)
            stock_log = StockLog(
                product_id=product.id,
                order_id=None,
                created_by=admin_id,
                change_type=ChangeType.INITIAL,
                quantity_change=product.stock_quantity,
                stock_before=0,
                stock_after=product.stock_quantity,
                note=f"Nhập hàng khởi tạo ban đầu cho {product.name}",
            )
            db.add(stock_log)

        db.commit()
        print(f"-> Hoàn tất tạo {len(product_list)} Products, {total_images} Images và {len(product_list)} StockLogs ban đầu.")

        # 6. Tạo Giỏ hàng & Sản phẩm trong giỏ (Carts & CartItems)
        print("\n--- 5. Đang tạo Giỏ hàng (Carts & CartItems) ---")
        customer1 = user_map.get("customer1@example.com")
        customer2 = user_map.get("customer2@example.com")
        customer3 = user_map.get("customer3@example.com")

        # Giỏ hàng customer 1 (2 món)
        if customer1:
            cart1 = Cart(user_id=customer1.id)
            db.add(cart1)
            db.flush()
            item1 = CartItem(cart_id=cart1.id, product_id=product_list[0].id, quantity=1, price_at_add=int(product_list[0].price))
            item2 = CartItem(cart_id=cart1.id, product_id=product_list[31].id, quantity=2, price_at_add=int(product_list[31].price))
            db.add_all([item1, item2])
            print(f"  + Giỏ hàng Customer 1: 2 sản phẩm ({product_list[0].name}, {product_list[31].name})")

        # Giỏ hàng customer 2 (1 món)
        if customer2:
            cart2 = Cart(user_id=customer2.id)
            db.add(cart2)
            db.flush()
            item3 = CartItem(cart_id=cart2.id, product_id=product_list[8].id, quantity=1, price_at_add=int(product_list[8].price))
            db.add(item3)
            print(f"  + Giỏ hàng Customer 2: 1 sản phẩm ({product_list[8].name})")

        # Giỏ hàng customer 3 (3 món)
        if customer3:
            cart3 = Cart(user_id=customer3.id)
            db.add(cart3)
            db.flush()
            item4 = CartItem(cart_id=cart3.id, product_id=product_list[14].id, quantity=1, price_at_add=int(product_list[14].price))
            item5 = CartItem(cart_id=cart3.id, product_id=product_list[28].id, quantity=1, price_at_add=int(product_list[28].price))
            item6 = CartItem(cart_id=cart3.id, product_id=product_list[27].id, quantity=1, price_at_add=int(product_list[27].price))
            db.add_all([item4, item5, item6])
            print(f"  + Giỏ hàng Customer 3: 3 sản phẩm ({product_list[14].name}, {product_list[28].name}, {product_list[27].name})")

        db.commit()

        # 7. Tạo Đơn hàng mẫu (Orders, OrderItems, OrderStatusHistories, StockLogs)
        print("\n--- 6. Đang tạo Đơn hàng mẫu, Chi tiết đơn & Lịch sử trạng thái ---")
        staff_user = user_map.get("staff@example.com")
        staff_id = staff_user.id if staff_user else None
        now = datetime.now()

        sample_orders_data = [
            # Đơn 1: PENDING (Chờ xác nhận)
            {
                "customer": user_map.get("customer1@example.com"),
                "order_code": "ORD20261112001",
                "payment_method": PaymentMethod.COD,
                "status": OrderModelStatus.PENDING,
                "cancel_reason": None,
                "created_at": now - timedelta(hours=2),
                "completed_at": None,
                "note": "Giao hàng vào giờ hành chính",
                "items": [
                    {"product": product_list[0], "quantity": 1},   # iPhone 15 Pro Max
                    {"product": product_list[29], "quantity": 1},  # Củ Sạc Anker Prime
                ],
                "histories": [
                    {"old": None, "new": HistoryStatus.PENDING, "note": "Khách hàng đặt đơn thành công", "by": user_map.get("customer1@example.com").id, "time": now - timedelta(hours=2)},
                ],
            },
            # Đơn 2: CONFIRMED (Đã xác nhận)
            {
                "customer": user_map.get("customer2@example.com"),
                "order_code": "ORD20261112002",
                "payment_method": PaymentMethod.BANK_TRANSFER,
                "status": OrderModelStatus.CONFIRMED,
                "cancel_reason": None,
                "created_at": now - timedelta(hours=5),
                "completed_at": None,
                "note": "Đã chuyển khoản qua Vietcombank",
                "items": [
                    {"product": product_list[7], "quantity": 1},   # MacBook Pro 14 M3 Pro
                ],
                "histories": [
                    {"old": None, "new": HistoryStatus.PENDING, "note": "Khách hàng đặt đơn qua chuyển khoản", "by": user_map.get("customer2@example.com").id, "time": now - timedelta(hours=5)},
                    {"old": HistoryStatus.PENDING, "new": HistoryStatus.CONFIRMED, "note": "Nhân viên đã kiểm tra sao kê ngân hàng và xác nhận đơn", "by": staff_id, "time": now - timedelta(hours=4, minutes=30)},
                ],
            },
            # Đơn 3: SHIPPING (Đang giao hàng)
            {
                "customer": user_map.get("customer3@example.com"),
                "order_code": "ORD20261112003",
                "payment_method": PaymentMethod.COD,
                "status": OrderModelStatus.SHIPPING,
                "cancel_reason": None,
                "created_at": now - timedelta(days=1),
                "completed_at": None,
                "note": "Gọi trước khi giao 15 phút",
                "items": [
                    {"product": product_list[14], "quantity": 1},  # Sony WH-1000XM5
                    {"product": product_list[28], "quantity": 1},  # Chuột Logitech MX Master 3S
                ],
                "histories": [
                    {"old": None, "new": HistoryStatus.PENDING, "note": "Khách hàng đặt hàng COD", "by": user_map.get("customer3@example.com").id, "time": now - timedelta(days=1)},
                    {"old": HistoryStatus.PENDING, "new": HistoryStatus.CONFIRMED, "note": "Đơn hàng đã được xác nhận", "by": staff_id, "time": now - timedelta(hours=20)},
                    {"old": HistoryStatus.CONFIRMED, "new": HistoryStatus.SHIPPING, "note": "Đã đóng gói và bàn giao cho bưu tá giao hàng", "by": staff_id, "time": now - timedelta(hours=10)},
                ],
            },
            # Đơn 4: COMPLETED (Đã hoàn thành)
            {
                "customer": user_map.get("customer4@example.com"),
                "order_code": "ORD20261110004",
                "payment_method": PaymentMethod.BANK_TRANSFER,
                "status": OrderModelStatus.COMPLETED,
                "cancel_reason": None,
                "created_at": now - timedelta(days=3),
                "completed_at": now - timedelta(days=1),
                "note": None,
                "items": [
                    {"product": product_list[22], "quantity": 1},  # Apple Watch Series 9
                ],
                "histories": [
                    {"old": None, "new": HistoryStatus.PENDING, "note": "Tạo đơn hàng thành công", "by": user_map.get("customer4@example.com").id, "time": now - timedelta(days=3)},
                    {"old": HistoryStatus.PENDING, "new": HistoryStatus.CONFIRMED, "note": "Nhân viên xác nhận đơn", "by": staff_id, "time": now - timedelta(days=2, hours=20)},
                    {"old": HistoryStatus.CONFIRMED, "new": HistoryStatus.SHIPPING, "note": "Đơn hàng đang trên đường giao tới người nhận", "by": staff_id, "time": now - timedelta(days=2)},
                    {"old": HistoryStatus.SHIPPING, "new": HistoryStatus.DELIVERED, "note": "Giao hàng thành công, khách đã nhận hàng nguyên vẹn", "by": staff_id, "time": now - timedelta(days=1)},
                ],
            },
            # Đơn 5: CANCELLED (Đã hủy)
            {
                "customer": user_map.get("customer5@example.com"),
                "order_code": "ORD20261111005",
                "payment_method": PaymentMethod.COD,
                "status": OrderModelStatus.CANCELLED,
                "cancel_reason": "Khách hàng đổi ý muốn đổi sang sản phẩm khác",
                "created_at": now - timedelta(days=1, hours=4),
                "completed_at": None,
                "note": None,
                "items": [
                    {"product": product_list[34], "quantity": 1},  # Robot Hút Bụi Dreame L20 Ultra
                ],
                "histories": [
                    {"old": None, "new": HistoryStatus.PENDING, "note": "Tạo đơn hàng COD", "by": user_map.get("customer5@example.com").id, "time": now - timedelta(days=1, hours=4)},
                    {"old": HistoryStatus.PENDING, "new": HistoryStatus.CANCELLED, "note": "Khách gọi hotline yêu cầu hủy đơn do đổi ý", "by": staff_id, "time": now - timedelta(days=1, hours=2)},
                ],
            },
        ]

        for order_info in sample_orders_data:
            customer = order_info["customer"]
            user_addr = address_map.get(customer.id)

            subtotal = sum(int(item["product"].price) * item["quantity"] for item in order_info["items"])
            shipping_fee = 0 if subtotal >= 500000 else 30000
            total_amount = subtotal + shipping_fee

            order = Order(
                order_code=order_info["order_code"],
                user_id=customer.id,
                address_id=user_addr.id if user_addr else None,
                receiver_name=customer.full_name,
                receiver_phone=customer.phone,
                shipping_address=f"{user_addr.street_detail}, {user_addr.ward}, {user_addr.province}" if user_addr else "Hà Nội",
                note=order_info["note"],
                payment_method=order_info["payment_method"],
                subtotal_amount=subtotal,
                shipping_fee=shipping_fee,
                total_amount=total_amount,
                status=order_info["status"],
                cancel_reason=order_info["cancel_reason"],
                created_at=order_info["created_at"],
                completed_at=order_info["completed_at"],
            )
            db.add(order)
            db.flush()

            # Thêm các sản phẩm trong đơn (OrderItem)
            for item in order_info["items"]:
                prod = item["product"]
                qty = item["quantity"]
                unit_price = int(prod.price)
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=prod.id,
                    product_name=prod.name,
                    unit_price=unit_price,
                    quantity=qty,
                    subtotal=unit_price * qty,
                )
                db.add(order_item)

                # Ghi nhận StockLog trừ tồn kho khi tạo đơn
                stock_log_order = StockLog(
                    product_id=prod.id,
                    order_id=order.id,
                    created_by=customer.id,
                    change_type=ChangeType.ORDER,
                    quantity_change=-qty,
                    stock_before=prod.stock_quantity,
                    stock_after=prod.stock_quantity - qty,
                    note=f"Trừ tồn kho khi tạo đơn hàng {order.order_code}",
                )
                db.add(stock_log_order)

                # Nếu đơn hàng bị hủy, ghi nhận StockLog hoàn tồn kho (CANCEL)
                if order.status == OrderModelStatus.CANCELLED:
                    stock_log_cancel = StockLog(
                        product_id=prod.id,
                        order_id=order.id,
                        created_by=staff_id,
                        change_type=ChangeType.CANCEL,
                        quantity_change=qty,
                        stock_before=prod.stock_quantity - qty,
                        stock_after=prod.stock_quantity,
                        note=f"Hoàn lại tồn kho do đơn hàng {order.order_code} bị hủy",
                    )
                    db.add(stock_log_cancel)

            # Thêm lịch sử trạng thái đơn hàng (OrderStatusHistory)
            for h in order_info["histories"]:
                status_history = OrderStatusHistory(
                    order_id=order.id,
                    changed_by=h["by"],
                    old_status=h["old"],
                    new_status=h["new"],
                    note=h["note"],
                    changed_at=h["time"],
                )
                db.add(status_history)

            print(f"  + Đơn hàng [{order.order_code}] - Khách: {customer.full_name} | Trạng thái: {order.status.value} | Tổng tiền: {order.total_amount:,.0f} đ ({len(order_info['items'])} món)")

        db.commit()

        # 8. TỔNG KẾT
        print("\n" + "=" * 65)
        print("SEED DỮ LIỆU TOÀN BỘ HỆ THỐNG THÀNH CÔNG!")
        print("=" * 65)
        print(f"  - Người dùng (Users)              : {db.query(User).count()} tài khoản")
        print(f"  - Địa chỉ nhận hàng (Addresses)   : {db.query(Address).count()} địa chỉ")
        print(f"  - Danh mục (Categories)           : {db.query(Category).count()} danh mục")
        print(f"  - Sản phẩm (Products)             : {db.query(Product).count()} sản phẩm")
        print(f"  - Ảnh sản phẩm (ProductImages)    : {db.query(ProductImage).count()} ảnh")
        print(f"  - Lịch sử kho (StockLogs)         : {db.query(StockLog).count()} lượt ghi nhận")
        print(f"  - Giỏ hàng (Carts)                : {db.query(Cart).count()} giỏ hàng")
        print(f"  - Món trong giỏ (CartItems)       : {db.query(CartItem).count()} món hàng")
        print(f"  - Đơn hàng (Orders)               : {db.query(Order).count()} đơn hàng mẫu")
        print(f"  - Món trong đơn (OrderItems)      : {db.query(OrderItem).count()} dòng sản phẩm")
        print(f"  - Lịch sử đơn (OrderStatusHistory): {db.query(OrderStatusHistory).count()} lượt thay đổi trạng thái")
        print("-" * 65)
        print(f"[*] Mật khẩu mặc định cho tất cả user: '{DEFAULT_PASSWORD}'")
        print("    + Admin   : admin@example.com")
        print("    + Staff   : staff@example.com")
        print("    + Customer: customer1@example.com -> customer5@example.com")
        print("=" * 65)

    except Exception as e:
        db.rollback()
        print(f"[!] Lỗi trong quá trình seed dữ liệu: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
