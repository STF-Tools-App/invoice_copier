"""Tìm file Invoice PDF và file Tờ khai (ToKhaiHQ7N_...) trong một thư mục."""
from __future__ import annotations

import os
from typing import Optional

from app.constants import TOKHAI_EXTENSIONS
from app.core.naming import invoice_number


def _iter_files(folder: str):
    """Duyệt file ở cấp ngoài cùng trước, rồi mới tới thư mục con."""
    try:
        with os.scandir(folder) as it:
            top = [e for e in it if e.is_file()]
        for e in top:
            yield e.name, e.path
    except OSError:
        return
    for dirpath, _dirs, filenames in os.walk(folder):
        if dirpath == folder:
            continue
        for fn in filenames:
            yield fn, os.path.join(dirpath, fn)


def invoice_pdf_names(invoice: str) -> list[str]:
    """Tên PDF cần tìm, theo thứ tự ưu tiên: '<Invoice>.pdf' rồi '<số>.pdf'."""
    inv = invoice.strip()
    names = [f"{inv}.pdf"]
    num = invoice_number(inv)
    if num and num.lower() != inv.lower():
        names.append(f"{num}.pdf")
    return names


def find_invoice_pdf(folder: str, invoice: str) -> Optional[str]:
    """Ưu tiên ISG-240010.pdf; không có thì lấy 240010.pdf."""
    wanted = [n.lower() for n in invoice_pdf_names(invoice)]
    found: dict[str, str] = {}
    for name, path in _iter_files(folder):
        low = name.lower()
        if low in wanted and low not in found:
            found[low] = path
            if low == wanted[0]:        # đã có file ưu tiên cao nhất
                break
    for w in wanted:
        if w in found:
            return found[w]
    return None


def find_tokhai_files(folder: str, prefix: str, tokhai: str = "") -> list[str]:
    """Các file tờ khai ứng viên (ToKhaiHQ7N_*.xls/xlsx); có số tờ khai thì lọc theo số đó."""
    prefix_l = prefix.lower()
    tokhai = tokhai.strip().lower()
    found = []
    for name, path in _iter_files(folder):
        low = name.lower()
        if low.startswith("~$") or not low.startswith(prefix_l) or not low.endswith(TOKHAI_EXTENSIONS):
            continue
        if tokhai and tokhai not in low:
            continue
        found.append(path)
    return found
