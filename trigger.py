#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   AERS — AI Emergency Response System                        ║
║   TRIGGER SCRIPT  |  python trigger.py                       ║
║                                                              ║
║   What this does:                                            ║
║   1. Checks all dependencies are installed                   ║
║   2. Trains ML model if model.pkl doesn't exist              ║
║   3. Starts FastAPI backend (uvicorn)                        ║
║   4. Opens main system in browser                            ║
║   5. Opens simulator dashboard in browser                    ║
║   6. Shows live server logs in terminal                      ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python trigger.py                     → Start normally
    python trigger.py --sim               → Start + auto-launch simulator
    python trigger.py --port 9000         → Custom port
    python trigger.py --no-browser        → No browser auto-open
"""

import os
import sys
import time
import argparse
import subprocess
import importlib
import webbrowser
import threading

# ── Colours for terminal output ───────────────────────────────────────
class C:
    RED    = '\033[91m'
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    BLUE   = '\033[94m'
    CYAN   = '\033[96m'
    WHITE  = '\033[97m'
    BOLD   = '\033[1m'
    DIM    = '\033[2m'
    RESET  = '\033[0m'

def banner():
    print(f"""
{C.BOLD}{C.BLUE}
  ╔═══════════════════════════════════════════════════════════╗
  ║  AERS — AI-Based Enhanced Emergency Response System       ║
  ║  Trigger v1.0  |  Darshan Ingalagi  |  BCA Final Year     ║
  ╚═══════════════════════════════════════════════════════════╝
{C.RESET}""")

def ok(msg):   print(f"  {C.GREEN}✓{C.RESET}  {msg}")
def warn(msg): print(f"  {C.YELLOW}!{C.RESET}  {msg}")
def err(msg):  print(f"  {C.RED}✗{C.RESET}  {msg}")
def info(msg): print(f"  {C.CYAN}→{C.RESET}  {msg}")
def step(n, msg): print(f"\n{C.BOLD}{C.WHITE}  [{n}] {msg}{C.RESET}")


# ── Step 1: Dependency check ──────────────────────────────────────────
REQUIRED = {
    "fastapi":   "fastapi",
    "uvicorn":   "uvicorn",
    "sklearn":   "scikit-learn",
    "pandas":    "pandas",
    "httpx":     "httpx",
    "pydantic":  "pydantic",
}

def check_deps():
    step("1/4", "Checking dependencies")
    missing = []
    for module, package in REQUIRED.items():
        try:
            importlib.import_module(module)
            ok(f"{package}")
        except ImportError:
            err(f"{package} — NOT INSTALLED")
            missing.append(package)

    if missing:
        warn(f"Installing {len(missing)} missing package(s)...")
        pkg_str = " ".join(missing)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install"] + missing + ["--quiet"],
            capture_output=True
        )
        if result.returncode == 0:
            ok(f"Installed: {pkg_str}")
        else:
            err(f"Failed to install: {pkg_str}")
            err("Run manually: pip install -r requirements.txt")
            sys.exit(1)
    else:
        ok("All dependencies satisfied")


# ── Step 2: Train model ───────────────────────────────────────────────
def check_and_train_model():
    step("2/4", "Checking ML model")

    base = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base, "model", "model.pkl")
    vec_path   = os.path.join(base, "model", "vectorizer.pkl")
    data_path  = os.path.join(base, "data", "data.csv")
    train_path = os.path.join(base, "model", "train.py")

    if os.path.exists(model_path) and os.path.exists(vec_path):
        size = os.path.getsize(model_path)
        ok(f"model.pkl found ({size:,} bytes)")
        ok("vectorizer.pkl found")
        return True

    warn("model.pkl not found — training now...")

    if not os.path.exists(data_path):
        err(f"data/data.csv not found at {data_path}")
        sys.exit(1)

    if not os.path.exists(train_path):
        err(f"model/train.py not found at {train_path}")
        sys.exit(1)

    info("Running: python model/train.py")
    result = subprocess.run(
        [sys.executable, train_path],
        capture_output=True, text=True, cwd=base
    )

    if result.returncode == 0:
        # Print accuracy line from output
        for line in result.stdout.splitlines():
            if "Accuracy" in line or "saved" in line:
                ok(line.strip())
        return True
    else:
        err("Model training failed:")
        print(result.stderr[-400:] if result.stderr else "(no output)")
        sys.exit(1)


# ── Step 3: Start server ──────────────────────────────────────────────
def start_server(port: int):
    step("3/4", f"Starting FastAPI server on port {port}")

    base = os.path.dirname(os.path.abspath(__file__))

    info(f"Command: uvicorn app:app --reload --port {port}")
    info(f"Working directory: {base}")

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app",
         "--reload", "--port", str(port),
         "--host", "0.0.0.0",
         "--log-level", "info"],
        cwd=base,
    )
    return proc


# ── Step 4: Open browsers ─────────────────────────────────────────────
def open_browsers(port: int, auto_sim: bool, open_browser: bool):
    step("4/4", "Opening interface")

    main_url = f"http://localhost:{port}"
    sim_url  = f"http://localhost:{port}/simulator"

    info(f"Main system  → {C.CYAN}{main_url}{C.RESET}")
    info(f"Simulator    → {C.CYAN}{sim_url}{C.RESET}")

    if not open_browser:
        warn("Browser auto-open disabled (--no-browser)")
        return

    time.sleep(2.5)  # Wait for server to be ready

    def _open():
        webbrowser.open(main_url)
        time.sleep(0.8)
        webbrowser.open(sim_url)
        if auto_sim:
            time.sleep(1.5)
            try:
                import urllib.request, json as js
                req = urllib.request.Request(
                    f"http://localhost:{port}/sim/start?speed=8",
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=4)
                ok("Auto-started simulator (--sim flag)")
            except Exception as e:
                warn(f"Could not auto-start simulator: {e}")

    threading.Thread(target=_open, daemon=True).start()


# ── Main ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AERS Trigger Script")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--sim", action="store_true", help="Auto-launch simulator on startup")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")
    parser.add_argument("--retrain", action="store_true", help="Force retrain model even if pkl exists")
    args = parser.parse_args()

    banner()

    # Pre-flight checks
    if args.retrain:
        base = os.path.dirname(os.path.abspath(__file__))
        for f in ["model/model.pkl", "model/vectorizer.pkl"]:
            fp = os.path.join(base, f)
            if os.path.exists(fp):
                os.remove(fp)
                warn(f"Deleted {f} (--retrain)")

    check_deps()
    check_and_train_model()
    proc = start_server(args.port)
    open_browsers(args.port, args.sim, not args.no_browser)

    # ── Summary ────────────────────────────────────────────────────────
    print(f"""
{C.BOLD}  ═══════════════════════════════════════════════════════════{C.RESET}
  {C.GREEN}{C.BOLD}AERS is running!{C.RESET}

  {C.CYAN}Main System{C.RESET}     →  http://localhost:{args.port}
  {C.CYAN}Simulator{C.RESET}       →  http://localhost:{args.port}/simulator
  {C.CYAN}API Docs{C.RESET}        →  http://localhost:{args.port}/docs
  {C.CYAN}API Status{C.RESET}      →  http://localhost:{args.port}/test

  {C.DIM}Press Ctrl+C to stop the server{C.RESET}
{C.BOLD}  ═══════════════════════════════════════════════════════════{C.RESET}
    """)

    try:
        proc.wait()
    except KeyboardInterrupt:
        print(f"\n\n  {C.YELLOW}Shutting down AERS...{C.RESET}")
        proc.terminate()
        proc.wait()
        print(f"  {C.GREEN}Server stopped.{C.RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
