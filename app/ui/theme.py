"""Giao diện: màu sắc, font, style ttk."""
from tkinter import ttk

BG = "#f4f6fa"
CARD = "#ffffff"
PRIMARY = "#2563eb"
PRIMARY_DARK = "#1d4ed8"
SUCCESS = "#16a34a"
WARN = "#d97706"
DANGER = "#dc2626"
TEXT = "#1f2937"
MUTED = "#6b7280"
FONT = "Segoe UI"


def apply_theme(root) -> None:
    root.configure(bg=BG)
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", font=(FONT, 10), background=BG, foreground=TEXT)
    s.configure("TFrame", background=BG)
    s.configure("Card.TFrame", background=CARD)
    s.configure("TLabel", background=BG)
    s.configure("Card.TLabel", background=CARD)
    s.configure("Muted.TLabel", background=CARD, foreground=MUTED)
    s.configure("Title.TLabel", font=(FONT, 18, "bold"), foreground=PRIMARY)
    s.configure("Sub.TLabel", foreground=MUTED)
    s.configure("TLabelframe", background=CARD, bordercolor="#d1d5db")
    s.configure("TLabelframe.Label", background=CARD, foreground=PRIMARY, font=(FONT, 10, "bold"))
    s.configure("TCheckbutton", background=CARD)
    s.configure("TEntry", padding=5)
    s.configure("TButton", padding=(10, 6))
    s.configure("Primary.TButton", background=PRIMARY, foreground="white", font=(FONT, 10, "bold"))
    s.map("Primary.TButton", background=[("active", PRIMARY_DARK), ("disabled", "#93c5fd")])
    s.configure("Big.TButton", background=PRIMARY, foreground="white",
                font=(FONT, 13, "bold"), padding=(18, 12))
    s.map("Big.TButton", background=[("active", PRIMARY_DARK), ("disabled", "#93c5fd")])
    s.configure("Run.TButton", background=SUCCESS, foreground="white",
                font=(FONT, 13, "bold"), padding=(18, 12))
    s.map("Run.TButton", background=[("active", "#15803d"), ("disabled", "#86efac")])
    s.configure("Danger.TButton", foreground=DANGER)
    s.configure("Treeview", rowheight=26, font=(FONT, 10), fieldbackground=CARD, background=CARD)
    s.configure("Treeview.Heading", font=(FONT, 10, "bold"), background="#e5e7eb", padding=5)
    s.configure("Horizontal.TProgressbar", troughcolor="#e5e7eb", background=PRIMARY, thickness=14)
