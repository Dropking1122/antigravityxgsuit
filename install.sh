#!/bin/bash
set -e

echo "=== Antigravity Auto - Ubuntu Installer ==="
echo "[*] Update & install dependencies..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip xvfb curl git

echo "[*] Buat virtualenv .venv..."
python3 -m venv .venv
source .venv/bin/activate

echo "[*] Upgrade pip..."
pip install --upgrade pip

echo "[*] Install python deps..."
pip install -r requirements.txt

echo "[*] Install Playwright browser (chromium) dengan deps..."
playwright install --with-deps chromium

echo "[*] Buat direktori data/ dan logs/..."
mkdir -p data logs

echo "[*] Setup .env jika belum ada..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[*] .env dibuat dari .env.example - silakan edit DASH_PASSWORD, HEADLESS, dll"
else
  echo "[*] .env sudah ada, skip"
fi

echo "[*] Setup accounts.txt jika belum ada..."
if [ ! -f data/accounts.txt ]; then
  cp data/accounts.txt.example data/accounts.txt 2>/dev/null || cp accounts.txt.example data/accounts.txt 2>/dev/null || echo "gmail1@example.com|password1" > data/accounts.txt
  echo "[*] data/accounts.txt dibuat - isi dengan format gmail|password per baris"
fi

echo ""
echo "=== Selesai ==="
echo "Cara jalan:"
echo "  source .venv/bin/activate"
echo "  python main.py                    # Menu Terminal Interactive (TUI)"
echo "  python app.py                     # Web Server UI http://localhost:5000"
echo "  HEADLESS=true python flow.py      # Otomasi langsung mode VPS"
echo ""
echo "Untuk VPS Ubuntu headless disarankan .env: HEADLESS=true, CLEAR_EACH=true"
