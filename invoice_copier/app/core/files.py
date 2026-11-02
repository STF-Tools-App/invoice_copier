"""Tìm file Invoice PDF và file Tờ khai (ToKhaiHQ7N_...) trong một thư mục."""
from __future__ import annotations

import os
import re
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


def _top_files(folder: str) -> list[tuple[str, str]]:
    try:
        with os.scandir(folder) as it:
            return [(e.name, e.path) for e in it if e.is_file()]
    except OSError:
        return []


def _sub_files(folder: str) -> list[tuple[str, str]]:
    out = []
    for dirpath, _dirs, filenames in os.walk(folder):
        if dirpath != folder:
            out.extend((fn, os.path.join(dirpath, fn)) for fn in filenames)
    return out


def _pdf_pattern(invoice: str) -> re.Pattern:
    """Khớp mọi tên PDF có chứa số Invoice (không dính vào dãy số dài hơn).

    'ISS-240019' -> khớp '240019.pdf', 'ISS-240019.pdf', 'ISS-240019  CUS DOC.pdf'
                    nhưng KHÔNG khớp '2400190.pdf'.
    Invoice không có số thì khớp theo cả chuỗi Invoice.
    """
    inv = invoice.strip()
    num = invoice_number(inv)
    if num:
        return re.compile(rf"(?<!\d){re.escape(num)}(?!\d)")
    return re.compile(re.escape(inv), re.IGNORECASE)


def find_invoice_pdfs(folder: str, invoice: str) -> list[str]:
    """Mọi file PDF chứa số Invoice trong thư mục (ưu tiên cấp ngoài cùng, không có mới xét thư mục con).

    Thứ tự: '<Invoice>.pdf' -> '<số>.pdf' -> các file còn lại (theo tên).
    """
    rx = _pdf_pattern(invoice)
    full = f"{invoice.strip()}.pdf".lower()
    num = invoice_number(invoice)
    only_num = f"{num}.pdf".lower() if num else ""

    def pick(files):
        return [(n, p) for n, p in files if n.lower().endswith(".pdf") and rx.search(n)]

    hits = pick(_top_files(folder)) or pick(_sub_files(folder))

    def rank(item):
        low = item[0].lower()
        return (0 if low == full else 1 if low == only_num else 2, low)

    return [p for _n, p in sorted(hits, key=rank)]


def find_invoice_pdf(folder: str, invoice: str) -> Optional[str]:
    """File PDF ưu tiên nhất (hoặc None)."""
    hits = find_invoice_pdfs(folder, invoice)
    return hits[0] if hits else None


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
