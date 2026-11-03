"""Cửa sổ quản lý các chuỗi dùng để bỏ qua PDF theo tên."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class IgnoredTokensWindow(tk.Toplevel):
    def __init__(self, master: tk.Misc, tokens: list[str], on_change: Callable[[], None]):
        super().__init__(master)
        self.tokens = tokens
        self.on_change = on_change
        self._editing: int | None = None
        self._entry: ttk.Entry | None = None
        self._edit_row: ttk.Frame | None = None
        self._outside_binding: str | None = None

        self.title("PDF đã loại trừ")
        self.geometry("580x500")
        self.minsize(380, 260)
        self.transient(master.winfo_toplevel())

        style = ttk.Style(self)
        style.configure("Token.Save.TButton", foreground="#16a34a")
        style.configure("Token.Cancel.TButton", foreground="#dc2626")

        container = ttk.Frame(self, padding=(8, 8, 8, 4))
        container.pack(fill="both", expand=True)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(container, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.rows = ttk.Frame(self.canvas)
        self._rows_window = self.canvas.create_window((0, 0), window=self.rows, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.rows.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_rows)

        ttk.Button(self, text="Đóng", command=self.destroy).pack(anchor="e", padx=10, pady=(0, 10))
        self.bind("<Escape>", self._on_escape)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._render()

    def _update_scroll_region(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_rows(self, event) -> None:
        self.canvas.itemconfigure(self._rows_window, width=event.width)

    def _render(self) -> None:
        for child in self.rows.winfo_children():
            child.destroy()
        self._entry = None
        self._edit_row = None

        for index, token in enumerate(self.tokens):
            row = ttk.Frame(self.rows)
            row.pack(fill="x", pady=2)
            if self._editing == index:
                self._edit_row = row
                value = tk.StringVar(value=token)
                entry = ttk.Entry(row, textvariable=value)
                entry.pack(side="left", fill="x", expand=True)
                error = ttk.Label(row, foreground="#dc2626")
                error.pack(side="left", padx=4)
                ttk.Button(row, text="✕", width=3, style="Token.Cancel.TButton",
                           command=self._cancel_edit).pack(side="right")
                ttk.Button(row, text="✓", width=3, style="Token.Save.TButton",
                           command=lambda i=index, v=value, e=error: self._save(i, v, e)).pack(
                               side="right", padx=(4, 0))
                self._entry = entry
                entry.bind("<Return>", lambda _e, i=index, v=value, err=error: self._save(i, v, err))
                entry.bind("<Escape>", self._on_escape)
            else:
                ttk.Label(row, text=token).pack(side="left", fill="x", expand=True, padx=4, pady=4)
                ttk.Button(row, text="🗑", width=3, style="Token.Cancel.TButton",
                           command=lambda i=index: self._delete(i)).pack(side="right")
                ttk.Button(row, text="✎", width=3,
                           command=lambda i=index: self._start_edit(i)).pack(side="right", padx=(4, 0))

        self.rows.update_idletasks()
        self._update_scroll_region()

    def _start_edit(self, index: int) -> None:
        self._editing = index
        self._render()
        if self._entry:
            self._entry.focus_set()
            self._entry.selection_range(0, "end")
        if self._outside_binding is None:
            self._outside_binding = self.bind_all("<Button-1>", self._on_outside_click, add="+")

    def _save(self, index: int, value: tk.StringVar, error: ttk.Label):
        token = value.get().strip()
        if not token:
            error.configure(text="Không thể lưu mục trống.")
            return "break"
        if any(i != index and old.casefold() == token.casefold()
               for i, old in enumerate(self.tokens)):
            error.configure(text="Mục này đã có trong danh sách.")
            return "break"
        self.tokens[index] = token
        self._editing = None
        self._remove_outside_binding()
        self.on_change()
        self._render()
        return "break"

    def _delete(self, index: int) -> None:
        del self.tokens[index]
        if self._editing == index:
            self._editing = None
            self._remove_outside_binding()
        elif self._editing is not None and self._editing > index:
            self._editing -= 1
        self.on_change()
        self._render()

    def _cancel_edit(self) -> None:
        if self._editing is None:
            return
        self._editing = None
        self._remove_outside_binding()
        self._render()

    def _on_escape(self, _event=None):
        if self._editing is not None:
            self._cancel_edit()
        else:
            self.destroy()
        return "break"

    def _on_outside_click(self, event):
        if self._editing is None:
            return
        edit_row = self._edit_row
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget == edit_row:
                return
            parent = widget.winfo_parent()
            widget = self.nametowidget(parent) if parent else None
        self._cancel_edit()

    def _remove_outside_binding(self) -> None:
        if self._outside_binding is not None:
            self._unbind(("bind", "all", "<Button-1>"), self._outside_binding)
            self._outside_binding = None

    def _on_destroy(self, event) -> None:
        if event.widget == self:
            self._remove_outside_binding()
