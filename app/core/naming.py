"""Quy tắc đặt tên / tách số: số Invoice, số Tờ khai, tên thư mục đích."""
from __future__ import annotations

import os
import re
from typing import Optional

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MIN_DIGITS = 4


def safe_name(name: str) -> str:
    return _INVALID.sub("_", name.strip()).rstrip(". ") or "_"


def invoice_number(invoice: str) -> str:
    """Phần số của Invoice: 'ISG-240010' -> '240010'; '240010' -> '240010'.

    Trả về '' nếu không có dãy số đủ dài.
    """
    m = re.search(r"(\d+)\D*$", invoice.strip())
    return m.group(1) if m and len(m.group(1)) >= _MIN_DIGITS else ""


def tokhai_number_from_file(path: str, prefix: str) -> str:
    """Lấy số tờ khai từ tên file: 'ToKhaiHQ7N_106001895750.xls' -> '106001895750'."""
    stem = os.path.splitext(os.path.basename(path))[0]
    if stem.lower().startswith(prefix.lower()):
        stem = stem[len(prefix):]
    runs = re.findall(r"\d+", stem)
    return runs[-1] if runs else ""


def dest_folder_name(invoice: str, tokhai: Optional[str]) -> str:
    """Tên thư mục đích: <Invoice>_<TờKhai>, VD ISG-240010_106001895750."""
    inv = invoice.strip()
    tk = (tokhai or "").strip()
    return safe_name(f"{inv}_{tk}" if tk else inv)
