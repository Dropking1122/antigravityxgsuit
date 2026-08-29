#!/usr/bin/env python3
"""
Antigravity Auto - Interactive Terminal CLI Menu (TUI)
Provides a clean, hacker-style console interface for running automation,
managing accounts, configuring server options, and starting the Web UI.
"""
import os
import sys
import time
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
ENV_FILE = BASE_DIR / ".env"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

ACCOUNTS_FILE = DATA_DIR / "accounts.txt"
PROCESSED_FILE = DATA_DIR / "processed_accounts.txt"
FAILED_FILE = DATA_DIR / "failed_accounts.txt"

# ANSI Color Codes for Hacker/Terminal Theme
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    clear_screen()
    print(f"{CYAN}{BOLD}")
    print(r"  ╔══════════════════════════════════════════════════════════════════════╗")
    print(r"  ║    ___  _  _ ___ _ ____ ____ ____ _  _ _ ___ _ me ___ ____ ____      ║")
    print(r"  ║    |__| |\ |  |  | |  | |__/ |__| |  | |  |  | |__| |__/ |__|      ║")
    print(r"  ║    |  | | \|  |  | |__| |  \ |  |  \/  |  |  | |  | |  \ |  |      ║")
    print(r"  ║                --- Terminal Automation Engine v2.1 ---               ║")
    print(r"  ╚══════════════════════════════════════════════════════════════════════╝")
    print(f"{RESET}")

def detect_python():
    win_py = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    nix_py = BASE_DIR / ".venv" / "bin" / "python"
    if win_py.exists():
        return str(win_py)
    if nix_py.exists():
        return str(nix_py)
    return sys.executable

