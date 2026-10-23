"""Hằng số dùng chung toàn ứng dụng."""

APP_NAME = "Invoice Copier"
APP_VERSION = "1.0.0"

CONFIG_FILENAME = "config.json"
INDEX_FILENAME = "folder_index.json"

DEFAULT_TOKHAI_PREFIX = "ToKhaiHQ7N"
TOKHAI_EXTENSIONS = (".xls", ".xlsx", ".xlsm")

# Trạng thái kết quả của từng Invoice
STATUS_PENDING = "Chờ xử lý"
STATUS_OK = "Đã copy"
STATUS_SKIPPED = "Đã có (bỏ qua)"
STATUS_NO_FOLDER = "Không thấy thư mục"
STATUS_NO_FILES = "Thiếu file"
STATUS_ERROR = "Lỗi"
