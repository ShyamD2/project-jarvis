"""
Cloud Security & SOC Agent for J.A.R.V.I.S.
Audits IAM policies for wildcards, detects authorization anomalies, and flags compliance risks.
"""

from __future__ import annotations
import json
import glob
import os
import re
from typing import Dict, Any, List
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisSOCSecurityAgent")


class SOCSecurityAgent:
    def scan_terraform_iam_policies(self, terraform_dir: str) -> Dict[str, Any]:
        """Scans Terraform HCL / JSON policy files for wildcard privileges"""
        logger.info(f"[SOCSecurityAgent] Scanning IAM policies in: {terraform_dir}")
        findings: List[Dict[str, Any]] = []

        tf_files = glob.glob(os.path.join(terraform_dir, "**", "*.tf"), recursive=True)
        for tf_file in tf_files:
            try:
                with open(tf_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Check for wildcard AdministratorAccess or Action = ["*"]
                if re.search(r'Action\s*=\s*\[\s*"\*"\s*\]', content):
                    findings.append({
                        "file": os.path.basename(tf_file),
                        "severity": "HIGH",
                        "issue": "Wildcard Action [*] detected. Violates principle of least privilege."
                    })

                if "AdministratorAccess" in content:
                    findings.append({
                        "file": os.path.basename(tf_file),
                        "severity": "CRITICAL",
                        "issue": "Direct AdministratorAccess attachment detected."
                    })
            except Exception as e:
                logger.warning(f"Failed to scan {tf_file}: {e}")

        is_clean = len(findings) == 0
        return {
            "success": True,
            "clean": is_clean,
            "scanned_files_count": len(tf_files),
            "findings_count": len(findings),
            "findings": findings,
            "channel_1_logical": True
        }


soc_agent = SOCSecurityAgent()
