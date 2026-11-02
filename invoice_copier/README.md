# Invoice Copier

Copy **Invoice (.pdf)** + **Tờ khai (ToKhaiHQ7N_….xls/xlsx)** từ ổ share sang ổ riêng.

## Cấu trúc
```
invoice_copier/
├─ main.py                 # điểm chạy
├─ build_exe.bat           # đóng gói .exe
├─ requirements.txt
├─ config/                 # config.json + folder_index.json (cạnh .exe)
└─ app/
   ├─ constants.py
   ├─ core/                # logic, không phụ thuộc UI
   │  ├─ paths.py          # xác định thư mục config (hỗ trợ .exe)
   │  ├─ config.py         # ổ share (nhiều ổ), ổ riêng, tuỳ chọn
   │  ├─ index.py          # chỉ mục JSON nhiều ổ share + tra cứu theo Invoice
   │  ├─ files.py          # tìm Invoice.pdf & file tờ khai
   │  ├─ excel_io.py       # đọc Excel/CSV/clipboard
   │  ├─ service.py        # luồng xử lý + copy
   │  └─ models.py
   └─ ui/
      ├─ theme.py
      └─ main_window.py
```

## Cách dùng
1. Chọn **Thư mục TO (ổ share)** và **Thư mục ổ riêng** (được lưu cho lần sau).
   - Đổi sang ổ share khác: ổ mới được **thêm** vào config, ổ cũ và dữ liệu JSON cũ vẫn giữ nguyên.
     Ổ đang chọn được tìm trước, các ổ còn lại trong config tìm sau.
   - Nút **Bỏ ổ này** chỉ bỏ ổ khỏi danh sách tìm (JSON không bị xoá).
2. Bấm **ĐỌC THƯ MỤC TO** để lập chỉ mục cho ổ đang chọn (lưu `config/folder_index.json`, chứa nhiều ổ).
3. Nhập danh sách bằng **Nhập từ Excel/CSV** hoặc **Dán từ clipboard** (hoặc click vào bảng rồi **Ctrl+V**).
   - Mỗi dòng dán: `Invoice [Tờ khai]`. Excel: cột có tiêu đề “Invoice” / “Tờ khai”; không có tiêu đề thì cột A / cột B.
   - Click vào dòng rồi **Delete / Backspace** để xoá dòng đang chọn (**Ctrl+A** chọn tất cả).
   - **Xoá dòng đã copy**: bỏ các dòng thành công, giữ lại dòng lỗi / không tìm được.
4. Bấm **CHẠY COPY**.

## Quy tắc tìm
- Thư mục khớp nếu tên = Invoice hoặc bắt đầu bằng Invoice + ký tự không phải chữ/số
  (`IFS-240782` khớp `IFS-240782 DHL…`, không khớp `IFS-2407821`).
- Nếu có nhiều thư mục cùng tên trong một ổ: thử lần lượt từng thư mục (còn tồn tại, đủ `<Invoice>.pdf` và
  `ToKhaiHQ7N_*<số tờ khai>*.xls/xlsx`), thư mục nào đủ thì lấy.
- Không có ở ổ này → tìm tiếp ở các ổ còn lại trong config.
- Không ổ nào có → (nếu bật “Tự quét lại”) quét lại từng ổ, thêm thư mục mới vào JSON rồi tìm lại.
  Vẫn không thấy thì ghi chú chi tiết từng ổ vào log và cột Ghi chú.
- Không nhập số tờ khai mà thư mục có nhiều file tờ khai → báo “Thiếu file” để bạn nhập số.
- Ra ổ riêng: `<ổ riêng>/<Invoice>/<Invoice>.pdf` và `<ổ riêng>/<Invoice>/ToKhaiHQ7N_….xls`.

## File config (`config/`)
- `config.json`: ổ share đang chọn + danh sách ổ, ổ riêng, tuỳ chọn.
- `folder_index.json`: chỉ mục thư mục của tất cả các ổ. File JSON phiên bản cũ (một ổ) tự được chuyển
  sang định dạng mới và sao lưu thành `folder_index.v1.bak.json`.

## Build .exe
Chạy `build_exe.bat` → `dist\InvoiceCopier\InvoiceCopier.exe` (chế độ onedir, kèm `dist\InvoiceCopier.zip` để gửi máy khác).
Thư mục `config` nằm cạnh file .exe (nếu không ghi được, tool tự dùng `%LOCALAPPDATA%\InvoiceCopier\config`).
Khi chuyển sang máy khác hãy giải nén/copy cả thư mục `InvoiceCopier`, không chỉ lấy file .exe.
