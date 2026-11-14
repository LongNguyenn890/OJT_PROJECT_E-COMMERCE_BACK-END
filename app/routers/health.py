"""Router kiểm tra tình trạng hoạt động của hệ thống (Health Check Router).

Cung cấp endpoint kiểm tra máy chủ backend và kết nối tới cơ sở dữ liệu MySQL:
- GET /api/health
Phục vụ giám sát hệ thống (Monitoring / Liveness Probe).
"""
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Kiểm tra trạng thái server và kết nối CSDL",
    description=(
        "Endpoint kiểm tra sức khỏe của dịch vụ (Health Check / Readiness Probe).\n"
        "- Thực hiện lệnh `SELECT 1` tới MySQL Database.\n"
        "- **Phản hồi 200 OK**: Server đang chạy và kết nối MySQL ổn định (`database: connected`).\n"
        "- **Phản hồi 503 Service Unavailable**: Server không thể truy vấn MySQL Database."
    ),
)
def health_check(db: Session = Depends(get_db)):
    """Kiểm tra server và kiểm tra ping tới Database MySQL."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as error:  # noqa: BLE001 - muốn bắt mọi lỗi kết nối để báo ra
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "database": "disconnected", "detail": str(error)},
        )
