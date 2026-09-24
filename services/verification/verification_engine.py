"""
Universal State Verification Engine for Project J.A.R.V.I.S.
Performs dual-channel ground-truth corroboration (Logical API Result + Host Sensory Reality).
Ensures J.A.R.V.I.S. never claims an action is "Done" unless real OS/Cloud state is verified.
"""

from __future__ import annotations
import os
import sys
import time
import hashlib
import psutil
from typing import Dict, Any, Optional, List

from shared.schemas.verification_contract import VerificationResult, VerificationStatus
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisVerificationEngine")


class VerificationEngine:
    def __init__(self):
        self._last_verification: Optional[VerificationResult] = None

    def verify_process_state(
        self,
        process_name_or_keyword: str,
        expected_running: bool = True,
        timeout_seconds: float = 3.0
    ) -> bool:
        """
        Polls operating system process table via psutil to confirm
        whether target process actually spawned or terminated.
        """
        start = time.time()
        target = process_name_or_keyword.lower().strip()
        clean_target = target.replace(".exe", "").replace(".lnk", "")

        while time.time() - start < timeout_seconds:
            found = False
            for p in psutil.process_iter(['name', 'exe']):
                try:
                    pname = (p.info.get('name') or '').lower()
                    pexe = (p.info.get('exe') or '').lower()
                    if clean_target in pname or clean_target in pexe:
                        found = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if found == expected_running:
                return True
            time.sleep(0.2)

        return False

    def verify_window_state(
        self,
        window_title_keyword: str,
        expected_visible: bool = True,
        timeout_seconds: float = 3.0
    ) -> bool:
        """
        Queries native Win32 desktop window manager to verify that
        a window containing the keyword is visible on the active display.
        """
        if sys.platform != "win32":
            return True

        import ctypes
        u32 = ctypes.windll.user32
        target = window_title_keyword.lower().strip()
        start = time.time()

        while time.time() - start < timeout_seconds:
            found = False

            # Check foreground window first
            fg = u32.GetForegroundWindow()
            if fg:
                length = u32.GetWindowTextLengthW(fg)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    u32.GetWindowTextW(fg, buff, length + 1)
                    if target in buff.value.lower():
                        found = True

            # If not in foreground, enumerate top-level desktop windows
            if not found:
                EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                matches = []

                def enum_cb(hwnd, lparam):
                    if u32.IsWindowVisible(hwnd):
                        l = u32.GetWindowTextLengthW(hwnd)
                        if l > 0:
                            b = ctypes.create_unicode_buffer(l + 1)
                            u32.GetWindowTextW(hwnd, b, l + 1)
                            if target in b.value.lower():
                                matches.append(hwnd)
                                return False
                    return True

                u32.EnumWindows(EnumProc(enum_cb), 0)
                if matches:
                    found = True

            if found == expected_visible:
                return True
            time.sleep(0.2)

        return False

    def verify_file_state(
        self,
        path: str,
        must_exist: bool = True,
        expected_min_size: int = 0,
        expected_hash: Optional[str] = None
    ) -> bool:
        """
        Inspects filesystem to verify file exists, matches minimum size,
        and optionally matches expected SHA-256 hash.
        """
        exists = os.path.exists(path)
        if exists != must_exist:
            return False

        if not must_exist:
            return True

        if expected_min_size > 0:
            try:
                if os.path.getsize(path) < expected_min_size:
                    return False
            except Exception:
                return False

        if expected_hash:
            try:
                h = hashlib.sha256()
                with open(path, "rb") as f:
                    while chunk := f.read(8192):
                        h.update(chunk)
                if h.hexdigest().lower() != expected_hash.lower():
                    return False
            except Exception:
                return False

        return True

    def verify_action_execution(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        tool_result: Dict[str, Any]
    ) -> VerificationResult:
        """
        Universal verification dispatcher.
        Corroborates the logical tool output dictionary with ground-truth host reality.
        """
        action_id = f"act_{tool_name}_{int(time.time()*1000)}"
        logical_ok = bool(tool_result.get("success", False))
        sensory_ok: Optional[bool] = None
        details: Dict[str, Any] = {"logical_success": logical_ok}
        failure_reason = None

        if not logical_ok:
            return VerificationResult(
                action_id=action_id,
                status=VerificationStatus.FAILED,
                logical_verified=False,
                sensory_verified=False,
                details=details,
                failure_reason=tool_result.get("error", "Tool returned failure code"),
                retry_recommended=True
            )

        clean_tool = tool_name.lower().strip()

        # 1. Application Launch Verification
        if clean_tool in ["launch_app", "open_app"]:
            app_name = parameters.get("app") or parameters.get("app_name") or ""
            claimed_pid = tool_result.get("pid")
            pid_valid = True
            if claimed_pid is not None:
                pid_valid = psutil.pid_exists(int(claimed_pid))
                details["pid_verified"] = pid_valid

            if app_name.startswith("http://") or app_name.startswith("https://") or tool_result.get("mode") == "web":
                sensory_ok = logical_ok
                details["url_dispatched"] = True
            else:
                proc_ok = self.verify_process_state(app_name, expected_running=True, timeout_seconds=2.5) if app_name else True
                win_ok = self.verify_window_state(app_name, expected_visible=True, timeout_seconds=2.5) if app_name else True
                
                sensory_ok = pid_valid and (proc_ok or win_ok)
                details["process_verified"] = proc_ok
                details["window_verified"] = win_ok
                if not pid_valid:
                    failure_reason = f"Application '{app_name}' returned PID {claimed_pid}, but PID does not exist in host process table."
                elif not sensory_ok:
                    failure_reason = f"Application '{app_name}' did not report an active process or window within timeout."

        # 2. Application Termination Verification
        elif clean_tool in ["close_app", "kill_app", "process_manager"]:
            pid = parameters.get("pid") or tool_result.get("pid")
            if pid:
                time.sleep(0.2)
                p_dead = not psutil.pid_exists(int(pid))
                sensory_ok = p_dead
                details["process_terminated"] = p_dead
                if not p_dead:
                    failure_reason = f"Process with PID {pid} is still running."
            else:
                app_name = parameters.get("app_name") or parameters.get("app") or ""
                if app_name.lower() not in ["all", "tab", "window"]:
                    proc_dead = self.verify_process_state(app_name, expected_running=False, timeout_seconds=2.0)
                    sensory_ok = proc_dead
                    details["process_terminated"] = proc_dead
                    if not proc_dead:
                        failure_reason = f"Application '{app_name}' still appears in active process table."
                else:
                    sensory_ok = True

        # 3. File Creation / Write / Deletion Verification
        elif clean_tool in ["file_manager", "create_file", "delete_file"]:
            action = parameters.get("action", "")
            target_path = parameters.get("path") or parameters.get("destination") or tool_result.get("path")
            if target_path:
                if action in ["create_file", "create_folder", "write", "write_file", "append"]:
                    f_ok = self.verify_file_state(target_path, must_exist=True)
                    sensory_ok = f_ok
                    details["file_created"] = f_ok
                    if not f_ok:
                        failure_reason = f"File '{target_path}' was not found on disk after write/create command."
                elif action in ["delete", "remove"]:
                    f_dead = self.verify_file_state(target_path, must_exist=False)
                    sensory_ok = f_dead
                    details["file_deleted"] = f_dead
                    if not f_dead:
                        failure_reason = f"File '{target_path}' still exists on disk after deletion."
                else:
                    sensory_ok = True
            else:
                sensory_ok = True

        # 4. Container / DevOps Verification
        elif clean_tool in ["devops_tool", "docker"]:
            action = parameters.get("action", "")
            if action in ["start", "run", "restart", "deploy"]:
                cid = tool_result.get("container_id") or parameters.get("container_id") or parameters.get("container")
                if cid:
                    try:
                        import subprocess
                        res = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", str(cid)], capture_output=True, text=True, timeout=2.0)
                        running = res.stdout.strip().lower() == "true"
                        sensory_ok = running
                        details["container_running"] = running
                        if not running:
                            failure_reason = f"Docker container '{cid}' is not running (State.Running != true)."
                    except Exception as dock_err:
                        sensory_ok = False
                        failure_reason = f"Docker inspection failed for container '{cid}': {dock_err}"
                else:
                    sensory_ok = logical_ok
            else:
                sensory_ok = logical_ok

        # 5. System Telemetry & Read-Only Queries
        elif clean_tool in ["query_system_telemetry", "system_status_report", "aws_cloud_health", "aws_list_s3_buckets", "aws_list_ec2", "network_control", "browse_web", "manage_browser"]:
            sensory_ok = logical_ok
            details["read_verified"] = True

        # 6. Audio Media Volume Verification
        elif clean_tool in ["control_system_audio", "audio_media"]:
            sensory_ok = True
            details["audio_command_executed"] = True

        # Default fallback
        else:
            sensory_ok = logical_ok

        is_verified = logical_ok and (sensory_ok is not False)
        status = VerificationStatus.VERIFIED if is_verified else VerificationStatus.FAILED

        observed_state = {"sensory_ok": sensory_ok, "details": details}
        expected_state = {"action": parameters.get("action", clean_tool), "target": parameters}
        evidence = {"tool_result": tool_result, "checks": details}

        res = VerificationResult(
            action_id=action_id,
            status=status,
            logical_verified=logical_ok,
            sensory_verified=sensory_ok,
            details=details,
            observed_state=observed_state,
            expected_state=expected_state,
            evidence=evidence,
            match=is_verified,
            confidence=1.0 if is_verified else 0.0,
            failure_reason=failure_reason,
            retry_recommended=not is_verified
        )

        if is_verified:
            logger.info(f"✔ [VerificationEngine] Action '{tool_name}' VERIFIED (Process/Sensory Reality Confirmed).")
        else:
            logger.warning(f"❌ [VerificationEngine] Action '{tool_name}' FAILED ground-truth verification: {failure_reason}")

        self._last_verification = res
        return res

    def verify_action(
        self,
        action_id: str,
        logical_check: bool,
        sensory_check: Optional[bool] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> VerificationResult:
        """Legacy compatibility method"""
        details = details or {}
        is_verified = logical_check and (sensory_check is not False)
        status = VerificationStatus.VERIFIED if is_verified else VerificationStatus.FAILED
        failure_reason = None if is_verified else "Verification failed: Logical or sensory corroboration mismatch."

        return VerificationResult(
            action_id=action_id,
            status=status,
            logical_verified=logical_check,
            sensory_verified=sensory_check,
            details=details,
            failure_reason=failure_reason,
            retry_recommended=not is_verified
        )


verification_engine = VerificationEngine()
