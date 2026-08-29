@echo off
echo === Antigravity Auto - Windows Installer ===
echo [*] Cek Python...
python --version
if errorlevel 1 (
  echo [!] Python tidak ditemukan. Install Python 3.10+ dari python.org
  pause
  exit /b 1
)

echo [*] Buat venv .venv...
python -m venv .venv
call .venv\Scripts\activate.bat

echo [*] Upgrade pip...
python -m pip install --upgrade pip

echo [*] Install deps...
pip install -r requirements.txt

echo [*] Install Playwright chromium...
playwright install chromium

echo [*] Setup .env jika belum ada...
if not exist .env (
  copy .env.example .env
  echo [*] .env dibuat - silakan edit
) else (
  echo [*] .env sudah ada
)

if not exist accounts.txt (
  copy accounts.txt.example accounts.txt 2>nul
  if not exist accounts.txt echo gmail1@example.com^|password1 > accounts.txt
  echo [*] accounts.txt dibuat
)

echo.
echo === Selesai ===
echo Cara jalan:
echo   .venv\Scripts\activate
echo   python flow.py
echo   # atau: set HEADLESS=false ^& python flow.py  (visible)
pause
