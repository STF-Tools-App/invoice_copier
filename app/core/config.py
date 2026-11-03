"""Đọc/ghi cấu hình người dùng (các ổ chung, ổ riêng, tuỳ chọn) vào config.json."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from app.constants import DEFAULT_TOKHAI_PREFIX
from app.core.paths import config_file, ignored_pdf_tokens_file


def norm_root(p: str) -> str:
    return os.path.normpath(p.strip())


@dataclass
class AppConfig:
    source_roots: list[str] = field(default_factory=list)   # các thư mục TO (nhiều ổ chung)
    dest_root: str = ""                                      # thư mục đích trên ổ riêng
    auto_rescan: bool = True       # không thấy Invoice trong JSON -> tự quét lại
    overwrite: bool = False
    overwrite_folder: bool = False  # thay toàn bộ thư mục invoice đích bằng bộ file mới
    open_dest_when_done: bool = True
    tokhai_prefix: str = DEFAULT_TOKHAI_PREFIX
    last_excel_dir: str = ""
    last_export_dir: str = ""
    ignored_pdf_tokens: list[str] = field(default_factory=lambda: ["PLV", "PL V", "CO"])

    def add_root(self, root: str) -> bool:
        root = norm_root(root)
        keys = {os.path.normcase(r) for r in self.source_roots}
        if not root or os.path.normcase(root) in keys:
            return False
        self.source_roots.append(root)
        return True

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        path = path or config_file()
        cfg = cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cfg
        known = {f.name for f in fields(cls)}
        for k, v in data.items():
            if k in known:
                setattr(cfg, k, v)
        try:
            tokens = json.loads(ignored_pdf_tokens_file().read_text(encoding="utf-8"))
            if isinstance(tokens, list):
                cfg.ignored_pdf_tokens = list(dict.fromkeys(
                    str(token).strip() for token in tokens if str(token).strip()))
        except (OSError, ValueError):
            pass
        legacy = data.get("source_root")          # bản cũ chỉ có 1 ổ
        if legacy:
            cfg.add_root(legacy)
        return cfg

    def save(self, path: Path | None = None) -> None:
        path = path or config_file()
        tmp = path.with_suffix(".tmp")
        data = asdict(self)
        tokens = data.pop("ignored_pdf_tokens", [])
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        token_path = ignored_pdf_tokens_file()
        token_tmp = token_path.with_suffix(".tmp")
        token_tmp.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")
        token_tmp.replace(token_path)
