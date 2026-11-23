"""Service xử lý logic nghiệp vụ cho sản phẩm (Product Service).

Quy tắc nghiệp vụ:
- BR-05: Tên sản phẩm không rỗng; giá gốc phải lớn hơn 0; số lượng tồn kho >= 0.
- BR-18: Mã SKU phải là duy nhất, không trùng lặp giữa các sản phẩm (409 Conflict).
- BR-12 & FR-013: Sản phẩm đã có trong đơn hàng thì chỉ được ẩn (is_visible=0), không xóa cứng.
- Giá khuyến mãi (nếu có): phải >= 0 và nhỏ hơn giá gốc (400 Bad Request).
- Quản lý ảnh: Upload nhiều ảnh (JPG/PNG, tối đa 2MB), chọn ảnh đại diện, xóa ảnh.
- Phân quyền: Thao tác tạo/cập nhật/ẩn/xóa yêu cầu quyền Admin hoặc Staff.
"""
import uuid
from pathlib import Path
from typing import Optional
from decimal import Decimal
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session, selectinload

from app.models.product import Product
from app.models.category import Category
from app.models.product_image import ProductImage
from app.models.stock_log import StockLog, ChangeType
from app.models.order_item import OrderItem
from app.models.cart_item import CartItem
from app.schemas.product import ProductCreate, ProductUpdate

UPLOAD_DIR = Path("uploads/products")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def get_product_by_id(db: Session, product_id: int) -> Product:
    """Lấy thông tin sản phẩm theo ID kèm Category và ProductImages."""
    product = (
        db.query(Product)
        .options(selectinload(Product.category), selectinload(Product.product_images))
        .filter(Product.id == product_id)
        .first()
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm với ID {product_id} không tồn tại",
        )
    return product


def create_product(db: Session, data: ProductCreate, user_id: Optional[int] = None) -> Product:
    """Tạo mới sản phẩm với các ràng buộc nghiệp vụ.
    
    Ràng buộc:
    - SKU không được trùng (409 Conflict)
    - Giá gốc > 0 (400 Bad Request)
    - Giá khuyến mãi (nếu có) phải nhỏ hơn giá gốc (400 Bad Request)
    - Danh mục phải tồn tại (400 Bad Request)
    """
    # 1. Validate SKU
    sku_val = data.sku.strip() if data.sku else ""
    if not sku_val:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã SKU không được để trống",
        )

    existing_sku = db.query(Product.id).filter(Product.sku == sku_val).first()
    if existing_sku:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mã SKU '{sku_val}' đã tồn tại trong hệ thống",
        )

    # 2. Validate Giá gốc
    if data.price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá gốc sản phẩm phải lớn hơn 0",
        )

    # 3. Validate Giá khuyến mãi
    if data.promotional_price is not None:
        if data.promotional_price < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Giá khuyến mãi không được nhỏ hơn 0",
            )
        if data.promotional_price >= data.price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Giá khuyến mãi phải nhỏ hơn giá gốc",
            )

    # 4. Validate Danh mục
    category = db.query(Category.id).filter(Category.id == data.category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Danh mục với ID {data.category_id} không tồn tại",
        )

    # 5. Tạo đối tượng Product
    new_product = Product(
        category_id=data.category_id,
        name=data.name.strip(),
        sku=sku_val,
        description=data.description.strip() if data.description else None,
        price=data.price,
        promotional_price=data.promotional_price,
        stock_quantity=data.stock_quantity,
        is_visible=data.is_visible,
    )
    db.add(new_product)
    db.flush()

    # 6. Thêm danh sách ảnh (nếu có)
    if data.image_urls:
        for idx, url in enumerate(data.image_urls):
            clean_url = url.strip()
            if clean_url:
                db.add(
                    ProductImage(
                        product_id=new_product.id,
                        image_url=clean_url,
                        is_primary=1 if idx == 0 else 0,
                        sort_order=idx,
                    )
                )

    # 7. Ghi nhật ký kho ban đầu (INITIAL) nếu có tồn kho khởi tạo
    if new_product.stock_quantity > 0:
        stock_log = StockLog(
            product_id=new_product.id,
            change_type=ChangeType.INITIAL,
            quantity_change=new_product.stock_quantity,
            stock_before=0,
            stock_after=new_product.stock_quantity,
            order_id=None,
            created_by=user_id,
            note="Khởi tạo số lượng tồn kho ban đầu khi tạo sản phẩm",
        )
        db.add(stock_log)

    db.commit()
    db.refresh(new_product)

    return get_product_by_id(db, new_product.id)


