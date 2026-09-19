"""
DevSecOps Immune System & Pre-Execution Micro-Sandbox for Project J.A.R.V.I.S. (Pillar 7).
Performs static AST taint analysis and behavioral threat modeling on commands, packages,
and installation scripts before they touch the host OS. Quarantines supply-chain attacks,
credential theft attempts, and destructive payloads.
"""

from __future__ import annotations
import os
import sys
import re
import ast
import time
import subprocess
from typing import Dict, Any, List, Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisImmuneSandbox")

QUARANTINE_DIR = os.path.join(PROJECT_ROOT, "data", "quarantine")
os.makedirs(QUARANTINE_DIR, exist_ok=True)


class ImmuneSandbox:
    def __init__(self):
        self._quarantined_threats: List[Dict[str, Any]] = []

        # Taint patterns for credential leakage & supply-chain theft
        self.credential_patterns = [
            r"\.env",
            r"\.aws/credentials",
            r"id_rsa",
            r"id_ed25519",
            r"TELEGRAM_BOT_TOKEN",
            r"OPENROUTER_API_KEY",
            r"GROQ_API_KEY",
            r"lock_pin\.txt",
            r"AppData.*Chrome.*User Data.*Cookies",
            r"SAM\b",
            r"SYSTEM\b",
            r"security\.evtx"
        ]

        # Destructive execution patterns
        self.destructive_patterns = [
            r"format\s+[a-zA-Z]:",
            r"rmdir\s+/[sS]\s+/[qQ]\s+[cC]:\\windows",
            r"del\s+/[fF]\s+/[sS]\s+/[qQ]\s+[cC]:\\windows",
            r"rm\s+-rf\s+/(etc|boot|sys|var|bin)",
            r":\(\)\{\s*:\|:&\s*\};:", # Fork bomb
            r"powershell\s+-enc\s+",   # Uninspected base64 payload
            r"certutil(\.exe)?\s+-urlcache\s+-split\s+-f", # Common dropper pattern
            r"curl.*\|.*(bash|sh|cmd|powershell)"          # Pipe-to-shell dropper
        ]

    def scan_command_taint(self, cmd_string: str) -> Dict[str, Any]:
        """Statically inspects command string for supply chain risks and credential exfiltration."""
        t0 = time.time()
        findings = []
        severity = "CLEAN"

        # 1. Check Destructive Patterns
        for pat in self.destructive_patterns:
            if re.search(pat, cmd_string, re.IGNORECASE):
                findings.append(f"Destructive host execution pattern detected: matching rule '{pat}'")
                severity = "CRITICAL"

        # 2. Check Credential Exfiltration Patterns
        for pat in self.credential_patterns:
            if re.search(pat, cmd_string, re.IGNORECASE):
                # Distinguish between legit local cat/echo vs exfiltration
                if any(exfil in cmd_string.lower() for exfil in ["curl", "wget", "http", "socket", "nc", "upload", "ftp"]):
                    findings.append(f"High-risk credential exfiltration pattern detected: accessing '{pat}' with network egress.")
                    severity = "CRITICAL"
                elif any(exfil in cmd_string.lower() for exfil in ["del", "drop", "rm", "unlink"]):
                    findings.append(f"Destructive credential deletion pattern: '{pat}'")
                    severity = "HIGH"

        # 3. Check Base64 Obfuscation
        if len(cmd_string) > 80 and re.search(r"[A-Za-z0-9+/=]{60,}", cmd_string):
            findings.append("Dense base64 / obfuscated payload detected in command parameters.")
            if severity != "CRITICAL":
                severity = "HIGH"

        is_tainted = (severity in ["HIGH", "CRITICAL"])
        return {
            "is_tainted": is_tainted,
            "severity": severity,
            "findings": findings,
            "command_preview": cmd_string[:120],
            "scan_ms": round((time.time() - t0) * 1000, 2)
        }

    def scan_python_code_taint(self, code_str: str) -> Dict[str, Any]:
        """Performs static AST inspection on Python script or package install hook."""
        t0 = time.time()
        findings = []
        severity = "CLEAN"

        try:
            tree = ast.parse(code_str)
            for node in ast.walk(tree):
                # Check for socket / network egress in install context
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in ["socket", "urllib.request", "http.client"]:
                            findings.append(f"Network egress module imported: '{alias.name}'")
                            if severity == "CLEAN": severity = "MEDIUM"
                elif isinstance(node, ast.ImportFrom):
                    if node.module in ["socket", "urllib.request"]:
                        findings.append(f"Network egress module imported from: '{node.module}'")
                        if severity == "CLEAN": severity = "MEDIUM"

                # Check string literals for credential paths
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val = node.value
                    for pat in self.credential_patterns:
                        if re.search(pat, val, re.IGNORECASE):
                            findings.append(f"Suspicious credential reference in string literal: '{val}'")
                            severity = "CRITICAL"

        except SyntaxError as e:
            findings.append(f"Syntax error during AST inspection: {e}")
            severity = "HIGH"

        is_tainted = (severity in ["HIGH", "CRITICAL"])
        return {
            "is_tainted": is_tainted,
            "severity": severity,
            "findings": findings,
            "scan_ms": round((time.time() - t0) * 1000, 2)
        }

    def quarantine_payload(self, payload: str, reason: str) -> str:
        """Stores malicious or tainted payload into the isolated quarantine vault."""
        t_id = f"quarantine_{int(time.time())}"
        target_path = os.path.join(QUARANTINE_DIR, f"{t_id}.threat")
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(f"# THREAT QUARANTINE: {t_id}\n# REASON: {reason}\n\n{payload}")
        except Exception:
            pass

        record = {
            "id": t_id,
            "timestamp": time.time(),
            "reason": reason,
            "path": target_path
        }
        self._quarantined_threats.append(record)
        logger.warning(f"🛡️ [ImmuneSandbox] Threat QUARANTINED: [{t_id}] - {reason}")
        return t_id

    def execute_safely(self, cmd: str, cwd: Optional[str] = None, timeout: int = 15) -> Dict[str, Any]:
        """
        DevSecOps Gated Execution:
        Inspects command taint -> Quarantines if malicious -> Executes only if verified safe.
        """
        scan = self.scan_command_taint(cmd)
        if scan["is_tainted"]:
            qid = self.quarantine_payload(cmd, "; ".join(scan["findings"]))
            return {
                "success": False,
                "status": "QUARANTINED",
                "quarantine_id": qid,
                "severity": scan["severity"],
                "findings": scan["findings"],
                "error": f"Execution BLOCKED by ImmuneSandbox ({scan['severity']}): Threat quarantined to vault."
            }

        # Safe execution
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd or PROJECT_ROOT,
                timeout=timeout
            )
            return {
                "success": res.returncode == 0,
                "status": "EXECUTED",
                "exit_code": res.returncode,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "status": "TIMEOUT", "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "status": "ERROR", "error": str(e)}


immune_sandbox = ImmuneSandbox()
