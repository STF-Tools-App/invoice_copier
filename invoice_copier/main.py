"""Điểm khởi chạy ứng dụng Invoice Copier."""
import tkinter as tk

from app.ui.main_window import MainWindow


def main() -> None:
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
