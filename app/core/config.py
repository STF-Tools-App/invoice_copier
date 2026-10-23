"""Đọc/ghi cấu hình người dùng (ổ chung, ổ riêng, tuỳ chọn) vào config.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from app.constants import DEFAULT_TOKHAI_PREFIX
from app.core.paths import config_file


@dataclass
class AppConfig:
    source_root: str = ""          # thư mục TO trên ổ chung
    dest_root: str = ""            # thư mục đích trên ổ riêng
    auto_rescan: bool = True       # không thấy trong index -> tự quét lại
    overwrite: bool = False        # ghi đè file đã có ở đích
    open_dest_when_done: bool = True
    tokhai_prefix: str = DEFAULT_TOKHAI_PREFIX
    last_excel_dir: str = ""

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        path = path or config_file()
        cfg = cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {f.name for f in fields(cls)}
            for k, v in data.items():
                if k in known:
                    setattr(cfg, k, v)
        except (OSError, ValueError):
            pass
        return cfg

    def save(self, path: Path | None = None) -> None:
        path = path or config_file()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
