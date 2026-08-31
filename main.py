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

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
ENV_FILE = BASE_DIR / ".env"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

ACCOUNTS_FILE = BASE_DIR / "accounts.txt"

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
    print(r"  ║            --- Antigravity Automation Engine v2.5 ---                ║")
    print(r"  ║                Terminal Console & Management CLI                     ║")
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

def requeue_failed_accounts():
    """Pindahkan semua akun yang ada di failed_accounts.txt kembali ke antrean accounts.txt."""
    if not FAILED_FILE.exists():
        print(f"\n  {YELLOW}[!] File failed_accounts.txt tidak ditemukan.{RESET}")
        time.sleep(1.5)
        return
    failed_lines = [l.strip() for l in FAILED_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not failed_lines:
        print(f"\n  {YELLOW}[!] Tidak ada akun gagal untuk diulangi.{RESET}")
        time.sleep(1.5)
        return
    
    # Ekstrak email|pass
    requeue_items = []
    for l in failed_lines:
        parts = l.split("|")
        if len(parts) >= 2:
            requeue_items.append(f"{parts[0].strip()}|{parts[1].strip()}")
    
    current_accs = ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines() if ACCOUNTS_FILE.exists() else []
    merged = [l.strip() for l in current_accs if l.strip()]
    for item in requeue_items:
        if item not in merged:
            merged.append(item)
            
    ACCOUNTS_FILE.write_text("\n".join(merged) + ("\n" if merged else ""), encoding="utf-8")
    if (DATA_DIR / "accounts.txt").exists():
        (DATA_DIR / "accounts.txt").write_text("\n".join(merged) + ("\n" if merged else ""), encoding="utf-8")
    if (BASE_DIR / "accounts.txt").exists():
        (BASE_DIR / "accounts.txt").write_text("\n".join(merged) + ("\n" if merged else ""), encoding="utf-8")
        
    FAILED_FILE.write_text("", encoding="utf-8")
    print(f"\n  {GREEN}[✓] Berhasil memindahkan {len(requeue_items)} akun gagal kembali ke antrean accounts.txt!{RESET}")
    time.sleep(1.5)

def run_automation(headless=True):
    py = detect_python()
    env = os.environ.copy()
    env["HEADLESS"] = "true" if headless else "false"
    env["PYTHONUNBUFFERED"] = "1"
    
    mode_name = "HEADLESS (VPS Mode)" if headless else "VISIBLE (Browser GUI Mode)"
    print(f"\n{GREEN}[*] Memulai Automation Flow dalam mode {BOLD}{mode_name}{RESET}...")
    print(f"{DIM}[*] Executing: {py} -u flow.py{RESET}\n")
    time.sleep(1)
    
    try:
        proc = subprocess.run([py, "-u", "flow.py"], cwd=str(BASE_DIR), env=env)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!] Otomasi dihentikan oleh pengguna (Ctrl+C).{RESET}")
    except Exception as e:
        print(f"\n{RED}[!] Error menjalankan otomasi: {e}{RESET}")
    
    # Ringkasan hasil setelah eksekusi
    print("\n" + "═" * 68)
    pending, processed, failed = count_accounts()
    print(f"  {BOLD}RINGKASAN HASIL OTOMASI:{RESET}")
    print(f"    • {GREEN}Akun Berhasil Selesai :{RESET} {BOLD}{processed}{RESET} akun")
    print(f"    • {RED}Akun Gagal / Timeout  :{RESET} {BOLD}{failed}{RESET} akun")
    print(f"    • {CYAN}Sisa Dalam Antrean    :{RESET} {BOLD}{pending}{RESET} akun")
    print("═" * 68)
    
    if failed > 0:
        print(f"\n  {YELLOW}Pilihan Tindakan:{RESET}")
        print(f"    {GREEN}[1]{RESET} Ulangi Jalankan Akun yang Gagal")
        print(f"    {CYAN}[2]{RESET} Kembali ke Menu Utama")
        print(f"    {RED}[0]{RESET} Keluar (Exit)")
        sub_choice = input(f"\n  {CYAN}Pilih opsi [0-2]: {RESET}").strip()
        if sub_choice == "1":
            requeue_failed_accounts()
            run_automation(headless=headless)
            return
        elif sub_choice == "0":
            print(f"\n  {GREEN}[*] Keluar dari aplikasi. Sampai jumpa!{RESET}\n")
            sys.exit(0)
    else:
        input(f"\n{CYAN}Tekan [Enter] untuk kembali ke menu utama...{RESET}")

def start_web_ui():
    py = detect_python()
    print(f"\n{GREEN}[*] Memulai Flask Web Server UI...{RESET}")
    print(f"{CYAN}[*] Akses Web UI di browser: http://localhost:5000{RESET}\n")
    try:
        subprocess.run([py, "app.py"], cwd=str(BASE_DIR))
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[*] Web UI server dihentikan.{RESET}")
    except Exception as e:
        print(f"\n{RED}[!] Error menjalankan server: {e}{RESET}")
    input(f"\n{CYAN}Tekan [Enter] untuk kembali ke menu utama...{RESET}")

def main_menu():
    while True:
        print_banner()
        pending, processed, failed = count_accounts()
        print(f"  {BOLD}Status Antrean Akun:{RESET}")
        print(f"    • {CYAN}Antrean Tersedia  :{RESET} {BOLD}{pending}{RESET} akun")
        print(f"    • {GREEN}Berhasil Diimpor  :{RESET} {BOLD}{processed}{RESET} akun")
        print(f"    • {RED}Gagal / Timeout   :{RESET} {BOLD}{failed}{RESET} akun")
        print("  " + "─" * 68)
        print(f"  {BOLD}Menu Pilihan:{RESET}")
        print(f"    {GREEN}[1]{RESET} Jalankan Otomasi Headless (VPS - Rekomendasi)")
        print(f"    {GREEN}[2]{RESET} Jalankan Otomasi Visible (Tampilan Browser)")
        print(f"    {CYAN}[3]{RESET} Buka Flask Web Dashboard (Port 5000)")
        print(f"    {YELLOW}[4]{RESET} Ulangi Semua Akun Gagal (Requeue Failed)")
        print(f"    {YELLOW}[5]{RESET} Bersihkan Data & Riwayat")
        print(f"    {RED}[0]{RESET} Keluar")
        print("  " + "─" * 68)
        
        choice = input(f"  {CYAN}Pilih opsi [0-5]: {RESET}").strip()
        if choice == "1":
            run_automation(headless=True)
        elif choice == "2":
            run_automation(headless=False)
        elif choice == "3":
            start_web_ui()
        elif choice == "4":
            requeue_failed_accounts()
        elif choice == "5":
            confirm = input(f"\n  {RED}Yakin ingin mereset data riwayat processed & failed? (y/N): {RESET}").strip().lower()
            if confirm == "y":
                if PROCESSED_FILE.exists(): PROCESSED_FILE.write_text("", encoding="utf-8")
                if FAILED_FILE.exists(): FAILED_FILE.write_text("", encoding="utf-8")
                print(f"  {GREEN}[✓] Data riwayat dibersihkan.{RESET}")
                time.sleep(1)
        elif choice == "0":
            print(f"\n  {GREEN}[*] Selesai. Sampai jumpa!{RESET}\n")
            break

if __name__ == "__main__":
    main_menu()