def count_accounts():
    pending = 0
    processed = 0
    failed = 0
    if ACCOUNTS_FILE.exists():
        lines = [l.strip() for l in ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")]
        pending = len(lines)
    if PROCESSED_FILE.exists():
        lines = [l.strip() for l in PROCESSED_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        processed = len(lines)
    if FAILED_FILE.exists():
        lines = [l.strip() for l in FAILED_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        failed = len(lines)
    return pending, processed, failed

def run_automation(headless=False):
    py = detect_python()
    env = os.environ.copy()
    env["HEADLESS"] = "true" if headless else "false"
    env["PYTHONUNBUFFERED"] = "1"
    
    mode_name = "HEADLESS (VPS)" if headless else "VISIBLE (Browser Kelihatan)"
    print(f"\n{GREEN}[*] Memulai Automation Flow dalam mode {BOLD}{mode_name}{RESET}...")
    print(f"{DIM}[*] Executing: {py} flow.py{RESET}\n")
    time.sleep(1)
    
    try:
        proc = subprocess.run([py, "flow.py"], cwd=str(BASE_DIR), env=env)
        print(f"\n{GREEN}[✓] Otomasi selesai dengan exit code {proc.returncode}{RESET}")
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!] Otomasi dihentikan oleh pengguna (Ctrl+C).{RESET}")
    except Exception as e:
        print(f"\n{RED}[!] Error menjalankan otomasi: {e}{RESET}")
    
    input(f"\n{CYAN}Tekan [Enter] untuk kembali ke menu utama...{RESET}")

def start_web_ui():
    py = detect_python()
    print(f"\n{GREEN}[*] Memulai Flask Web Server UI...{RESET}")
    print(f"{CYAN}[*] Akses Web UI di browser: http://localhost:5000{RESET}\n")
    try:
        subprocess.run([py, "app.py"], cwd=str(BASE_DIR))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!] Web Server UI dihentikan.{RESET}")
    except Exception as e:
        print(f"\n{RED}[!] Error Web Server: {e}{RESET}")
    input(f"\n{CYAN}Tekan [Enter] untuk kembali ke menu utama...{RESET}")

def add_account_prompt():
    print(f"\n{CYAN}{BOLD}=== TAMBAH AKUN BARU ==={RESET}")
    email = input(f"{YELLOW}Masukkan Email Google (gmail): {RESET}").strip()
    if not email or "@" not in email:
        print(f"{RED}[!] Email tidak valid!{RESET}")
        time.sleep(1.5)
        return
    password = input(f"{YELLOW}Masukkan Password Google: {RESET}").strip()
    if not password:
        print(f"{RED}[!] Password tidak boleh kosong!{RESET}")
        time.sleep(1.5)
        return
    
    line = f"{email}|{password}\n"
    with open(ACCOUNTS_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(f"{GREEN}[✓] Berhasil menambahkan {email} ke {ACCOUNTS_FILE}{RESET}")
    time.sleep(1.5)

def list_accounts_prompt():
    print(f"\n{CYAN}{BOLD}=== DAFTAR AKUN DALAM ANTREAN ==={RESET}")
    if not ACCOUNTS_FILE.exists():
        print(f"{DIM}Antrean kosong.{RESET}")
    else:
        lines = [l.strip() for l in ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")]
        if not lines:
            print(f"{DIM}Tidak ada akun dalam antrean.{RESET}")
        else:
            for idx, line in enumerate(lines, 1):
                parts = line.split("|")
                em = parts[0]
                print(f"  {GREEN}{idx:02d}.{RESET} {em:<35} | {DIM}••••••••{RESET}")
    
    print(f"\n{CYAN}{BOLD}=== AKUN GAGAL (Need Requeue) ==={RESET}")
    if FAILED_FILE.exists():
        flines = [l.strip() for l in FAILED_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        for idx, line in enumerate(flines, 1):
            parts = line.split("|")
            em = parts[0] if len(parts) > 0 else ""
            reason = parts[4] if len(parts) > 4 else "Gagal"
            print(f"  {RED}{idx:02d}.{RESET} {em:<35} | {RED}{reason}{RESET}")
    else:
        print(f"{DIM}Tidak ada akun gagal.{RESET}")

    input(f"\n{CYAN}Tekan [Enter] untuk kembali...{RESET}")

def requeue_failed_prompt():
    if not FAILED_FILE.exists() or not FAILED_FILE.read_text().strip():
        print(f"\n{YELLOW}[!] Tidak ada akun gagal untuk di-requeue.{RESET}")
        time.sleep(1.5)
        return
    
    flines = [l.strip() for l in FAILED_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"\n{CYAN}{BOLD}=== REQUEUE AKUN GAGAL ==={RESET}")
    for idx, line in enumerate(flines, 1):
        parts = line.split("|")
        print(f"  {RED}{idx:02d}.{RESET} {parts[0]}")
    
    choice = input(f"\n{YELLOW}Pilih nomor akun untuk diulangi (atau 'all' untuk semua, '0' batal): {RESET}").strip()
    if choice == '0':
        return
    if choice.lower() == 'all':
        with open(ACCOUNTS_FILE, "a", encoding="utf-8") as af:
            for line in flines:
                parts = line.split("|")
                af.write(f"{parts[0]}|{parts[1]}\n")
        FAILED_FILE.write_text("", encoding="utf-8")
        print(f"{GREEN}[✓] Semua akun gagal berhasil dikembalikan ke antrean!{RESET}")
    elif choice.isdigit() and 1 <= int(choice) <= len(flines):
        target = flines[int(choice) - 1]
        parts = target.split("|")
        with open(ACCOUNTS_FILE, "a", encoding="utf-8") as af:
            af.write(f"{parts[0]}|{parts[1]}\n")
        
        remaining = [l for i, l in enumerate(flines) if i != (int(choice) - 1)]
        FAILED_FILE.write_text("\n".join(remaining) + ("\n" if remaining else ""), encoding="utf-8")
        print(f"{GREEN}[✓] Akun {parts[0]} berhasil dikembalikan ke antrean!{RESET}")
    else:
        print(f"{RED}[!] Pilihan tidak valid!{RESET}")
    time.sleep(1.5)

def main_menu():
    while True:
        print_banner()
        pending, processed, failed = count_accounts()
        
        print(f"  {BOLD}STATUS SIKLUS ANTREAN:{RESET}")
        print(f"    • Antrean Belum Diproses : {YELLOW}{BOLD}{pending}{RESET} Akun")
        print(f"    • Sukses Terimpor       : {GREEN}{BOLD}{processed}{RESET} Akun")
        print(f"    • Gagal Terimpor        : {RED}{BOLD}{failed}{RESET} Akun")
        print(f"  ──────────────────────────────────────────────────────────────────────")
        print(f"  {BOLD}PILIH MENU OPERASI Terminal (TUI):{RESET}")
        print(f"    {GREEN}1.{RESET} {BOLD}Start with Visible Mode{RESET}   (Browser Kelihatan - Windows/Desktop)")
        print(f"    {GREEN}2.{RESET} {BOLD}Start with Headless Mode{RESET}  (Tanpa Display - Dedicated VPS)")
        print(f"    {GREEN}3.{RESET} {BOLD}Start Web Server UI{RESET}       (Interface Browser http://localhost:5000)")
        print(f"  ──────────────────────────────────────────────────────────────────────")
        print(f"    {CYAN}4.{RESET} Tambah Akun Ke Antrean (Email & Password)")
        print(f"    {CYAN}5.{RESET} Lihat Daftar Akun Antrean & Riwayat")
        print(f"    {CYAN}6.{RESET} Ulangi Akun Gagal (Requeue Failed Accounts)")
        print(f"  ──────────────────────────────────────────────────────────────────────")
        print(f"    {RED}0.{RESET} Keluar dari Program")
        print(f"  ──────────────────────────────────────────────────────────────────────")
        
        choice = input(f"  {BOLD}{GREEN}select_option > {RESET}").strip()
        
        if choice == "1":
            run_automation(headless=False)
        elif choice == "2":
            run_automation(headless=True)
        elif choice == "3":
            start_web_ui()
        elif choice == "4":
            add_account_prompt()
        elif choice == "5":
            list_accounts_prompt()
        elif choice == "6":
            requeue_failed_prompt()
        elif choice == "0":
            print(f"\n{GREEN}[*] Terima kasih! Program dihentikan.{RESET}\n")
            sys.exit(0)
        else:
            print(f"\n{RED}[!] Pilihan tidak valid, coba lagi.{RESET}")
            time.sleep(1)

if __name__ == "__main__":
    main_menu()
