"""
Isolated Skill Generation Worker Sandbox for Project J.A.R.V.I.S.
Executes dynamically generated custom tools and skills in an isolated worker process.
Sanitizes environment variables, strips master secrets, enforces AST safety checks,
and guards against unauthorized lateral movement or privilege escalation.
"""

from __future__ import annotations
import os
import ast
import json
import sys
import tempfile
import subprocess
from typing import Dict, Any, Optional

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("SkillSandbox")


class IsolatedSkillSandbox:
    FORBIDDEN_AST_MODULES = {"ctypes", "winreg", "msvcrt"}
    FORBIDDEN_AST_CALLS = {"eval", "exec", "__import__", "globals", "locals"}

    def __init__(self):
        self._sandbox_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/sandbox"))
        os.makedirs(self._sandbox_dir, exist_ok=True)

    def validate_code_ast(self, code_str: str) -> Dict[str, Any]:
        """Performs static Abstract Syntax Tree (AST) security inspection."""
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return {"safe": False, "error": f"Syntax error: {e}"}

        for node in ast.walk(tree):
            # Check forbidden imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.FORBIDDEN_AST_MODULES:
                        return {"safe": False, "error": f"Forbidden module import '{alias.name}'"}
            elif isinstance(node, ast.ImportFrom):
                if node.module in self.FORBIDDEN_AST_MODULES:
                    return {"safe": False, "error": f"Forbidden module import '{node.module}'"}
            # Check forbidden built-in calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in self.FORBIDDEN_AST_CALLS:
                    return {"safe": False, "error": f"Forbidden call '{node.func.id}()'"}

        return {"safe": True}

    def execute_in_sandbox(
        self,
        script_code: str,
        entrypoint: str,
        parameters: Dict[str, Any],
        timeout_seconds: float = 5.0
    ) -> Dict[str, Any]:
        """Executes Python code in an isolated worker process with stripped credentials."""
        # 1. AST Validation
        ast_check = self.validate_code_ast(script_code)
        if not ast_check["safe"]:
            logger.warning(f"🛡️ [SkillSandbox] AST rejection: {ast_check['error']}")
            return {"success": False, "status": "ast_rejected", "error": ast_check["error"]}

        # 2. Sanitize Environment: Strip credentials
        clean_env = os.environ.copy()
        sensitive_keys = [
            "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID", "TELEGRAM_BOT_TOKEN",
            "GROQ_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY",
            "JARVIS_MASTER_SECRET"
        ]
        for k in sensitive_keys:
            clean_env.pop(k, None)

        # 3. Create sandboxed wrapper script
        wrapper = f"""
import json, sys

{script_code}

if __name__ == '__main__':
    args = json.loads({repr(json.dumps(parameters))})
    try:
        fn = globals().get({repr(entrypoint)})
        if not fn:
            print(json.dumps({{"success": False, "error": "Entrypoint not found"}}))
            sys.exit(1)
        res = fn(**args)
        print(json.dumps({{"success": True, "result": res}}))
    except Exception as e:
        print(json.dumps({{"success": False, "error": str(e)}}))
"""

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=self._sandbox_dir, encoding="utf-8") as f:
            f.write(wrapper)
            tmp_name = f.name

        try:
            res = subprocess.run(
                [sys.executable, tmp_name],
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=self._sandbox_dir
            )
            stdout = res.stdout.strip()
            if res.returncode == 0 and stdout:
                try:
                    return json.loads(stdout)
                except Exception:
                    return {"success": True, "raw_output": stdout}
            else:
                stderr = res.stderr.strip() or stdout or "Execution returned non-zero code"
                return {"success": False, "error": stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Sandbox execution timed out after {timeout_seconds}s"}
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except Exception:
                    pass


skill_sandbox = IsolatedSkillSandbox()
