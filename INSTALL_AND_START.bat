@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Face ID Davomat - O'rnatish va ishga tushirish

echo ======================================================
echo       FACE ID DAVOMAT - BIR BOSISHDA ISHGA TUSHIRISH
echo ======================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo XATO: Python topilmadi.
  echo Python 3.11-3.13 ni python.org saytidan o'rnating va
  echo o'rnatishda "Add Python to PATH" ni belgilang.
  echo Keyin ushbu faylni qayta ishga tushiring.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Virtual muhit yaratilmoqda...
  python -m venv .venv
  if errorlevel 1 goto :fail
) else (
  echo [1/3] Virtual muhit mavjud.
)

echo.
echo [2/3] Kerakli kutubxonalar o'rnatilmoqda/tekshirilmoqda...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo [3/3] Davomat sayti ishga tushmoqda...
echo Brauzer manzili: http://127.0.0.1:5000
echo Admin login: admin
echo Dastlabki parol: ChangeMe123!
echo Birinchi kirishda parolni almashtiring.
echo CMD oynasini yopmang. To'xtatish uchun Ctrl+C bosing.
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:5000"
".venv\Scripts\python.exe" app.py
echo.
echo Dastur to'xtadi. Xato bo'lsa, shu oynaning rasmini oling.
pause
exit /b 0

:fail
echo.
echo O'RNATISHDA XATO YUZ BERDI. Internetni tekshiring va xato yozuvining rasmini oling.
pause
exit /b 1
