"""
Flask UI untuk Antigravity Auto
- Config IP:PORT via .env (LOGIN_URL, TARGET_URL, REDIRECT_TO, dll)
- Start/Stop flow.py + tampilkan log real-time
- Edit accounts.txt & lihat urls.txt
"""
import os
import sys
import time
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from flask import Flask, render_template, request, jsonify
except ImportError:
    print("[!] Flask belum terinstall. Jalankan: pip install -r requirements.txt")
    sys.exit(1)

try:
    from dotenv import dotenv_values, set_key, load_dotenv
except ImportError:
    dotenv_values = None

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"
ACCOUNTS_FILE_DEFAULT = "accounts.txt"
URLS_FILE_DEFAULT = "urls.txt"
LOG_FILE = BASE_DIR / "flow.log"

# Load env for Flask port/host
if ENV_FILE.exists() and dotenv_values:
    _vals = dotenv_values(ENV_FILE)
    FLASK_HOST = _vals.get("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(_vals.get("FLASK_PORT", "5000"))
else:
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

app = Flask(__name__)

# Global state
proc = None
proc_lock = threading.Lock()
log_lines = []
log_lock = threading.Lock()
MAX_LOG_LINES = 2000

def detect_python():
    # prioritas: .venv
    win_py = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    nix_py = BASE_DIR / ".venv" / "bin" / "python"
    if win_py.exists():
        return str(win_py)
    if nix_py.exists():
        return str(nix_py)
    return sys.executable

def read_env_config():
    cfg = {}
    # default dari .env.example / flow.py
    defaults = {
        "LOGIN_URL": "http://38.47.85.35:20128/login",
        "TARGET_URL": "http://38.47.85.35:20128/dashboard/providers/antigravity",
        "DASH_PASSWORD": "Masuk123321",
        "REDIRECT_FROM": "http://localhost:20128",
        "REDIRECT_TO": "http://38.47.85.35:20128",
        "HEADLESS": "false",
        "RESET_PROFILE": "false",
        "CLEAR_EACH": "true",
        "RESTART_BROWSER_PER_ACCOUNT": "false",
        "ACCOUNTS_FILE": "accounts.txt",
        "URL_LOG_FILE": "urls.txt",
        "USER_DATA_DIR": "./browser_profile",
        "FLASK_HOST": FLASK_HOST,
        "FLASK_PORT": str(FLASK_PORT),
    }
    if ENV_FILE.exists() and dotenv_values:
        vals = dotenv_values(ENV_FILE)
        for k, v in defaults.items():
            cfg[k] = vals.get(k, v if v is not None else "")
    else:
        for k, v in defaults.items():
            cfg[k] = os.getenv(k, v)
    # tambahkan info IP:PORT terpisah untuk UI
    # extract ip:port dari REDIRECT_TO
    try:
        from urllib.parse import urlparse
        parsed = urlparse(cfg.get("REDIRECT_TO", ""))
        cfg["_IP"] = parsed.hostname or ""
        cfg["_PORT"] = str(parsed.port or "")
        cfg["_IP_PORT"] = f"{cfg['_IP']}:{cfg['_PORT']}" if cfg["_PORT"] else cfg["_IP"]
    except:
        cfg["_IP"] = ""
        cfg["_PORT"] = ""
        cfg["_IP_PORT"] = ""
    return cfg

def write_env_config(updates: dict):
    # updates: dict key->value, tulis ke .env via set_key atau manual
    if not ENV_FILE.exists():
        ENV_FILE.touch()
    for k, v in updates.items():
        # set_key dari python-dotenv
        try:
            if dotenv_values:
                set_key(str(ENV_FILE), k, str(v))
            else:
                raise Exception("no dotenv")
        except Exception:
            # fallback manual: baca, update, tulis
            lines = []
            found = False
            if ENV_FILE.exists():
                with open(ENV_FILE, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
            new_lines = []
            for line in lines:
                if line.strip().startswith(f"{k}="):
                    new_lines.append(f"{k}={v}")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"{k}={v}")
            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
    return True

def append_log(line: str):
    with log_lock:
        log_lines.append(line.rstrip("\n"))
        if len(log_lines) > MAX_LOG_LINES:
            del log_lines[: len(log_lines) - MAX_LOG_LINES]
    # juga tulis ke flow.log
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
            if not line.endswith("\n"):
                f.write("\n")
    except:
        pass

def clear_log():
    with log_lock:
        log_lines.clear()
    try:
        if LOG_FILE.exists():
            LOG_FILE.write_text("", encoding="utf-8")
    except:
        pass

def reader_thread(p):
    # baca stdout line by line
    try:
        for line in iter(p.stdout.readline, ""):
            if line == "":
                break
            append_log(line)
            # juga cek stderr via poll? stdout sudah merge stderr via STDERR
        # jika masih ada sisa
        try:
            remaining = p.stdout.read()
            if remaining:
                for l in remaining.splitlines():
                    append_log(l + "\n")
        except:
            pass
    except Exception as e:
        append_log(f"[!] reader error: {e}\n")
    finally:
        try:
            p.stdout.close()
        except:
            pass
        append_log(f"\n[*] Proses selesai exit code={p.poll()}\n")

def is_running():
    global proc
    with proc_lock:
        return proc is not None and proc.poll() is None

@app.route("/")
def index():
    cfg = read_env_config()
    # hitung akun
    acc_path = BASE_DIR / cfg.get("ACCOUNTS_FILE", "accounts.txt")
    acc_count = 0
    acc_preview = ""
    if acc_path.exists():
        try:
            txt = acc_path.read_text(encoding="utf-8")
            lines = [l.strip() for l in txt.splitlines() if l.strip() and not l.strip().startswith("#")]
            acc_count = len(lines)
            acc_preview = "\n".join(lines[:5])
            if len(lines) > 5:
                acc_preview += f"\n... +{len(lines)-5} lagi"
        except:
            pass
    return render_template("index.html", cfg=cfg, acc_count=acc_count, acc_preview=acc_preview)

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        cfg = read_env_config()
        # juga baca accounts & urls
        acc_file = BASE_DIR / cfg.get("ACCOUNTS_FILE", "accounts.txt")
        urls_file = BASE_DIR / cfg.get("URL_LOG_FILE", "urls.txt")
        acc_content = ""
        urls_content = ""
        if acc_file.exists():
            try:
                acc_content = acc_file.read_text(encoding="utf-8")
            except:
                pass
        if urls_file.exists():
            try:
                urls_content = urls_file.read_text(encoding="utf-8")
            except:
                pass
        return jsonify({"config": cfg, "accounts": acc_content, "urls": urls_content})
    else:
        data = request.get_json(force=True, silent=True) or {}
        # data bisa {LOGIN_URL:..., TARGET_URL:..., REDIRECT_TO:...} atau {ip:..., port:...}
        updates = {}
        # jika ada _IP dan _PORT terpisah, rakit REDIRECT_TO dan URL lain
        if "_IP" in data or "_PORT" in data:
            cfg = read_env_config()
            ip = data.get("_IP", cfg.get("_IP", "38.47.85.35")).strip()
            port = str(data.get("_PORT", cfg.get("_PORT", "20128"))).strip()
            # validasi
            if not ip:
                return jsonify({"error": "IP tidak boleh kosong"}), 400
            if not port.isdigit():
                return jsonify({"error": "PORT harus angka"}), 400
            ip_port = f"{ip}:{port}"
            base = f"http://{ip_port}"
            updates["REDIRECT_TO"] = base
            updates["REDIRECT_FROM"] = "http://localhost:20128"  # tetap localhost
            updates["LOGIN_URL"] = f"{base}/login"
            updates["TARGET_URL"] = f"{base}/dashboard/providers/antigravity"
            # juga update config lain jika ada di data
            for k in ["DASH_PASSWORD", "HEADLESS", "RESET_PROFILE", "CLEAR_EACH", "RESTART_BROWSER_PER_ACCOUNT", "FLASK_PORT", "FLASK_HOST"]:
                if k in data:
                    updates[k] = str(data[k])
        else:
            # langsung update key yang dikirim
            allowed = ["LOGIN_URL","TARGET_URL","DASH_PASSWORD","REDIRECT_FROM","REDIRECT_TO","HEADLESS","RESET_PROFILE","CLEAR_EACH","RESTART_BROWSER_PER_ACCOUNT","ACCOUNTS_FILE","URL_LOG_FILE","USER_DATA_DIR","FLASK_PORT","FLASK_HOST"]
            for k in allowed:
                if k in data:
                    updates[k] = str(data[k])
        if not updates:
            return jsonify({"error": "tidak ada config yang diupdate"}), 400
        write_env_config(updates)
        # jika ada IP_PORT, juga kembalikan config baru
        cfg = read_env_config()
        return jsonify({"ok": True, "config": cfg, "updated": updates})

@app.route("/api/start", methods=["POST"])
def api_start():
    global proc
    data = request.get_json(silent=True) or {}
    with proc_lock:
        if proc is not None and proc.poll() is None:
            return jsonify({"error": "sudah berjalan", "pid": proc.pid}), 400
        py = detect_python()
        # pastikan flow.py ada
        flow = BASE_DIR / "flow.py"
        if not flow.exists():
            return jsonify({"error": "flow.py tidak ditemukan"}), 500
        # siapkan env untuk subprocess: load .env + override dari request jika ada
        env = os.environ.copy()
        # load .env ke env
        if ENV_FILE.exists() and dotenv_values:
            vals = dotenv_values(ENV_FILE)
            for k, v in vals.items():
                if v is not None:
                    env[k] = str(v)
        # override dari data jika ada (misal HEADLESS)
        for k in ["HEADLESS","RESET_PROFILE","CLEAR_EACH","RESTART_BROWSER_PER_ACCOUNT","ACCOUNTS_FILE","LOGIN_URL","TARGET_URL","REDIRECT_TO"]:
            if k in data and data[k] is not None:
                env[k] = str(data[k])
        env["PYTHONUNBUFFERED"] = "1"
        # clear log sebelum start jika diminta
        if data.get("clear_log"):
            clear_log()
        else:
            append_log(f"\n=== START {datetime.now().isoformat()} ===\n")
            append_log(f"[*] python: {py}\n")
            append_log(f"[*] env HEADLESS={env.get('HEADLESS')} RESET_PROFILE={env.get('RESET_PROFILE')} CLEAR_EACH={env.get('CLEAR_EACH')}\n")
        # jalankan flow.py
        try:
            # gunakan Popen dengan stdout piped, stderr merged
            proc = subprocess.Popen(
                [py, "flow.py"],
                cwd=str(BASE_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
            # start reader thread
            t = threading.Thread(target=reader_thread, args=(proc,), daemon=True)
            t.start()
            return jsonify({"ok": True, "pid": proc.pid, "python": py})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/stop", methods=["POST"])
def api_stop():
    global proc
    with proc_lock:
        if proc is None or proc.poll() is not None:
            return jsonify({"error": "tidak ada proses berjalan"}), 400
        try:
            # coba terminate gracefully
            proc.terminate()
            # tunggu 3 detik
            for _ in range(30):
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
            if proc.poll() is None:
                proc.kill()
            append_log(f"\n[*] Proses dihentikan (pid={proc.pid})\n")
            return jsonify({"ok": True, "pid": proc.pid})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/logs", methods=["GET"])
def api_logs():
    with log_lock:
        lines = list(log_lines)
    # query param ?tail=100
    try:
        tail = int(request.args.get("tail", "500"))
        if tail > 0:
            lines = lines[-tail:]
    except:
        pass
    # juga baca urls.txt dan flow.log file info
    cfg = read_env_config()
    urls_path = BASE_DIR / cfg.get("URL_LOG_FILE", "urls.txt")
    urls_count = 0
    urls_tail = []
    if urls_path.exists():
        try:
            txt = urls_path.read_text(encoding="utf-8").splitlines()
            urls_count = len([l for l in txt if l.strip()])
            urls_tail = txt[-10:]
        except:
            pass
    return jsonify({
        "running": is_running(),
        "pid": proc.pid if proc and proc.poll() is None else None,
        "logs": lines,
        "log_count": len(log_lines),
        "urls_count": urls_count,
        "urls_tail": urls_tail,
        "log_file_exists": LOG_FILE.exists(),
    })

@app.route("/api/clear_logs", methods=["POST"])
def api_clear_logs():
    clear_log()
    return jsonify({"ok": True})

@app.route("/api/status", methods=["GET"])
def api_status():
    cfg = read_env_config()
    acc_path = BASE_DIR / cfg.get("ACCOUNTS_FILE", "accounts.txt")
    acc_count = 0
    if acc_path.exists():
        try:
            txt = acc_path.read_text(encoding="utf-8").splitlines()
            acc_count = len([l for l in txt if l.strip() and not l.strip().startswith("#")])
        except:
            pass
    return jsonify({
        "running": is_running(),
        "pid": proc.pid if proc and is_running() else None,
        "config": cfg,
        "accounts_count": acc_count,
        "log_lines": len(log_lines),
    })

@app.route("/api/accounts", methods=["GET", "POST"])
def api_accounts():
    cfg = read_env_config()
    acc_path = BASE_DIR / cfg.get("ACCOUNTS_FILE", "accounts.txt")
    if request.method == "GET":
        content = ""
        if acc_path.exists():
            content = acc_path.read_text(encoding="utf-8")
        return jsonify({"content": content})
    else:
        data = request.get_json(force=True, silent=True) or {}
        content = data.get("content", "")
        # tulis
        acc_path.write_text(content, encoding="utf-8")
        return jsonify({"ok": True, "lines": len([l for l in content.splitlines() if l.strip()])})

if __name__ == "__main__":
    # buat templates folder jika belum ada
    print(f"[*] Antigravity UI di http://{FLASK_HOST}:{FLASK_PORT}")
    print(f"[*] IP:PORT tersimpan di {ENV_FILE} (REDIRECT_TO, LOGIN_URL, TARGET_URL)")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True)
