# 📁 Invoice Copier

Công cụ copy **Invoice (.pdf)** và **Tờ khai hải quan (ToKhaiHQ7N_….xls/xlsx)** từ ổ chung sang ổ riêng.
Mỗi Invoice được đặt trong **một thư mục riêng mang tên Invoice** ở ổ riêng.

---

## 1. Tính năng

- Quét toàn bộ thư mục to trên ổ chung (đệ quy) và lưu cấu trúc vào file JSON để tra cứu nhanh.
- Tìm thư mục theo tên Invoice, kể cả khi thư mục có thêm ký tự phía sau (VD: `IFS-240782 DHL ...`).
- Lấy đúng 2 file cần thiết trong thư mục: `<Invoice>.pdf` và file tờ khai `ToKhaiHQ7N_...`.
- Copy sang ổ riêng, tạo thư mục theo tên Invoice.
- Không thấy Invoice trong JSON → tự quét lại thư mục to, bổ sung thư mục mới vào JSON rồi chạy lại.
- Nhập danh sách bằng file Excel/CSV, dán từ clipboard hoặc gõ tay.
- Ghi nhớ đường dẫn ổ chung / ổ riêng cho lần sau.
- Đóng gói được thành `.exe`, vẫn đọc/ghi được thư mục `config`.

---

## 2. Cài đặt & chạy

### Yêu cầu
- Windows 10/11
- Python 3.10 trở lên (đã gồm Tkinter)

### Chạy bằng Python
```bash
pip install -r requirements.txt
python main.py
```

### Đóng gói thành .exe
Bấm đúp `build_exe.bat` (hoặc chạy trong CMD). Kết quả:

```
dist/
├─ InvoiceCopier.exe
└─ config/            ← chứa config.json và folder_index.json sau lần chạy đầu
```

> Có thể copy riêng file `InvoiceCopier.exe` sang máy khác. Thư mục `config` sẽ tự tạo cạnh file `.exe`.
> Nếu thư mục cạnh `.exe` không có quyền ghi (VD: `C:\Program Files`), tool tự chuyển sang
> `%LOCALAPPDATA%\InvoiceCopier\config`.

---

## 3. Hướng dẫn sử dụng

### Bước 1 – Chọn đường dẫn
| Ô | Ý nghĩa |
|---|---|
| **Thư mục TO (ổ chung)** | Thư mục gốc trên ổ chung, chứa tất cả thư mục Invoice (kể cả nằm sâu nhiều cấp). |
| **Thư mục ổ riêng** | Nơi nhận file sau khi copy. |

Bấm **Chọn…** để duyệt thư mục. Hai đường dẫn được lưu tự động, lần sau mở tool không cần chọn lại.

Các tuỳ chọn bên dưới:
- **Tự quét lại khi không thấy Invoice trong chỉ mục** *(nên bật)*: nếu Invoice chưa có trong JSON, tool tự quét lại thư mục to rồi thử lại.
- **Ghi đè file đã tồn tại**: bật nếu muốn copy đè lên file cũ ở ổ riêng. Tắt thì file đã có (cùng dung lượng) sẽ được bỏ qua.
- **Ghi đè toàn bộ**: bật nếu muốn xoá thư mục đích cũ của Invoice trước khi ghi. Thư mục mới chỉ chứa các file lấy được ở lần chạy hiện tại.
- **Mở thư mục đích khi xong**: tự mở thư mục ổ riêng sau khi chạy xong.

### Bước 2 – Đọc thư mục to (lập chỉ mục)
Bấm nút to **🔍 ĐỌC THƯ MỤC TO**.

- Tool đi vào tất cả thư mục con, rồi các thư mục con của chúng, cho đến hết.
- Cấu trúc đường dẫn được lưu vào `config/folder_index.json`.
- Dòng bên cạnh nút hiển thị số thư mục đã lập chỉ mục và thời điểm cập nhật.
- Bấm **Dừng** nếu muốn ngắt giữa chừng (phần đã quét vẫn được giữ lại).

