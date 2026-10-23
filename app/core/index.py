"""Chỉ mục cấu trúc thư mục (lưu JSON) của thư mục TO.

- scan(): đọc đệ quy toàn bộ thư mục con, thêm thư mục mới vào chỉ mục
  (thư mục đã có thì giữ nguyên, không thêm trùng).
- find_folders(): tra cứu nhanh thư mục theo tên Invoice (bisect).
"""
from __future__ import annotations

import json
import os
from bisect import bisect_left
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Callable, Optional

from app.core.models import ScanResult

ProgressCb = Callable[[int, str], None]


def _norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(p))


class FolderIndex:
    VERSION = 1

    def __init__(self, path: Path):
        self.path = path
        self.root: str = ""
        self.updated_at: str = ""
        self.folders: list[str] = []
        self._sorted: list[tuple[str, str]] = []
        self._rebuild()

    # ---------- lưu / đọc ----------
    def load(self) -> bool:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.root = data.get("root", "")
            self.updated_at = data.get("updated_at", "")
            self.folders = list(data.get("folders", []))
            self._rebuild()
            return True
        except (OSError, ValueError):
            return False

    def save(self) -> None:
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "version": self.VERSION,
            "root": self.root,
            "updated_at": self.updated_at,
            "count": len(self.folders),
            "folders": self.folders,
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def _rebuild(self) -> None:
        self._sorted = sorted((os.path.basename(p).upper(), p) for p in self.folders)

    def is_valid_for(self, root: str) -> bool:
        return bool(self.folders) and bool(root) and _norm(root) == _norm(self.root)

    # ---------- quét ----------
    def scan(self, root: str, on_progress: Optional[ProgressCb] = None,
             cancel: Optional[Event] = None) -> ScanResult:
        if not os.path.isdir(root):
            raise FileNotFoundError(f"Không tìm thấy thư mục: {root}")

        same_root = _norm(root) == _norm(self.root)
        known = set(self.folders) if same_root else set()

        seen: list[str] = []
        stack = [root]
        cancelled = False
        tick = 0
        while stack:
            if cancel is not None and cancel.is_set():
                cancelled = True
                break
            cur = stack.pop()
            try:
                with os.scandir(cur) as it:
                    for e in it:
                        try:
                            if e.is_dir(follow_symlinks=False):
                                seen.append(e.path)
                                stack.append(e.path)
                        except OSError:
                            continue
            except OSError:
                continue
            tick += 1
            if on_progress and tick % 50 == 0:
                on_progress(len(seen), cur)

        seen_set = set(seen)
        added = sum(1 for p in seen if p not in known)
        if cancelled:       # quét dở: chỉ bổ sung, không xoá gì
            merged = known | seen_set
            removed = 0
        else:
            merged = seen_set
            removed = len(known - seen_set)

        self.root = root
        self.folders = sorted(merged)
        self._rebuild()
        self.save()
        if on_progress:
            on_progress(len(self.folders), "")
        return ScanResult(total=len(self.folders), added=added,
                          removed=removed, cancelled=cancelled)

    # ---------- tra cứu ----------
    def find_folders(self, invoice: str) -> list[str]:
        """Thư mục trùng tên Invoice, hoặc bắt đầu bằng Invoice + ký tự phân tách.

        VD: 'IFS-240782' khớp 'IFS-240782 DHL ...' nhưng KHÔNG khớp 'IFS-2407821'.
        Kết quả: khớp chính xác trước, rồi đến thư mục nông nhất.
        """
        key = invoice.strip().upper()
        if not key:
            return []
        names = self._sorted
        i = bisect_left(names, (key, ""))
        exact, prefix = [], []
        while i < len(names) and names[i][0].startswith(key):
            name, path = names[i]
            if name == key:
                exact.append(path)
            elif not name[len(key)].isalnum():
                prefix.append(path)
            i += 1
        prefix.sort(key=lambda p: (p.count(os.sep), p))
        return exact + prefix
