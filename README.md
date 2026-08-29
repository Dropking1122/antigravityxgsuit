# Antigravity Auto

Otomasi `flow.py` untuk login dashboard 9Router (`<IP>:<PORT>`) → `/dashboard/providers/antigravity` → `Add` → `I Understand, Continue` → Google OAuth (isi email/pass, auto-klik `Sign in`/`Login`/`Continue`/`Allow`, rewrite `localhost:20128` → `<IP>:<PORT>`).

## Fitur
- Browser visible (`HEADLESS=false`) untuk handle verifikasi manual, auto-klik `Sign in` sekarang.
- Rewrite `localhost` ke IP via `context.route` (tidak perlu konek ke localhost).
- `CLEAR_EACH=true` bersihkan Google session tiap akun agar `Use another account` tidak nyangkut di akun ke-2.
- `RESTART_BROWSER_PER_ACCOUNT=true` close & buka browser baru tiap akun (solusi VPS).
- Auto fixed `LAST_REWRITE` hanya untuk `/callback?code=` (tidak tertimpa static `woff2/css`).

## Langkah-Langkah Install dan Cara Penggunaan

### Prasyarat
- Git, Python 3.10+ (`python --version`), pip
- Ubuntu: `sudo apt update` ; Windows: install Python dari python.org (centang Add to PATH)

### 1. Clone Repo
```bash
git clone https://github.com/Dropking1122/testantigravity.git
cd testantigravity
```

### 2. Install (otomatis)
**Windows** `install.bat:1`
```bat
install.bat
:: buat .venv, pip install -r requirements.txt:1 (playwright==1.62.0 + Flask==3.0.3), playwright install chromium
```

**Ubuntu VPS** `install.sh:1`
```bash
chmod +x install.sh
./install.sh
# apt install python3-venv xvfb, buat .venv, pip install -r requirements.txt, playwright install --with-deps chromium
# otomatis buat .env & accounts.txt dari .env.example/accounts.txt.example jika belum ada
```
Manual tanpa script:
```bash
python3 -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install --with-deps chromium  # Ubuntu
playwright install chromium              # Windows
cp .env.example .env
cp accounts.txt.example accounts.txt
```

### 3. Konfigurasi
**Via UI (disarankan)** `app.py:1` `templates/index.html:1`
```bash
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python app.py
# buka http://localhost:5000 (VPS: http://<VPS_IP>:5000, buka port: sudo ufw allow 5000)
```
- **Config IP:PORT** `app.py:40` → isi **IP Server** + **Port** → auto rakit `REDIRECT_TO`, `LOGIN_URL=http://<IP>:<PORT>/login`, `TARGET_URL=.../antigravity` → **Simpan Konfigurasi** (`POST /api/config` tulis `.env:1`)
- **DASH_PASSWORD / HEADLESS / RESET_PROFILE / CLEAR_EACH / RESTART_BROWSER_PER_ACCOUNT** di panel sama → Simpan
- **Tambah Akun** `templates/index.html:84` → isi **Email** + **Password** → **Tambah Akun** (tabel preview, hapus per baris, sync Tabel↔Textarea) → auto `POST /api/accounts` simpan `accounts.txt:1`

**Manual:**
```bash
nano .env          # isi DASH_PASSWORD, HEADLESS=false (visible) / true (VPS)
nano accounts.txt  # per baris: gmail|password  (# komentar diabaikan)
```

### 4. Jalankan
**Via UI:** tombol **Jalankan** (`POST /api/start` → `subprocess.Popen` `flow.py`), log real-time `GET /api/logs` poll 1.5s, **Hentikan** untuk terminate, **Bersihkan Log**

**Via CLI:**
```bash
source .venv/bin/activate
python flow.py                    # pakai .env
HEADLESS=true python flow.py      # override
# Windows visible
.\.venv\Scripts\python.exe flow.py
# VPS headless virtual display
xvfb-run -a python flow.py
# background VPS
tmux new -s antig && python app.py
# atau: nohup python app.py & / FLASK_HOST=0.0.0.0 FLASK_PORT=5000 python app.py
```

