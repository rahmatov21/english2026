"""
Multi-Bot Process Supervisor for Heroku and Local Execution
Runs both the English Teaching Telegram Bot and the Halal Crypto Auto-Trader concurrently in a single dyno.
"""

import os
import sys
import io
import time
import signal
import threading
import subprocess
from pathlib import Path

# Fix Windows console encoding for Unicode/emojis
if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent
TRADER_DIR = ROOT_DIR / "files (5)"

# Fallback: locate trader directory if renamed
if not TRADER_DIR.exists():
    for candidate in ROOT_DIR.iterdir():
        if candidate.is_dir() and (candidate / "luxalgo.py").exists() and (candidate / "bot.py").exists():
            TRADER_DIR = candidate
            break

BOT_CONFIGS = [
    {
        "name": "ENGLISH-BOT",
        "cwd": ROOT_DIR,
        "script": ROOT_DIR / "bot.py",
    },
    {
        "name": "TRADER-BOT",
        "cwd": TRADER_DIR,
        "script": TRADER_DIR / "bot.py",
    },
]

RUNNING = True
processes = {}


def log_stream(proc, name):
    """Read subprocess stdout line by line and print with a clean prefix."""
    try:
        for line in iter(proc.stdout.readline, ""):
            if not line:
                break
            print(f"[{name}] {line.rstrip()}", flush=True)
    except Exception:
        pass


def start_process(config):
    name = config["name"]
    cwd = config["cwd"]
    script = config["script"]

    if not script.exists():
        print(f"[{name}] [!] Script not found: {script}", flush=True)
        return None

    print(f"[{name}] [*] Starting {script.name} in {cwd}...", flush=True)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.Popen(
        [sys.executable, "-u", str(script.name)],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )

    t = threading.Thread(target=log_stream, args=(proc, name), daemon=True)
    t.start()
    return proc


def handle_exit(signum, frame):
    global RUNNING
    sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
    print(f"\n[SUPERVISOR] [!] Received {sig_name}. Stopping all bots gracefully...", flush=True)
    RUNNING = False

    for name, proc in list(processes.items()):
        if proc and proc.poll() is None:
            print(f"[SUPERVISOR] Terminating {name} (PID: {proc.pid})...", flush=True)
            proc.terminate()

    # Wait up to 8 seconds for graceful exit
    t_end = time.time() + 8.0
    for name, proc in list(processes.items()):
        if proc and proc.poll() is None:
            rem = max(0.1, t_end - time.time())
            try:
                proc.wait(timeout=rem)
            except subprocess.TimeoutExpired:
                print(f"[SUPERVISOR] Force-killing {name}...", flush=True)
                proc.kill()

    print("[SUPERVISOR] [OK] All bots stopped cleanly.", flush=True)
    sys.exit(0)


def main():
    global RUNNING
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    print("=" * 70, flush=True)
    print("[SUPERVISOR] MULTI-BOT SUPERVISOR INITIALIZED", flush=True)
    print(f"[SUPERVISOR] Root:   {ROOT_DIR}", flush=True)
    print(f"[SUPERVISOR] Trader: {TRADER_DIR}", flush=True)
    print("=" * 70, flush=True)

    for cfg in BOT_CONFIGS:
        processes[cfg["name"]] = start_process(cfg)

    # Monitor processes and auto-restart if one crashes
    while RUNNING:
        for cfg in BOT_CONFIGS:
            name = cfg["name"]
            proc = processes.get(name)

            if proc is not None and proc.poll() is not None:
                ret = proc.poll()
                if RUNNING:
                    print(f"[{name}] [!] Exited with code {ret}! Restarting in 5s...", flush=True)
                    time.sleep(5)
                    if RUNNING:
                        processes[name] = start_process(cfg)

        time.sleep(1)


if __name__ == "__main__":
    main()