Chỉ cần làm bước này **một lần** (hoặc khi muốn làm mới). Những lần sau tool dùng lại file JSON nên chạy rất nhanh.
Nếu bạn đổi **Thư mục TO** sang thư mục khác, tool sẽ cảnh báo chỉ mục không còn phù hợp và cần quét lại.

### Bước 3 – Nhập danh sách Invoice & Tờ khai
Chọn một trong ba cách:

**a) Nhập từ Excel/CSV** – bấm **📥 Nhập từ Excel/CSV**, chọn file `.xlsx`, `.xlsm`, `.xls` hoặc `.csv`.

Định dạng file:

| Invoice | Tờ khai |
|---|---|
| IFS-240782 | 10567890123 |
| IFS-240783 | 10567890456 |

- Tool tự nhận cột có tiêu đề chứa chữ **Invoice** và **Khai** (Tờ khai).
- Nếu file không có tiêu đề: **cột A = Invoice, cột B = Tờ khai**.
- Cột Tờ khai có thể để trống (xem phần *Quy tắc chọn file tờ khai* bên dưới).
- Dòng trùng được tự loại bỏ.

**b) Dán từ clipboard** – copy các dòng từ Excel/Notepad, bấm **📋 Dán từ clipboard**.
Mỗi dòng gồm `Invoice` và (tuỳ chọn) `Tờ khai`, ngăn cách bằng Tab, dấu phẩy, chấm phẩy hoặc khoảng trắng.

**c) Nhập tay** – gõ Invoice và Tờ khai vào hai ô rồi bấm **➕ Thêm** (hoặc nhấn Enter).

Quản lý danh sách: chọn dòng rồi bấm **Xoá dòng chọn** (hoặc phím `Delete`), hoặc **Xoá tất cả**.

### Bước 4 – Chạy
Bấm **▶ CHẠY COPY**. Với mỗi Invoice, tool sẽ:

1. Tra trong JSON để tìm thư mục cùng tên Invoice (hoặc tên bắt đầu bằng Invoice).
2. Vào thư mục, lấy `<Invoice>.pdf` và file `ToKhaiHQ7N_...` tương ứng.
3. Tạo thư mục `<ổ riêng>\<Invoice>\` và copy 2 file vào đó.

Nếu có Invoice **chưa có trong JSON**, tool tự động:
quét lại thư mục to → bỏ qua thư mục đã có, thêm thư mục mới vào JSON → lưu JSON → chạy lại các Invoice còn thiếu.

### Bước 5 – Xem kết quả
Bảng danh sách hiển thị trạng thái từng dòng, thanh tiến trình và log nằm phía dưới.

| Trạng thái | Màu | Ý nghĩa |
|---|---|---|
| Đã copy | 🟢 | Copy thành công. |
| Đã có (bỏ qua) | 🟢 | File đã tồn tại ở ổ riêng, không copy lại. |
| Thiếu file | 🟠 | Tìm thấy thư mục nhưng thiếu PDF hoặc file tờ khai (xem cột Ghi chú). |
| Không thấy thư mục | 🔴 | Không có thư mục nào khớp tên Invoice, kể cả sau khi quét lại. |
| Lỗi | 🔴 | Lỗi khi copy (mất kết nối ổ mạng, không có quyền ghi…). |

Kết quả ở ổ riêng:
```
<ổ riêng>/
├─ IFS-240782/
│  ├─ IFS-240782.pdf
│  └─ ToKhaiHQ7N_10567890123.xls
└─ IFS-240783/
   ├─ IFS-240783.pdf
   └─ ToKhaiHQ7N_10567890456.xlsx
