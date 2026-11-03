"""Luồng xử lý chính: tra JSON -> thử lần lượt từng thư mục/ổ -> copy ra ổ riêng.

Với mỗi Invoice:
  1. Lấy mọi thư mục khớp tên trong JSON, xếp theo ổ (thứ tự trong config).
  2. Thử lần lượt từng thư mục: có <Invoice>.pdf VÀ file tờ khai đúng số -> lấy.
     Không đủ -> sang thư mục kế tiếp (hết ổ này thì sang ổ khác trong JSON).
  3. Hết mà không có -> ghi log lỗi. Nếu không có thư mục nào khớp -> quét lại các ổ rồi thử lại.
Ra ổ riêng: <ổ riêng>/<Invoice>_<TờKhai>/ chứa file PDF + file tờ khai (giữ nguyên tên file gốc)
"""
from __future__ import annotations

import os
import shutil
from threading import Event
from typing import Callable, Optional

from app.constants import (STATUS_ERROR, STATUS_MULTI, STATUS_NO_FILES, STATUS_NO_FOLDER,
                           STATUS_OK, STATUS_SKIPPED)
from app.core.config import AppConfig
from app.core.files import find_invoice_pdfs, find_tokhai_files
from app.core.index import FolderIndex
from app.core.models import Job, JobResult, Resolution
from app.core.naming import dest_folder_name, invoice_number, tokhai_number_from_file

Emit = Callable[..., None]   # emit(event, *payload)
Note = Callable[[str, str], None]

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

    num = invoice_number(job.invoice)
    attempts: list[str] = []
    for n, c in enumerate(reachable, 1):
        pdfs = find_invoice_pdfs(c.path, job.invoice, tuple(cfg.ignored_pdf_tokens))
        tks = find_tokhai_files(c.path, cfg.tokhai_prefix, job.tokhai)
        problems = []
        if not pdfs:
            problems.append(f"không có file PDF chứa {num or job.invoice.strip()}")
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
        if len(pdfs) > 1:
            note("warn", f"[{job.invoice}] Có nhiều hơn một file Inv ({len(pdfs)} file PDF): "
                         + ", ".join(os.path.basename(p) for p in pdfs) + " → lấy tất cả")
        elif os.path.basename(pdfs[0]).lower() != f"{job.invoice.strip()}.pdf".lower():
            note("info", f"[{job.invoice}] Dùng file {os.path.basename(pdfs[0])}")
        if attempts:
            note("info", f"[{job.invoice}] Lấy được ở {where} sau khi bỏ qua {len(attempts)} thư mục")
        tk_no = job.tokhai.strip() or tokhai_number_from_file(tks[0], cfg.tokhai_prefix)
        return Resolution(job, "ok", folder=c.path, root=c.root, pdf=pdfs[0], pdfs=pdfs,
                          tokhai_file=tks[0], tokhai_no=tk_no, tried=n)
    return Resolution(job, "no_files", folder=reachable[0].path,
                      message=" | ".join(attempts), tried=len(reachable))


# ------------------------------------------------------------------ copy
def copy_job(res: Resolution, dest_root: str, overwrite: bool,
             overwrite_folder: bool = False) -> JobResult:
    dest = os.path.join(dest_root, dest_folder_name(res.job.invoice, res.tokhai_no))
    if overwrite_folder and os.path.exists(dest):
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        else:
            os.remove(dest)
    os.makedirs(dest, exist_ok=True)
    copied, skipped = [], []
    pdfs = res.pdfs or ([res.pdf] if res.pdf else [])
    used = set()
    for src in [*pdfs, res.tokhai_file]:
        name = os.path.basename(src)
        if name.casefold() in used:
            stem, ext = os.path.splitext(name)
            suffix = 2
            while f"{stem}_{suffix}{ext}".casefold() in used:
                suffix += 1
            name = f"{stem}_{suffix}{ext}"
        used.add(name.casefold())
        target = os.path.join(dest, name)
        if (os.path.exists(target) and not overwrite
                and os.path.getsize(target) == os.path.getsize(src)):
            skipped.append(name)
            continue
        shutil.copy2(src, target)
        copied.append(name)
    status = STATUS_MULTI if len(pdfs) > 1 else STATUS_OK if copied else STATUS_SKIPPED
    msg = ", ".join(copied or skipped) + f"  ← {os.path.basename(res.folder)} [{root_label(res.root or '')}]"
    if len(pdfs) > 1:
        msg = f"⚠ Có nhiều hơn 1 file Inv ({len(pdfs)} file PDF) – đã lấy tất cả. " + msg
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
                    r = copy_job(res, cfg.dest_root, cfg.overwrite, cfg.overwrite_folder)
                    level = {STATUS_OK: "ok", STATUS_MULTI: "warn"}.get(r.status, "info")
                    log(level, f"[{job.invoice}] {r.status}: {r.message}")
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
    ok = sum(1 for r in out if r.status in (STATUS_OK, STATUS_SKIPPED, STATUS_MULTI))
    multi = sum(1 for r in out if r.status == STATUS_MULTI)
    log("info", f"Hoàn tất: {ok}/{len(jobs)} thành công"
                f"{f' (trong đó {multi} invoice có nhiều hơn 1 file Inv)' if multi else ''}, "
                f"{len(jobs) - ok} lỗi/thiếu.")
    return out