def update_product(
    db: Session,
    product_id: int,
    data: ProductUpdate,
    user_id: Optional[int] = None,
) -> Product:
    """Cập nhật thông tin sản phẩm đã có.
    
    Ràng buộc:
    - Sản phẩm phải tồn tại (404 Not Found)
    - Nếu cập nhật SKU: không được trùng với sản phẩm khác (409 Conflict)
    - Nếu cập nhật giá gốc: giá gốc > 0 (400 Bad Request)
    - Giá khuyến mãi phải nhỏ hơn giá gốc (400 Bad Request)
    - Nếu cập nhật danh mục: danh mục phải tồn tại (400 Bad Request)
    """
    # 1. Kiểm tra sản phẩm tồn tại
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm với ID {product_id} không tồn tại",
        )

    # 2. Validate SKU (nếu có cập nhật)
    if data.sku is not None:
        sku_val = data.sku.strip()
        if not sku_val:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã SKU không được để trống",
            )
        existing_sku = (
            db.query(Product.id)
            .filter(Product.sku == sku_val, Product.id != product_id)
            .first()
        )
        if existing_sku:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mã SKU '{sku_val}' đã được sử dụng bởi sản phẩm khác",
            )
        product.sku = sku_val

    # 3. Validate Danh mục (nếu có cập nhật)
    if data.category_id is not None:
        cat = db.query(Category.id).filter(Category.id == data.category_id).first()
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Danh mục với ID {data.category_id} không tồn tại",
            )
        product.category_id = data.category_id

    # 4. Validate Giá gốc & Giá khuyến mãi
    # Ràng buộc nghiệp vụ: Giá gốc chỉ được điền 1 lần khi thêm sản phẩm, những lần sau không được sửa
    if data.price is not None:
        from decimal import Decimal
        if abs(Decimal(str(data.price)) - Decimal(str(product.price))) > Decimal("0.001"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Giá gốc sản phẩm chỉ được điền 1 lần khi thêm sản phẩm và không được phép chỉnh sửa. Để nhập thêm hàng hoặc thay đổi số lượng tồn kho, vui lòng thực hiện qua nghiệp vụ Quản lý Kho hàng.",
            )

    target_price = product.price
    target_promo = (
        data.promotional_price
        if "promotional_price" in data.model_fields_set
        else product.promotional_price
    )

    if target_promo is not None and target_promo < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá khuyến mãi không được nhỏ hơn 0",
        )

    if target_promo is not None and target_price is not None:
        if target_promo >= target_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Giá khuyến mãi phải nhỏ hơn giá gốc",
            )

    # Giá gốc cố định, chỉ cập nhật giá khuyến mãi nếu có gửi lên
    if "promotional_price" in data.model_fields_set:
        product.promotional_price = data.promotional_price

    # 5. Cập nhật các trường thông tin khác
    if data.name is not None:
        name_val = data.name.strip()
        if not name_val:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên sản phẩm không được để trống",
            )
        product.name = name_val

    if data.description is not None:
        product.description = data.description.strip() if data.description else None

    if data.is_visible is not None:
        product.is_visible = data.is_visible

    # 6. Cập nhật tồn kho và ghi nhật ký kho (ADJUST) nếu có thay đổi
    if data.stock_quantity is not None and data.stock_quantity != product.stock_quantity:
        diff = data.stock_quantity - product.stock_quantity
        stock_log = StockLog(
            product_id=product.id,
            change_type=ChangeType.ADJUST,
            quantity_change=diff,
            stock_before=product.stock_quantity,
            stock_after=data.stock_quantity,
            order_id=None,
            created_by=user_id,
            note="Điều chỉnh tồn kho khi cập nhật thông tin sản phẩm",
        )
        db.add(stock_log)
        product.stock_quantity = data.stock_quantity

    # 7. Cập nhật danh sách ảnh nếu có truyền
    if data.image_urls is not None:
        db.query(ProductImage).filter(ProductImage.product_id == product.id).delete()
        for idx, url in enumerate(data.image_urls):
            clean_url = url.strip()
            if clean_url:
                db.add(
                    ProductImage(
                        product_id=product.id,
                        image_url=clean_url,
                        is_primary=1 if idx == 0 else 0,
                        sort_order=idx,
                    )
                )

    db.commit()
    db.refresh(product)

    return get_product_by_id(db, product.id)


