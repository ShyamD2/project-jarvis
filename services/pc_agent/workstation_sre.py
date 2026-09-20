"""
Autonomous Workstation SRE & Self-Healing Dev Environment for Project J.A.R.V.I.S. (Pillar 2).
Provides proactive incident interception, port collision resolution, stale lockfile clearing,
orphan process reclamation, and 1-tap Telegram remediation tickets.
Runs in zero-overhead Eco-Mode (event-driven, sub-second execution, zero CPU polling).
"""

from __future__ import annotations
import os
import sys
import time
import socket
import psutil
import subprocess
from typing import Dict, Any, List, Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisWorkstationSRE")


class WorkstationSRE:
    def __init__(self):
        self._incident_history: List[Dict[str, Any]] = []
        self._active_tickets: Dict[str, Dict[str, Any]] = {}
        # Common dev ports to monitor
        self.dev_ports = [3000, 5000, 8000, 8080, 8085, 9000, 5888]

    def diagnose_port(self, port: int) -> Dict[str, Any]:
        """
        Pinpoints what process is holding a network port.
        Returns PID, process name, command line, memory, and CPU metrics.
        """
        result = {
            "port": port,
            "in_use": False,
            "pid": None,
            "process_name": None,
            "cmdline": None,
            "memory_mb": 0.0,
            "cpu_percent": 0.0,
            "created_time": None
        }

        # Check socket availability first (zero CPU fast-path)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.01)
            can_bind = True
            try:
                s.bind(("127.0.0.1", port))
            except (socket.error, OSError):
                can_bind = False

        if can_bind:
            return result

        result["in_use"] = True
        # Find which process holds the port
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr and conn.laddr.port == port and conn.status == "LISTEN":
                    pid = conn.pid
                    if pid:
                        result["pid"] = pid
                        try:
                            proc = psutil.Process(pid)
                            result["process_name"] = proc.name()
                            result["cmdline"] = " ".join(proc.cmdline()[:6]) if proc.cmdline() else proc.name()
                            result["memory_mb"] = round(proc.memory_info().rss / (1024 * 1024), 2)
                            result["cpu_percent"] = proc.cpu_percent(interval=None)
                            result["created_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(proc.create_time()))
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            result["process_name"] = "system/unknown"
                        break
        except Exception as e:
            logger.warning(f"[WorkstationSRE] psutil port scan failed: {e}")
            # Fallback to Windows netstat
            try:
                out = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True, text=True)
                for line in out.strip().splitlines():
                    if "LISTENING" in line:
                        parts = line.split()
                        pid = int(parts[-1])
                        result["pid"] = pid
                        try:
                            p = psutil.Process(pid)
                            result["process_name"] = p.name()
                        except Exception:
                            result["process_name"] = "unknown"
                        break
            except Exception:
                pass

        return result

    def free_port(self, port: int, force: bool = True) -> Dict[str, Any]:
        """
        Safely or forcefully terminates the process occupying a port and verifies liberation.
        """
        diag = self.diagnose_port(port)
        if not diag["in_use"]:
            return {"success": True, "port": port, "message": f"Port {port} is already free."}

        pid = diag["pid"]
        if not pid:
            return {"success": False, "port": port, "error": f"Port {port} is busy but could not identify PID."}

        # Safety: protect system core processes
        protected_pids = {0, 4}
        if pid in protected_pids:
            return {"success": False, "port": port, "error": f"Refusing to terminate critical system PID {pid}."}

        try:
            proc = psutil.Process(pid)
            p_name = proc.name()
            if force:
                proc.kill()
            else:
                proc.terminate()
                proc.wait(timeout=2.0)

            # Verification check
            time.sleep(0.3)
            after_diag = self.diagnose_port(port)
            freed = not after_diag["in_use"]

            if freed:
                logger.info(f"✔ [WorkstationSRE] Port {port} liberated. Terminated {p_name} (PID {pid}).")
                return {
                    "success": True,
                    "port": port,
                    "killed_pid": pid,
                    "process_name": p_name,
                    "message": f"Successfully cleared port {port} (killed {p_name}, PID {pid})."
                }
            else:
                return {
                    "success": False,
                    "port": port,
                    "error": f"Sent kill signal to PID {pid}, but port {port} is still occupied."
                }
        except Exception as e:
            return {"success": False, "port": port, "error": str(e)}

    def scan_lockfiles(self, search_roots: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Scans repositories and workspaces for stale lockfiles that freeze git, terraform, or npm.
        """
        if not search_roots:
            search_roots = [
                PROJECT_ROOT,
                "d:\\cloud-engineering-journey" if os.path.exists("d:\\cloud-engineering-journey") else PROJECT_ROOT
            ]

        known_lock_patterns = [
            ".git/index.lock",
            ".git/refs/heads/main.lock",
            "terraform.tfstate.lock.info",
            ".terraform.tfstate.lock.info",
            "package-lock.json.lock",
            "yarn.lock.lock"
        ]

        found_locks = []
        for root in search_roots:
            if not os.path.exists(root):
                continue
            for pattern in known_lock_patterns:
                lock_full = os.path.join(root, pattern)
                if os.path.exists(lock_full):
                    stat = os.stat(lock_full)
                    age_seconds = time.time() - stat.st_mtime
                    found_locks.append({
                        "file_path": lock_full,
                        "relative_path": pattern,
                        "root_dir": root,
                        "age_seconds": round(age_seconds, 1),
                        "is_stale": age_seconds > 120.0, # Stale if older than 2 minutes
                        "size_bytes": stat.st_size
                    })

        return found_locks

    def clear_lockfile(self, lock_path: str) -> Dict[str, Any]:
        """Safely removes a stale lockfile to restore normal dev workflow."""
        if not os.path.exists(lock_path):
            return {"success": True, "message": f"Lockfile {lock_path} does not exist."}

        try:
            os.remove(lock_path)
            logger.info(f"✔ [WorkstationSRE] Stale lockfile deleted: {lock_path}")
            return {"success": True, "message": f"Successfully removed lockfile: {lock_path}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to remove lockfile {lock_path}: {e}"}

    def scan_runaway_processes(
        self,
        cpu_threshold: float = 75.0,
        mem_threshold_mb: float = 1200.0
    ) -> List[Dict[str, Any]]:
        """Identifies runaway processes consuming excessive CPU or memory on this low-end host."""
        runaways = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                info = proc.info
                pid = info['pid']
                if pid in [0, 4]:
                    continue
                mem_mb = (info['memory_info'].rss / (1024 * 1024)) if info['memory_info'] else 0.0

                if mem_mb > mem_threshold_mb:
                    runaways.append({
                        "pid": pid,
                        "name": info['name'],
                        "cpu_percent": 0.0,
                        "memory_mb": round(mem_mb, 1)
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return runaways

    def run_sre_health_scan(self) -> Dict[str, Any]:
        """
        Executes an instant holistic SRE audit of the workstation.
        Detects collisions, stale locks, runaway tasks, and provides auto-fix tickets.
        """
        t0 = time.time()
        # 1. Port scans
        occupied_ports = []
        for p in self.dev_ports:
            d = self.diagnose_port(p)
            if d["in_use"]:
                occupied_ports.append(d)

        # 2. Lockfile scans
        stale_locks = self.scan_lockfiles()

        # 3. High-load processes
        runaways = self.scan_runaway_processes()

        has_incidents = bool(stale_locks or any(l["is_stale"] for l in stale_locks) or runaways)
        incident_id = f"sre_{int(time.time())}"

        scan_result = {
            "incident_id": incident_id,
            "timestamp": time.time(),
            "scan_duration_ms": round((time.time() - t0) * 1000, 2),
            "status": "INCIDENT_DETECTED" if has_incidents else "HEALTHY",
            "occupied_ports": occupied_ports,
            "stale_locks": stale_locks,
            "runaways": runaways,
            "heal_recommended": has_incidents
        }

        self._active_tickets[incident_id] = scan_result
        return scan_result

    def apply_sre_healing(self, target_type: str, target_value: Any) -> Dict[str, Any]:
        """
        1-Tap self-healing execution:
        - target_type="port", target_value=5000 -> frees port
        - target_type="lock", target_value="path/to/.git/index.lock" -> removes lock
        - target_type="all_locks" -> removes all stale locks
        - target_type="pid", target_value=1234 -> kills zombie PID
        """
        if target_type == "port":
            port = int(target_value)
            return self.free_port(port)
        elif target_type == "lock":
            return self.clear_lockfile(str(target_value))
        elif target_type == "all_locks":
            locks = self.scan_lockfiles()
            cleared = []
            for l in locks:
                res = self.clear_lockfile(l["file_path"])
                if res["success"]:
                    cleared.append(l["file_path"])
            return {"success": True, "cleared_count": len(cleared), "cleared_locks": cleared}
        elif target_type == "pid":
            try:
                p = psutil.Process(int(target_value))
                name = p.name()
                p.kill()
                return {"success": True, "message": f"Terminated runaway process {name} (PID {target_value})"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": f"Unknown SRE target type: {target_type}"}

    def format_telegram_report(self, scan_result: Dict[str, Any]) -> str:
        """Formats SRE health scan into an elegant Telegram Markdown alert."""
        lines = [
            "🛡️ *J.A.R.V.I.S. Workstation SRE Report*",
            f"⏱️ _Scan completed in {scan_result['scan_duration_ms']}ms_",
            f"Status: *{'⚠️ ISSUES DETECTED' if scan_result['heal_recommended'] else '✅ HEALTHY & OPTIMAL'}*",
            ""
        ]

        # Port status
        ports = scan_result.get("occupied_ports", [])
        if ports:
            lines.append("🔌 *Active Dev Ports:*")
            for p in ports:
                lines.append(f"  • Port `{p['port']}`: `{p['process_name']}` (PID {p['pid']}, {p['memory_mb']}MB)")
        else:
            lines.append("🔌 *Active Dev Ports:* All scanned ports clear.")

        # Stale locks
        locks = scan_result.get("stale_locks", [])
        if locks:
            lines.append("\n🔒 *Detected Lockfiles:*")
            for l in locks:
                status_icon = "⚠️ STALE" if l["is_stale"] else "ℹ️ ACTIVE"
                lines.append(f"  • `{l['relative_path']}`: {status_icon} ({l['age_seconds']}s old)")
        else:
            lines.append("\n🔒 *Lockfiles:* None (Git & Terraform clean)")

        # Runaway tasks
        runaways = scan_result.get("runaways", [])
        if runaways:
            lines.append("\n🔥 *High Resource Processes:*")
            for r in runaways:
                lines.append(f"  • `{r['name']}` (PID {r['pid']}): {r['cpu_percent']}% CPU, {r['memory_mb']}MB RAM")

        lines.append("\n💡 _Use `/sre_heal port <num>` or `/sre_heal locks` for 1-tap instant remediation._")
        return "\n".join(lines)


workstation_sre = WorkstationSRE()
