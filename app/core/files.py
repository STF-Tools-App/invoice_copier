"""Tìm file Invoice PDF và file Tờ khai (ToKhaiHQ7N_...) trong một thư mục."""
from __future__ import annotations

import os
from typing import Optional

from app.constants import TOKHAI_EXTENSIONS


def _iter_files(folder: str):
    """Duyệt file ở cấp ngoài cùng trước, rồi mới tới thư mục con."""
    try:
        with os.scandir(folder) as it:
            top = [e for e in it if e.is_file()]
        for e in top:
            yield e.name, e.path
    except OSError:
        return
    for dirpath, dirnames, filenames in os.walk(folder):
        if dirpath == folder:
            continue
        for fn in filenames:
            yield fn, os.path.join(dirpath, fn)


def find_invoice_pdf(folder: str, invoice: str) -> Optional[str]:
    target = f"{invoice.strip()}.pdf".lower()
    for name, path in _iter_files(folder):
        if name.lower() == target:
            return path
    return None


def find_tokhai_files(folder: str, prefix: str, tokhai: str = "") -> list[str]:
    """Trả về các file tờ khai ứng viên (ToKhaiHQ7N_*.xls/xlsx).

    Nếu có số tờ khai thì chỉ lấy file có chứa số đó trong tên.
    """
    prefix_l = prefix.lower()
    tokhai = tokhai.strip()
    found = []
    for name, path in _iter_files(folder):
        low = name.lower()
        if not low.startswith(prefix_l) or not low.endswith(TOKHAI_EXTENSIONS):
            continue
        if low.startswith("~$"):
            continue
        if tokhai and tokhai.lower() not in low:
            continue
        found.append(path)
    return found