def upload_product_images(
    db: Session,
    product_id: int,
    files: list[UploadFile],
) -> list[ProductImage]:
    """Tải lên nhiều ảnh cho sản phẩm với giới hạn định dạng (jpg/png) và dung lượng (tối đa 100MB)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm với ID {product_id} không tồn tại",
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn ít nhất một file ảnh để tải lên",
        )

    # Kiểm tra xem sản phẩm đã có ảnh đại diện chưa
    has_primary = (
        db.query(ProductImage.id)
        .filter(ProductImage.product_id == product_id, ProductImage.is_primary == 1)
        .first()
        is not None
    )

    current_count = (
        db.query(ProductImage).filter(ProductImage.product_id == product_id).count()
    )

    created_images: list[ProductImage] = []

    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{file.filename}' không đúng định dạng. Hệ thống chỉ hỗ trợ định dạng JPG, JPEG và PNG.",
            )

        # Đọc dữ liệu file và kiểm tra dung lượng
        content = file.file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{file.filename}' có dung lượng ({len(content) / (1024*1024):.2f}MB) vượt quá giới hạn tối đa cho phép là 100MB.",
            )

        # Lưu file vật lý
        unique_name = f"{uuid.uuid4().hex}{ext}"
        saved_path = UPLOAD_DIR / unique_name
        saved_path.write_bytes(content)

        # Quyết định ảnh đại diện: Nếu sản phẩm chưa có ảnh đại diện nào thì ảnh đầu tiên sẽ là ảnh đại diện
        is_primary = 1 if not has_primary else 0
        if is_primary == 1:
            has_primary = True

        current_count += 1
        new_image = ProductImage(
            product_id=product_id,
            image_url=f"/uploads/products/{unique_name}",
            is_primary=is_primary,
            sort_order=current_count,
        )
        db.add(new_image)
        created_images.append(new_image)

    db.commit()
    for img in created_images:
        db.refresh(img)

    return created_images


def set_primary_image(db: Session, product_id: int, image_id: int) -> ProductImage:
    """Chọn một ảnh làm ảnh đại diện cho sản phẩm (các ảnh khác tự động về is_primary = 0)."""
    product = db.query(Product.id).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm với ID {product_id} không tồn tại",
        )

    target_image = (
        db.query(ProductImage)
        .filter(ProductImage.id == image_id, ProductImage.product_id == product_id)
        .first()
    )
    if not target_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ảnh với ID {image_id} không tồn tại hoặc không thuộc sản phẩm này",
        )

    # Đặt tất cả ảnh của sản phẩm về is_primary = 0
    db.query(ProductImage).filter(ProductImage.product_id == product_id).update(
        {"is_primary": 0}
    )

    # Đặt ảnh được chọn thành primary
    target_image.is_primary = 1
    db.commit()
    db.refresh(target_image)

    return target_image


def delete_product_image(db: Session, product_id: int, image_id: int) -> dict:
    """Xóa một ảnh của sản phẩm. Nếu là ảnh đại diện, tự động chọn ảnh còn lại đầu tiên làm ảnh đại diện."""
    product = db.query(Product.id).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm với ID {product_id} không tồn tại",
        )

    image = (
        db.query(ProductImage)
        .filter(ProductImage.id == image_id, ProductImage.product_id == product_id)
        .first()
    )
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ảnh với ID {image_id} không tồn tại hoặc không thuộc sản phẩm này",
        )

    was_primary = image.is_primary == 1
    img_url = image.image_url

    # Xóa file vật lý trên máy chủ nếu nằm trong thư mục uploads
    if img_url.startswith("/uploads/"):
        file_path = Path(".") / img_url.lstrip("/")
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass

    db.delete(image)
    db.flush()

    # Nếu ảnh vừa xóa là ảnh đại diện, gán ảnh đầu tiên còn lại làm primary
    if was_primary:
        next_image = (
            db.query(ProductImage)
            .filter(ProductImage.product_id == product_id)
            .order_by(ProductImage.sort_order.asc(), ProductImage.id.asc())
            .first()
        )
        if next_image:
            next_image.is_primary = 1

    db.commit()

    return {
        "message": "Đã xóa ảnh sản phẩm thành công",
        "deleted_image_id": image_id,
    }


def delete_or_hide_product(db: Session, product_id: int) -> dict:
    """Xóa hoặc ẩn sản phẩm theo quy tắc BR-12 & FR-013.
    
    Quy tắc:
    - Nếu sản phẩm đã từng phát sinh trong bất kỳ đơn hàng nào (order_items):
      KHÔNG ĐƯỢC XÓA CỨNG, chỉ được chuyển trạng thái sang Ẩn (is_visible = 0).
    - Nếu sản phẩm chưa từng có trong đơn hàng nào:
      Được phép xóa vĩnh viễn khỏi CSDL (và xóa các file ảnh vật lý liên kết).
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm với ID {product_id} không tồn tại",
        )

    # Kiểm tra xem sản phẩm đã có trong bất kỳ đơn hàng nào chưa
    has_orders = (
        db.query(OrderItem.id).filter(OrderItem.product_id == product_id).first()
        is not None
    )

    if has_orders:
        # Chuyển sang ẩn (is_visible = 0)
        product.is_visible = 0
        db.commit()
        return {
            "message": "Sản phẩm đã phát sinh trong đơn hàng nên không thể xóa vĩnh viễn; hệ thống đã tự động chuyển sang trạng thái Ẩn (is_visible=0).",
            "action": "HIDDEN",
            "product_id": product_id,
            "is_visible": 0,
        }

    # Chưa có trong đơn hàng: Tiến hành xóa cứng
    # 1. Dọn dẹp file ảnh vật lý
    images = db.query(ProductImage).filter(ProductImage.product_id == product_id).all()
    for img in images:
        if img.image_url.startswith("/uploads/"):
            file_path = Path(".") / img.image_url.lstrip("/")
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception:
                    pass

    # 2. Xóa giỏ hàng liên quan nếu có
    db.query(CartItem).filter(CartItem.product_id == product_id).delete()

    # 3. Xóa sản phẩm (các bảng cascade như ProductImage, StockLog sẽ tự xóa theo CASCADE)
    db.delete(product)
    db.commit()

    return {
        "message": "Đã xóa vĩnh viễn sản phẩm khỏi hệ thống thành công.",
        "action": "DELETED",
        "product_id": product_id,
    }


def set_product_visibility(db: Session, product_id: int, is_visible: int) -> dict:
    """Bật hoặc tắt trạng thái hiển thị của sản phẩm (is_visible: 1 hoặc 0)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm với ID {product_id} không tồn tại",
        )

    product.is_visible = 1 if is_visible else 0
    db.commit()

    status_text = "hiển thị" if product.is_visible == 1 else "ẩn"
    return {
        "message": f"Đã chuyển sản phẩm sang trạng thái {status_text} thành công.",
        "product_id": product_id,
        "is_visible": product.is_visible,
    }
