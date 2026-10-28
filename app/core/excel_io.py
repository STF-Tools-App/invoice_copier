"""Đọc danh sách (Invoice, Tờ khai) từ file Excel/CSV hoặc từ văn bản dán vào."""
from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

from app.core.models import Job


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").lower().strip()


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _read_rows(path: Path) -> list[list[str]]:
    ext = path.suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError as e:
            raise RuntimeError("Thiếu thư viện openpyxl (pip install openpyxl)") from e
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = [[_cell(c) for c in r] for r in ws.iter_rows(values_only=True)]
        wb.close()
        return rows
    if ext == ".xls":
        try:
            import xlrd
        except ImportError as e:
            raise RuntimeError("Thiếu thư viện xlrd (pip install xlrd)") from e
        sh = xlrd.open_workbook(str(path)).sheet_by_index(0)
        return [[_cell(sh.cell_value(r, c)) for c in range(sh.ncols)] for r in range(sh.nrows)]
    if ext in (".csv", ".txt"):
        with open(path, newline="", encoding="utf-8-sig") as f:
            return [[_cell(c) for c in row] for row in csv.reader(f)]
    raise ValueError(f"Định dạng không hỗ trợ: {ext}")


def read_jobs_from_file(path: str | Path) -> list[Job]:
    rows = [r for r in _read_rows(Path(path)) if any(r)]
    if not rows:
        return []

    inv_col, tk_col, start = 0, 1, 0
    header = [_fold(c) for c in rows[0]]
    h_inv = next((i for i, h in enumerate(header) if "invoice" in h or h in ("inv", "so invoice")), None)
    h_tk = next((i for i, h in enumerate(header)
                 if "khai" in h or h in ("tk", "so tk", "declaration")), None)
    if h_inv is not None or h_tk is not None:
        start = 1
        inv_col = h_inv if h_inv is not None else 0
        tk_col = h_tk if h_tk is not None else (inv_col + 1)

    jobs, seen = [], set()
    for r in rows[start:]:
        inv = r[inv_col].strip() if inv_col < len(r) else ""
        tk = r[tk_col].strip() if tk_col < len(r) else ""
        if not inv:
            continue
        job = Job(inv, tk)
        if job.key not in seen:
            seen.add(job.key)
            jobs.append(job)
    return jobs


def parse_text(text: str) -> list[Job]:
    """Mỗi dòng: `Invoice [Tờ khai]` – phân tách bằng tab / dấu phẩy / chấm phẩy / khoảng trắng."""
    jobs, seen = [], set()
    for n, line in enumerate(text.splitlines()):
        if n == 0 and _fold(line).startswith(("invoice", "so invoice", "inv ")):
            continue                      # bỏ dòng tiêu đề khi copy từ Excel
        if "\t" in line:                 # copy từ Excel / từ bảng: giữ ô trống đúng cột
            cells = [c.strip() for c in line.split("\t")]
            if not cells[0]:
                continue
            job = Job(cells[0], cells[1] if len(cells) > 1 else "")
        else:
            parts = [p for p in re.split(r"[,;]+|\s+", line.strip()) if p]
            if not parts:
                continue
            job = Job(parts[0], parts[1] if len(parts) > 1 else "")
        if job.key not in seen:
            seen.add(job.key)
            jobs.append(job)
    return jobs
