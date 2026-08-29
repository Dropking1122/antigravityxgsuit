# ANTIGRAVITY CREATOR X GSUITE

Otomasi auto-login & auto-import akun Google OAuth (GSuite) ke Provider Antigravity 9Router.

---

### Cara Penggunaan (4 Langkah Mudah)

#### 1. Clone Repository
```bash
git clone https://github.com/Dropking1122/testantigravity.git
cd testantigravity
```

#### 2. Jalankan Installer
**Linux / Ubuntu VPS:**
```bash
chmod +x install.sh
./install.sh
```
**Windows:**
```cmd
install.bat
```

#### 3. Isi Daftar Akun
Isi file `data/accounts.txt` dengan format `gmail|password` per baris:
```text
email1@domain.com|password1
email2@domain.com|password2
```
*(Atau gunakan fitur Web UI untuk menambah akun)*

#### 4. Jalankan Otomasi

**Cara 1: Gunakan Quick Launcher Script (Rekomendasi)**
```bash
# Linux / Ubuntu VPS
./start.sh

# Windows
start.bat
```

**Cara 2: Jalankan via Terminal Menu / Web UI / CLI**
```bash
# Aktifkan Virtual Environment
source .venv/bin/activate        # Linux / VPS
# .venv\Scripts\activate          # Windows

# Pilih salah satu:
python main.py                   # Terminal Interactive Menu (TUI)
python app.py                    # Web Server UI (http://localhost:5000)
python flow.py                   # Otomasi langsung (CLI)
```

---

### Fitur Utama
- **Web UI & Terminal TUI**: Antarmuka berbasis Web (`app.py`) dan Terminal Console (`main.py`).
- **Auto Import & Sign-In**: Mengisi credentials & meng-klik tombol konfirmasi OAuth secara otomatis.
- **Validasi Dashboard**: Memeriksa keberadaan email di dashboard provider. Akun sukses dipindahkan ke `processed_accounts.txt`.
- **IP:PORT Auto Rewrite**: Otomatis mengalihkan callback `localhost` ke Server IP target.
