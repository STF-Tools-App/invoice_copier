"""Chuyển dữ liệu bảng sang clipboard (TSV – dán thẳng vào Excel) và kết xuất file .xlsx."""
from __future__ import annotations

from typing import Sequence

from app.constants import (STATUS_MULTI, STATUS_NO_FILES, STATUS_OK,
                           STATUS_PENDING, STATUS_SKIPPED)

COLUMNS = ("Invoice", "Số tờ khai", "Trạng thái", "Ghi chú")
_OK = {STATUS_OK, STATUS_SKIPPED}


def row_kind(status: str) -> str:
    if status in _OK:
        return "ok"
    if status == STATUS_MULTI:
        return "multi"
    if status == STATUS_NO_FILES:
        return "warn"
    if status == STATUS_PENDING or not status:
        return "pending"
    return "err"


_RANK = {"multi": 0, "pending": 1, "ok": 2, "warn": 3, "err": 3}


def sort_rank(status: str) -> int:
    return _RANK[row_kind(status)]


def _clean(v: object) -> str:
    return str(v).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def rows_to_tsv(rows: Sequence[Sequence[object]], header: Sequence[str] | None = None) -> str:
    """Các ô cách nhau bằng TAB, các dòng cách nhau bằng xuống dòng – đúng định dạng Excel."""
    lines = []
    if header:
        lines.append("\t".join(_clean(h) for h in header))
    lines += ["\t".join(_clean(c) for c in r) for r in rows]
    return "\r\n".join(lines)


def export_xlsx(path: str, rows: Sequence[Sequence[str]], title: str = "Danh sách") -> None:
    """Ghi trạng thái hiện tại của bảng ra Excel (có STT, tô màu theo trạng thái)."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError as e:
        raise RuntimeError("Thiếu thư viện openpyxl (pip install openpyxl)") from e

    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    headers = ("STT",) + tuple(COLUMNS)
    ws.append(headers)

    thin = Side(style="thin", color="D1D5DB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill("solid", fgColor="2563EB")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = border

    fills = {"ok": PatternFill("solid", fgColor="DCFCE7"),
             "multi": PatternFill("solid", fgColor="DDD6FE"),
             "warn": PatternFill("solid", fgColor="FEF3C7"),
             "err": PatternFill("solid", fgColor="FEE2E2")}
    for i, r in enumerate(rows, 1):
        status = r[2] if len(r) > 2 else ""
        ws.append([i] + [str(x) for x in r])
        kind = row_kind(status)
        for c in ws[ws.max_row]:
            c.border = border
            c.alignment = Alignment(vertical="top", wrap_text=(c.column == 5))
            if kind != "pending":
                c.fill = fills[kind]
            if c.column in (2, 3):          # Invoice / Tờ khai luôn là văn bản (tránh 1.06E+11)
                c.number_format = "@"

    widths = [6, 22, 18, 20, 70]
    for idx, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)
