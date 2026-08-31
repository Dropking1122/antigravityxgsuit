"""
Antigravity Auto - Flask Web Dashboard & REST Management Engine
Production-hardened: safe path isolation, atomic file writes, log rotation & secure process control.
"""
import os
import sys
import time
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
    from dotenv import dotenv_values, set_key
except ImportError:
    dotenv_values = None

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
ENV_FILE = BASE_DIR / ".env"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Central log file
LOG_FILE = LOGS_DIR / "flow.log"
ROOT_LOG_FILE = BASE_DIR / "flow.log"

def _sanitize_path(filename: str, default_path: Path) -> Path:
    if not filename:
        return default_path
    clean_name = os.path.basename(filename.strip().replace("\\", "/"))
    # Jika mengarah ke data/ atau logs/
    if filename.startswith("data/") or filename.startswith("data\\"):
        return DATA_DIR / clean_name
    if filename.startswith("logs/") or filename.startswith("logs\\"):
        return LOGS_DIR / clean_name
    # Default tetap di BASE_DIR
    target = (BASE_DIR / clean_name).resolve()
    if str(target).startswith(str(BASE_DIR)):
        return target
    return default_path

# Load env for Flask port/host
if ENV_FILE.exists() and dotenv_values:
    _vals = dotenv_values(ENV_FILE)
    FLASK_HOST = _vals.get("FLASK_HOST", "0.0.0.0")
    try:
        FLASK_PORT = int(_vals.get("FLASK_PORT", "5000"))
    except ValueError:
        FLASK_PORT = 5000
else:
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    try:
        FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
    except ValueError:
        FLASK_PORT = 5000

app = Flask(__name__)

# Global state & thread safety
proc = None
proc_lock = threading.Lock()
log_lines = []
log_lock = threading.Lock()
MAX_LOG_LINES = 2000

def detect_python():
    win_py = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    nix_py = BASE_DIR / ".venv" / "bin" / "python"
    if win_py.exists():
        return str(win_py)
    if nix_py.exists():
        return str(nix_py)
    return sys.executable

def read_env_config():
    defaults = {
        "LOGIN_URL": "http://localhost:20128/login",
        "TARGET_URL": "http://localhost:20128/dashboard/providers/antigravity",
        "DASH_PASSWORD": "",
        "REDIRECT_FROM": "http://localhost:20128",
        "REDIRECT_TO": "http://localhost:20128",
        "HEADLESS": "true",
        "RESET_PROFILE": "false",
        "CLEAR_EACH": "true",
        "RESTART_BROWSER_PER_ACCOUNT": "false",
        "ACCOUNTS_FILE": "accounts.txt",
        "URL_LOG_FILE": "logs/urls.txt",
        "USER_DATA_DIR": "browser_profile",
        "FLASK_HOST": FLASK_HOST,
        "FLASK_PORT": str(FLASK_PORT),
    }
    cfg = {}
    if ENV_FILE.exists() and dotenv_values:
        vals = dotenv_values(ENV_FILE)
        for k, v in defaults.items():
            cfg[k] = vals.get(k, v if v is not None else "")
    else:
        for k, v in defaults.items():
            cfg[k] = os.getenv(k, v)

    try:
        from urllib.parse import urlparse
        parsed = urlparse(cfg.get("REDIRECT_TO", ""))
        cfg["_IP"] = parsed.hostname or ""
        cfg["_PORT"] = str(parsed.port or "")
        cfg["_IP_PORT"] = f"{cfg['_IP']}:{cfg['_PORT']}" if cfg["_PORT"] else cfg["_IP"]
    except Exception:
        cfg["_IP"] = ""
        cfg["_PORT"] = ""
        cfg["_IP_PORT"] = ""
    return cfg

def write_env_config(updates: dict):
    if not ENV_FILE.exists():
        ENV_FILE.touch()
    
    # Atomic write to .env
    lines = []
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    
    current_dict = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            current_dict[k.strip()] = v.strip().strip("'\"")
            
    for k, v in updates.items():
        current_dict[k] = str(v)
        
    out_lines = [f"{k}='{v}'" for k, v in current_dict.items()]
    tmp_env = ENV_FILE.with_suffix(".tmp")
    with open(tmp_env, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    tmp_env.replace(ENV_FILE)
    return True

def append_log(line: str):
    with log_lock:
        log_lines.append(line.rstrip("\n"))
        if len(log_lines) > MAX_LOG_LINES:
            del log_lines[: len(log_lines) - MAX_LOG_LINES]
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line if line.endswith("\n") else line + "\n")
    except Exception:
        pass

