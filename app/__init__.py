import sys
from pathlib import Path

# Tự động nạp các thư viện trong .venv nếu người dùng chạy uvicorn qua Python toàn cục (global)
_BASE_DIR = Path(__file__).resolve().parent.parent
_VENV_PACKAGES = _BASE_DIR / ".venv" / "Lib" / "site-packages"
if _VENV_PACKAGES.exists() and str(_VENV_PACKAGES) not in sys.path:
    sys.path.insert(0, str(_VENV_PACKAGES))
