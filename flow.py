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
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from playwright.sync_api import sync_playwright

# ---- Konfigurasi ----
LOGIN_URL = os.getenv("LOGIN_URL", "http://localhost:20128/login")
TARGET_URL = os.getenv("TARGET_URL", "http://localhost:20128/dashboard/providers/antigravity")
PASSWORD = os.getenv("DASH_PASSWORD", "")
PROFILE = os.getenv("USER_DATA_DIR", "./browser_profile")
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
ACCOUNTS_FILE = os.getenv("ACCOUNTS_FILE", "accounts.txt")
# Kalau "true", hapus folder profil agar benar-benar fresh (akun Google lama hilang)
RESET_PROFILE = os.getenv("RESET_PROFILE", "false").lower() == "true"
# Jika true, tiap akun restart browser (fresh) agar account chooser tidak muncul - solusi VPS
RESTART_BROWSER_PER_ACCOUNT = os.getenv("RESTART_BROWSER_PER_ACCOUNT", "false").lower() == "true"
# Jika true, bersihkan cookie Google tiap akun (agar chooser kosong)
CLEAR_EACH = os.getenv("CLEAR_EACH", "true").lower() == "true"

# OAuth callback Google mengarah ke localhost, kita rewrite ke IP server
REDIRECT_FROM = os.getenv("REDIRECT_FROM", "http://localhost:20128")
REDIRECT_TO = os.getenv("REDIRECT_TO", "http://38.47.85.35:20128")

# File log semua URL (terutama callback localhost / IP server), 1 URL per baris
URL_LOG_FILE = os.getenv("URL_LOG_FILE", "urls.txt")

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
    """Baca file teks baris: gmail|password"""
    accounts = []
    if not os.path.exists(path):
        print(f"[!] File akun tidak ada: {path}")
        return accounts
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                email, pw = line.split("|", 1)
                accounts.append((email.strip(), pw.strip()))
    print(f"[*] Total akun dibaca: {len(accounts)}")
    return accounts