```

---

## 4. Quy tắc tìm kiếm

### Tìm thư mục theo Invoice
Một thư mục được coi là khớp nếu tên thư mục:
- **bằng** Invoice, hoặc
- **bắt đầu bằng** Invoice và ký tự ngay sau đó **không phải chữ/số** (khoảng trắng, `-`, `_`, …).

| Invoice | Tên thư mục | Kết quả |
|---|---|---|
| `IFS-240782` | `IFS-240782` | ✅ Khớp |
| `IFS-240782` | `IFS-240782 DHL ...` | ✅ Khớp |
| `IFS-240782` | `IFS-2407821` | ❌ Không khớp (khác Invoice) |

Không phân biệt chữ hoa/thường. Nếu có nhiều thư mục khớp, tool ưu tiên khớp chính xác, rồi đến thư mục nằm nông nhất; nếu thư mục đầu thiếu file thì thử thư mục tiếp theo.

### Quy tắc chọn file tờ khai
- Tên file bắt đầu bằng `ToKhaiHQ7N`, đuôi `.xls` / `.xlsx` / `.xlsm`.
- **Có nhập số tờ khai** → chỉ lấy file có chứa số đó trong tên.
- **Không nhập số tờ khai**:
  - Thư mục chỉ có 1 file tờ khai → lấy file đó.
  - Có nhiều file tờ khai → báo **Thiếu file** và yêu cầu nhập số tờ khai (tool không chọn bừa).
- File Invoice phải tên đúng `<Invoice>.pdf`.

Tool tìm ở cấp ngoài cùng của thư mục Invoice trước, sau đó mới tìm trong thư mục con.

---

## 5. Các file cấu hình (thư mục `config/`)

| File | Nội dung |
|---|---|
| `config.json` | Thư mục ổ chung, ổ riêng, các tuỳ chọn, tiền tố tờ khai (`tokhai_prefix`, mặc định `ToKhaiHQ7N`). |
| `folder_index.json` | Danh sách đường dẫn thư mục đã quét, thời điểm cập nhật. |

Nút **Mở thư mục config** trên giao diện mở nhanh thư mục này. Xoá `folder_index.json` để buộc tool lập chỉ mục lại từ đầu.
Nếu tên file tờ khai của bạn đổi tiền tố, sửa `tokhai_prefix` trong `config.json`.

---

## 6. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| "Không tìm thấy thư mục" dù chắc chắn có | Kiểm tra tên thư mục có bắt đầu đúng bằng Invoice; kiểm tra ổ chung đã kết nối; bấm **Đọc thư mục to** để làm mới. |
| "Thiếu file – có N file tờ khai" | Nhập thêm số tờ khai cho Invoice đó. |
| "Thiếu file – không có Invoice.pdf" | Kiểm tra tên file PDF trong thư mục có đúng `<Invoice>.pdf`. |
| Không đọc được file Excel | Cài thêm thư viện: `pip install openpyxl xlrd` (bản `.exe` đã đóng gói sẵn). |
| Cảnh báo "Chỉ mục thuộc thư mục khác" | Bạn vừa đổi Thư mục TO – bấm **Đọc thư mục to** lại. |
| Quét lâu | Ổ mạng lớn nên quét mất thời gian ở lần đầu; các lần sau dùng JSON nên nhanh. |
| `.exe` không lưu được config | Chạy `.exe` ở thư mục có quyền ghi, hoặc dùng thư mục `%LOCALAPPDATA%\InvoiceCopier\config`. |

---

## 7. Cấu trúc project

```
invoice_copier/
├─ main.py                  # điểm khởi chạy
├─ build_exe.bat            # đóng gói .exe bằng PyInstaller
├─ requirements.txt
├─ README.md
├─ config/                  # config.json + folder_index.json
└─ app/
   ├─ constants.py          # hằng số, tên trạng thái
   ├─ core/                 # logic nghiệp vụ (không phụ thuộc giao diện)
   │  ├─ paths.py           # xác định thư mục config (hỗ trợ .exe)
   │  ├─ config.py          # lưu/đọc cấu hình
   │  ├─ index.py           # quét thư mục → JSON, tra cứu theo Invoice
   │  ├─ files.py           # tìm Invoice.pdf và file tờ khai
   │  ├─ excel_io.py        # đọc Excel/CSV/clipboard
   │  ├─ service.py         # luồng xử lý chính + copy
   │  └─ models.py          # dataclass
   └─ ui/                   # giao diện Tkinter
      ├─ theme.py
      └─ main_window.py
```