Alur `flow.py:179` : login → `Add` → `I Understand, Continue` → popup Google isi email/pass → auto-klik `Sign in`/`Login`/`Continue`/`Allow` → rewrite `localhost` → `REDIRECT_TO` (`flow.py:138`) → tunggu callback → `urls.txt`.

### 5. Lihat Log
- UI: panel **Log** + `urls.txt` textarea, file `flow.log:1` & `urls.txt:1`
- CLI: stdout + `cat urls.txt` / `cat flow.log`

### Quick Start (singkat)
**Windows**
```bat
install.bat
# edit .env & accounts.txt via UI atau nano
.venv\Scripts\activate
python app.py  # UI di http://localhost:5000
```

**Ubuntu VPS**
```bash
chmod +x install.sh && ./install.sh
nano .env && nano accounts.txt
source .venv/bin/activate && python app.py
# atau langsung: python flow.py
```

## Konfigurasi `.env`
Lihat `.env.example`. Salin jadi `.env`:
```bash
cp .env.example .env
```
Penting (isi di `.env`, jangan commit):
- `DASH_PASSWORD` — password dashboard 9Router
- `LOGIN_URL`/`TARGET_URL`/`REDIRECT_TO` — `http://<IP>:<PORT>/...` (diatur via UI atau `.env`)
- `HEADLESS=false` visible, `true` untuk VPS tanpa display
- `RESET_PROFILE=true` hapus `browser_profile` tiap run (fresh)
- `CLEAR_EACH=true` bersihkan cookie tiap akun (fix akun 2)
- `RESTART_BROWSER_PER_ACCOUNT=false` set `true` jika mau close browser tiap akun (workaround account chooser)

## Menjalankan Visible
```powershell
cd C:\lara\laragon\www\antig-auto
.\.venv\Scripts\python.exe flow.py
# atau
$env:HEADLESS="false"; python flow.py
```

## Troubleshooting
- `playwright TimeoutError Next` → pastikan `accounts.txt` format `gmail|password`, cek Google block bot (jalankan `HEADLESS=false`).
- Akun ke-2 stuck `accountchooser` → aktifkan `CLEAR_EACH=true` atau `RESTART_BROWSER_PER_ACCOUNT=true`.
- `localhost` tidak keganti IP → sudah di-fix di `flow.py:138` rewrite `localhost` → `REDIRECT_TO` (hanya callback `code=` yang disimpan).
- Password login salah → cek `DASH_PASSWORD` di `.env`.

## Web UI (baru)
IP:PORT sekarang tersimpan di `.env` (`REDIRECT_TO`, `LOGIN_URL`, `TARGET_URL`) dan bisa diedit via UI.

```bash
# install Flask (sudah di requirements.txt)
pip install -r requirements.txt
python app.py
# buka http://localhost:5000  (atau http://<VPS_IP>:5000)
```
Fitur UI:
- **Config IP:PORT** — isi IP & Port, auto-rakit `REDIRECT_TO`/`LOGIN_URL`/`TARGET_URL`, simpan ke `.env` (tombol *Simpan Konfigurasi*)
- **Accounts** — edit `accounts.txt` langsung
- **Start / Stop** — jalankan `flow.py` visible/headless sesuai `.env`, tampilkan log real-time + `urls.txt`
- Log aktivitas proses, auto-scroll, `Bersihkan Log`

Untuk VPS Ubuntu buka port `5000`:
```bash
sudo ufw allow 5000
FLASK_HOST=0.0.0.0 FLASK_PORT=5000 python app.py
# atau via systemd / tmux
```

## File
- `flow.py` — alur utama
- `app.py` — Flask UI (start/stop + log + config IP:PORT)
- `templates/index.html` — UI
- `requirements.txt` — `playwright==1.62.0` + `Flask==3.0.3`
- `install.sh` / `install.bat` — installer
- `accounts.txt.example` — contoh akun
- `urls.txt` — log URL callback (auto generate)

## Git
```bash
git clone https://github.com/Dropking1122/testantigravity.git
cd testantigravity
./install.sh
python app.py  # UI
```
