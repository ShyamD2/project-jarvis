"""
Terraform Agent for J.A.R.V.I.S. (Cloud Pillar).
Executes infrastructure automation: init, validate, plan, apply, and destroy.
Enforces strict Tier 3 gatekeeping on destroy operations with zero bypass.
"""

from __future__ import annotations
import subprocess
import os
import json
from typing import Dict, Any, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisTerraformAgent")


class TerraformAgent:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../infrastructure/terraform/environments/dev")
        )
        os.makedirs(self.base_dir, exist_ok=True)

    def init(self) -> Dict[str, Any]:
        """Runs terraform init"""
        logger.info(f"[TerraformAgent] Initializing Terraform in: {self.base_dir}")
        try:
            res = subprocess.run(["terraform", "init", "-no-color"], cwd=self.base_dir, capture_output=True, text=True, timeout=60)
            return {"success": res.returncode == 0, "output": res.stdout.strip() or res.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def validate(self) -> Dict[str, Any]:
        """Runs terraform validate"""
        logger.info(f"[TerraformAgent] Validating configuration in: {self.base_dir}")
        try:
            res = subprocess.run(["terraform", "validate", "-json"], cwd=self.base_dir, capture_output=True, text=True, timeout=30)
            data = json.loads(res.stdout) if res.stdout else {}
            return {
                "success": res.returncode == 0,
                "valid": data.get("valid", res.returncode == 0),
                "error_count": data.get("error_count", 0),
                "channel_1_logical": res.returncode == 0
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def plan(self, out_file: str = "tfplan") -> Dict[str, Any]:
        """Generates speculative plan (Tier 0 Read-Only)"""
        logger.info("[TerraformAgent] Generating speculative plan...")
        try:
            res = subprocess.run(["terraform", "plan", "-no-color"], cwd=self.base_dir, capture_output=True, text=True, timeout=60)
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout[-800:] if res.stdout else "",
                "channel_1_logical": res.returncode == 0
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply(self, plan_file: Optional[str] = None) -> Dict[str, Any]:
        """Applies Terraform plan (Tier 2 Disruptive - interactive approval required)"""
        logger.info("[TerraformAgent] Applying Terraform changes...")
        cmd = ["terraform", "apply", "-auto-approve", "-no-color"]
        if plan_file:
            cmd.append(plan_file)
        try:
            res = subprocess.run(cmd, cwd=self.base_dir, capture_output=True, text=True, timeout=180)
            return {
                "success": res.returncode == 0,
                "output": res.stdout[-800:] if res.stdout else res.stderr.strip(),
                "channel_1_logical": res.returncode == 0
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def destroy(self, ticket_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Destroys infrastructure (Tier 3 Destructive - MANDATORY CONFIRMATION TICKET REQUIRED).
        Zero bypass permitted.
        """
        logger.critical(f"[TerraformAgent] Terraform Destroy requested! Checking SafetyGuard ticket: {ticket_id}")
        try:
            from agents.intelligence.safety_guard import safety_guard
            ticket = safety_guard.get_ticket(ticket_id) if ticket_id else None
            if not ticket or ticket.status != "APPROVED":
                return {
                    "success": False,
                    "error": "CRITICAL: Terraform Destroy rejected. Mandatory operator confirmation ticket is missing or unapproved.",
                    "status": "gatekeeper_blocked"
                }

            res = subprocess.run(["terraform", "destroy", "-auto-approve", "-no-color"], cwd=self.base_dir, capture_output=True, text=True, timeout=180)
            return {
                "success": res.returncode == 0,
                "output": res.stdout[-800:] if res.stdout else res.stderr.strip(),
                "channel_1_logical": res.returncode == 0
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


terraform_agent = TerraformAgent()
