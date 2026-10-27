"""Luồng xử lý chính: tra JSON -> thử lần lượt từng thư mục/ổ -> copy ra ổ riêng.

Với mỗi Invoice:
  1. Lấy mọi thư mục khớp tên trong JSON, xếp theo ổ (thứ tự trong config).
  2. Thử lần lượt từng thư mục: có <Invoice>.pdf VÀ file tờ khai đúng số -> lấy.
     Không đủ -> sang thư mục kế tiếp (hết ổ này thì sang ổ khác trong JSON).
  3. Hết mà không có -> ghi log lỗi. Nếu không có thư mục nào khớp -> quét lại các ổ rồi thử lại.
Ra ổ riêng: <ổ riêng>/<Invoice>/<Invoice>.pdf + <ổ riêng>/<Invoice>/ToKhaiHQ7N_...xls
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
Note = Callable[[str, str], None]

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name: str) -> str:
    return _INVALID.sub("_", name.strip()).rstrip(". ") or "_"


def root_label(root: str) -> str:
    return os.path.splitdrive(root)[0] or root


# ---------------------------------------------------------------- tra cứu
def resolve(job: Job, index: FolderIndex, cfg: AppConfig, note: Optional[Note] = None) -> Resolution:
    note = note or (lambda *_: None)
    cands = index.find_folders(job.invoice, cfg.source_roots)
    reachable = [c for c in cands if os.path.isdir(c.path)]
    for c in cands:
        if c not in reachable:
            note("warn", f"[{job.invoice}] Không truy cập được {c.path} (ổ {root_label(c.root)} offline/đã đổi tên?)")
    if not reachable:
        return Resolution(job, "no_folder", message="Không có thư mục trùng tên Invoice trong JSON")

    attempts: list[str] = []
    for n, c in enumerate(reachable, 1):
        pdf = find_invoice_pdf(c.path, job.invoice)
        tks = find_tokhai_files(c.path, cfg.tokhai_prefix, job.tokhai)
        problems = []
        if not pdf:
            problems.append(f"không có {job.invoice}.pdf")
        if not tks:
            problems.append("không có tờ khai" + (f" {job.tokhai}" if job.tokhai else ""))
        elif len(tks) > 1 and not job.tokhai:
            problems.append(f"có {len(tks)} file tờ khai (cần nhập số tờ khai)")
        where = f"{os.path.basename(c.path)} [{root_label(c.root)}]"
        if problems:
            txt = f"{where}: " + "; ".join(problems)
            attempts.append(txt)
            if n < len(reachable):
                note("info", f"[{job.invoice}] {txt} → thử thư mục tiếp theo")
            continue
        if attempts:
            note("info", f"[{job.invoice}] Lấy được ở {where} sau khi bỏ qua {len(attempts)} thư mục")
        return Resolution(job, "ok", folder=c.path, root=c.root, pdf=pdf,
                          tokhai_file=tks[0], tried=n)
    return Resolution(job, "no_files", folder=reachable[0].path,
                      message=" | ".join(attempts), tried=len(reachable))


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
    msg = ", ".join(copied or skipped) + f"  ← {os.path.basename(res.folder)} [{root_label(res.root or '')}]"
    return JobResult(res.job, status, msg, dest, copied + skipped)


# ---------------------------------------------------------- luồng chính
def process(jobs: list[Job], cfg: AppConfig, index: FolderIndex, emit: Emit,
            cancel: Optional[Event] = None) -> list[JobResult]:
    cancel = cancel or Event()
    results: dict[str, JobResult] = {}

    def log(level: str, msg: str):
        emit("log", level, msg)

    def finish(r: JobResult):
        results[r.job.key] = r
        emit("result", r)
        emit("progress", len(results), len(jobs))

    log("info", f"Bắt đầu xử lý {len(jobs)} invoice...")
    if not cfg.source_roots:
        log("error", "Chưa cấu hình ổ chung nào.")
        return []
    offline = [r for r in cfg.source_roots if not os.path.isdir(r)]
    for r in offline:
        log("warn", f"Ổ/thư mục không truy cập được: {r}")
    os.makedirs(cfg.dest_root, exist_ok=True)

    # Ổ mới thêm vào config mà chưa có trong JSON -> đọc & lưu tiếp vào JSON trước khi tìm
    new_roots = [r for r in cfg.source_roots
                 if index.root_count(r) is None and os.path.isdir(r)]
    if new_roots and cfg.auto_rescan:
        log("warn", "Ổ chưa có trong JSON, đang đọc: " + ", ".join(new_roots))
        try:
            sr = index.scan(new_roots, lambda n, cur: emit("scan_progress", n, cur), cancel)
            emit("scan_done", sr)
            log("info", f"Đã thêm {sr.added:,} thư mục vào JSON.")
        except OSError as e:
            log("error", f"Không quét được ổ mới: {e}")

    def attempt(pending: list[Job]) -> list[Resolution]:
        missing = []
        for job in pending:
            if cancel.is_set():
                break
            res = resolve(job, index, cfg, note=log)
            if res.kind == "no_folder":
                missing.append(res)
            elif res.kind == "no_files":
                log("error", f"[{job.invoice}] Đã thử {res.tried} thư mục nhưng không đủ file: {res.message}")
                finish(JobResult(job, STATUS_NO_FILES, res.message, res.folder or ""))
            else:
                try:
                    r = copy_job(res, cfg.dest_root, cfg.overwrite)
                    log("ok" if r.status == STATUS_OK else "info", f"[{job.invoice}] {r.status}: {r.message}")
                    finish(r)
                except OSError as e:
                    log("error", f"[{job.invoice}] Lỗi copy: {e}")
                    finish(JobResult(job, STATUS_ERROR, str(e)))
        return missing

    missing = attempt(jobs)

    if missing and cfg.auto_rescan and not cancel.is_set():
        log("warn", f"{len(missing)} invoice chưa có trong JSON -> quét lại các ổ...")
        try:
            sr = index.scan(cfg.source_roots, lambda n, cur: emit("scan_progress", n, cur), cancel)
            emit("scan_done", sr)
            for r in sr.skipped:
                log("warn", f"Bỏ qua {r} (không truy cập được), giữ dữ liệu cũ trong JSON.")
            log("info", f"Quét xong: {sr.total:,} thư mục (+{sr.added:,} mới).")
        except OSError as e:
            log("error", f"Không quét được: {e}")
        missing = attempt([m.job for m in missing])

    for res in missing:
        log("error", f"[{res.job.invoice}] Không tìm thấy thư mục nào trong tất cả các ổ (đã tra JSON).")
        finish(JobResult(res.job, STATUS_NO_FOLDER, res.message))

    out = list(results.values())
    ok = sum(1 for r in out if r.status in (STATUS_OK, STATUS_SKIPPED))
    log("info", f"Hoàn tất: {ok}/{len(jobs)} thành công, {len(jobs) - ok} lỗi/thiếu.")
    return out
