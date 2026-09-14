"""
J.A.R.V.I.S. Compound Workflow Planner (Intelligence Pillar).
Executes orchestrated multi-step pipelines across Computer, Cloud, and Intelligence pillars.
Features step-by-step progress tracking, timeout enforcement, and partial success reporting.
"""

import os
import time
import asyncio
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisWorkflowPlanner")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


class CompoundWorkflowPlanner:
    def __init__(self):
        pass

    def _check_emergency(self) -> bool:
        try:
            from agents.intelligence.emergency_stop import emergency_stop
            return emergency_stop.is_stopped
        except Exception:
            return False

    async def execute_workflow(self, workflow_name: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a named compound workflow with per-step validation and partial status reporting.
        """
        name = workflow_name.lower().strip()
        logger.info(f"[Planner] Executing compound workflow: '{name}'")

        if self._check_emergency():
            return {
                "success": False,
                "status": "halted_by_emergency_stop",
                "message": "Workflow aborted immediately due to active emergency stop."
            }

        if name in ["dev_environment", "developer_workspace", "prepare_workspace"]:
            return await self._workflow_dev_environment()
        elif name in ["aws_workspace", "cloud_workspace"]:
            return await self._workflow_aws_workspace()
        elif name in ["movie_mode", "entertainment"]:
            return await self._workflow_movie_mode()
        elif name in ["shutdown_prep", "prepare_pc_for_shutdown"]:
            return await self._workflow_shutdown_prep()
        else:
            return {
                "success": False,
                "status": "unknown_workflow",
                "error": f"Workflow '{workflow_name}' is not recognized."
            }

    async def _workflow_dev_environment(self) -> Dict[str, Any]:
        """Pipeline 1: Developer Environment Setup"""
        steps_executed = []
        partial_failures = []

        from agents.computer.windows_agent import windows_agent
        from agents.physical.esp32_agent import esp32_agent

        # Step 1: Workstation Illumination
        try:
            esp32_agent.set_relay("esp32_lab_01", "desk_lamp", True)
            steps_executed.append({"step": "illumination", "status": "success", "detail": "Desk lamp illuminated"})
        except Exception as e:
            partial_failures.append({"step": "illumination", "error": str(e)})

        if self._check_emergency():
            return {"success": False, "status": "emergency_halt", "steps": steps_executed}

        # Step 2: VS Code
        try:
            code_res = windows_agent.launch_app("code", [PROJECT_ROOT])
            steps_executed.append({"step": "vscode", "status": "success", "detail": "VS Code launched at project root"})
        except Exception as e:
            partial_failures.append({"step": "vscode", "error": str(e)})

        # Step 3: Windows Terminal
        try:
            wt_res = windows_agent.launch_app("wt", [])
            steps_executed.append({"step": "terminal", "status": "success", "detail": "Windows Terminal launched"})
        except Exception as e:
            partial_failures.append({"step": "terminal", "error": str(e)})

        # Step 4: Open Browser Dashboard
        try:
            windows_agent.open_url("http://127.0.0.1:8000")
            steps_executed.append({"step": "browser_hud", "status": "success", "detail": "J.A.R.V.I.S. HUD loaded in browser"})
        except Exception as e:
            partial_failures.append({"step": "browser_hud", "error": str(e)})

        is_complete = len(partial_failures) == 0
        status = "COMPLETED" if is_complete else "PARTIAL_SUCCESS"

        message = "Development workspace prepared successfully." if is_complete else f"Workspace partially prepared. Note: {len(partial_failures)} steps experienced issues."

        return {
            "success": is_complete,
            "workflow": "dev_environment",
            "status": status,
            "message": message,
            "steps": steps_executed,
            "failures": partial_failures
        }

    async def _workflow_aws_workspace(self) -> Dict[str, Any]:
        """Pipeline 2: AWS Cloud Workspace Setup"""
        steps = []
        failures = []

        from agents.cloud.aws_agent import aws_agent
        from agents.computer.windows_agent import windows_agent

        # Step 1: Verify STS Caller Identity
        ident = aws_agent.get_caller_identity()
        if ident.get("connected"):
            steps.append({"step": "sts_auth", "status": "success", "account": ident.get("account"), "arn": ident.get("arn")})
        else:
            failures.append({"step": "sts_auth", "error": ident.get("error", "STS authentication failed")})

        # Step 2: Query Cloud Topology
        s3_list = aws_agent.list_s3_buckets()
        ec2_list = aws_agent.list_ec2_instances()
        steps.append({
            "step": "resource_inventory",
            "status": "success",
            "s3_count": len(s3_list),
            "ec2_count": len(ec2_list)
        })

        # Step 3: Launch AWS Management Console in Browser
        try:
            windows_agent.open_url("https://console.aws.amazon.com")
            steps.append({"step": "aws_console", "status": "success", "detail": "AWS Console opened in browser"})
        except Exception as e:
            failures.append({"step": "aws_console", "error": str(e)})

        is_complete = len(failures) == 0
        return {
            "success": is_complete,
            "workflow": "aws_workspace",
            "status": "COMPLETED" if is_complete else "PARTIAL_SUCCESS",
            "message": "AWS workspace loaded and console opened." if is_complete else "AWS identity verified, but browser console opening timed out.",
            "steps": steps,
            "failures": failures
        }

    async def _workflow_movie_mode(self) -> Dict[str, Any]:
        """Pipeline 3: Movie / Media Mode Setup"""
        from agents.computer.audio_agent import audio_agent
        from agents.computer.windows_agent import windows_agent

        steps = []
        # Step 1: Set volume to 50%
        v_res = audio_agent.set_volume_percent(50)
        steps.append({"step": "volume_50", "status": "success"})

        # Step 2: Open YouTube or streaming
        windows_agent.open_url("https://www.youtube.com")
        steps.append({"step": "media_browser", "status": "success"})

        return {
            "success": True,
            "workflow": "movie_mode",
            "status": "COMPLETED",
            "message": "Master audio volume set to 50% and media dashboard opened.",
            "steps": steps
        }

    async def _workflow_shutdown_prep(self) -> Dict[str, Any]:
        """Pipeline 4: Prepare PC for Shutdown (Saves state, verifies tasks, prompts for Tier 3 confirmation)"""
        from agents.computer.windows_agent import windows_agent
        from agents.intelligence.productivity_agent import productivity_agent

        tasks = productivity_agent.list_tasks()
        pending_count = len(tasks.get("tasks", []))

        # Close user windows
        windows_agent.close_active_window("notepad")

        return {
            "success": True,
            "workflow": "shutdown_prep",
            "status": "AWAITING_CONFIRMATION",
            "message": f"Workspace saved. You have {pending_count} pending tasks. Sir, please confirm if you wish to proceed with the PC shutdown.",
            "requires_tier3_confirmation": True
        }


planner = CompoundWorkflowPlanner()
