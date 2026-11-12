"""Seed dữ liệu: 6 danh mục, 40 sản phẩm có ảnh minh hoạ.

Chạy lệnh:
    python app/seed_product.py
hoặc:
    python -m app.seed_product
"""
import sys
from decimal import Decimal
from pathlib import Path

# Đảm bảo import được module app khi chạy trực tiếp file này
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.session import Base, SessionLocal, engine
from app.models.category import Category
from app.models.product import Product
from app.models.product_image import ProductImage
from app import models  # noqa: F401 - đảm bảo nạp toàn bộ metadata


CATEGORIES_SEED = [
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

# 40 sản phẩm (phân bổ qua 6 danh mục: 7 + 7 + 7 + 6 + 7 + 6 = 40)
PRODUCTS_SEED = [
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


def seed_data():
    """Hàm chính thực hiện seed 6 danh mục và 40 sản phẩm có ảnh."""
    print("=" * 60)
    print("Bắt đầu quá trình seed dữ liệu sản phẩm...")
    print("=" * 60)

    # 1. Đảm bảo cấu trúc bảng trong DB đã được tạo
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 2. Xóa dữ liệu cũ theo thứ tự ràng buộc khóa ngoại (ProductImage -> Product -> Category)
        # để đảm bảo script có thể chạy lại nhiều lần (idempotent)
        deleted_images = db.query(ProductImage).delete()
        deleted_products = db.query(Product).delete()
        deleted_categories = db.query(Category).delete()
        db.commit()
        if deleted_categories or deleted_products or deleted_images:
            print(f"[*] Đã dọn dẹp dữ liệu cũ: {deleted_categories} danh mục, {deleted_products} sản phẩm, {deleted_images} ảnh.")

        # 3. Tạo 6 Danh mục
        print("\n--- Đang tạo danh mục ---")
        category_map = {}
        for cat_data in CATEGORIES_SEED:
            category = Category(
                name=cat_data["name"],
                description=cat_data.get("description"),
            )
            db.add(category)
            db.flush()  # Để lấy ngay category.id
            category_map[cat_data["name"]] = category.id
            print(f"  + Danh mục [ID={category.id}]: {category.name}")

        db.commit()
        print(f"-> Hoàn tất tạo {len(category_map)} danh mục.")

        # 4. Tạo 40 Sản phẩm và gắn ảnh tương ứng
        print("\n--- Đang tạo 40 sản phẩm và ảnh ---")
        total_images = 0
        for index, prod_data in enumerate(PRODUCTS_SEED, start=1):
            cat_id = category_map.get(prod_data["category_name"])
            if not cat_id:
                print(f"  ! Cảnh báo: Không tìm thấy danh mục '{prod_data['category_name']}'")
                continue

            product = Product(
                category_id=cat_id,
                name=prod_data["name"],
                description=prod_data["description"],
                price=prod_data["price"],
                stock_quantity=prod_data["stock_quantity"],
                is_visible=1,
            )
            db.add(product)
            db.flush()  # Lấy product.id để tạo ProductImage

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

            print(f"  [{index:02d}/40] {product.name} - Giá: {product.price:,.0f} đ ({len(prod_data.get('images', []))} ảnh)")

        db.commit()
        print("\n" + "=" * 60)
        print(f"SEED DỮ LIỆU THÀNH CÔNG:")
        print(f"  - Danh mục : {len(category_map)} danh mục")
        print(f"  - Sản phẩm : {len(PRODUCTS_SEED)} sản phẩm")
        print(f"  - Ảnh      : {total_images} ảnh")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"[!] Lỗi trong quá trình seed: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
