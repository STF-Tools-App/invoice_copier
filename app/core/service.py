"""Luồng xử lý chính: tra index -> (quét lại nếu thiếu) -> copy ra ổ riêng.

Khi copy, mỗi Invoice được đặt trong thư mục riêng tên đúng Invoice:
    <ổ riêng>/<Invoice>/<Invoice>.pdf
    <ổ riêng>/<Invoice>/ToKhaiHQ7N_...xls
"""
from __future__ import annotations

import os
import re
import shutil
from threading import Event
from typing import Callable, Optional

from app.constants import (STATUS_ERROR, STATUS_NO_FILES, STATUS_NO_FOLDER,
                           STATUS_OK, STATUS_SKIPPED)
from app.core.config import AppConfig
from app.core.files import find_invoice_pdf, find_tokhai_files
from app.core.index import FolderIndex
from app.core.models import Job, JobResult, Resolution

Emit = Callable[..., None]   # emit(event, *payload)

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name: str) -> str:
    return _INVALID.sub("_", name.strip()).rstrip(". ") or "_"


# ---------------------------------------------------------------- tra cứu
def resolve(job: Job, index: FolderIndex, cfg: AppConfig) -> Resolution:
    candidates = [p for p in index.find_folders(job.invoice) if os.path.isdir(p)]
    if not candidates:
        return Resolution(job, "no_folder", message="Không có thư mục trùng tên Invoice")

    last_msg = ""
    for folder in candidates:
        pdf = find_invoice_pdf(folder, job.invoice)
        tks = find_tokhai_files(folder, cfg.tokhai_prefix, job.tokhai)
        problems = []
        if not pdf:
            problems.append(f"không có {job.invoice}.pdf")
        if not tks:
            problems.append("không có file tờ khai" + (f" chứa số {job.tokhai}" if job.tokhai else ""))
        elif len(tks) > 1 and not job.tokhai:
            problems.append(f"có {len(tks)} file tờ khai, hãy nhập số tờ khai")
        if problems:
            last_msg = f"{os.path.basename(folder)}: " + "; ".join(problems)
            continue
        return Resolution(job, "ok", folder=folder, pdf=pdf, tokhai_file=tks[0])
    return Resolution(job, "no_files", folder=candidates[0], message=last_msg)


# ------------------------------------------------------------------ copy
def copy_job(res: Resolution, dest_root: str, overwrite: bool) -> JobResult:
    dest = os.path.join(dest_root, safe_name(res.job.invoice))
    os.makedirs(dest, exist_ok=True)
    copied, skipped = [], []
    for src in (res.pdf, res.tokhai_file):
        target = os.path.join(dest, os.path.basename(src))
        if (os.path.exists(target) and not overwrite
                and os.path.getsize(target) == os.path.getsize(src)):
            skipped.append(os.path.basename(src))
            continue
        shutil.copy2(src, target)
        copied.append(os.path.basename(src))
    status = STATUS_OK if copied else STATUS_SKIPPED
    msg = ", ".join(copied or skipped)
    return JobResult(res.job, status, msg, dest, copied + skipped)


# ---------------------------------------------------------- luồng chính
def process(jobs: list[Job], cfg: AppConfig, index: FolderIndex, emit: Emit,
            cancel: Optional[Event] = None) -> list[JobResult]:
    cancel = cancel or Event()
    results: dict[str, JobResult] = {}

    def finish(r: JobResult):
        results[r.job.key] = r
        emit("result", r)
        emit("progress", len(results), len(jobs))

    emit("log", "info", f"Bắt đầu xử lý {len(jobs)} invoice...")
    if not os.path.isdir(cfg.source_root):
        emit("log", "error", f"Thư mục ổ chung không tồn tại: {cfg.source_root}")
        return []
    os.makedirs(cfg.dest_root, exist_ok=True)

    if not index.is_valid_for(cfg.source_root):
        emit("log", "warn", "Chưa có chỉ mục phù hợp với thư mục ổ chung hiện tại.")

    def attempt(pending: list[Job]) -> list[Resolution]:
        """Resolve + copy; trả về các Job chưa tìm thấy thư mục."""
        missing = []
        for job in pending:
            if cancel.is_set():
                break
            res = resolve(job, index, cfg)
            if res.kind == "no_folder":
                missing.append(res)
            elif res.kind == "no_files":
                emit("log", "warn", f"[{job.invoice}] {res.message}")
                finish(JobResult(job, STATUS_NO_FILES, res.message, res.folder or ""))
            else:
                try:
                    r = copy_job(res, cfg.dest_root, cfg.overwrite)
                    emit("log", "ok" if r.status == STATUS_OK else "info",
                         f"[{job.invoice}] {r.status}: {r.message}")
                    finish(r)
                except OSError as e:
                    emit("log", "error", f"[{job.invoice}] Lỗi copy: {e}")
                    finish(JobResult(job, STATUS_ERROR, str(e)))
        return missing

    missing = attempt(jobs)

    if missing and cfg.auto_rescan and not cancel.is_set():
        emit("log", "warn", f"{len(missing)} invoice chưa có trong chỉ mục -> quét lại thư mục to...")
        try:
            sr = index.scan(cfg.source_root,
                            lambda n, cur: emit("scan_progress", n, cur), cancel)
            emit("scan_done", sr)
            emit("log", "info", f"Quét xong: {sr.total} thư mục (+{sr.added} mới).")
        except OSError as e:
            emit("log", "error", f"Không quét được: {e}")
        missing = attempt([m.job for m in missing])

    for res in missing:
        emit("log", "error", f"[{res.job.invoice}] Không tìm thấy thư mục.")
        finish(JobResult(res.job, STATUS_NO_FOLDER, res.message))

    out = list(results.values())
    ok = sum(1 for r in out if r.status in (STATUS_OK, STATUS_SKIPPED))
    emit("log", "info", f"Hoàn tất: {ok}/{len(jobs)} thành công.")
    return out