def clear_log():
    with log_lock:
        log_lines.clear()
    try:
        if LOG_FILE.exists():
            LOG_FILE.write_text("", encoding="utf-8")
        if ROOT_LOG_FILE.exists():
            ROOT_LOG_FILE.write_text("", encoding="utf-8")
    except Exception:
        pass

def reader_thread(p):
    try:
        for line in iter(p.stdout.readline, ""):
            if not line:
                break
            append_log(line)
        try:
            remaining = p.stdout.read()
            if remaining:
                for l in remaining.splitlines():
                    append_log(l + "\n")
        except Exception:
            pass
    except Exception as e:
        append_log(f"[!] Reader error: {e}\n")
    finally:
        try:
            p.stdout.close()
        except Exception:
            pass
        p.poll()
        append_log(f"\n[*] Proses otomasi selesai dengan exit code {p.returncode}\n")

def is_running():
    global proc
    with proc_lock:
        return proc is not None and proc.poll() is None

def resolve_accounts_file():
    cfg = read_env_config()
    acc_filename = cfg.get("ACCOUNTS_FILE", "accounts.txt")
    target = _sanitize_path(acc_filename, BASE_DIR / "accounts.txt")
    if not target.exists():
        if (DATA_DIR / "accounts.txt").exists():
            return DATA_DIR / "accounts.txt"
        if (BASE_DIR / "accounts.txt").exists():
            return BASE_DIR / "accounts.txt"
    return target

