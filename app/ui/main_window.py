"""Cửa sổ chính của ứng dụng (Tkinter)."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from app.constants import (APP_NAME, APP_VERSION, STATUS_ERROR, STATUS_NO_FILES,
                           STATUS_NO_FOLDER, STATUS_OK, STATUS_PENDING, STATUS_SKIPPED)
from app.core import excel_io
from app.core.config import AppConfig
from app.core.index import FolderIndex
from app.core.models import Job, JobResult
from app.core.paths import config_dir, index_file
from app.core.service import process
from app.ui import theme


class MainWindow(ttk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root, padding=14)
        self.root = root
        self.cfg = AppConfig.load()
        self.index = FolderIndex(index_file())
        self.index.load()

        self.jobs: list[Job] = []
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.busy = False

        self.var_src = tk.StringVar(value=self.cfg.source_root)
        self.var_dst = tk.StringVar(value=self.cfg.dest_root)
        self.var_rescan = tk.BooleanVar(value=self.cfg.auto_rescan)
        self.var_overwrite = tk.BooleanVar(value=self.cfg.overwrite)
        self.var_open = tk.BooleanVar(value=self.cfg.open_dest_when_done)
        self.var_inv = tk.StringVar()
        self.var_tk = tk.StringVar()
        self.var_index_info = tk.StringVar()
        self.var_summary = tk.StringVar(value="Sẵn sàng.")

        root.title(f"{APP_NAME} v{APP_VERSION}")
        root.geometry("1000x820")
        root.minsize(900, 700)
        theme.apply_theme(root)
        self.pack(fill="both", expand=True)
        self._build()
        self._refresh_index_info()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)

    # ================================================================ UI
    def _build(self) -> None:
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(0, 10))
        ttk.Label(head, text="📁 Invoice Copier", style="Title.TLabel").pack(anchor="w")
        ttk.Label(head, text="Copy Invoice (.pdf) + Tờ khai (ToKhaiHQ7N_…) từ ổ chung sang ổ riêng, "
                             "mỗi Invoice một thư mục.", style="Sub.TLabel").pack(anchor="w")

        # 1. Cấu hình
        box = ttk.LabelFrame(self, text=" 1. Cấu hình đường dẫn ", padding=10)
        box.pack(fill="x", pady=4)
        box.columnconfigure(1, weight=1)
        self._path_row(box, 0, "Thư mục TO (ổ chung):", self.var_src, self._pick_src)
        self._path_row(box, 1, "Thư mục ổ riêng:", self.var_dst, self._pick_dst)
        opts = ttk.Frame(box, style="Card.TFrame")
        opts.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Checkbutton(opts, text="Tự quét lại khi không thấy Invoice trong chỉ mục",
                        variable=self.var_rescan).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(opts, text="Ghi đè file đã tồn tại", variable=self.var_overwrite).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(opts, text="Mở thư mục đích khi xong", variable=self.var_open).pack(side="left")

        # 2. Chỉ mục
        box2 = ttk.LabelFrame(self, text=" 2. Chỉ mục thư mục (JSON) ", padding=10)
        box2.pack(fill="x", pady=4)
        self.btn_scan = ttk.Button(box2, text="🔍  ĐỌC THƯ MỤC TO", style="Big.TButton", command=self._scan)
        self.btn_scan.pack(side="left")
        self.btn_stop = ttk.Button(box2, text="Dừng", command=self.cancel_event.set, state="disabled")
        self.btn_stop.pack(side="left", padx=8)
        info = ttk.Frame(box2, style="Card.TFrame")
        info.pack(side="left", fill="x", expand=True, padx=14)
        ttk.Label(info, textvariable=self.var_index_info, style="Card.TLabel",
                  justify="left", wraplength=520).pack(anchor="w")
        ttk.Button(box2, text="Mở thư mục config", command=lambda: self._open(str(config_dir()))).pack(side="right")

        # 3. Danh sách
        box3 = ttk.LabelFrame(self, text=" 3. Danh sách Invoice & Tờ khai ", padding=10)
        box3.pack(fill="both", expand=True, pady=4)
        bar = ttk.Frame(box3, style="Card.TFrame")
        bar.pack(fill="x")
        ttk.Button(bar, text="📥 Nhập từ Excel/CSV", command=self._import_excel).pack(side="left")
        ttk.Button(bar, text="📋 Dán từ clipboard", command=self._paste).pack(side="left", padx=6)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(bar, text="Invoice", style="Card.TLabel").pack(side="left")
        e1 = ttk.Entry(bar, textvariable=self.var_inv, width=18)
        e1.pack(side="left", padx=4)
        ttk.Label(bar, text="Tờ khai", style="Card.TLabel").pack(side="left")
        e2 = ttk.Entry(bar, textvariable=self.var_tk, width=16)
        e2.pack(side="left", padx=4)
        ttk.Button(bar, text="➕ Thêm", command=self._add_manual).pack(side="left")
        e1.bind("<Return>", lambda _e: e2.focus_set())
        e2.bind("<Return>", lambda _e: self._add_manual())
        ttk.Button(bar, text="Xoá tất cả", command=self._clear, style="Danger.TButton").pack(side="right")
        ttk.Button(bar, text="Xoá dòng chọn", command=self._remove_selected).pack(side="right", padx=6)

        cols = ("invoice", "tokhai", "status", "note")
        wrap = ttk.Frame(box3)
        wrap.pack(fill="both", expand=True, pady=(8, 0))
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="extended", height=8)
        for c, t, w in (("invoice", "Invoice", 170), ("tokhai", "Số tờ khai", 150),
                        ("status", "Trạng thái", 150), ("note", "Ghi chú", 420)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("ok", foreground=theme.SUCCESS)
        self.tree.tag_configure("warn", foreground=theme.WARN)
        self.tree.tag_configure("err", foreground=theme.DANGER)
        self.tree.bind("<Delete>", lambda _e: self._remove_selected())

        # 4. Chạy
        run = ttk.Frame(self)
        run.pack(fill="x", pady=(8, 2))
        self.btn_run = ttk.Button(run, text="▶  CHẠY COPY", style="Run.TButton", command=self._run)
        self.btn_run.pack(side="left")
        right = ttk.Frame(run)
        right.pack(side="left", fill="x", expand=True, padx=14)
        self.progress = ttk.Progressbar(right, mode="determinate")
        self.progress.pack(fill="x")
        ttk.Label(right, textvariable=self.var_summary, style="Sub.TLabel").pack(anchor="w", pady=(3, 0))

        # Log
        self.log = scrolledtext.ScrolledText(self, height=8, font=("Consolas", 9), state="disabled",
                                             bg="#111827", fg="#e5e7eb", relief="flat")
        self.log.pack(fill="both", expand=False, pady=(6, 0))
        for tag, color in (("info", "#e5e7eb"), ("ok", "#4ade80"), ("warn", "#fbbf24"), ("error", "#f87171")):
            self.log.tag_configure(tag, foreground=color)

    def _path_row(self, parent, row, label, var, cmd):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Button(parent, text="Chọn…", command=cmd).grid(row=row, column=2, padx=(8, 0), pady=3)

    # ============================================================ helpers
    def _log(self, level: str, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n", level)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _save_cfg(self) -> None:
        self.cfg.source_root = self.var_src.get().strip()
        self.cfg.dest_root = self.var_dst.get().strip()
        self.cfg.auto_rescan = self.var_rescan.get()
        self.cfg.overwrite = self.var_overwrite.get()
        self.cfg.open_dest_when_done = self.var_open.get()
        try:
            self.cfg.save()
        except OSError as e:
            self._log("error", f"Không lưu được config: {e}")

    def _refresh_index_info(self) -> None:
        if self.index.folders:
            ok = self.index.is_valid_for(self.var_src.get().strip())
            txt = f"Đã lập chỉ mục {len(self.index.folders):,} thư mục • cập nhật {self.index.updated_at}"
            if not ok:
                txt += "\n⚠ Chỉ mục thuộc thư mục khác – hãy bấm “Đọc thư mục to”."
        else:
            txt = "Chưa có chỉ mục. Chọn thư mục TO rồi bấm “Đọc thư mục to”."
        self.var_index_info.set(txt)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        st = "disabled" if busy else "normal"
        self.btn_scan.configure(state=st)
        self.btn_run.configure(state=st)
        self.btn_stop.configure(state="normal" if busy else "disabled")

    @staticmethod
    def _open(path: str) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError:
            pass

    # ========================================================== pick dirs
    def _pick_src(self) -> None:
        d = filedialog.askdirectory(title="Chọn thư mục TO trên ổ chung",
                                    initialdir=self.var_src.get() or None)
        if d:
            self.var_src.set(os.path.normpath(d))
            self._save_cfg()
            self._refresh_index_info()

    def _pick_dst(self) -> None:
        d = filedialog.askdirectory(title="Chọn thư mục ổ riêng", initialdir=self.var_dst.get() or None)
        if d:
            self.var_dst.set(os.path.normpath(d))
            self._save_cfg()

    # ============================================================== list
    def _add_jobs(self, new: list[Job]) -> int:
        have = {j.key for j in self.jobs}
        n = 0
        for j in new:
            if j.key in have:
                continue
            have.add(j.key)
            self.jobs.append(j)
            self.tree.insert("", "end", iid=j.key, values=(j.invoice, j.tokhai, STATUS_PENDING, ""))
            n += 1
        self.var_summary.set(f"Có {len(self.jobs)} invoice trong danh sách.")
        return n

    def _add_manual(self) -> None:
        inv = self.var_inv.get().strip()
        if not inv:
            messagebox.showwarning(APP_NAME, "Vui lòng nhập Invoice.")
            return
        self._add_jobs([Job(inv, self.var_tk.get().strip())])
        self.var_inv.set("")
        self.var_tk.set("")

    def _import_excel(self) -> None:
        p = filedialog.askopenfilename(
            title="Chọn file Excel/CSV chứa Invoice & Tờ khai",
            initialdir=self.cfg.last_excel_dir or None,
            filetypes=[("Excel / CSV", "*.xlsx *.xlsm *.xls *.csv"), ("Tất cả", "*.*")])
        if not p:
            return
        try:
            jobs = excel_io.read_jobs_from_file(p)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_NAME, f"Không đọc được file:\n{e}")
            return
        self.cfg.last_excel_dir = os.path.dirname(p)
        n = self._add_jobs(jobs)
        self._log("info", f"Nhập {n} dòng từ {os.path.basename(p)}.")

    def _paste(self) -> None:
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            messagebox.showinfo(APP_NAME, "Clipboard đang trống.")
            return
        n = self._add_jobs(excel_io.parse_text(text))
        self._log("info", f"Dán {n} dòng từ clipboard.")

    def _remove_selected(self) -> None:
        if self.busy:
            return
        sel = set(self.tree.selection())
        for iid in sel:
            self.tree.delete(iid)
        self.jobs = [j for j in self.jobs if j.key not in sel]

    def _clear(self) -> None:
        if self.busy:
            return
        self.tree.delete(*self.tree.get_children())
        self.jobs.clear()
        self.progress["value"] = 0
        self.var_summary.set("Đã xoá danh sách.")

    # ============================================================ actions
    def _validate_paths(self, need_dst: bool) -> bool:
        src = self.var_src.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showwarning(APP_NAME, "Hãy chọn thư mục TO (ổ chung) hợp lệ.")
            return False
        if need_dst and not self.var_dst.get().strip():
            messagebox.showwarning(APP_NAME, "Hãy chọn thư mục ổ riêng.")
            return False
        return True

    def _scan(self) -> None:
        if not self._validate_paths(need_dst=False):
            return
        self._save_cfg()
        self.cancel_event.clear()
        self._set_busy(True)
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self._log("info", "Đang đọc thư mục to…")
        src = self.cfg.source_root

        def work():
            try:
                sr = self.index.scan(src, lambda n, cur: self.events.put(("scan_progress", n, cur)),
                                     self.cancel_event)
                self.events.put(("scan_done", sr))
                self.events.put(("log", "ok", f"Quét xong: {sr.total:,} thư mục "
                                              f"(+{sr.added:,} mới, -{sr.removed:,} đã mất)."
                                 + (" [bị dừng giữa chừng]" if sr.cancelled else "")))
            except Exception as e:  # noqa: BLE001
                self.events.put(("log", "error", f"Lỗi quét: {e}"))
            self.events.put(("idle",))

        threading.Thread(target=work, daemon=True).start()

    def _run(self) -> None:
        if not self.jobs:
            messagebox.showinfo(APP_NAME, "Danh sách trống. Hãy nhập Excel hoặc thêm Invoice.")
            return
        if not self._validate_paths(need_dst=True):
            return
        self._save_cfg()
        self.cancel_event.clear()
        self._set_busy(True)
        self.progress.configure(mode="determinate", maximum=len(self.jobs), value=0)
        for j in self.jobs:
            self.tree.item(j.key, values=(j.invoice, j.tokhai, STATUS_PENDING, ""), tags=())
        jobs = list(self.jobs)

        def work():
            try:
                process(jobs, self.cfg, self.index, lambda *a: self.events.put(a), self.cancel_event)
            except Exception as e:  # noqa: BLE001
                self.events.put(("log", "error", f"Lỗi không mong đợi: {e}"))
            self.events.put(("done",))

        threading.Thread(target=work, daemon=True).start()

    # ======================================================== event loop
    def _poll(self) -> None:
        try:
            while True:
                ev = self.events.get_nowait()
                self._handle(ev)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _handle(self, ev: tuple) -> None:
        kind = ev[0]
        if kind == "log":
            self._log(ev[1], ev[2])
        elif kind == "progress":
            self.progress["value"] = ev[1]
            self.var_summary.set(f"Đã xử lý {ev[1]}/{ev[2]}")
        elif kind == "scan_progress":
            self.var_summary.set(f"Đang quét… {ev[1]:,} thư mục")
        elif kind == "scan_done":
            self._refresh_index_info()
        elif kind == "result":
            self._show_result(ev[1])
        elif kind == "idle":
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
            self.var_summary.set("Sẵn sàng.")
            self._refresh_index_info()
            self._set_busy(False)
        elif kind == "done":
            self._refresh_index_info()
            self._set_busy(False)
            self._finish_summary()

    def _show_result(self, r: JobResult) -> None:
        tag = {STATUS_OK: "ok", STATUS_SKIPPED: "ok", STATUS_NO_FILES: "warn"}.get(r.status, "err")
        if r.job.key in self.tree.get_children():
            self.tree.item(r.job.key, values=(r.job.invoice, r.job.tokhai, r.status, r.message), tags=(tag,))
            self.tree.see(r.job.key)

    def _finish_summary(self) -> None:
        total = len(self.jobs)
        rows = [self.tree.item(i, "values")[2] for i in self.tree.get_children()]
        ok = sum(1 for s in rows if s in (STATUS_OK, STATUS_SKIPPED))
        bad = total - ok
        self.var_summary.set(f"Xong: {ok} thành công • {bad} lỗi/thiếu • tổng {total}")
        if ok and self.var_open.get() and os.path.isdir(self.var_dst.get()):
            self._open(self.var_dst.get())

    def _on_close(self) -> None:
        if self.busy and not messagebox.askyesno(APP_NAME, "Đang xử lý. Bạn có chắc muốn thoát?"):
            return
        self.cancel_event.set()
        self._save_cfg()
        self.root.destroy()
