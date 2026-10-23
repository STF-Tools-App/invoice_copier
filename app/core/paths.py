"""Xác định đường dẫn gốc & thư mục config.

Khi chạy bằng .exe (PyInstaller --onefile) thì __file__ trỏ vào thư mục tạm,
nên phải dùng sys.executable để lấy thư mục chứa file .exe. Thư mục `config`
luôn nằm cạnh file .exe (hoặc cạnh main.py khi chạy bằng Python).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from app.constants import CONFIG_FILENAME, INDEX_FILENAME


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
        return True
    except OSError:
        return False


def config_dir() -> Path:
    """Thư mục config cạnh .exe; nếu không ghi được thì dùng %LOCALAPPDATA%."""
    primary = app_dir() / "config"
    if _writable(primary):
        return primary
    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "InvoiceCopier" / "config"
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_file() -> Path:
    return config_dir() / CONFIG_FILENAME


def index_file() -> Path:
    return config_dir() / INDEX_FILENAME
