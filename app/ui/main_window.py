"""Cửa sổ chính của ứng dụng (Tkinter)."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext, ttk

from app.constants import (APP_NAME, APP_VERSION, STATUS_NO_FILES, STATUS_OK,
                           STATUS_PENDING, STATUS_SKIPPED)
from app.core import excel_io
from app.core.config import AppConfig, norm_root
from app.core.index import FolderIndex
from app.core.logger import log as file_log
from app.core.models import Job, JobResult
from app.core.paths import config_dir, index_file
from app.core.service import process
from app.core.table_io import COLUMNS, export_xlsx, rows_to_tsv
from app.ui import theme

SUCCESS_STATUSES = (STATUS_OK, STATUS_SKIPPED)


class MainWindow(ttk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root, padding=14)
        self.root = root
        self.cfg = AppConfig.load()
        self.index = FolderIndex(index_file())
        self.index.load()

        self.jobs: list[Job] = []
        self.job_map: dict[str, Job] = {}            # iid -> Job (giữ nguyên chuỗi, không bị Tk đổi kiểu số)
        self.row_state: dict[str, list[str]] = {}    # iid -> [trạng thái, ghi chú]
        self._anchor: str | None = None              # dòng bắt đầu khi kéo chọn
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.busy = False

        self.var_dst = tk.StringVar(value=self.cfg.dest_root)
        self.var_rescan = tk.BooleanVar(value=self.cfg.auto_rescan)
        self.var_overwrite = tk.BooleanVar(value=self.cfg.overwrite)
        self.var_open = tk.BooleanVar(value=self.cfg.open_dest_when_done)
        self.var_summary = tk.StringVar(value="Sẵn sàng.")

        root.title(f"{APP_NAME} v{APP_VERSION}")
        root.geometry("1020x860")
        root.minsize(920, 720)
        theme.apply_theme(root)
        self.pack(fill="both", expand=True)
        self._build()
        self._refresh_roots()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)

    # ================================================================ UI
    def _build(self) -> None:
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(0, 8))
        ttk.Label(head, text="📁 Invoice Copier", style="Title.TLabel").pack(anchor="w")
        ttk.Label(head, text="Copy Invoice (.pdf) + Tờ khai (ToKhaiHQ7N_…) từ các ổ chung sang ổ riêng, "
                             "mỗi Invoice một thư mục.", style="Sub.TLabel").pack(anchor="w")

        # 1. Cấu hình
        box = ttk.LabelFrame(self, text=" 1. Ổ chung (thư mục TO) & ổ riêng ", padding=10)
        box.pack(fill="x", pady=4)
        box.columnconfigure(1, weight=1)

        ttk.Label(box, text="Các ổ chung:", style="Card.TLabel").grid(row=0, column=0, sticky="nw", padx=(0, 8))
        lwrap = ttk.Frame(box)
        lwrap.grid(row=0, column=1, sticky="ew")
        self.lst_roots = tk.Listbox(lwrap, height=4, activestyle="none", font=(theme.FONT, 10),
                                    selectmode="browse", relief="solid", borderwidth=1,
                                    highlightthickness=0)
        lsb = ttk.Scrollbar(lwrap, orient="vertical", command=self.lst_roots.yview)
        self.lst_roots.configure(yscrollcommand=lsb.set)
        self.lst_roots.pack(side="left", fill="x", expand=True)
        lsb.pack(side="right", fill="y")
        rbtn = ttk.Frame(box, style="Card.TFrame")
        rbtn.grid(row=0, column=2, sticky="n", padx=(8, 0))
        ttk.Button(rbtn, text="➕ Thêm ổ…", command=self._add_root).pack(fill="x")
        ttk.Button(rbtn, text="🗑 Bỏ ổ", command=self._remove_root).pack(fill="x", pady=(4, 0))

        ttk.Label(box, text="Thư mục ổ riêng:", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(box, textvariable=self.var_dst).grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(box, text="Chọn…", command=self._pick_dst).grid(row=1, column=2, padx=(8, 0), pady=(8, 0))

        opts = ttk.Frame(box, style="Card.TFrame")
        opts.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Checkbutton(opts, text="Tự đọc/quét lại khi ổ mới hoặc không thấy Invoice trong JSON",
                        variable=self.var_rescan).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(opts, text="Ghi đè file đã có", variable=self.var_overwrite).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(opts, text="Mở thư mục đích khi xong", variable=self.var_open).pack(side="left")

        # 2. Chỉ mục
        box2 = ttk.LabelFrame(self, text=" 2. Chỉ mục thư mục (JSON) ", padding=10)
        box2.pack(fill="x", pady=4)
        self.btn_scan = ttk.Button(box2, text="🔍  ĐỌC THƯ MỤC TO", style="Big.TButton",
                                   command=lambda: self._scan(None))
        self.btn_scan.pack(side="left")
        self.btn_stop = ttk.Button(box2, text="Dừng", command=self.cancel_event.set, state="disabled")
        self.btn_stop.pack(side="left", padx=8)
        self.lbl_index = ttk.Label(box2, text="", style="Card.TLabel", justify="left")
        self.lbl_index.pack(side="left", padx=14)
        ttk.Button(box2, text="Mở thư mục config", command=lambda: self._open(str(config_dir()))).pack(side="right")

        # 3. Danh sách
        box3 = ttk.LabelFrame(self, text=" 3. Danh sách Invoice & Tờ khai ", padding=10)
        box3.pack(fill="both", expand=True, pady=4)
        bar = ttk.Frame(box3, style="Card.TFrame")
        bar.pack(fill="x")
        ttk.Button(bar, text="📥 Nhập từ Excel/CSV", command=self._import_excel).pack(side="left")
        ttk.Button(bar, text="📋 Dán từ clipboard", command=self._paste).pack(side="left", padx=6)
        ttk.Button(bar, text="Xoá tất cả", command=self._clear, style="Danger.TButton").pack(side="right")
        ttk.Button(bar, text="🧹 Xoá dòng đã copy thành công", command=self._remove_done).pack(side="right", padx=6)
        ttk.Button(bar, text="📤 Kết xuất Excel", command=self._export_excel,
                   style="Primary.TButton").pack(side="right")
        ttk.Label(box3, style="Muted.TLabel", wraplength=940,
                  text="Ctrl+V dán • Ctrl+C copy dòng chọn • Ctrl+A chọn tất cả • kéo chuột / Shift / Ctrl để chọn nhiều dòng • "
                       "chuột phải: copy ô / cột / cả bảng • Delete hoặc Backspace xoá dòng chọn"
                  ).pack(anchor="w", pady=(6, 0))

        cols = ("invoice", "tokhai", "status", "note")
        wrap = ttk.Frame(box3)
        wrap.pack(fill="both", expand=True, pady=(8, 0))
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="extended", height=8)
        for c, t, w in (("invoice", "Invoice", 160), ("tokhai", "Số tờ khai", 140),
                        ("status", "Trạng thái", 150), ("note", "Ghi chú", 460)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("ok", foreground=theme.SUCCESS)
        self.tree.tag_configure("warn", foreground=theme.WARN)
        self.tree.tag_configure("err", foreground=theme.DANGER)

        self.tree.bind("<Button-1>", self._on_tree_click, add="+")
        self.tree.bind("<B1-Motion>", self._on_tree_drag, add="+")
        self.tree.bind("<Button-3>", self._on_tree_context)
        for seq in ("<Control-c>", "<Control-C>"):
            self.tree.bind(seq, self._on_tree_copy)
        for seq in ("<Control-v>", "<Control-V>"):
            self.tree.bind(seq, self._on_tree_paste)
        for seq in ("<Delete>", "<BackSpace>"):
            self.tree.bind(seq, self._on_tree_delete)
        for seq in ("<Control-a>", "<Control-A>"):
            self.tree.bind(seq, self._on_tree_select_all)

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

        self.log_box = scrolledtext.ScrolledText(self, height=9, font=("Consolas", 9), state="disabled",
                                                 bg="#111827", fg="#e5e7eb", relief="flat")
        self.log_box.pack(fill="both", expand=False, pady=(6, 0))
        for tag, color in (("info", "#e5e7eb"), ("ok", "#4ade80"), ("warn", "#fbbf24"), ("error", "#f87171")):
            self.log_box.tag_configure(tag, foreground=color)

    # ============================================================ helpers
    def _log(self, level: str, msg: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n", level)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        file_log(level, msg)

    def _save_cfg(self) -> None:
        self.cfg.dest_root = self.var_dst.get().strip()
        self.cfg.auto_rescan = self.var_rescan.get()
        self.cfg.overwrite = self.var_overwrite.get()
        self.cfg.open_dest_when_done = self.var_open.get()
        try:
            self.cfg.save()
        except OSError as e:
            self._log("error", f"Không lưu được config: {e}")

    def _refresh_roots(self) -> None:
        sel = self.lst_roots.curselection()
        self.lst_roots.delete(0, "end")
        for r in self.cfg.source_roots:
            n = self.index.root_count(r)
            if n is None:
                info = "chưa đọc vào JSON"
            else:
                info = f"{n:,} thư mục • đọc lúc {self.index.root_scanned_at(r)}"
            if not os.path.isdir(r):
                info += " • ⚠ không truy cập được"
            self.lst_roots.insert("end", f"{r}    —    {info}")
        if sel and sel[0] < self.lst_roots.size():
            self.lst_roots.selection_set(sel[0])
        if self.index.total:
            self.lbl_index.configure(text=f"Tổng {self.index.total:,} thư mục trong JSON "
                                          f"• cập nhật {self.index.updated_at}")
        else:
            self.lbl_index.configure(text="Chưa có chỉ mục. Thêm ổ chung rồi bấm “Đọc thư mục to”.")

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

    # ====================================================== ổ chung / riêng
    def _add_root(self) -> None:
        d = filedialog.askdirectory(title="Chọn thư mục TO / ổ chung cần thêm")
        if not d:
            return
        d = norm_root(d)
        if not self.cfg.add_root(d):
            messagebox.showinfo(APP_NAME, "Ổ/thư mục này đã có trong danh sách.")
            return
        self._save_cfg()
        self._refresh_roots()
        if messagebox.askyesno(APP_NAME, f"Đọc {d} và lưu tiếp vào JSON ngay bây giờ?"):
            self._scan([d])

    def _remove_root(self) -> None:
        sel = self.lst_roots.curselection()
        if not sel or self.busy:
            return
        root = self.cfg.source_roots[sel[0]]
        if not messagebox.askyesno(APP_NAME, f"Bỏ “{root}” khỏi danh sách và xoá dữ liệu của ổ này trong JSON?"):
            return
        self.cfg.source_roots.pop(sel[0])
        self.index.remove_root(root)
        self._save_cfg()
        self._refresh_roots()

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
            self.job_map[j.key] = j
            self.row_state[j.key] = [STATUS_PENDING, ""]
            self.tree.insert("", "end", iid=j.key, values=(j.invoice, j.tokhai, STATUS_PENDING, ""))
            n += 1
        self.var_summary.set(f"Có {len(self.jobs)} invoice trong danh sách.")
        return n

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

    def _on_tree_paste(self, _e=None):
        if not self.busy:
            self._paste()
        return "break"

    def _on_tree_delete(self, _e=None):
        self._remove_selected()
        return "break"

    def _on_tree_select_all(self, _e=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    # ------------------------------------------------ copy kiểu Excel
    def _rows(self, iids=None) -> list[list[str]]:
        """Dữ liệu bảng dạng chuỗi theo đúng thứ tự hiển thị (không dùng tree.item vì Tk tự đổi chuỗi số)."""
        want = None if iids is None else set(iids)
        out = []
        for iid in self.tree.get_children():
            if want is not None and iid not in want:
                continue
            j = self.job_map[iid]
            st, note = self.row_state.get(iid, [STATUS_PENDING, ""])
            out.append([j.invoice, j.tokhai, st, note])
        return out

    def _set_clipboard(self, text: str, what: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self.var_summary.set(f"Đã copy {what} – dán thẳng vào Excel được (Ctrl+V).")

    def _copy_rows(self, iids, header: bool, what: str) -> None:
        rows = self._rows(iids)
        if not rows:
            self.var_summary.set("Không có dòng nào để copy.")
            return
        self._set_clipboard(rows_to_tsv(rows, COLUMNS if header else None), f"{len(rows)} dòng {what}".strip())

    def _copy_column(self, col: int) -> None:
        rows = self._rows()
        if not rows:
            self.var_summary.set("Bảng đang trống.")
            return
        self._set_clipboard(rows_to_tsv([[r[col]] for r in rows]),
                            f"cột “{COLUMNS[col]}” ({len(rows)} dòng)")

    def _copy_cell(self, iid: str, col: int) -> None:
        row = self._rows([iid])
        if row:
            self._set_clipboard(rows_to_tsv([[row[0][col]]]), "1 ô")

    def _on_tree_copy(self, _e=None):
        sel = self.tree.selection()
        if sel:
            self._copy_rows(sel, header=False, what="đã chọn")
        else:
            self.var_summary.set("Chưa chọn dòng nào để copy (Ctrl+A để chọn tất cả).")
        return "break"

    def _on_tree_click(self, e) -> None:
        self.tree.focus_set()
        ctrl_or_shift = e.state & 0x0005
        row = self.tree.identify_row(e.y)
        self._anchor = row if (row and not ctrl_or_shift
                               and self.tree.identify_region(e.x, e.y) == "cell") else None

    def _on_tree_drag(self, e) -> None:
        """Kéo chuột để chọn dải dòng liên tiếp (giống kéo chọn trong Excel)."""
        if not self._anchor or not self.tree.exists(self._anchor):
            return
        kids = self.tree.get_children()
        row = self.tree.identify_row(e.y)
        if not row:
            row = kids[-1] if e.y > self.tree.winfo_height() // 2 else kids[0]
        a, b = sorted((kids.index(self._anchor), kids.index(row)))
        self.tree.selection_set(kids[a:b + 1])
        self.tree.see(row)

    def _on_tree_context(self, e):
        """Menu chuột phải: copy ô / dòng / cột / cả bảng."""
        self.tree.focus_set()
        row = self.tree.identify_row(e.y)
        col_id = self.tree.identify_column(e.x)
        col = int(col_id[1:]) - 1 if col_id.startswith("#") else -1
        col = col if 0 <= col < len(COLUMNS) else -1
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        sel = self.tree.selection()
        has_rows = bool(self.tree.get_children())

        m = tk.Menu(self.tree, tearoff=0)
        st = lambda ok: "normal" if ok else "disabled"          # noqa: E731
        m.add_command(label="Copy ô", state=st(row and col >= 0),
                      command=lambda: self._copy_cell(row, col))
        m.add_command(label=f"Copy cột “{COLUMNS[col]}”" if col >= 0 else "Copy cột",
                      state=st(has_rows and col >= 0), command=lambda: self._copy_column(col))
        m.add_separator()
        m.add_command(label=f"Copy {len(sel)} dòng chọn  (Ctrl+C)", state=st(sel),
                      command=lambda: self._copy_rows(sel, False, "đã chọn"))
        m.add_command(label="Copy dòng chọn kèm tiêu đề", state=st(sel),
                      command=lambda: self._copy_rows(sel, True, "đã chọn (kèm tiêu đề)"))
        m.add_command(label="Copy toàn bộ bảng (kèm tiêu đề)", state=st(has_rows),
                      command=lambda: self._copy_rows(None, True, "của cả bảng"))
        m.add_separator()
        m.add_command(label="Dán từ clipboard  (Ctrl+V)", state=st(not self.busy), command=self._paste)
        m.add_command(label="Xoá dòng chọn  (Delete)", state=st(sel and not self.busy),
                      command=self._remove_selected)
        m.add_command(label="Kết xuất Excel…", state=st(has_rows), command=self._export_excel)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()
        return "break"

    # ------------------------------------------------ kết xuất Excel
    def _export_excel(self) -> None:
        rows = self._rows()
        if not rows:
            messagebox.showinfo(APP_NAME, "Bảng đang trống, không có gì để kết xuất.")
            return
        default = f"ketqua_invoice_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        path = filedialog.asksaveasfilename(
            title="Kết xuất trạng thái bảng ra Excel", defaultextension=".xlsx",
            initialfile=default, initialdir=self.cfg.last_export_dir or self.var_dst.get() or None,
            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        try:
            export_xlsx(path, rows)
        except PermissionError:
            messagebox.showerror(APP_NAME, "Không ghi được file – có thể file đang mở trong Excel. "
                                           "Hãy đóng file hoặc chọn tên khác.")
            return
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_NAME, f"Không kết xuất được:\n{e}")
            return
        self.cfg.last_export_dir = os.path.dirname(path)
        self._save_cfg()
        self._log("ok", f"Đã kết xuất {len(rows)} dòng → {path}")
        if messagebox.askyesno(APP_NAME, f"Đã kết xuất {len(rows)} dòng.\nMở file ngay?"):
            self._open(path)

    def _drop(self, iids) -> None:
        iids = set(iids)
        for iid in iids:
            if self.tree.exists(iid):
                self.tree.delete(iid)
        self.jobs = [j for j in self.jobs if j.key not in iids]
        for iid in iids:
            self.job_map.pop(iid, None)
            self.row_state.pop(iid, None)
        self.var_summary.set(f"Còn {len(self.jobs)} invoice trong danh sách.")

    def _remove_selected(self) -> None:
        if not self.busy:
            self._drop(self.tree.selection())

    def _remove_done(self) -> None:
        """Xoá các dòng đã copy thành công; giữ lại dòng lỗi / không tìm được / chưa chạy."""
        if self.busy:
            return
        done = [i for i in self.tree.get_children()
                if self.row_state.get(i, [""])[0] in SUCCESS_STATUSES]
        if not done:
            messagebox.showinfo(APP_NAME, "Chưa có dòng nào copy thành công.")
            return
        self._drop(done)
        self._log("info", f"Đã xoá {len(done)} dòng thành công, giữ lại {len(self.jobs)} dòng lỗi/chưa chạy.")

    def _clear(self) -> None:
        if self.busy:
            return
        self.tree.delete(*self.tree.get_children())
        self.jobs.clear()
        self.job_map.clear()
        self.row_state.clear()
        self.progress["value"] = 0
        self.var_summary.set("Đã xoá danh sách.")

    # ============================================================ actions
    def _scan(self, roots: list[str] | None) -> None:
        roots = roots or list(self.cfg.source_roots)
        if not roots:
            messagebox.showwarning(APP_NAME, "Hãy thêm ít nhất một ổ chung (thư mục TO).")
            return
        self._save_cfg()
        self.cancel_event.clear()
        self._set_busy(True)
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self._log("info", "Đang đọc: " + ", ".join(roots))

        def work():
            try:
                sr = self.index.scan(roots, lambda n, cur: self.events.put(("scan_progress", n, cur)),
                                     self.cancel_event)
                for r, (tot, add, rem) in sr.per_root.items():
                    self.events.put(("log", "ok", f"{r}: {tot:,} thư mục (+{add:,} mới, -{rem:,} đã mất)."))
                for r in sr.skipped:
                    self.events.put(("log", "warn", f"{r}: không truy cập được – giữ dữ liệu cũ trong JSON."))
                if sr.cancelled:
                    self.events.put(("log", "warn", "Quét bị dừng giữa chừng."))
                self.events.put(("scan_done", sr))
            except Exception as e:  # noqa: BLE001
                self.events.put(("log", "error", f"Lỗi quét: {e}"))
            self.events.put(("idle",))

        threading.Thread(target=work, daemon=True).start()

    def _run(self) -> None:
        if not self.jobs:
            messagebox.showinfo(APP_NAME, "Danh sách trống. Hãy nhập Excel hoặc dán từ clipboard.")
            return
        if not self.cfg.source_roots:
            messagebox.showwarning(APP_NAME, "Hãy thêm ít nhất một ổ chung.")
            return
        if not self.var_dst.get().strip():
            messagebox.showwarning(APP_NAME, "Hãy chọn thư mục ổ riêng.")
            return
        self._save_cfg()
        self.cancel_event.clear()
        self._set_busy(True)
        self.progress.configure(mode="determinate", maximum=len(self.jobs), value=0)
        for j in self.jobs:
            self.row_state[j.key] = [STATUS_PENDING, ""]
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
                self._handle(self.events.get_nowait())
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
            self._refresh_roots()
        elif kind == "result":
            self._show_result(ev[1])
        elif kind == "idle":
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
            self.var_summary.set("Sẵn sàng.")
            self._refresh_roots()
            self._set_busy(False)
        elif kind == "done":
            self._refresh_roots()
            self._set_busy(False)
            self._finish_summary()

    def _show_result(self, r: JobResult) -> None:
        tag = {STATUS_OK: "ok", STATUS_SKIPPED: "ok", STATUS_NO_FILES: "warn"}.get(r.status, "err")
        if self.tree.exists(r.job.key):
            self.row_state[r.job.key] = [r.status, r.message]
            self.tree.item(r.job.key, values=(r.job.invoice, r.job.tokhai, r.status, r.message), tags=(tag,))
            self.tree.see(r.job.key)

    def _finish_summary(self) -> None:
        rows = [self.row_state.get(i, [""])[0] for i in self.tree.get_children()]
        ok = sum(1 for s in rows if s in SUCCESS_STATUSES)
        self.var_summary.set(f"Xong: {ok} thành công • {len(rows) - ok} lỗi/thiếu • tổng {len(rows)}")
        if ok and self.var_open.get() and os.path.isdir(self.var_dst.get()):
            self._open(self.var_dst.get())

    def _on_close(self) -> None:
        if self.busy and not messagebox.askyesno(APP_NAME, "Đang xử lý. Bạn có chắc muốn thoát?"):
            return
        self.cancel_event.set()
        self._save_cfg()
        self.root.destroy()
