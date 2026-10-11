@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual muhit topilmadi. Avval Python o'rnatilgan bo'lishi kerak.
  python -m venv .venv
)
call ".venv\Scripts\activate.bat"
echo Kutubxonalar tekshirilmoqda...
python -m pip install -r requirements.txt
echo.
echo Face ID davomat serveri ishga tushmoqda...
start "Face ID Davomat" http://127.0.0.1:5000
python app.py
echo.
echo Dastur to'xtadi. Xatolar bo'lsa, yuqoridagi yozuvni suratga oling.
pause
