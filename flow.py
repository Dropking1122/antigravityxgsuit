"""
Alur otomatis:
  1. Buka halaman login -> isi password -> Enter
  2. Ke /dashboard/providers/antigravity -> klik "Add"
  3. Modal "I Understand, Continue" -> klik (buka tab baru Google)
  4. Tab baru: isi email -> Next -> isi password -> Next
  5. Jika muncul "Don't get locked out" -> klik "Do this later"
  6. Tombol "Sign in" -> klik OTOMATIS (tidak perlu manual)
  7. Tunggu callback OAuth -> rewrite localhost -> IP server

Catatan: login Google via otomasi sering terblokir deteksi bot Google
& melanggar ToS Google. Mode headful (HEADLESS=false) tetap disarankan.
"""
import os
import time
import shutil
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ---- Konfigurasi ----
ROUTER_HOST = os.getenv("ROUTER_HOST", "").rstrip("/")
LOGIN_URL = os.getenv("LOGIN_URL", f"{ROUTER_HOST}/login" if ROUTER_HOST else "")
TARGET_URL = os.getenv("TARGET_URL", f"{ROUTER_HOST}/dashboard/providers/antigravity" if ROUTER_HOST else "")
PASSWORD = os.getenv("DASH_PASSWORD", "")
PROFILE = os.getenv("USER_DATA_DIR", "./browser_profile")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
ACCOUNTS_FILE = os.getenv("ACCOUNTS_FILE", "accounts.txt")
# Kalau "true", hapus folder profil agar benar-benar fresh (akun Google lama hilang)
RESET_PROFILE = os.getenv("RESET_PROFILE", "false").lower() == "true"
# Jika true, tiap akun restart browser (fresh) agar account chooser tidak muncul - solusi VPS
RESTART_BROWSER_PER_ACCOUNT = os.getenv("RESTART_BROWSER_PER_ACCOUNT", "false").lower() == "true"
# Jika true, bersihkan cookie Google tiap akun (agar chooser kosong)
CLEAR_EACH = os.getenv("CLEAR_EACH", "true").lower() == "true"

# OAuth callback Google mengarah ke localhost, kita rewrite ke IP server
REDIRECT_FROM = os.getenv("REDIRECT_FROM", "http://localhost:20128")
REDIRECT_TO = os.getenv("REDIRECT_TO", ROUTER_HOST)

if not LOGIN_URL or not TARGET_URL or not PASSWORD:
    raise ValueError("[!] LOGIN_URL, TARGET_URL/ROUTER_HOST, dan DASH_PASSWORD wajib diisi di .env atau environment variables!")

# File log semua URL & file riwayat akun
URL_LOG_FILE = os.getenv("URL_LOG_FILE", "urls.txt")
FLOW_LOG_FILE = LOGS_DIR / "flow.log"
PROCESSED_ACCOUNTS_FILE = DATA_DIR / "processed_accounts.txt"
FAILED_ACCOUNTS_FILE = DATA_DIR / "failed_accounts.txt"

