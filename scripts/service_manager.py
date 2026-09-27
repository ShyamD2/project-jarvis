#!/usr/bin/env python3
"""
Production Daemon Service Manager for Project J.A.R.V.I.S. (Phase 2 Reliability).
Provides robust service lifecycle management:
  - start: Spawns the J.A.R.V.I.S. Core server in background mode with detached process group.
  - stop: Gracefully terminates the running engine and checkpoints state.
  - restart: Seamless rolling restart with readiness validation.
  - status: Inspects PID, memory/CPU consumption, and live subsystem readiness.
  - health: Probes the live /health/ready endpoint.
"""

from __future__ import annotations
import os
import sys
import time
import signal
import json
import argparse
import subprocess
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PID_DIR = os.path.join(PROJECT_ROOT, "data")
PID_FILE = os.path.join(PID_DIR, "jarvis.pid")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "jarvis_service.log")

try:
    import psutil
except ImportError:
    psutil = None


def get_stored_pid() -> Optional[int]:
    """Reads PID from pidfile if present and valid."""
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return int(content) if content else None
    except Exception:
        return None


def is_pid_alive(pid: int) -> bool:
    """Checks whether the specified PID is currently running."""
    if psutil:
        try:
            p = psutil.Process(pid)
            return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def probe_health_endpoint(port: int = 8000, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
    """Sends HTTP GET to /health/ready and returns JSON payload if responsive."""
    url = f"http://127.0.0.1:{port}/health/ready"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisServiceManager/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status in (200, 503):
                return json.loads(response.read().decode("utf-8"))
    except Exception:
        pass
    return None


def start_service(port: int = 8000) -> int:
    """Spawns J.A.R.V.I.S. Core server in background mode."""
    existing_pid = get_stored_pid()
    if existing_pid and is_pid_alive(existing_pid):
        print(f"[WARN] [ServiceManager] J.A.R.V.I.S. Core is already running with PID {existing_pid}.")
        return 0

    if existing_pid and not is_pid_alive(existing_pid):
        print(f"[CLEANUP] [ServiceManager] Cleaning up stale PID file ({existing_pid}).")
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

    os.makedirs(PID_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    main_script = os.path.join(PROJECT_ROOT, "services", "jarvis_core", "main.py")
    if not os.path.exists(main_script):
        print(f"[ERROR] [ServiceManager] Entrypoint script not found: {main_script}")
        return 1

    print("[STARTING] [ServiceManager] Starting Project J.A.R.V.I.S. Core Engine...")
    log_fd = open(LOG_FILE, "a", encoding="utf-8")

    creationflags = 0
    start_new_session = False
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008  # DETACHED_PROCESS
    else:
        start_new_session = True

    cmd = [sys.executable, main_script]
    env = os.environ.copy()
    env["JARVIS_PORT"] = str(port)

    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=log_fd,
        stderr=log_fd,
        creationflags=creationflags,
        start_new_session=start_new_session
    )

    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(proc.pid))

    print(f"   PID: {proc.pid}")
    print(f"   Logs: {LOG_FILE}")
    print(f"   Port: {port}")
    print("... [ServiceManager] Waiting for health probe readiness...")

    started = False
    for _ in range(20):
        time.sleep(0.5)
        if not is_pid_alive(proc.pid):
            print("[ERROR] [ServiceManager] Engine process exited prematurely. Inspect logs for details:")
            print(f"   tail -n 20 {LOG_FILE}")
            return 1
        data = probe_health_endpoint(port=port, timeout=1.0)
        if data is not None:
            started = True
            break

    if started:
        print("[SUCCESS] [ServiceManager] J.A.R.V.I.S. Core Engine is ONLINE and HEALTHY.")
        return 0
    else:
        print(f"[WARN] [ServiceManager] Engine started with PID {proc.pid} but /health/ready probe timed out.")
        print(f"   Inspect logs at {LOG_FILE}")
        return 0


