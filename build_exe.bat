@echo off
chcp 65001 >nul
echo === Cai thu vien ===
pip install -r requirements.txt || goto :err
echo === Build exe ===
pyinstaller --noconfirm --onefile --windowed --name InvoiceCopier main.py || goto :err
if not exist dist\config mkdir dist\config
echo === Xong! File: dist\InvoiceCopier.exe  (thu muc dist\config se chua config.json + folder_index.json) ===
pause
exit /b 0
:err
echo Build that bai.
pause
exit /b 1