# Hook print bawaan agar otomatis menulis ke logs/flow.log dan stdout sekaligus
_builtin_print = print
def print(*args, **kwargs):
    _builtin_print(*args, **kwargs)
    try:
        msg = " ".join(str(a) for a in args)
        with open(FLOW_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
        with open(BASE_DIR / "flow.log", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

# Menyimpan URL callback terakhir yang sudah di-rewrite ke IP
# (dipakai untuk re-hit kalau tab keburu close)
LAST_REWRITE = {"url": None}


def reset_profile():
    if os.path.isdir(PROFILE):
        print(f"[*] Reset profil: hapus {PROFILE}")
        shutil.rmtree(PROFILE, ignore_errors=True)


def clear_google_sessions(context):
    """Hapus session Google agar daftar 'Choose an account' jadi KOSONG,
    plus bersihkan cache/storage terkait Google. Dipanggil tiap 10 akun."""
    print("[*] Reset session Google (akun di picker dibuang, jadi kosong)...")
    # 1. Hapus cookie Google (OSID/HSID dkk yang nyimpan akun login)
    try:
        cookies = context.cookies()
        google_domains = sorted({c.get("domain", "") for c in cookies
                                 if "google" in c.get("domain", "")})
        for d in google_domains:
            try:
                context.clear_cookies(filter={"domain": d})
            except Exception as e:
                print(f"[!] Gagal clear cookie domain {d}: {e}")
        print(f"[*] Cookie Google dihapus ({len(google_domains)} domain).")
    except Exception as e:
        print(f"[!] Gagal baca/clear cookie: {e}")
    # 2. Bersihkan localStorage / sessionStorage Google lewat halaman tersembunyi
    try:
        pg = context.new_page()
        try:
            pg.goto("https://accounts.google.com/", wait_until="domcontentloaded", timeout=10000)
            pg.evaluate("try{localStorage.clear();sessionStorage.clear();}catch(e){}")
        except Exception:
            pass
        pg.close()
    except Exception:
        pass
    # 3. Hapus folder cache profil (Cache / Code Cache) biar benar-benar bersih
    for sub in ("Cache", "Code Cache", "GPUCache", "Service Worker"):
        p = os.path.join(PROFILE, sub)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
    print("[*] Cache profil dibersihkan.")


def load_accounts(path: str):
    """Baca file teks baris: gmail|password dengan deduplikasi & abaikan akun yang SUDAH SUKSES"""
    accounts = []
    seen = set()

    # Baca daftar email yang SUDAH SUKSES agar tidak diproses ulang
    success_emails = set()
    if PROCESSED_ACCOUNTS_FILE.exists():
        try:
            for l in PROCESSED_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
                if l.strip() and "|" in l:
                    success_emails.add(l.split("|")[0].strip().lower())
        except Exception:
            pass

    if not os.path.exists(path):
        if os.path.exists(os.path.join("data", path)):
            path = os.path.join("data", path)
        else:
            print(f"[!] File akun tidak ada: {path}")
            return accounts
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                email, pw = line.split("|", 1)
                email_clean = email.strip()
                # Lewati jika sudah pernah sukses atau duplikat
                if email_clean.lower() in success_emails:
                    continue
                if email_clean.lower() not in seen and pw.strip():
                    seen.add(email_clean.lower())
                    accounts.append((email_clean, pw.strip()))
    print(f"[*] Total akun valid siap diproses: {len(accounts)}")
    return accounts


def move_account(email: str, gpw: str, status: str, error_msg: str = ""):
    target_file = PROCESSED_ACCOUNTS_FILE if status == "SUCCESS" else FAILED_ACCOUNTS_FILE
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{email}|{gpw}|{status}|{timestamp}"
    if error_msg:
        log_entry += f"|{error_msg}"

    try:
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception:
        pass

    # Hapus akun dari file antrean accounts.txt
    target_acc_files = [Path(ACCOUNTS_FILE), DATA_DIR / "accounts.txt", BASE_DIR / "accounts.txt"]
    for acc_f in target_acc_files:
        if acc_f.exists():
            try:
                lines = acc_f.read_text(encoding="utf-8").splitlines()
                new_lines = []
                removed = False
                for line in lines:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        new_lines.append(line)
                        continue
                    if "|" in stripped:
                        em, _ = stripped.split("|", 1)
                        if em.strip().lower() == email.strip().lower() and not removed:
                            removed = True
                            continue
                    new_lines.append(line)
                acc_f.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
            except Exception:
                pass


def log_url(url: str):
    """Simpan URL ke file log (1 baris per URL). Aman dari duplikat berurutan."""
    if not url:
        return
    try:
        url_file = LOGS_DIR / "urls.txt"
        if url_file.exists():
            with open(url_file, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            if lines and lines[-1] == url:
                return
        with open(url_file, "a", encoding="utf-8") as f:
            f.write(url + "\n")
        with open(BASE_DIR / "urls.txt", "a", encoding="utf-8") as f:
            f.write(url + "\n")
    except Exception:
        pass


# ==============================================================================
# PENTING / JANGAN DIUBAH: Logika intercept redirect callback localhost ke IP server
# ==============================================================================
def _rewrite_redirect(route):
    url = route.request.url
    # Hanya tangani jika request benar-benar mengarah ke localhost/127.0.0.1 port 20128
    # (PENTING: Jangan gunakan pengecekan substring 'localhost' karena URL internal Google
    # membawa parameter 'redirect_uri=http://localhost:20128/callback' yang tidak boleh di-redirect).
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.hostname in ("localhost", "127.0.0.1") and (parsed.port == 20128 or ":20128" in url):
        ip_host = REDIRECT_TO.split("://", 1)[-1].split(":", 1)[0]
        new_url = url.replace("localhost:20128", f"{ip_host}:20128").replace("127.0.0.1:20128", f"{ip_host}:20128")
        if "/callback" in url:
            LAST_REWRITE["url"] = new_url
            log_url(url)
            log_url(new_url)
            print(f"[*] Callback localhost terdeteksi ({url[:60]}...) -> redirect ke {new_url[:70]}...")
            route.fulfill(status=302, headers={"Location": new_url})
            return
        route.continue_(url=new_url)
        return
    route.continue_()
# ==============================================================================


# ---- Selector ----
SEL_PASSWORD_INPUT = 'input[placeholder="Enter password"]'
SEL_ADD_BTN = 'button:has-text("Add")'
SEL_CONTINUE_BTN = 'button:has-text("I Understand, Continue")'
SEL_GOOGLE_EMAIL = '#identifierId'
SEL_GOOGLE_NEXT = 'button:has-text("Next")'
SEL_GOOGLE_PASS = 'input[name="Passwd"]'
SEL_LOCKED_OUT = 'div.ap24pb:has-text("Don\'t get locked out")'
SEL_DO_LATER = 'a:has-text("Do this later")'
SEL_I_UNDERSTAND = 'button:has-text("I understand")'
SEL_GOOGLE_SIGNIN = 'button:has-text("Sign in")'
SEL_GOOGLE_SIGNIN_VARIANTS = 'button:has-text("Sign in"), button:has-text("Sign In"), button:has-text("Login"), button:has-text("Log in")'
SEL_LOGIN_BTN = 'button:has-text("Login"), button:has-text("Log in"), button:has-text("Sign in"), button:has-text("Masuk")'
SEL_USE_ANOTHER = 'div[role="link"]:has-text("Use another account")'
SEL_ALLOW = 'button:has-text("Allow"), button:has-text("Allow access"), button:has-text("Continue"), button:has-text("Confirm")'


def run():
    accounts = load_accounts(ACCOUNTS_FILE)
    if not accounts:
        print("[!] Tidak ada akun. Isi accounts.txt dengan format gmail|password")
        return

    if RESET_PROFILE:
        reset_profile()

    with sync_playwright() as p:
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ]
        context = p.chromium.launch_persistent_context(
            PROFILE, headless=HEADLESS, args=args)
        page = context.new_page()

        # 1. Login dashboard (sekali saja)
        print("[*] Buka login dashboard...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        page.fill(SEL_PASSWORD_INPUT, PASSWORD)
        page.press(SEL_PASSWORD_INPUT, "Enter")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        # FIX: setelah I understand / login, ada tombol Login lagi yang harus di-klik
        # cek beberapa varian tombol Login/Sign in di halaman dashboard setelah login
        try:
            # tunggu sebentar kalau ada tombol Login muncul setelah I understand
            for sel in [SEL_LOGIN_BTN, 'button:has-text("I understand")', 'button:has-text("I Understand")']:
                try:
                    loc = page.locator(sel)
                    if loc.count() > 0:
                        try:
                            # cek visible dalam 2 detik
                            page.wait_for_selector(sel, timeout=2000)
                            print(f"[*] Tombol tambahan terdeteksi '{sel}' -> klik")
                            page.click(sel, timeout=3000)
                            time.sleep(2)
                            page.wait_for_load_state("domcontentloaded")
                            time.sleep(1)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        # Pasang route rewrite redirect localhost -> IP server (global, ringan).
        # Ini berjalan di level request, SEBELUM browser nyoba konek ke localhost,
        # sehingga tab tidak pernah load halaman localhost yang gagal/blank.
        context.route("**/*", _rewrite_redirect)

        # 2. Loop tiap akun Google
        for idx, (email, gpw) in enumerate(accounts, 1):
            try:
                # Reset session Google tiap akun (jika CLEAR_EACH=true) agar account chooser kosong
                # atau restart browser per akun jika RESTART_BROWSER_PER_ACCOUNT=true
                if idx > 1:
                    if RESTART_BROWSER_PER_ACCOUNT:
                        print(f"[*] Menutup context lama dan membuat context/browser baru sebelum akun {idx}...")
                        try:
                            context.close()
                        except Exception:
                            pass
                        # Hapus profil agar benar-benar fresh
                        reset_profile()
                        context = p.chromium.launch_persistent_context(
                            PROFILE, headless=HEADLESS,
                            args=args)
                        context.route("**/*", _rewrite_redirect)
                        page = context.new_page()
                        # login lagi setelah restart
                        print("[*] Login ulang dashboard setelah restart...")
                        page.goto(LOGIN_URL, wait_until="domcontentloaded")
                        page.fill(SEL_PASSWORD_INPUT, PASSWORD)
                        page.press(SEL_PASSWORD_INPUT, "Enter")
                        page.wait_for_load_state("domcontentloaded")
                        time.sleep(2)
                    elif CLEAR_EACH:
                        clear_google_sessions(context)
                        print(f"[*] (sudah {idx} akun) session Google di-reset (CLEAR_EACH).\n")
                    elif idx % 10 == 0:
                        clear_google_sessions(context)
                        print(f"[*] (sudah {idx} akun) session Google di-reset.\n")
                print(f"\n=== Akun {idx}/{len(accounts)}: {email} ===")

                # 2a. Ke halaman provider
                print("[*] Buka halaman provider...")
                page.goto(TARGET_URL, wait_until="domcontentloaded")
                time.sleep(2)

                # 2b. Klik Add
                print("[*] Klik Add...")
                page.click(SEL_ADD_BTN)
                time.sleep(1)

                # 2c. Modal -> I Understand, Continue (buka tab baru)
                # Tunggu maks 5 dtk; kalau tidak muncul, halaman mungkin auto-redirect.
                print("[*] Cari 'I Understand, Continue' (maks 5 dtk)...")
                popup = None
                try:
                    page.wait_for_selector(SEL_CONTINUE_BTN, timeout=5000)
                    with page.expect_popup() as popup_info:
                        page.click(SEL_CONTINUE_BTN)
                    popup = popup_info.value
                except Exception:
                    print("[*] Tombol tidak muncul 5 dtk -> cek popup/redirect...")
                    # Coba ambil tab baru yang mungkin sudah terbuka
                    opened = [p for p in context.pages if p != page]
                    if opened:
                        popup = opened[-1]
                    else:
                        # Halaman mungkin reload/redirect -> ulangi alur Add
                        page.goto(TARGET_URL, wait_until="domcontentloaded")
                        time.sleep(2)
                        page.click(SEL_ADD_BTN)
                        time.sleep(1)
                        page.wait_for_selector(SEL_CONTINUE_BTN, timeout=5000)
                        with page.expect_popup() as popup_info:
                            page.click(SEL_CONTINUE_BTN)
                        popup = popup_info.value

                if popup is None:
                    print("[!] Gagal membuka tab Google, lewati akun ini.")
                    move_account(email, gpw, "FAILED", "Gagal membuka tab Google OAuth")
                    continue
                popup.wait_for_load_state("domcontentloaded", timeout=15000)

                # 2c2. Cek & klik "Use another account" hanya jika BUKAN mode restart browser
                if not RESTART_BROWSER_PER_ACCOUNT:
                    try:
                        # tunggu popup benar2 load (accountchooser sering lambat)
                        try:
                            popup.wait_for_load_state("domcontentloaded", timeout=5000)
                        except Exception:
                            pass
                        time.sleep(1)
                        # cek URL apakah di accountchooser -> wajib klik Use another
                        try:
                            cur = popup.url
                            if "accountchooser" in cur:
                                print(f"[*] Di halaman accountchooser: {cur[:100]}... -> cari 'Use another account'")
                        except Exception:
                            pass
                        found_use_another = False
                        # coba selector paling generic dulu: text=Use another account
                        generic_selectors = [
                            SEL_USE_ANOTHER,
                            'text=Use another account',
                            'div:has-text("Use another account")',
                            'a:has-text("Use another account")',
                            'span:has-text("Use another account")',
                            'button:has-text("Use another account")',
                            '*:has-text("Use another account")',
                        ]
                        for sel in generic_selectors:
                            try:
                                loc = popup.locator(sel)
                                cnt = loc.count()
                                if cnt > 0:
                                    # tunggu visible 5 dtk
                                    try:
                                        # untuk text= selector, wait_for_selector butuh syntax berbeda
                                        if sel.startswith("text="):
                                            loc.first.wait_for(state="visible", timeout=5000)
                                        else:
                                            popup.wait_for_selector(sel, timeout=5000)
                                        print(f"[*] Ada akun sebelumnya -> klik 'Use another account' ({sel} cnt={cnt})")
                                        loc.first.click(timeout=5000)
                                        found_use_another = True
                                        time.sleep(3)
                                        break
                                    except Exception as e:
                                        print(f"[*] Gagal klik {sel}: {e}")
                                        pass
                            except Exception:
                                pass
                        if not found_use_another:
                            # fallback: coba get_by_text via evaluate
                            try:
                                # cek apakah ada elemen dengan text tersebut via JS
                                has_text = popup.evaluate("() => document.body.innerText.includes('Use another account')")
                                if has_text:
                                    print("[*] Body mengandung 'Use another account' tapi selector tidak ketemu, coba click via JS")
                                    popup.evaluate("() => { const els=[...document.querySelectorAll('*')]; const el=els.find(e=>e.innerText&&e.innerText.includes('Use another account')); if(el){el.click(); return true} return false }")
                                    time.sleep(2)
                                    found_use_another = True
                            except Exception:
                                pass
                        if not found_use_another:
                            print("[*] Tidak ada 'Use another account', lanjut isi email.")
                        else:
                            print("[*] Klik 'Use another account' berhasil")
                    except Exception as e:
                        print(f"[*] Error cek 'Use another account': {e}, lanjut isi email.")

                # 2d. Isi email Google (robust: tunggu 15s, fill, klik Next dengan beberapa selector)
                print("[*] Isi email Google...")
                try:
                    popup.wait_for_selector(SEL_GOOGLE_EMAIL, timeout=15000)
                    print("[*] Input email ditemukan")
                except Exception:
                    print("[!] Input email tidak ditemukan dalam 15s, coba cek URL popup:", popup.url if not popup.is_closed() else "closed")
                try:
                    popup.fill(SEL_GOOGLE_EMAIL, email, timeout=10000)
                    print(f"[*] Email diisi: {email}")
                except Exception as e:
                    print(f"[!] Gagal isi email: {e}")
                    # coba via locator
                    try:
                        popup.locator(SEL_GOOGLE_EMAIL).fill(email, timeout=5000)
                        print("[*] Email diisi via locator")
                    except Exception as e2:
                        print(f"[!] Gagal isi email via locator: {e2}")
                # klik Next dengan beberapa selector fallback
                next_clicked = False
                for sel in [SEL_GOOGLE_NEXT, '#identifierNext', 'button:has-text("Next")', 'div[role="button"]:has-text("Next")']:
                    try:
                        loc = popup.locator(sel)
                        if loc.count() > 0:
                            if loc.first.is_enabled(timeout=2000):
                                print(f"[*] Klik Next via {sel}")
                                loc.first.click(timeout=5000)
                                next_clicked = True
                                break
                    except Exception:
                        try:
                            popup.click(sel, timeout=3000)
                            next_clicked = True
                            print(f"[*] Klik Next via click({sel})")
                            break
                        except Exception:
                            pass
                if not next_clicked:
                    print("[!] Next tidak terklik via selector, coba click generic")
                    try:
                        popup.click(SEL_GOOGLE_NEXT, timeout=5000)
                        next_clicked = True
                    except Exception as e:
                        print(f"[!] Gagal klik Next: {e}")
                time.sleep(3)

                # 2e. Isi password (robust)
                print("[*] Isi password Google...")
                try:
                    # tunggu input password muncul (hingga 15s), jika tidak muncul mungkin sudah di halaman lain
                    try:
                        popup.wait_for_selector(SEL_GOOGLE_PASS, timeout=15000)
                        print("[*] Input password ditemukan")
                        popup.fill(SEL_GOOGLE_PASS, gpw, timeout=10000)
                        print("[*] Password diisi")
                    except Exception as e:
                        print(f"[!] Input password tidak ditemukan / gagal isi: {e}, cek URL: {popup.url if not popup.is_closed() else 'closed'}")
                        # coba pakai selector alternatif
                        for alt in ['input[type="password"]', 'input[name="password"]', '#password']:
                            try:
                                if popup.locator(alt).count() > 0:
                                    popup.locator(alt).fill(gpw, timeout=3000)
                                    print(f"[*] Password diisi via {alt}")
                                    break
                            except Exception:
                                pass
                    # klik Next setelah password
                    pw_next_clicked = False
                    for sel in [SEL_GOOGLE_NEXT, '#passwordNext', 'button:has-text("Next")']:
                        try:
                            loc = popup.locator(sel)
                            if loc.count() > 0 and loc.first.is_enabled(timeout=2000):
                                print(f"[*] Klik Next password via {sel}")
                                loc.first.click(timeout=5000)
                                pw_next_clicked = True
                                break
                        except Exception:
                            pass
                    if not pw_next_clicked:
                        try:
                            popup.click(SEL_GOOGLE_NEXT, timeout=5000)
                            pw_next_clicked = True
                        except Exception as e:
                            print(f"[!] Gagal klik Next password: {e}")
                except Exception as e:
                    print(f"[*] Gagal isi password (mungkin navigasi terjadi): {e}")
                time.sleep(5)

                # 2f. Opsional: "Don't get locked out" -> Do this later (aman dari error)
                try:
                    if popup.locator(SEL_LOCKED_OUT).count() > 0:
                        print("[*] Terdeteksi 'Don't get locked out' -> klik Do this later")
                        popup.click(SEL_DO_LATER)
                        time.sleep(3)
                except Exception:
                    pass

                # 2f2. Opsional: "Welcome to your new account" -> I understand
                try:
                    popup.wait_for_selector(SEL_I_UNDERSTAND, timeout=8000)
                    print("[*] 'Welcome to your new account' -> klik 'I understand'")
                    popup.click(SEL_I_UNDERSTAND)
                    time.sleep(3)
                except Exception:
                    pass

                # 2g. Auto-klik tombol konfirmasi
                LAST_REWRITE["url"] = None
                print("[*] Menunggu & auto-klik tombol konfirmasi (Login/Sign in/Continue/Allow) hingga callback...")
                start_wait = time.time()
                while time.time() - start_wait < 40:
                    if LAST_REWRITE["url"]:
                        print(f"[*] Callback terdeteksi via rewrite")
                        break
                    try:
                        if popup.is_closed():
                            break
                    except Exception:
                        pass

                    # ==============================================================================
                    # PENTING / JANGAN DIUBAH: Penanganan konfirmasi layar persetujuan & speedbump Google
                    # ==============================================================================
                    try:
                        login_candidates = [
                            'button:has-text("Login")',
                            'span.VfPpkd-vQzf8d:has-text("Login")',
                            'button:has-text("Sign in")',
                            'button:has-text("I understand")',
                            'button:has-text("Saya mengerti")',
                            'button:has-text("Understand")',
                            'button:has-text("Accept")',
                            'button:has-text("Setuju")',
                            'button:has-text("Agree")',
                            'button:has-text("Lanjutkan")',
                            'button:has-text("Izinkan")',
                            'button:has-text("Allow")',
                            'button:has-text("Continue")',
                            '#submit_approve_access',
                            '#confirm',
                            'input[type="submit"]',
                        ]
                        for b_sel in login_candidates:
                            loc = popup.locator(b_sel)
                            if loc.count() > 0 and loc.first.is_visible(timeout=800):
                                print(f"[*] Tombol persetujuan ('{b_sel}') terdeteksi -> klik otomatis")
                                loc.first.click(timeout=3000)
                                time.sleep(2)
                                break
                        # Scroll bawah jika ada speedbump termsofservice
                        if "speedbump" in popup.url or "termsofservice" in popup.url:
                            popup.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    except Exception:
                        pass
                    # ==============================================================================

                    time.sleep(1)
                    try:
                        if popup.is_closed():
                            break
                    except Exception:
                        pass

                # 2h. Tunggu callback OAuth selesai - JANGAN langsung close, beri waktu load IP
                # Tunggu hingga LAST_REWRITE terisi atau timeout 60 dtk
                print("[*] Menunggu callback localhost -> IP selesai...")
                cb_start = time.time()
                while time.time() - cb_start < 60:
                    if LAST_REWRITE["url"]:
                        break
                    try:
                        if popup.is_closed():
                            break
                    except Exception:
                        pass
                    time.sleep(1)

                if LAST_REWRITE["url"]:
                    print(f"[*] Menavigasikan tab popup ke callback server IP...")
                    # Langsung catat sukses & pindahkan akun seketika tanpa menunggu timer selesai
                    move_account(email, gpw, "SUCCESS")
                    print(f"[✓] PROSES AKUN SUKSES: {email} -> langsung dicatat & dipindahkan.")
                
                    try:
                        if not popup.is_closed():
                            popup.goto(LAST_REWRITE["url"], wait_until="domcontentloaded", timeout=15000)
                            print("[*] Navigasi ke callback IP selesai.")
                    except Exception as e:
                        print(f"[*] Info navigasi popup: {e}")

                    print("[*] Tunggu 5 detik agar server 9Router menyelesaikan impor akun...")
                    time.sleep(5)
                    try:
                        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=10000)
                        time.sleep(2)
                    except Exception as e:
                        pass
                    # Menunggu tab close sendiri atau beri waktu tambahan
                    try:
                        if not popup.is_closed():
                            print("[*] Menunggu tab ditutup secara otomatis oleh sistem...")
                            popup.wait_for_event("close", timeout=15000)
                            print("[*] Tab ditutup otomatis.")
                        else:
                            print("[*] Tab sudah ditutup secara otomatis.")
                    except Exception:
                        try:
                            if not popup.is_closed():
                                popup.close()
                        except Exception:
                            pass
                else:
                    print(f"[!] Callback tidak terdeteksi (Timeout)")
                    try:
                        if not popup.is_closed():
                            popup.close()
                    except Exception:
                        pass
                    move_account(email, gpw, "FAILED", "Callback OAuth tidak terdeteksi (Timeout)")
                    print(f"[✗] PROSES AKUN GAGAL: {email} -> dipindahkan ke failed_accounts.txt")

            except Exception as e_account:
                print(f"[!] Error saat memproses akun {email}: {e_account}")
                move_account(email, gpw, "FAILED", str(e_account)[:100])
                print(f"[*] Melanjutkan ke akun berikutnya...")

            finally:
                if RESTART_BROWSER_PER_ACCOUNT:
                    print(f"[*] Tutup browser/context setelah selesai akun {idx}...")
                    try:
                        context.close()
                    except Exception:
                        pass
                print("[*] Jeda 5 detik sebelum lanjut akun berikutnya...")
                time.sleep(5)

        print("\n[*] Semua akun selesai diproses. Biarkan terbuka 15 detik.")
        time.sleep(15)
        context.close()


if __name__ == "__main__":
    run()