def stop_service(timeout: float = 10.0) -> int:
    """Gracefully terminates the running engine."""
    pid = get_stored_pid()
    if not pid:
        print("[INFO] [ServiceManager] No running service detected (PID file not found).")
        return 0

    if not is_pid_alive(pid):
        print(f"[INFO] [ServiceManager] Process {pid} is not running. Removing stale PID file.")
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
        return 0

    print(f"[SHUTDOWN] [ServiceManager] Sending graceful shutdown signal to PID {pid}...")
    try:
        if sys.platform == "win32":
            os.kill(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception as e:
        print(f"[WARN] [ServiceManager] Error signaling PID {pid}: {e}")

    t_end = time.time() + timeout
    while time.time() < t_end:
        if not is_pid_alive(pid):
            break
        time.sleep(0.5)

    if is_pid_alive(pid):
        print(f"[WARN] [ServiceManager] PID {pid} did not exit within {timeout}s. Forcefully terminating...")
        if psutil:
            try:
                psutil.Process(pid).kill()
            except Exception:
                pass
        else:
            try:
                os.kill(pid, signal.SIGKILL if hasattr(signal, "SIGKILL") else signal.SIGTERM)
            except Exception:
                pass

    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

    print(f"[SUCCESS] [ServiceManager] Service (PID {pid}) stopped successfully.")
    return 0


def status_service(port: int = 8000) -> int:
    """Displays real-time status, process metrics, and health probe summary."""
    pid = get_stored_pid()
    if not pid or not is_pid_alive(pid):
        print("[STOPPED] [ServiceManager] Status: STOPPED (Service is not running)")
        return 1

    print(f"[RUNNING] [ServiceManager] Status: RUNNING (PID {pid})")
    if psutil:
        try:
            p = psutil.Process(pid)
            cpu = p.cpu_percent(interval=0.1)
            mem_info = p.memory_info()
            rss_mb = round(mem_info.rss / (1024 * 1024), 1)
            create_time = p.create_time()
            uptime_sec = round(time.time() - create_time, 1)
            print(f"   Uptime: {uptime_sec}s")
            print(f"   Memory (RSS): {rss_mb} MB")
            print(f"   CPU Usage: {cpu}%")
            print(f"   Threads: {p.num_threads()}")
        except Exception as e:
            print(f"   Metrics notice: {e}")

    health = probe_health_endpoint(port=port)
    if health:
        print(f"   Readiness: {'READY' if health.get('ready') else 'NOT_READY'}")
        checks = health.get("checks", {})
        for name, detail in checks.items():
            st = detail.get("status", "UNKNOWN")
            print(f"     - {name}: {st}")
    else:
        print(f"   Readiness: UNREACHABLE (HTTP probe failed on port {port})")

    return 0


def main():
    parser = argparse.ArgumentParser(description="Project J.A.R.V.I.S. Production Service Manager")
    parser.add_argument("action", choices=["start", "stop", "restart", "status", "health"], help="Service action")
    parser.add_argument("--port", type=int, default=8000, help="Core API server port (default: 8000)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Graceful shutdown timeout in seconds")

    args = parser.parse_args()

    if args.action == "start":
        sys.exit(start_service(port=args.port))
    elif args.action == "stop":
        sys.exit(stop_service(timeout=args.timeout))
    elif args.action == "restart":
        stop_service(timeout=args.timeout)
        time.sleep(1.0)
        sys.exit(start_service(port=args.port))
    elif args.action == "status":
        sys.exit(status_service(port=args.port))
    elif args.action == "health":
        h = probe_health_endpoint(port=args.port)
        if h:
            print(json.dumps(h, indent=2))
            sys.exit(0 if h.get("ready") else 1)
        else:
            print(json.dumps({"status": "unreachable", "error": f"Connection refused on port {args.port}"}, indent=2))
            sys.exit(1)


if __name__ == "__main__":
    main()
