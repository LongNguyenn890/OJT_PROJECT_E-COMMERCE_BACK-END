from pydantic import BaseModel, ConfigDict, Field


# Dữ liệu API trả về cho từng dòng sản phẩm trong đơn hàng
class OrderItemResponse(BaseModel):
    id: int
    order_id: int | None = None
    product_id: int
    product_name: str
    unit_price: int = Field(description="Đơn giá tại thời điểm đặt hàng (BR-06)")
    quantity: int = Field(description="Số lượng sản phẩm")
    subtotal: int = Field(description="Thành tiền = đơn giá x số lượng")

    model_config = ConfigDict(from_attributes=True)
