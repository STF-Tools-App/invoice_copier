"""Chỉ mục cấu trúc thư mục (JSON) của NHIỀU thư mục TO / ổ chung.

Định dạng:
{
  "version": 2,
  "roots": { "S:\\\\": {"scanned_at": "...", "folders": [...]}, "D:\\\\": {...} }
}
- scan(): đọc đệ quy từng ổ, thêm thư mục mới vào đúng ổ đó; ổ khác giữ nguyên.
  Ổ không truy cập được thì bỏ qua và giữ dữ liệu cũ.
- find_folders(): tra cứu thư mục theo tên Invoice, xếp theo thứ tự ổ (theo config).
"""
from __future__ import annotations

import json
import os
from bisect import bisect_left
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Callable, Iterable, Optional

from app.core.models import Candidate, ScanResult

ProgressCb = Callable[[int, str], None]


def _key(p: str) -> str:
    return os.path.normcase(os.path.abspath(p))


class FolderIndex:
    VERSION = 2

    def __init__(self, path: Path):
        self.path = path
        self.updated_at = ""
        self.roots: dict[str, list[str]] = {}
        self.scanned_at: dict[str, str] = {}
        self._sorted: list[tuple[str, str, str]] = []
        self._rebuild()

    # ---------- lưu / đọc ----------
    def load(self) -> bool:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        self.updated_at = data.get("updated_at", "")
        self.roots, self.scanned_at = {}, {}
        if "roots" in data:
            for root, info in data["roots"].items():
                self.roots[root] = list(info.get("folders", []))
                self.scanned_at[root] = info.get("scanned_at", "")
        elif data.get("root"):                      # JSON bản cũ (1 ổ)
            self.roots[data["root"]] = list(data.get("folders", []))
            self.scanned_at[data["root"]] = data.get("updated_at", "")
        self._rebuild()
        return True

    def save(self) -> None:
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "version": self.VERSION,
            "updated_at": self.updated_at,
            "roots": {r: {"scanned_at": self.scanned_at.get(r, ""),
                          "count": len(f), "folders": f} for r, f in self.roots.items()},
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def _rebuild(self) -> None:
        self._sorted = sorted(
            (os.path.basename(p).upper(), p, root)
            for root, folders in self.roots.items() for p in folders)

    # ---------- thông tin ----------
    def root_count(self, root: str) -> Optional[int]:
        k = _key(root)
        for r, f in self.roots.items():
            if _key(r) == k:
                return len(f)
        return None

    def root_scanned_at(self, root: str) -> str:
        k = _key(root)
        for r, t in self.scanned_at.items():
            if _key(r) == k:
                return t
        return ""

    @property
    def total(self) -> int:
        return sum(len(f) for f in self.roots.values())

    def remove_root(self, root: str) -> None:
        k = _key(root)
        for r in [r for r in self.roots if _key(r) == k]:
            self.roots.pop(r, None)
            self.scanned_at.pop(r, None)
        self._rebuild()
        self.save()

    # ---------- quét ----------
    def scan(self, roots: Iterable[str], on_progress: Optional[ProgressCb] = None,
             cancel: Optional[Event] = None) -> ScanResult:
        res = ScanResult()
        base = 0
        for root in roots:
            if cancel is not None and cancel.is_set():
                res.cancelled = True
                break
            if not os.path.isdir(root):
                res.skipped.append(root)
                continue
            # gom khoá trùng (khác hoa/thường) về cùng một ổ
            existing = next((r for r in self.roots if _key(r) == _key(root)), root)
            known = set(self.roots.get(existing, []))

            seen, cancelled = self._walk(
                root, (lambda n, cur, b=base: on_progress(b + n, cur)) if on_progress else None, cancel)
            seen_set = set(seen)
            added = sum(1 for p in seen if p not in known)
            if cancelled:                       # quét dở: chỉ bổ sung, không xoá
                merged, removed = known | seen_set, 0
                res.cancelled = True
            else:
                merged, removed = seen_set, len(known - seen_set)
            self.roots[existing] = sorted(merged)
            self.scanned_at[existing] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            res.per_root[existing] = (len(merged), added, removed)
            res.added += added
            res.removed += removed
            base += len(seen)
            if cancelled:
                break

        self._rebuild()
        self.save()
        res.total = self.total
        if on_progress:
            on_progress(res.total, "")
        return res

    @staticmethod
    def _walk(root: str, on_progress, cancel):
        seen: list[str] = []
        stack = [root]
        tick = 0
        while stack:
            if cancel is not None and cancel.is_set():
                return seen, True
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
        return seen, False

    # ---------- tra cứu ----------
    def find_folders(self, invoice: str, root_order: Optional[list[str]] = None) -> list[Candidate]:
        """Thư mục trùng tên Invoice hoặc bắt đầu bằng Invoice + ký tự phân tách.

        'ISG-240010' khớp 'ISG-240010 DHL ETT', KHÔNG khớp 'ISG-2400101'.
        Thứ tự: theo ổ (thứ tự trong config, ổ khác xếp sau) -> khớp chính xác -> thư mục nông nhất.
        """
        key = invoice.strip().upper()
        if not key:
            return []
        rank = {_key(r): i for i, r in enumerate(root_order or [])}
        names = self._sorted
        i = bisect_left(names, (key, "", ""))
        found = []
        while i < len(names) and names[i][0].startswith(key):
            name, path, root = names[i]
            if name == key or not name[len(key)].isalnum():
                found.append((rank.get(_key(root), len(rank)), name != key,
                              path.count(os.sep), path, root))
            i += 1
        found.sort()
        return [Candidate(root=f[4], path=f[3]) for f in found]
