"""
Security Regression Test Suite: Phase 1 Enterprise Security Hardening
Validates:
  1. Global API Zero-Trust Authentication Middleware (401/403 on protected routes)
  2. Public Health & Telemetry Exemption Whitelist
  3. Emergency Resume Mandatory Passphrase Verification
  4. System Control Sensitive Path Traversal Defense
  5. Zero-Tolerance shell=True Subprocess Invariant (AST Scan)
"""

import os
import ast
import unittest
from fastapi.testclient import TestClient
from services.jarvis_core.main import app
from services.pc_agent.system_control import system_control


class TestPhase1SecurityHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master_secret = "test_security_secret_key_32_bytes_len_1234"
        os.environ["JARVIS_MASTER_SECRET"] = cls.master_secret
        cls.client = TestClient(app)

    def test_unauthenticated_api_request_rejected(self):
        """Invariant: Mutating REST endpoints reject unauthenticated requests with 401."""
        response = self.client.post("/api/v1/actions", json={
            "name": "test_unauth",
            "target_world": "computer",
            "target_agent": "system",
            "tier": "tier_1_soft"
        })
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertEqual(data.get("error"), "UNAUTHORIZED")

    def test_invalid_bearer_token_rejected(self):
        """Invariant: Requests with invalid tokens receive 403 Forbidden."""
        response = self.client.post(
            "/api/v1/actions",
            headers={"Authorization": "Bearer fraudulent_attacker_token_xyz"},
            json={
                "name": "test_invalid_token",
                "target_world": "computer",
                "target_agent": "system",
                "tier": "tier_1_soft"
            }
        )
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data.get("error"), "FORBIDDEN")

    def test_valid_bearer_token_accepted(self):
        """Invariant: Requests with valid Bearer master secret pass authentication guard."""
        response = self.client.post(
            "/api/v1/actions",
            headers={"Authorization": f"Bearer {self.master_secret}"},
            json={
                "name": "system_status_report",
                "target_world": "computer",
                "target_agent": "system",
                "tier": "tier_0_reflex"
            }
        )
        # Should NOT be 401 or 403
        self.assertNotIn(response.status_code, [401, 403])

    def test_valid_x_jarvis_key_accepted(self):
        """Invariant: Requests with valid X-Jarvis-Key header pass authentication guard."""
        response = self.client.post(
            "/api/v1/actions",
            headers={"X-Jarvis-Key": self.master_secret},
            json={
                "name": "system_status_report",
                "target_world": "computer",
                "target_agent": "system",
                "tier": "tier_0_reflex"
            }
        )
        self.assertNotIn(response.status_code, [401, 403])

    def test_public_health_and_metrics_exempted(self):
        """Invariant: Public health and metrics probes do not require credentials."""
        for endpoint in ["/api/v1/health", "/api/v1/metrics", "/api/v1/status"]:
            resp = self.client.get(endpoint)
            self.assertEqual(resp.status_code, 200, f"Public endpoint '{endpoint}' should return 200 without auth")

    def test_emergency_resume_without_passphrase_rejected(self):
        """Invariant: Emergency resume without valid passphrase is blocked with 403."""
        resp = self.client.post(
            "/api/v1/emergency/resume",
            headers={"Authorization": f"Bearer {self.master_secret}"},
            json={"passphrase": "wrong_password"}
        )
        self.assertEqual(resp.status_code, 403)

    def test_system_control_blocks_sensitive_path_traversal(self):
        """Invariant: SystemControl blocks read/preview of sensitive credentials and system files."""
        sensitive_paths = [
            r"C:\Users\admin\.aws\credentials",
            r"C:\Users\admin\.ssh\id_rsa",
            r"C:\Windows\System32\config\SAM",
            r"/etc/shadow",
            r"../.env",
            r".env"
        ]
        for path in sensitive_paths:
            res = system_control.read_file_preview(path)
            self.assertFalse(res.get("success"), f"Path '{path}' must be blocked.")
            self.assertIn("SECURITY_ERROR", res.get("error", ""))

    def test_zero_shell_true_occurrences_across_codebase(self):
        """Invariant: Zero instances of shell=True exist across all production Python modules."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        violations = []
        production_dirs = ["agents", "services", "shared", "devices"]

        class ShellTrueFinder(ast.NodeVisitor):
            def __init__(self, filename):
                self.filename = filename

            def visit_Call(self, node):
                for kw in node.keywords:
                    if kw.arg == "shell" and getattr(kw.value, "value", None) is True:
                        violations.append(f"{self.filename}:{node.lineno}")
                self.generic_visit(node)

        for p_dir in production_dirs:
            full_dir = os.path.join(project_root, p_dir)
            if not os.path.exists(full_dir):
                continue
            for root, _, files in os.walk(full_dir):
                for f in files:
                    if f.endswith(".py"):
                        full_p = os.path.join(root, f)
                        try:
                            with open(full_p, "r", encoding="utf-8", errors="ignore") as fp:
                                tree = ast.parse(fp.read(), filename=full_p)
                            ShellTrueFinder(os.path.relpath(full_p, project_root)).visit(tree)
                        except Exception:
                            pass

        self.assertEqual(violations, [], f"Found forbidden shell=True AST calls: {violations}")


if __name__ == "__main__":
    unittest.main()
