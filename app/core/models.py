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


@dataclass
class Resolution:
    """Kết quả tìm thư mục + 2 file nguồn cho một Job."""
    job: Job
    kind: str = "ok"            # ok | no_folder | no_files
    folder: Optional[str] = None
    pdf: Optional[str] = None
    tokhai_file: Optional[str] = None
    message: str = ""


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
