# Antigravity Auto

Otomasi `flow.py` untuk login dashboard 9Router (`<IP>:<PORT>`) → `/dashboard/providers/antigravity` → `Add` → `I Understand, Continue` → Google OAuth (isi email/pass, auto-klik `Sign in`/`Login`/`Continue`/`Allow`, rewrite `localhost:20128` → `<IP>:<PORT>`).

## Fitur
- Browser visible (`HEADLESS=false`) untuk handle verifikasi manual, auto-klik `Sign in` sekarang.
- Rewrite `localhost` ke IP via `context.route` (tidak perlu konek ke localhost).
- `CLEAR_EACH=true` bersihkan Google session tiap akun agar `Use another account` tidak nyangkut di akun ke-2.
- `RESTART_BROWSER_PER_ACCOUNT=true` close & buka browser baru tiap akun (solusi VPS).
- Auto fixed `LAST_REWRITE` hanya untuk `/callback?code=` (tidak tertimpa static `woff2/css`).

## Quick Start

### Windows
```bat
install.bat
# edit .env dan accounts.txt
.venv\Scripts\activate
python flow.py
```

### Ubuntu VPS
```bash
chmod +x install.sh
./install.sh
nano .env          # isi DASH_PASSWORD, HEADLESS=true, IP:PORT
nano accounts.txt  # gmail|password per baris
source .venv/bin/activate
python flow.py
# atau headless virtual display:
xvfb-run -a python flow.py
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
- **Config IP:PORT** — isi IP & Port, auto-rakit `REDIRECT_TO`/`LOGIN_URL`/`TARGET_URL`, simpan ke `.env` (tombol *Simpan .env*)
- **Accounts** — edit `accounts.txt` langsung
- **Start / Stop** — jalankan `flow.py` visible/headless sesuai `.env`, tampilkan log real-time + `urls.txt`
- Log di `flow.log`, auto-scroll, `Clear Log`

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
