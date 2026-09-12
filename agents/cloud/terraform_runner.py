"""
Terraform Agent for J.A.R.V.I.S.
Executes infrastructure-as-code automation: validate, plan, apply, and drift detection.
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

    def validate(self) -> Dict[str, Any]:
        """Runs terraform validate"""
        logger.info(f"[TerraformAgent] Validating configuration in: {self.base_dir}")
        try:
            res = subprocess.run(
                ["terraform", "validate", "-json"],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            data = json.loads(res.stdout) if res.stdout else {}
            return {
                "success": res.returncode == 0,
                "valid": data.get("valid", res.returncode == 0),
                "error_count": data.get("error_count", 0),
                "channel_1_logical": res.returncode == 0
            }
        except Exception as e:
            logger.error(f"[TerraformAgent] validate failed: {e}")
            return {"success": False, "error": str(e)}

    def plan(self, out_file: str = "tfplan") -> Dict[str, Any]:
        """Generates speculative plan"""
        logger.info(f"[TerraformAgent] Generating speculative plan...")
        try:
            res = subprocess.run(
                ["terraform", "plan", "-no-color"],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout[-800:] if res.stdout else "",
                "channel_1_logical": res.returncode == 0
            }
        except Exception as e:
            logger.error(f"[TerraformAgent] plan failed: {e}")
            return {"success": False, "error": str(e)}


terraform_agent = TerraformAgent()
