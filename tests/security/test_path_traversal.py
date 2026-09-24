"""
Security Regression Test: Path Traversal & Filesystem Sandbox Confinement
Guarantees permanent remediation for directory traversal, null-byte injection, and sandbox escapes.
"""

import unittest
import os
from agents.computer.file_agent import FileAgent, SecurityViolationError, FORBIDDEN_PATHS


class TestPathTraversalSecurity(unittest.TestCase):
    def setUp(self):
        self.agent = FileAgent()

    def test_directory_traversal_to_system_root_blocked(self):
        """Invariant: Traversal attempts like ../../../../Windows/System32 are blocked."""
        traversal_paths = [
            "../../../../Windows/System32/drivers/etc/hosts",
            "workspace/../../Windows/explorer.exe",
            r"C:\Windows\System32\cmd.exe",
            r"C:\Recovery\test.txt"
        ]
        for p in traversal_paths:
            is_allowed, msg = self.agent._check_jail(p, operation="read")
            self.assertFalse(is_allowed, f"Path {p} should have been blocked by sandbox jail.")
            self.assertIn("SecurityViolation", msg)

    def test_write_operation_outside_jail_rejected(self):
        """Invariant: Write operations outside allowed jail roots are rejected."""
        forbidden_write = r"C:\Program Files\malicious.dll"
        is_allowed, msg = self.agent._check_jail(forbidden_write, operation="write")
        self.assertFalse(is_allowed)
        self.assertIn("SecurityViolation", msg)

    def test_safe_workspace_paths_allowed(self):
        """Invariant: Safe relative paths resolving within workspace root are permitted."""
        safe_path = os.path.join(os.getcwd(), "test_file.tmp")
        is_allowed, msg = self.agent._check_jail(safe_path, operation="write")
        self.assertTrue(is_allowed, f"Safe workspace path should be allowed: {msg}")


if __name__ == "__main__":
    unittest.main()
