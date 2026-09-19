"""
Custom Tool: test_ping_verifier
Auto-synthesized by J.A.R.V.I.S. SkillSynthesizer.
"""

import subprocess
import asyncio
from typing import Dict, Any
from services.brain.tools.base import JarvisTool, ToolDefinition
from shared.schemas.action_envelope import ActionTier, TargetWorld
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("Tool_test_ping_verifier")


class TestPingVerifierTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="test_ping_verifier",
                description="Verifies ping to local loopback",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "argument": {"type": "string", "default": ""},
                    "timeout_seconds": {"type": "integer", "default": 15}
                },
                risk_level="LOW",
                timeout_seconds=20
            )
        )
        self._preset_commands = ["ping -n 1 127.0.0.1"]

    async def execute(self, argument: str = "", timeout_seconds: int = 15, **kwargs) -> Dict[str, Any]:
        logger.info(f"Executing synthesized skill 'test_ping_verifier' with arg='{argument}'")
        outputs = []
        loop = asyncio.get_event_loop()
        
        for cmd in self._preset_commands:
            formatted_cmd = cmd.replace("{arg}", argument) if argument else cmd
            try:
                res = await loop.run_in_executor(
                    None,
                    lambda c=formatted_cmd: subprocess.run(
                        c, shell=True, capture_output=True, text=True, timeout=timeout_seconds
                    )
                )
                outputs.append({
                    "command": formatted_cmd,
                    "stdout": res.stdout.strip(),
                    "stderr": res.stderr.strip(),
                    "exit_code": res.returncode
                })
            except Exception as e:
                outputs.append({"command": formatted_cmd, "error": str(e), "exit_code": -1})

        success = all(o.get("exit_code") == 0 for o in outputs) if outputs else True
        return {
            "success": success,
            "tool": "test_ping_verifier",
            "steps_executed": len(outputs),
            "outputs": outputs
        }


tool_instance = TestPingVerifierTool()