def log_url(url: str):
    """Simpan URL ke file log (1 baris per URL). Aman dari duplikat berurutan."""
    if not url:
        return
    try:
        if os.path.exists(URL_LOG_FILE):
            with open(URL_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            if lines and lines[-1] == url:
                return
    except Exception:
        pass
    try:
        with open(URL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(url + "\n")
        print(f"[*] Log URL: {url}")
    except Exception as e:
        print(f"[!] Gagal tulis log URL: {e}")


def _rewrite_redirect(route):
    """Bila browser mencoba melakukan navigasi ke localhost, cegah koneksi langsung
    dan alihkan (redirect) langsung ke IP host server."""
    url = route.request.url
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url)
    if parsed.hostname == "localhost":
        ip_host = REDIRECT_TO.split("://", 1)[-1].split(":", 1)[0]
        port = f":{parsed.port}" if parsed.port else ""
        new_netloc = ip_host + port
        new_url = urlunparse(parsed._replace(netloc=new_netloc))
        is_real_callback = ("/callback?" in url and "code=" in url) or ("/callback" in url and "code=" in url and "state=" in url)
        if is_real_callback:
            LAST_REWRITE["url"] = new_url
            log_url(url)
            log_url(new_url)
            print(f"[*] Callback localhost terdeteksi ({url}) -> langsung redirect ke IP ({new_url})")
            route.fulfill(status=302, headers={"Location": new_url})
            return
        route.continue_(url=new_url)
    else:
        try:
            ip_host_dyn = REDIRECT_TO.split("://", 1)[-1].split(":", 1)[0]
        except Exception:
            ip_host_dyn = "38.47.85.35"
        if ("/callback" in url or "code=" in url) and (ip_host_dyn in url or "38.47.85.35" in url or "43.133.41.179" in url):
            log_url(url)
        route.continue_()


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
            # Reset session Google tiap akun (jika CLEAR_EACH=true) agar account chooser kosong
            # atau restart browser per akun jika RESTART_BROWSER_PER_ACCOUNT=true
            if idx > 1:
                if RESTART_BROWSER_PER_ACCOUNT:
                    print(f"[*] Membuat context/browser baru sebelum akun {idx}...")
                    for sub in ("Cache", "Code Cache", "GPUCache"):
                        cache_path = os.path.join(PROFILE, sub)
                        if os.path.isdir(cache_path):
                            shutil.rmtree(cache_path, ignore_errors=True)
                    context = p.chromium.launch_persistent_context(
                        PROFILE, headless=HEADLESS,
                        args=["--disable-blink-features=AutomationControlled"])
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
                continue
            popup.wait_for_load_state("domcontentloaded", timeout=15000)

            # 2c2. Cek & klik "Use another account" jika ada akun sebelumnya (lebih robust untuk accountchooser v3)
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
                        try:
                            # pastikan tombol enabled/visible
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

            # 2g. Auto-klik "Sign in" / "Login" / "Continue" / "Allow" - loop hingga callback atau timeout
            # reset rewrite untuk akun ini agar tidak pakai sisa akun sebelumnya
            LAST_REWRITE["url"] = None
            print("[*] Menunggu & auto-klik tombol konfirmasi (Sign in/Login/Continue/Allow) hingga callback...")
            start_wait = time.time()
            clicked_any = False
            while time.time() - start_wait < 40:
                # jika callback sudah ter-detect, break langsung ke handling callback
                if LAST_REWRITE["url"]:
                    print(f"[*] Callback terdeteksi via rewrite: {LAST_REWRITE['url']}")
                    break
                try:
                    cur_url = popup.url if not popup.is_closed() else ""
                    if "callback" in cur_url or "localhost:20128" in cur_url or "38.47.85.35:20128/callback" in cur_url:
                        print(f"[*] URL popup sudah callback: {cur_url}")
                        break
                except Exception:
                    pass
                # daftar selector yang mungkin muncul - klik jika ada
                handled = False
                for sel, name in [
                    (SEL_GOOGLE_SIGNIN, "Sign in"),
                    (SEL_GOOGLE_SIGNIN_VARIANTS, "Login/Sign in variant"),
                    ('button:has-text("Continue")', "Continue"),
                    ('button:has-text("Allow")', "Allow"),
                    ('button:has-text("Confirm")', "Confirm"),
                    ('button:has-text("I understand")', "I understand"),
                    (SEL_LOGIN_BTN, "Login"),
                ]:
                    try:
                        loc = popup.locator(sel)
                        if loc.count() > 0:
                            # cek visible pertama
                            try:
                                first = loc.first
                                if first.is_visible(timeout=1000):
                                    print(f"[*] Tombol '{name}' ({sel}) terdeteksi -> klik otomatis")
                                    try:
                                        first.click(timeout=3000)
                                    except Exception:
                                        try:
                                            popup.click(sel, timeout=3000)
                                        except Exception:
                                            pass
                                    clicked_any = True
                                    handled = True
                                    time.sleep(2)
                                    break
                            except Exception:
                                pass
                    except Exception:
                        pass
                if handled:
                    continue
                # jika tidak ada tombol, tunggu sebentar lalu cek lagi
                time.sleep(1)
                # juga cek jika popup sudah tertutup sendiri
                try:
                    if popup.is_closed():
                        print("[*] Popup sudah tertutup")
                        break
                except Exception:
                    pass
            if not LAST_REWRITE["url"]:
                # coba sekali lagi deteksi Sign in secara eksplisit (fallback lama)
                try:
                    popup.wait_for_selector(SEL_GOOGLE_SIGNIN, timeout=3000)
                    print("[*] 'Sign in' muncul (fallback) -> klik otomatis")
                    try:
                        popup.click(SEL_GOOGLE_SIGNIN, timeout=3000)
                    except Exception:
                        popup.locator(SEL_GOOGLE_SIGNIN).first.click(timeout=3000)
                    time.sleep(3)
                except Exception:
                    if not clicked_any:
                        print("[*] Tidak ada tombol konfirmasi terdeteksi dalam 40 dtk, lanjut cek callback")

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
                    cur = popup.url
                    if "callback" in cur:
                        print(f"[*] Popup URL callback: {cur}")
                        break
                except Exception:
                    pass
                time.sleep(1)

            if LAST_REWRITE["url"]:
                print(f"[*] Callback IP berhasil diproses: {LAST_REWRITE['url']}")
                print("[*] Tunggu 5 detik agar server 9Router menyelesaikan impor akun...")
                time.sleep(5)
                try:
                    print("[*] Navigasi ke halaman provider dashboard untuk mengecek status...")
                    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=10000)
                    time.sleep(3)
                except Exception as e:
                    print(f"[!] Goto dashboard provider gagal: {e}")
                # Menunggu tab close sendiri atau beri waktu tambahan
                try:
                    if not popup.is_closed():
                        print("[*] Menunggu tab ditutup secara otomatis oleh sistem (30 detik max)...")
                        popup.wait_for_event("close", timeout=30000)
                        print("[*] Tab ditutup otomatis.")
                    else:
                        print("[*] Tab sudah ditutup secara otomatis.")
                except Exception:
                    print("[*] Tab tidak ditutup otomatis, biarkan tetap terbuka tanpa dipaksa close.")
            else:
                print("[!] Callback tidak terdeteksi dalam 60 dtk (LAST_REWRITE kosong)")
                print(f"[*] URL popup terakhir: {popup.url if not popup.is_closed() else 'closed'}")
                # fallback: tunggu close lama seperti sebelumnya
                try:
                    popup.wait_for_event("close", timeout=30000)
                    print("[*] Tab ditutup (fallback).")
                except Exception:
                    print("[*] Timeout fallback, lanjut akun berikutnya.")
                    try:
                        if not popup.is_closed():
                            popup.close()
                    except Exception:
                        pass

            if RESTART_BROWSER_PER_ACCOUNT:
                print(f"[*] Tutup browser/context setelah selesai akun {idx}...")
                try:
                    context.close()
                except Exception:
                    pass

            time.sleep(2)

        print("\n[*] Semua akun selesai diproses. Biarkan terbuka 15 detik.")
        time.sleep(15)
        context.close()


if __name__ == "__main__":
    run()