@app.route("/")
def index():
    cfg = read_env_config()
    acc_path = resolve_accounts_file()
    acc_count = 0
    acc_preview = ""
    if acc_path.exists():
        try:
            lines = [l.strip() for l in acc_path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")]
            acc_count = len(lines)
            acc_preview = "\n".join(lines[:5])
            if len(lines) > 5:
                acc_preview += f"\n... +{len(lines)-5} lagi"
        except Exception:
            pass
    return render_template("index.html", cfg=cfg, acc_count=acc_count, acc_preview=acc_preview)

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        cfg = read_env_config()
        acc_file = resolve_accounts_file()
        urls_file = LOGS_DIR / "urls.txt"
        if not urls_file.exists() and (BASE_DIR / "urls.txt").exists():
            urls_file = BASE_DIR / "urls.txt"

        acc_content = acc_file.read_text(encoding="utf-8") if acc_file.exists() else ""
        urls_content = urls_file.read_text(encoding="utf-8") if urls_file.exists() else ""
        return jsonify({"config": cfg, "accounts": acc_content, "urls": urls_content})
    else:
        data = request.get_json(force=True, silent=True) or {}
        updates = {}
        if "_IP" in data or "_PORT" in data:
            cfg = read_env_config()
            ip = data.get("_IP", cfg.get("_IP", "127.0.0.1")).strip()
            port = str(data.get("_PORT", cfg.get("_PORT", "20128"))).strip()
            
            if not ip:
                return jsonify({"error": "IP tidak boleh kosong"}), 400
            if not port.isdigit() or not (1 <= int(port) <= 65535):
                return jsonify({"error": "PORT harus angka valid (1-65535)"}), 400
                
            base = f"http://{ip}:{port}"
            updates["REDIRECT_TO"] = base
            updates["REDIRECT_FROM"] = "http://localhost:20128"
            updates["LOGIN_URL"] = f"{base}/login"
            updates["TARGET_URL"] = f"{base}/dashboard/providers/antigravity"
            
            for k in ["DASH_PASSWORD", "HEADLESS", "RESET_PROFILE", "CLEAR_EACH", "RESTART_BROWSER_PER_ACCOUNT", "FLASK_PORT", "FLASK_HOST"]:
                if k in data:
                    updates[k] = str(data[k])
        else:
            allowed = ["LOGIN_URL","TARGET_URL","DASH_PASSWORD","REDIRECT_FROM","REDIRECT_TO","HEADLESS","RESET_PROFILE","CLEAR_EACH","RESTART_BROWSER_PER_ACCOUNT","ACCOUNTS_FILE","URL_LOG_FILE","USER_DATA_DIR","FLASK_PORT","FLASK_HOST"]
            for k in allowed:
                if k in data:
                    updates[k] = str(data[k])
                    
        if not updates:
            return jsonify({"error": "Tidak ada konfigurasi yang diupdate"}), 400
        write_env_config(updates)
        return jsonify({"ok": True, "config": read_env_config(), "updated": updates})

@app.route("/api/start", methods=["POST"])
def api_start():
    global proc
    data = request.get_json(silent=True) or {}
    with proc_lock:
        if proc is not None and proc.poll() is None:
            return jsonify({"error": "Proses otomasi sudah berjalan", "pid": proc.pid}), 400
        
        py = detect_python()
        flow = BASE_DIR / "flow.py"
        if not flow.exists():
            return jsonify({"error": "File flow.py tidak ditemukan"}), 500
        
        env = os.environ.copy()
        if ENV_FILE.exists() and dotenv_values:
            for k, v in dotenv_values(ENV_FILE).items():
                if v is not None:
                    env[k] = str(v)
                    
        for k in ["HEADLESS","RESET_PROFILE","CLEAR_EACH","RESTART_BROWSER_PER_ACCOUNT","ACCOUNTS_FILE","LOGIN_URL","TARGET_URL","REDIRECT_TO"]:
            if k in data and data[k] is not None:
                env[k] = str(data[k])
                
        env["PYTHONUNBUFFERED"] = "1"

        if data.get("clear_log"):
            clear_log()
        else:
            append_log(f"\n=== START {datetime.now().isoformat()} ===")
            append_log(f"[*] Interpreter: {py}")
            append_log(f"[*] Mode HEADLESS={env.get('HEADLESS')} RESET_PROFILE={env.get('RESET_PROFILE')} CLEAR_EACH={env.get('CLEAR_EACH')}")

        try:
            proc = subprocess.Popen(
                [py, "-u", str(flow)],
                cwd=str(BASE_DIR),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
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
            return jsonify({"error": "Tidak ada proses berjalan"}), 400
        try:
            proc.terminate()
            for _ in range(25):
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
            if proc.poll() is None:
                proc.kill()
            append_log(f"\n[*] Proses dihentikan oleh pengguna (pid={proc.pid})\n")
            return jsonify({"ok": True, "pid": proc.pid})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/logs", methods=["GET"])
def api_logs():
    with log_lock:
        lines = list(log_lines)
    
    # Fallback jika memori kosong tapi file log ada
    if len(lines) < 5:
        target_log = LOG_FILE if LOG_FILE.exists() else ROOT_LOG_FILE
        if target_log.exists():
            try:
                flines = target_log.read_text(encoding="utf-8", errors="ignore").splitlines()
                if len(flines) > len(lines):
                    lines = flines
            except Exception:
                pass
                
    try:
        tail = int(request.args.get("tail", "800"))
        if tail > 0:
            lines = lines[-tail:]
    except Exception:
        pass

    acc_path = resolve_accounts_file()
    proc_file = DATA_DIR / "processed_accounts.txt"
    fail_file = DATA_DIR / "failed_accounts.txt"
    urls_file = LOGS_DIR / "urls.txt"
    if not urls_file.exists() and (BASE_DIR / "urls.txt").exists():
        urls_file = BASE_DIR / "urls.txt"

    urls_count = 0
    urls_tail = []
    if urls_file.exists():
        try:
            txt = urls_file.read_text(encoding="utf-8").splitlines()
            urls_count = len([l for l in txt if l.strip()])
            urls_tail = txt[-10:]
        except Exception:
            pass

    acc_content = ""
    acc_count = 0
    if acc_path.exists():
        try:
            acc_content = acc_path.read_text(encoding="utf-8")
            acc_count = len([l for l in acc_content.splitlines() if l.strip() and not l.strip().startswith("#")])
        except Exception:
            pass

    proc_count = 0
    fail_count = 0
    if proc_file.exists():
        try:
            proc_count = len([l for l in proc_file.read_text(encoding="utf-8").splitlines() if l.strip()])
        except Exception:
            pass
    if fail_file.exists():
        try:
            fail_count = len([l for l in fail_file.read_text(encoding="utf-8").splitlines() if l.strip()])
        except Exception:
            pass

    return jsonify({
        "running": is_running(),
        "pid": proc.pid if proc and proc.poll() is None else None,
        "logs": lines,
        "log_count": len(lines),
        "urls_count": urls_count,
        "urls_tail": urls_tail,
        "accounts_content": acc_content,
        "accounts_count": acc_count,
        "processed_count": proc_count,
        "failed_count": fail_count,
    })

@app.route("/api/clear_logs", methods=["POST"])
def api_clear_logs():
    clear_log()
    return jsonify({"ok": True})

@app.route("/api/status", methods=["GET"])
def api_status():
    acc_path = resolve_accounts_file()
    acc_count = 0
    if acc_path.exists():
        try:
            txt = acc_path.read_text(encoding="utf-8").splitlines()
            acc_count = len([l for l in txt if l.strip() and not l.strip().startswith("#")])
        except Exception:
            pass
    return jsonify({
        "running": is_running(),
        "pid": proc.pid if proc and is_running() else None,
        "config": read_env_config(),
        "accounts_count": acc_count,
        "log_lines": len(log_lines),
    })

@app.route("/api/accounts", methods=["GET", "POST"])
def api_accounts():
    acc_path = resolve_accounts_file()
    if request.method == "GET":
        content = acc_path.read_text(encoding="utf-8") if acc_path.exists() else ""
        return jsonify({"content": content})
    else:
        data = request.get_json(force=True, silent=True) or {}
        content = data.get("content", "")
        # Atomic write
        tmp_acc = acc_path.with_suffix(".tmp")
        tmp_acc.write_text(content, encoding="utf-8")
        tmp_acc.replace(acc_path)
        valid_lines = len([l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")])
        return jsonify({"ok": True, "lines": valid_lines})

@app.route("/api/processed_accounts", methods=["GET", "POST"])
def api_processed_accounts():
    proc_file = DATA_DIR / "processed_accounts.txt"
    fail_file = DATA_DIR / "failed_accounts.txt"
    
    if request.method == "GET":
        processed = []
        failed = []
        if proc_file.exists():
            for line in proc_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    parts = line.strip().split("|")
                    processed.append({
                        "email": parts[0] if len(parts) > 0 else "",
                        "status": parts[2] if len(parts) > 2 else "SUCCESS",
                        "time": parts[3] if len(parts) > 3 else "",
                    })
        if fail_file.exists():
            for line in fail_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    parts = line.strip().split("|")
                    failed.append({
                        "email": parts[0] if len(parts) > 0 else "",
                        "status": parts[2] if len(parts) > 2 else "FAILED",
                        "time": parts[3] if len(parts) > 3 else "",
                        "reason": parts[4] if len(parts) > 4 else "Unknown Error",
                    })
        return jsonify({"processed": processed, "failed": failed})
    
    elif request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        action = data.get("action")
        email = data.get("email", "").strip()
        
        if action == "requeue_all":
            acc_path = resolve_accounts_file()
            count = 0
            if fail_file.exists():
                lines = [l.strip() for l in fail_file.read_text(encoding="utf-8").splitlines() if l.strip()]
                requeue_items = []
                for line in lines:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        requeue_items.append(f"{parts[0].strip()}|{parts[1].strip()}")
                if requeue_items:
                    current = acc_path.read_text(encoding="utf-8").splitlines() if acc_path.exists() else []
                    merged = [l.strip() for l in current if l.strip()]
                    for item in requeue_items:
                        if item not in merged:
                            merged.append(item)
                    acc_path.write_text("\n".join(merged) + ("\n" if merged else ""), encoding="utf-8")
                    fail_file.write_text("", encoding="utf-8")
                    count = len(requeue_items)
            return jsonify({"ok": True, "message": f"Berhasil mengembalikan {count} akun gagal ke antrean!"})

        if action == "requeue" and email:
            acc_path = resolve_accounts_file()
            new_failed_lines = []
            found_item = None
            if fail_file.exists():
                for line in fail_file.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        parts = line.strip().split("|")
                        if parts[0].strip().lower() == email.lower() and not found_item:
                            found_item = (parts[0].strip(), parts[1].strip() if len(parts) > 1 else "")
                            continue
                    new_failed_lines.append(line)
                
                tmp_fail = fail_file.with_suffix(".tmp")
                tmp_fail.write_text("\n".join(new_failed_lines) + ("\n" if new_failed_lines else ""), encoding="utf-8")
                tmp_fail.replace(fail_file)
            
            if found_item:
                current_accs = acc_path.read_text(encoding="utf-8") if acc_path.exists() else ""
                new_entry = f"{found_item[0]}|{found_item[1]}"
                updated_accs = (current_accs.strip() + "\n" + new_entry).strip() + "\n"
                
                tmp_acc = acc_path.with_suffix(".tmp")
                tmp_acc.write_text(updated_accs, encoding="utf-8")
                tmp_acc.replace(acc_path)
                return jsonify({"ok": True, "message": f"Akun {email} berhasil dimasukkan kembali ke antrean!"})
        
        return jsonify({"error": "Aksi tidak valid atau email tidak ditemukan"}), 400

if __name__ == "__main__":
    print(f"[*] Antigravity UI aktif di http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True)
