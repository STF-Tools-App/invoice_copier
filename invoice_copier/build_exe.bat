@echo off
chcp 65001 >nul
echo === Cai thu vien ===
pip install -r requirements.txt || goto :err

echo === Build exe (onedir, khong UPX - it bi antivirus bao nham) ===
rmdir /s /q build dist 2>nul
pyinstaller --noconfirm --onedir --windowed --noupx --name InvoiceCopier main.py || goto :err

if not exist dist\InvoiceCopier\config mkdir dist\InvoiceCopier\config

echo === Nen zip de gui may khac ===
powershell -NoProfile -Command "Compress-Archive -Path 'dist\InvoiceCopier' -DestinationPath 'dist\InvoiceCopier.zip' -Force"

echo.
echo Xong! Chay: dist\InvoiceCopier\InvoiceCopier.exe
echo Gui may khac: dist\InvoiceCopier.zip  (giai nen ca thu muc, khong chi lay file exe)
pause
exit /b 0
:err
echo Build that bai.
pause
exit /b 1
