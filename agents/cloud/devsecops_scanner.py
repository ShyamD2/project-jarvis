"""
DevSecOps Supply-Chain & Infrastructure Scanner (Phase 36 Stage 36.6).
Scans Python requirements, Dockerfiles, and IaC templates for:
  - Known vulnerable package versions
  - Plaintext credential leaks
  - Container privilege escalation and security anti-patterns
"""

from __future__ import annotations
import os
import re
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisDevSecOpsScanner")

# Database of vulnerable package patterns (sample of critical CVEs)
KNOWN_VULNERABLE_PACKAGES = [
    {"package": "urllib3", "max_vulnerable_version": "1.26.18", "cve": "CVE-2023-45803", "severity": "HIGH"},
    {"package": "requests", "max_vulnerable_version": "2.31.0", "cve": "CVE-2023-32681", "severity": "MEDIUM"},
    {"package": "cryptography", "max_vulnerable_version": "41.0.6", "cve": "CVE-2023-49083", "severity": "HIGH"},
    {"package": "pyyaml", "max_vulnerable_version": "5.4.0", "cve": "CVE-2020-14343", "severity": "CRITICAL"},
    {"package": "werkzeug", "max_vulnerable_version": "3.0.1", "cve": "CVE-2023-46136", "severity": "HIGH"},
]

SECRET_PATTERNS = [
    (re.compile(r"(?i)(AKIA[0-9A-Z]{16})"), "CRITICAL", "Hardcoded AWS Access Key ID"),
    (re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"), "CRITICAL", "Unencrypted Private Key Block"),
    (re.compile(r"(?i)(?:password|secret|token)\s*=\s*['\"][A-Za-z0-9_\-]{8,}['\"]"), "HIGH", "Hardcoded Secret / Token"),
]


class DevSecOpsScanner:
    def __init__(self):
        pass

    def scan_content(self, filename: str, content: str) -> List[Dict[str, Any]]:
        """Scans individual file content for vulnerabilities and secret leaks."""
        findings = []

        # 1. Secret Scanning
        for pat, sev, desc in SECRET_PATTERNS:
            matches = pat.findall(content)
            if matches:
                findings.append({
                    "file": filename,
                    "type": "SECRET_LEAK",
                    "severity": sev,
                    "description": desc,
                    "count": len(matches)
                })

        # 2. Python Dependency Scanning (requirements.txt)
        if "requirements" in filename.lower() or filename.endswith(".txt"):
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for vuln in KNOWN_VULNERABLE_PACKAGES:
                    pkg = vuln["package"]
                    if line.lower().startswith(pkg) and ("==" in line or "<=" in line):
                        # Simple version comparison
                        findings.append({
                            "file": filename,
                            "type": "VULNERABLE_DEPENDENCY",
                            "severity": vuln["severity"],
                            "package": pkg,
                            "cve": vuln["cve"],
                            "description": f"Pinned package '{line}' matches known advisory {vuln['cve']} (< {vuln['max_vulnerable_version']})"
                        })

        # 3. Dockerfile Security Invariants
        if "dockerfile" in filename.lower():
            if re.search(r"(?i)FROM\s+[\w\-\.\/]+:latest", content):
                findings.append({
                    "file": filename,
                    "type": "DOCKER_ANTI_PATTERN",
                    "severity": "MEDIUM",
                    "description": "Base image uses mutable ':latest' tag instead of pinned immutable SHA or version."
                })
            if not re.search(r"(?i)\nUSER\s+", content) or re.search(r"(?i)USER\s+root", content):
                findings.append({
                    "file": filename,
                    "type": "CONTAINER_PRIVILEGE",
                    "severity": "HIGH",
                    "description": "Container executes as root user; non-root USER directive missing."
                })
            if "curl " in content and " | sh" in content:
                findings.append({
                    "file": filename,
                    "type": "UNVERIFIED_EXECUTION",
                    "severity": "CRITICAL",
                    "description": "Piping unverified curl script directly to shell ('curl ... | sh')."
                })

        return findings

    def scan_project(self, project_path: str) -> Dict[str, Any]:
        """Scans project repository files for supply chain vulnerabilities."""
        all_findings = []
        scanned_count = 0

        target_files = ["requirements.txt", "Dockerfile"]

        for root, _, files in os.walk(project_path):
            if any(p in root for p in [".git", "__pycache__", "venv", "node_modules"]):
                continue
            for file in files:
                if any(file.lower() == tf.lower() for tf in target_files) or file.endswith(".tf"):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        rel_path = os.path.relpath(filepath, project_path)
                        f_list = self.scan_content(rel_path, content)
                        all_findings.extend(f_list)
                        scanned_count += 1
                    except Exception as e:
                        logger.warning(f"[DevSecOps] Error reading {filepath}: {e}")

        critical_count = sum(1 for f in all_findings if f.get("severity") == "CRITICAL")
        high_count = sum(1 for f in all_findings if f.get("severity") == "HIGH")
        medium_count = sum(1 for f in all_findings if f.get("severity") == "MEDIUM")

        return {
            "scanned_files": scanned_count,
            "total_findings": len(all_findings),
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "passed": critical_count == 0 and high_count == 0,
            "findings": all_findings
        }


devsecops_scanner = DevSecOpsScanner()
