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


def find_invoice_pdf(folder: str, invoice: str, ignored_tokens: tuple[str, ...] = ()) -> Optional[str]:
    """Ưu tiên ISG-240010.pdf; không có thì lấy 240010.pdf."""
    wanted = [n.lower() for n in invoice_pdf_names(invoice)]
    found: dict[str, str] = {}
    for name, path in _iter_files(folder):
        low = name.lower()
        if any(token.casefold() in low.casefold() for token in ignored_tokens if token):
            continue
        if low in wanted and low not in found:
            found[low] = path
            if low == wanted[0]:        # đã có file ưu tiên cao nhất
                break
    for w in wanted:
        if w in found:
            return found[w]
    return None


def find_invoice_pdfs(folder: str, invoice: str,
                      ignored_tokens: tuple[str, ...] = ()) -> list[str]:
    """Tìm mọi PDF khớp Invoice, ưu tiên file ở thư mục gốc và bỏ qua tên bị cấm."""
    inv = invoice.strip()
    num = invoice_number(inv)
    rx = re.compile(rf"(?<!\d){re.escape(num)}(?!\d)") if num else re.compile(re.escape(inv), re.IGNORECASE)
    ignored = tuple(token.casefold() for token in ignored_tokens if token)

    def pick(files):
        return [(name, path) for name, path in files
                if name.lower().endswith(".pdf")
                and not any(token in name.casefold() for token in ignored)
                and rx.search(name)]

    try:
        with os.scandir(folder) as entries:
            top = [(e.name, e.path) for e in entries if e.is_file()]
    except OSError:
        top = []
    hits = pick(top)
    if not hits:
        subs = []
        for dirpath, _dirs, filenames in os.walk(folder):
            if dirpath != folder:
                subs.extend((name, os.path.join(dirpath, name)) for name in filenames)
        hits = pick(subs)

    full = f"{inv}.pdf".lower()
    only_num = f"{num}.pdf".lower() if num else ""
    hits.sort(key=lambda item: (0 if item[0].lower() == full else
                                1 if only_num and item[0].lower() == only_num else 2,
                                item[0].casefold()))
    return [path for _name, path in hits]


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
