"""
=============================================================================
           UNIFIED LAUNCHER: AI TECHNICAL & SPEECH INTERVIEW PLATFORM
=============================================================================
Launches both:
1. FastAPI Backend:  http://127.0.0.1:8000 (Swagger docs: http://127.0.0.1:8000/docs)
2. Streamlit Web App: http://localhost:8501
=============================================================================
"""

import os
import sys
import subprocess
import time
import socket


def kill_process_on_port(port: int):
    """Finds and terminates any existing process listening on the given port."""
    try:
        if sys.platform == "win32":
            cmd = f'netstat -ano | findstr :{port}'
            out = subprocess.check_output(cmd, shell=True).decode(errors="ignore")
            for line in out.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and "LISTENING" in line.upper():
                    pid = parts[-1]
                    if pid != "0" and pid != str(os.getpid()):
                        try:
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            print(f"  [Cleaned] Freed port {port} (Terminated stale PID {pid})")
                        except Exception:
                            pass
    except Exception:
        pass


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

print("\n" + "=" * 80)
print("     AI TECHNICAL & SPEECH INTERVIEW PLATFORM (ALL-IN-ONE LAUNCHER)")
print("=" * 80)
print(f"Project Root Directory : {BASE_DIR}")
print(f"Backend Directory      : {BACKEND_DIR}")
print(f"Frontend Directory     : {FRONTEND_DIR}")
print("1. FastAPI Backend       : http://127.0.0.1:8000")
print("2. Interactive Swagger   : http://127.0.0.1:8000/docs")
print("3. Streamlit Frontend UI : http://localhost:8501")
print("=" * 80)

# Ensure ports 8000 and 8501 are free
for p in [8000, 8501]:
    if is_port_in_use(p):
        print(f"Port {p} is currently in use. Freeing port...")
        kill_process_on_port(p)
        time.sleep(1)

# Start backend
backend_cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]
print("\n[1/2] Starting FastAPI Backend on http://127.0.0.1:8000 ...")
backend_process = subprocess.Popen(backend_cmd, cwd=BACKEND_DIR)

time.sleep(3)

# Start frontend
frontend_cmd = [sys.executable, "-m", "streamlit", "run", "frontend/app.py", "--server.port", "8501"]
print("[2/2] Starting Streamlit Frontend Web App on http://localhost:8501 ...")
frontend_process = subprocess.Popen(frontend_cmd, cwd=BASE_DIR)

print("\n🚀 Both servers running! Press Ctrl+C in this terminal to shut down.\n")

try:
    backend_process.wait()
    frontend_process.wait()
except KeyboardInterrupt:
    print("\nShutting down servers...")
    backend_process.terminate()
    frontend_process.terminate()
    print("Shutdown complete.")
