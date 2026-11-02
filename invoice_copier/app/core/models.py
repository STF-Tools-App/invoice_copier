"""Các dataclass dùng chung."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.constants import STATUS_PENDING


@dataclass(frozen=True)
class Job:
    invoice: str
    tokhai: str = ""

    @property
    def key(self) -> str:
        return f"{self.invoice.upper()}|{self.tokhai.upper()}"


@dataclass(frozen=True)
class Candidate:
    """Một thư mục trong chỉ mục, kèm ổ/thư mục gốc chứa nó."""
    root: str
    path: str


@dataclass
class Resolution:
    """Kết quả tìm thư mục + 2 file nguồn cho một Job."""
    job: Job
    kind: str = "ok"            # ok | no_folder | no_files
    folder: Optional[str] = None
    root: Optional[str] = None
    pdf: Optional[str] = None
    pdfs: list[str] = field(default_factory=list)   # mọi PDF Inv tìm được (có thể > 1)
    tokhai_file: Optional[str] = None
    tokhai_no: str = ""
    message: str = ""
    tried: int = 0              # số thư mục đã thử


@dataclass
class JobResult:
    job: Job
    status: str = STATUS_PENDING
    message: str = ""
    dest_folder: str = ""
    files: list[str] = field(default_factory=list)


@dataclass
class ScanResult:
    total: int = 0
    added: int = 0
    removed: int = 0
    cancelled: bool = False
    skipped: list[str] = field(default_factory=list)          # ổ không truy cập được
    per_root: dict[str, tuple[int, int, int]] = field(default_factory=dict)  # root -> (tổng, mới, mất)
