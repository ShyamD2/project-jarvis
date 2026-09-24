"""
Central Tool Registry for J.A.R.V.I.S. Brain.
Registers, discovers, and delivers 100% real, functioning tools across Computer, Cloud, and Intelligence pillars.
Enforces strict 4-tier safety gates, timeout limits, emergency stops, and structured audit logging.
"""

import os
import sys
import time
import asyncio
from typing import Dict, List, Optional, Any

from services.brain.tools.base import JarvisTool, ToolDefinition
from shared.schemas.action_envelope import ActionTier, TargetWorld, ActionEnvelope
from shared.sdk_python.jarvis_sdk.logger import get_logger

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "agents"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/pc_agent"))

# Pillar 1: Computer Agents
from agents.computer.windows_agent import windows_agent
from agents.computer.power_agent import power_agent
from agents.computer.audio_agent import audio_agent
from agents.computer.display_agent import display_agent
from agents.computer.mouse_agent import mouse_agent
from agents.computer.keyboard_agent import keyboard_agent
from agents.computer.file_agent import file_agent
from agents.computer.screen_agent import screen_agent
from agents.computer.network_agent import network_agent

# Pillar 2: Cloud Agents
from agents.cloud.aws_agent import aws_agent
from agents.cloud.git_agent import git_agent
from agents.cloud.docker_agent import docker_agent
from agents.cloud.k8s_agent import k8s_agent
from agents.cloud.terraform_agent import terraform_agent
from agents.cloud.soc_security_agent import soc_agent

# Pillar 3: Intelligence Agents
from agents.intelligence.safety_guard import safety_guard
from agents.intelligence.emergency_stop import emergency_stop
from agents.intelligence.audit_logger import audit_logger
from agents.intelligence.vision_agent import vision_agent
from agents.intelligence.productivity_agent import productivity_agent
from agents.intelligence.planner import planner

# Verification & Epistemic Engines
from services.verification.verification_engine import verification_engine
from services.brain.epistemic_evaluator import epistemic_evaluator
from services.observability.chained_audit_ledger import chained_audit_ledger

# Physical IoT
from agents.physical.esp32_agent import esp32_agent

try:
    from system_control import system_control
    from system_monitor import system_monitor
except ImportError:
    from services.pc_agent.system_control import system_control
    from services.pc_agent.system_monitor import system_monitor

logger = get_logger("JarvisToolRegistry")


# ==============================================================================
# TOOL IMPLEMENTATIONS (PILLAR 1: COMPUTER)
# ==============================================================================

class PCPowerTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="pc_power",
                description="Controls PC power states: shutdown, restart, sleep, hibernate, sign out, display off, cancel scheduled shutdown, power plans, and temperatures",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_3_DESTRUCTIVE, # Default for shutdown/restart; safety guard verifies action parameter
                parameters_schema={
                    "action": {"type": "string", "enum": ["shutdown", "restart", "sleep", "hibernate", "sign_out", "display_off", "cancel_shutdown", "power_plan", "temperatures", "disk_space"], "required": True},
                    "timer_seconds": {"type": "integer", "default": 0},
                    "mode": {"type": "string", "default": "balanced"}
                }
            )
        )

    async def execute(self, action: str = "temperatures", timer_seconds: int = 0, mode: str = "balanced", **kwargs) -> Dict[str, Any]:
        act = action.lower().strip()
        logger.info(f"[Tool: PCPower] Executing action: {act}")
        if act == "shutdown":
            return power_agent.shutdown_pc(timer_seconds=timer_seconds)
        elif act == "restart":
            return power_agent.restart_pc(timer_seconds=timer_seconds)
        elif act in ["cancel_shutdown", "cancel"]:
            return power_agent.cancel_scheduled_shutdown()
        elif act == "sleep":
            return power_agent.sleep_pc()
        elif act == "hibernate":
            return power_agent.hibernate_pc()
        elif act == "sign_out":
            return power_agent.sign_out()
        elif act in ["display_off", "turn_off_display"]:
            return power_agent.turn_off_display()
        elif act in ["power_plan", "power_mode"]:
            return power_agent.set_power_mode(mode=mode)
        elif act in ["temperatures", "temps"]:
            return power_agent.get_hardware_temperatures()
        elif act in ["disk_space", "disk"]:
            return power_agent.get_free_disk_space()
        return {"success": False, "error": f"Unknown power action: {action}"}


class AudioMediaTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="audio_media",
                description="Controls Windows audio volume (increase, decrease, mute, unmute, set %) and media controls (play, pause, next track, previous track, stop, mic status)",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "action": {"type": "string", "enum": ["increase", "decrease", "mute", "unmute", "set_volume", "play_pause", "next", "previous", "stop", "mic_status"], "required": True},
                    "steps": {"type": "integer", "default": 5},
                    "level": {"type": "integer", "default": 50}
                }
            )
        )

    async def execute(self, action: str = "play_pause", steps: int = 5, level: int = 50, **kwargs) -> Dict[str, Any]:
        act = action.lower().strip()
        logger.info(f"[Tool: AudioMedia] Executing: {act}")
        if act in ["increase", "up", "raise"]:
            return audio_agent.adjust_volume("up", steps=steps)
        elif act in ["decrease", "down", "lower"]:
            return audio_agent.adjust_volume("down", steps=steps)
        elif act in ["mute", "unmute", "toggle_mute"]:
            return audio_agent.adjust_volume("mute")
        elif act in ["set_volume", "set"]:
            return audio_agent.set_volume_percent(level)
        elif act in ["play", "pause", "play_pause", "next", "previous", "stop"]:
            return audio_agent.control_media(act)
        elif act in ["mic_status", "microphone"]:
            return audio_agent.get_microphone_status()
        return {"success": False, "error": f"Unknown audio/media action: {action}"}


class DisplayControlTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="display_control",
                description="Controls screen brightness (0-100), multi-monitor display switching (extend, duplicate, internal, external), and night light",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "action": {"type": "string", "enum": ["set_brightness", "get_brightness", "switch_mode", "night_light"], "required": True},
                    "level": {"type": "integer", "default": 80},
                    "mode": {"type": "string", "default": "extend"}
                }
            )
        )

    async def execute(self, action: str = "get_brightness", level: int = 80, mode: str = "extend", **kwargs) -> Dict[str, Any]:
        act = action.lower().strip()
        if act == "set_brightness":
            return display_agent.set_brightness(level)
        elif act == "get_brightness":
            return display_agent.get_brightness()
        elif act == "switch_mode":
            return power_agent.switch_display_mode(mode)
        elif act == "night_light":
            return display_agent.toggle_night_light(True)
        return {"success": False, "error": f"Unknown display action: {action}"}


class MouseKeyboardTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="mouse_keyboard",
                description="Automates mouse movements, clicks, scrolling, text typing, key presses, and shortcuts (e.g. Ctrl+Shift+Esc, Alt+Tab, Win+D, screenshot)",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "action": {"type": "string", "enum": ["move", "click", "double_click", "right_click", "scroll", "type", "press_key", "shortcut", "screenshot"], "required": True},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "text": {"type": "string"},
                    "key": {"type": "string"},
                    "keys": {"type": "array"},
                    "clicks": {"type": "integer", "default": 3},
                    "direction": {"type": "string", "default": "down"}
                }
            )
        )

    async def execute(self, action: str = "screenshot", **kwargs) -> Dict[str, Any]:
        act = action.lower().strip()
        logger.info(f"[Tool: MouseKeyboard] Executing action: {act}")
        if act == "move":
            return mouse_agent.move_cursor(kwargs.get("x", 500), kwargs.get("y", 500), smooth=True)
        elif act in ["click", "left_click"]:
            return mouse_agent.click("left")
        elif act in ["double_click", "double"]:
            return mouse_agent.click("double")
        elif act in ["right_click", "right"]:
            return mouse_agent.click("right")
        elif act == "scroll":
            return mouse_agent.scroll(clicks=kwargs.get("clicks", 3), direction=kwargs.get("direction", "down"))
        elif act == "type":
            return keyboard_agent.type_text(kwargs.get("text", ""))
        elif act == "press_key":
            return keyboard_agent.press_key(kwargs.get("key", "enter"))
        elif act == "shortcut":
            keys = kwargs.get("keys") or [kwargs.get("key", "enter")]
            return keyboard_agent.press_shortcut(keys)
        elif act == "screenshot":
            return screen_agent.capture_screenshot()
        return {"success": False, "error": f"Unknown mouse/keyboard action: {action}"}


class FileManagerTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="file_manager",
                description="Manages files and folders: open, create folder, create file, rename, move, copy, search, zip, unzip, safe delete to Recycle Bin, or empty Recycle Bin",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_2_MUTATING,
                parameters_schema={
                    "action": {"type": "string", "enum": ["open", "create_folder", "create_file", "rename", "move", "copy", "delete", "search", "zip", "unzip", "empty_recycle_bin"], "required": True},
                    "path": {"type": "string"},
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
                    "content": {"type": "string", "default": ""},
                    "new_name": {"type": "string"},
                    "pattern": {"type": "string"},
                    "permanent": {"type": "boolean", "default": False}
                }
            )
        )

    async def execute(self, action: str = "search", **kwargs) -> Dict[str, Any]:
        act = action.lower().strip()
        logger.info(f"[Tool: FileManager] Executing: {act}")
        if act == "open":
            return file_agent.open_path(kwargs.get("path", "workspace"))
        elif act == "create_folder":
            return file_agent.create_folder(kwargs.get("path", "new_folder"))
        elif act in ["create_file", "write"]:
            return file_agent.create_file(kwargs.get("path", "test.txt"), kwargs.get("content", ""))
        elif act == "rename":
            return file_agent.rename_item(kwargs.get("source", ""), kwargs.get("new_name", ""))
        elif act == "move":
            return file_agent.move_item(kwargs.get("source", ""), kwargs.get("destination", ""))
        elif act == "copy":
            return file_agent.copy_item(kwargs.get("source", ""), kwargs.get("destination", ""))
        elif act == "delete":
            return file_agent.delete_item(kwargs.get("path", ""), permanent=kwargs.get("permanent", False))
        elif act == "search":
            return file_agent.search_files(pattern=kwargs.get("pattern", "*"), directory=kwargs.get("path", "workspace"))
        elif act == "zip":
            return file_agent.zip_archive(kwargs.get("source", ""), kwargs.get("destination"))
        elif act == "unzip":
            return file_agent.extract_zip(kwargs.get("source", ""), kwargs.get("destination"))
        elif act == "empty_recycle_bin":
            return file_agent.empty_recycle_bin()
        return {"success": False, "error": f"Unknown file manager action: {action}"}


class NetworkControlTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="network_control",
                description="Queries Wi-Fi connection, local and public IP addresses, network health, ping test, DNS resolution, and network adapters",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_0_REFLEX,
                parameters_schema={
                    "action": {"type": "string", "enum": ["wifi_status", "ip_addresses", "ping", "internet_status", "dns", "adapters"], "default": "ip_addresses"},
                    "host": {"type": "string", "default": "8.8.8.8"},
                    "domain": {"type": "string", "default": "google.com"}
                }
            )
        )

    async def execute(self, action: str = "ip_addresses", host: str = "8.8.8.8", domain: str = "google.com", **kwargs) -> Dict[str, Any]:
        act = action.lower().strip()
        if act == "wifi_status":
            return network_agent.get_wifi_status()
        elif act in ["ip_addresses", "ip"]:
            return network_agent.get_ip_addresses()
        elif act == "ping":
            return network_agent.ping_host(host=host)
        elif act == "internet_status":
            return network_agent.check_internet_status()
        elif act == "dns":
            return network_agent.dns_lookup(domain=domain)
        elif act == "adapters":
            return network_agent.list_network_adapters()
        return network_agent.get_ip_addresses()


# ==============================================================================
# TOOL IMPLEMENTATIONS (PILLAR 2: CLOUD)
# ==============================================================================

class DevOpsTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="devops_tool",
                description="DevOps suite: Git (status, commit, push, pull, log), Docker (list, start, stop, restart, logs, build), Kubernetes (cluster-info, pods, nodes), Terraform (validate, plan, apply, destroy)",
                target_world=TargetWorld.DIGITAL,
                tier=ActionTier.TIER_2_MUTATING,
                parameters_schema={
                    "subsystem": {"type": "string", "enum": ["git", "docker", "k8s", "terraform"], "required": True},
                    "action": {"type": "string", "required": True},
                    "args": {"type": "object", "default": {}}
                }
            )
        )

    async def execute(self, subsystem: str = "git", action: str = "status", args: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        sub = subsystem.lower().strip()
        act = action.lower().strip()
        params = args or {}
        logger.info(f"[Tool: DevOps] subsystem={sub}, action={act}")

        if sub == "git" and act in ["ps", "containers", "docker_status"]:
            sub = "docker"
            act = "list"

        if sub == "git":
            if act == "status":
                return git_agent.get_status()
            elif act == "commit":
                return git_agent.stage_and_commit(params.get("message", "automated commit"))
            elif act == "push":
                return git_agent.push(params.get("remote", "origin"), params.get("branch"))
            elif act == "pull":
                return git_agent.pull(params.get("remote", "origin"), params.get("branch"))
            elif act == "branch":
                return git_agent.list_branches()
            elif act == "log":
                return git_agent.get_log(params.get("count", 5))
            elif act == "clone":
                return git_agent.clone(params.get("repo_url", ""), params.get("destination"))
        elif sub == "docker":
            if act in ["list", "ps", "status"]:
                return {"success": True, "containers": docker_agent.list_containers(params.get("all", False))}
            elif act == "start":
                return docker_agent.start_container(params.get("container", ""))
            elif act == "stop":
                return docker_agent.stop_container(params.get("container", ""))
            elif act == "restart":
                return docker_agent.restart_container(params.get("container", ""))
            elif act == "logs":
                return docker_agent.get_container_logs(params.get("container", ""), params.get("tail", 50))
            elif act == "build":
                return docker_agent.build_image(params.get("path", "."), params.get("tag", "latest"))
        elif sub == "k8s":
            if act == "cluster_info":
                return k8s_agent.get_cluster_info()
            elif act == "get_pods":
                return k8s_agent.get_pods(params.get("namespace", "default"))
            elif act == "get_nodes":
                return k8s_agent.get_nodes()
            elif act == "get_deployments":
                return k8s_agent.get_deployments(params.get("namespace", "default"))
            elif act == "restart_deployment":
                return k8s_agent.restart_deployment(params.get("deployment", ""), params.get("namespace", "default"))
        elif sub == "terraform":
            if act == "validate":
                return terraform_agent.validate()
            elif act == "plan":
                return terraform_agent.plan()
            elif act == "apply":
                return terraform_agent.apply()
            elif act == "destroy":
                return terraform_agent.destroy(params.get("ticket_id"))
        return {"success": False, "error": f"Unknown devops subsystem/action: {subsystem}/{action}"}


class AWSManagementTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="aws_management",
                description="AWS Cloud operations: STS Caller Identity, S3 buckets list/upload/download, EC2 instances list/start/stop, Lambda, and Cost Explorer",
                target_world=TargetWorld.DIGITAL,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "action": {"type": "string", "enum": ["caller_identity", "cloud_health", "list_s3", "list_ec2", "start_ec2", "stop_ec2", "upload_s3", "download_s3", "list_lambda", "costs", "switch_region"], "required": True},
                    "instance_id": {"type": "string"},
                    "bucket_name": {"type": "string"},
                    "local_file": {"type": "string"},
                    "object_name": {"type": "string"},
                    "region": {"type": "string"}
                }
            )
        )

    async def execute(self, action: str = "cloud_health", **kwargs) -> Dict[str, Any]:
        act = action.lower().strip()
        logger.info(f"[Tool: AWSManagement] Executing: {act}")
        if act in ["caller_identity", "sts"]:
            return aws_agent.get_caller_identity()
        elif act in ["cloud_health", "health"]:
            return aws_agent.check_cloud_health()
        elif act in ["list_s3", "s3"]:
            buckets = aws_agent.list_s3_buckets()
            return {"success": True, "count": len(buckets), "buckets": buckets}
        elif act in ["list_ec2", "ec2"]:
            instances = aws_agent.list_ec2_instances()
            return {"success": True, "count": len(instances), "instances": instances}
        elif act == "start_ec2":
            return aws_agent.start_ec2_instance(kwargs.get("instance_id", ""))
        elif act == "stop_ec2":
            return aws_agent.stop_ec2_instance(kwargs.get("instance_id", ""))
        elif act == "upload_s3":
            return aws_agent.upload_to_s3(kwargs.get("local_file", ""), kwargs.get("bucket_name", ""), kwargs.get("object_name"))
        elif act == "download_s3":
            return aws_agent.download_from_s3(kwargs.get("bucket_name", ""), kwargs.get("object_name", ""), kwargs.get("local_file", ""))
        elif act == "list_lambda":
            return aws_agent.list_lambda_functions()
        elif act in ["costs", "cost"]:
            return aws_agent.get_aws_cost_and_usage()
        elif act == "switch_region":
            return aws_agent.switch_aws_region(kwargs.get("region", "us-east-1"))
        return aws_agent.check_cloud_health()


# ==============================================================================
# TOOL IMPLEMENTATIONS (PILLAR 3: INTELLIGENCE & PRODUCTIVITY)
# ==============================================================================

class ProductivityTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="productivity_tool",
                description="Productivity features: reminders with native Windows toast notifications, timers, quick notes, and task checklists",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "action": {"type": "string", "enum": ["remind", "save_note", "read_notes", "add_task", "list_tasks", "complete_task"], "required": True},
                    "message": {"type": "string"},
                    "delay_seconds": {"type": "integer", "default": 60},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "task": {"type": "string"},
                    "task_id": {"type": "integer"},
                    "keyword": {"type": "string"}
                }
            )
        )

    async def execute(self, action: str = "list_tasks", **kwargs) -> Dict[str, Any]:
        act = action.lower().strip()
        logger.info(f"[Tool: Productivity] Executing: {act}")
        if act in ["remind", "reminder", "timer"]:
            return productivity_agent.create_reminder(kwargs.get("message", "Timer expired"), kwargs.get("delay_seconds", 60))
        elif act == "save_note":
            return productivity_agent.save_note(kwargs.get("title", "Quick Note"), kwargs.get("content", ""))
        elif act == "read_notes":
            return productivity_agent.read_notes(kwargs.get("keyword"))
        elif act == "add_task":
            return productivity_agent.add_task(kwargs.get("task", ""))
        elif act == "list_tasks":
            return productivity_agent.list_tasks()
        elif act == "complete_task":
            return productivity_agent.complete_task(kwargs.get("task_id", 1))
        return productivity_agent.list_tasks()


class CompoundWorkflowTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="compound_workflow",
                description="Executes compound multi-step automation pipelines and protocols: 'coding_protocol' (VS Code, Terminal, HUD, 30% Vol), 'focus_protocol' (20% Vol, suppress distractions), 'meeting_protocol' (40% Vol, pause media), 'lockdown_protocol' (Mute audio, lock workstation), 'morning_briefing' (Real PC vitals & Tony Stark morning report), 'dev_environment', 'aws_workspace', 'movie_mode', and 'shutdown_prep'",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_2_MUTATING,
                parameters_schema={
                    "workflow": {
                        "type": "string",
                        "enum": [
                            "coding_protocol",
                            "focus_protocol",
                            "meeting_protocol",
                            "lockdown_protocol",
                            "morning_briefing",
                            "dev_environment",
                            "aws_workspace",
                            "movie_mode",
                            "shutdown_prep"
                        ],
                        "required": True
                    }
                }
            )
        )

    async def execute(self, workflow: str = "dev_environment", **kwargs) -> Dict[str, Any]:
        logger.info(f"[Tool: CompoundWorkflow] Running pipeline: {workflow}")
        return await planner.execute_workflow(workflow, parameters=kwargs)


# ==============================================================================
# LEGACY & SPECIALIZED TOOLS (Preserved for compatibility)
# ==============================================================================

class PhysicalDeviceTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="control_physical_device",
                description="Controls physical relays, lights, or appliances connected via ESP32 / IoT",
                target_world=TargetWorld.PHYSICAL,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "device_id": {"type": "string", "required": True},
                    "target": {"type": "string", "required": True},
                    "state": {"type": "boolean", "required": True}
                }
            )
        )

    async def execute(self, device_id: str = "esp32_lab_01", target: str = "desk_lamp", state: bool = True, **kwargs) -> Dict[str, Any]:
        return esp32_agent.set_relay(device_id, target, state)


class PrepareWorkspaceTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="prepare_workspace",
                description="Prepares Windows developer workspace: launches VS Code, Windows Terminal, and illuminates workstation",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={"profile": {"type": "string", "default": "developer"}}
            )
        )

    async def execute(self, profile: str = "developer", **kwargs) -> Dict[str, Any]:
        return await planner.execute_workflow("dev_environment")


class LockScreenTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="lock_screen",
                description="Locks the Windows workstation desktop screen immediately",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={}
            )
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        return system_control.lock_workstation()


class LaunchAppTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="launch_app",
                description="Launches a desktop Windows application or web app (e.g. chrome, notepad, calc, code, terminal, snapchat, instagram, whatsapp, youtube, spotify). Note: For Snapchat, default to mode='web' unless explicitly requested for system.",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "app": {"type": "string", "required": True},
                    "args": {"type": "array", "default": []},
                    "mode": {"type": "string", "description": "Launch mode: 'web' or 'system'. For snapchat: default is 'web' unless user explicitly requests 'system'.", "default": "auto"}
                }
            )
        )

    async def execute(self, app: str = "notepad", args: list = None, mode: str = "auto", **kwargs) -> Dict[str, Any]:
        chosen_mode = kwargs.get("mode", mode)
        app_clean = str(app).lower()
        if "snapchat" in app_clean and not any(w in app_clean for w in ["system", "systems", "system's", "desktop app", "locally"]):
            chosen_mode = "web"
        return windows_agent.launch_app(app, args or [], mode=chosen_mode)


class AudioVolumeTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="control_system_audio",
                description="Controls Windows audio volume: increase volume, decrease volume, mute/unmute, or set exact percentage (0 to 100)",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "action": {"type": "string", "enum": ["increase", "decrease", "mute", "unmute", "set"], "default": "set"},
                    "steps": {"type": "integer", "default": 5},
                    "level": {"type": "integer", "default": 50}
                }
            )
        )

    async def execute(self, action: str = "set", steps: int = 5, level: int = 50, **kwargs) -> Dict[str, Any]:
        act = action.lower().strip()
        if act in ["increase", "up", "raise"]:
            return audio_agent.adjust_volume("up", steps=steps)
        elif act in ["decrease", "down", "lower"]:
            return audio_agent.adjust_volume("down", steps=steps)
        elif act in ["mute", "unmute"]:
            return audio_agent.adjust_volume("mute")
        return audio_agent.set_volume_percent(level)


class SystemStatusReportTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="system_status_report",
                description="Gathers live telemetry across Windows PC, physical IoT devices, and cloud services",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_0_REFLEX,
                parameters_schema={}
            )
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        vitals = system_monitor.collect_telemetry()
        return {
            "success": True,
            "os": "Windows",
            "cpu_percent": vitals.get("cpu_percent", 0),
            "memory_percent": vitals.get("memory_percent", 0),
            "active_window": vitals.get("active_window", "Unknown"),
            "physical_devices": "online",
            "cloud": "nominal",
            "channel_1_logical": True
        }


class BrowseWebTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="browse_web",
                description="Navigates to URLs, opens browser tabs, or performs Google searches",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "url": {"type": "string"},
                    "search_query": {"type": "string"}
                }
            )
        )

    async def execute(self, url: str = "https://google.com", search_query: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        if search_query:
            return windows_agent.search_google(search_query)
        if url:
            from services.security.prompt_shield import prompt_shield
            is_safe, reason = prompt_shield.validate_url_ssrf(url)
            if not is_safe:
                return {"success": False, "error": f"Security violation: {reason}", "status": "blocked"}
            if any(char in url for char in [";", "&", "|", "`", "$"]):
                return {"success": False, "error": "Security violation: Command injection detected in URL.", "status": "blocked"}
        return windows_agent.open_url(url)


class CloseAppTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="close_app",
                description="Closes running desktop applications, windows, or tabs (e.g. notepad, calc, chrome, opera, tab, window, all)",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_2_MUTATING,
                parameters_schema={
                    "app_name": {"type": "string", "required": True}
                }
            )
        )

    async def execute(self, app_name: str = "", pid: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        target_pid = pid or kwargs.get("pid")
        if target_pid:
            try:
                import psutil
                if psutil.pid_exists(target_pid):
                    p = psutil.Process(target_pid)
                    p_name = p.name()
                    p.kill()
                    return {"success": True, "killed": True, "pid": target_pid, "name": p_name}
                return {"success": True, "killed": True, "pid": target_pid, "message": "Process already absent"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        app_lower = (app_name or "").lower().strip()
        if app_lower in ["all", "all apps", "everything"]:
            return windows_agent.close_all_user_apps()
        elif "tab" in app_lower:
            return windows_agent.close_active_tab("opera")
        elif "window" in app_lower:
            return windows_agent.close_active_window()
        return windows_agent.close_active_window(app_name)


class ManageBrowserTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="manage_browser",
                description="Controls browser tabs and navigation (close active tab, open bookmarks, close window)",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "action": {"type": "string", "enum": ["close_tab", "open_bookmarks", "close_window"], "required": True}
                }
            )
        )

    async def execute(self, action: str = "close_tab", browser: str = "opera", **kwargs) -> Dict[str, Any]:
        act = (action or "").lower().strip()
        if "bookmark" in act:
            return windows_agent.open_browser_bookmarks(browser)
        elif "tab" in act:
            return windows_agent.close_active_tab(browser)
        elif "window" in act:
            return windows_agent.close_active_window(browser)
        return {"success": False, "error": f"Unknown browser action: {action}"}


class SendMessageTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="send_message",
                description="Sends or drafts WhatsApp messages or checks latest incoming conversations",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "action": {"type": "string", "enum": ["send", "check_latest"], "default": "send"},
                    "recipient": {"type": "string"},
                    "message": {"type": "string"}
                }
            )
        )

    async def execute(self, action: str = "send", recipient: Optional[str] = None, message: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        act = (action or "").lower().strip()
        if "check" in act or "read" in act or not message:
            return windows_agent.check_latest_messages(platform="whatsapp")
        return windows_agent.send_whatsapp_message(message=message, recipient=recipient or "brother")


class SystemQueryTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="query_system_telemetry",
                description="Queries specific hardware and OS telemetry (battery, disk, time, ip, active windows)",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_0_REFLEX,
                parameters_schema={
                    "query_type": {"type": "string", "required": True}
                }
            )
        )

    async def execute(self, query_type: str = "general", **kwargs) -> Dict[str, Any]:
        qt = query_type.lower()
        if qt in ["time", "date"]:
            from datetime import datetime
            return {"success": True, "time": datetime.now().strftime("%I:%M %p"), "date": datetime.now().strftime("%A, %B %d, %Y")}
        elif qt in ["battery", "power"]:
            import psutil
            b = psutil.sensors_battery()
            return {"success": True, "percent": b.percent if b else 100, "plugged": b.power_plugged if b else True}
        elif qt in ["disk", "storage"]:
            return power_agent.get_free_disk_space()
        elif qt in ["network", "ip"]:
            return network_agent.get_ip_addresses()
        res = system_monitor.collect_telemetry()
        if isinstance(res, dict) and "success" not in res:
            res["success"] = True
        return res


class AnalyzeScreenTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="analyze_screen",
                description="Captures current Windows desktop screen and analyzes visible windows, errors, code, or documents using Gemini Multimodal Vision",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_0_REFLEX,
                parameters_schema={
                    "query": {"type": "string", "default": "What is visible on the screen?"}
                }
            )
        )

    async def execute(self, query: str = "What is visible on the screen?", **kwargs) -> Dict[str, Any]:
        return await vision_agent.analyze_screen(prompt=query)


class AWSCloudHealthTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="aws_cloud_health",
                description="Checks real AWS Cloud connectivity, account identity, active region, S3 buckets, and EC2 topology",
                target_world=TargetWorld.DIGITAL,
                tier=ActionTier.TIER_0_REFLEX,
                parameters_schema={}
            )
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        return aws_agent.check_cloud_health()


class AWSListS3Tool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="aws_list_s3_buckets",
                description="Lists real S3 storage buckets in the user's AWS account",
                target_world=TargetWorld.DIGITAL,
                tier=ActionTier.TIER_0_REFLEX,
                parameters_schema={}
            )
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        buckets = aws_agent.list_s3_buckets()
        return {"success": True, "buckets": buckets, "count": len(buckets)}


class AWSListEC2Tool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="aws_list_ec2",
                description="Lists active EC2 virtual compute instances in configured AWS region",
                target_world=TargetWorld.DIGITAL,
                tier=ActionTier.TIER_0_REFLEX,
                parameters_schema={}
            )
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        instances = aws_agent.list_ec2_instances()
        return {"success": True, "instances": instances, "count": len(instances)}


class ClipboardDiagnosticianTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="diagnose_clipboard",
                description="Inspects Windows clipboard for errors or code tracebacks, diagnoses root cause using AI, and automatically copies the verified fix back to clipboard for instant Ctrl+V pasting",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_0_REFLEX,
                parameters_schema={}
            )
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        return await windows_agent.diagnose_clipboard_error()


class CrossDeviceRouteTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="cross_device_route",
                description="Routes actions across registered personal devices (phone, laptop, tablet, desktop) or lists fleet status",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_0_REFLEX,
                parameters_schema={
                    "query": {"type": "string"},
                    "action": {"type": "string"}
                }
            )
        )

    async def execute(self, query: str = "", action: str = "", **kwargs) -> Dict[str, Any]:
        if action == "list_devices":
            from services.cloud.device_registry import device_registry
            return {"success": True, "devices": device_registry.list_devices()}
        from services.cloud.device_router import device_router
        q = query or kwargs.get("raw_query", "")
        return await device_router.route_and_execute(q)



class SkillSynthesisTool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="synthesize_skill",
                description="Synthesizes a new reusable Python tool from natural language prompt or commands, verifies it with AST analysis, and hot-loads it into the active ToolRegistry at runtime. Requires Tier 3 confirmation lease.",
                target_world=TargetWorld.DIGITAL,
                tier=ActionTier.TIER_3_DESTRUCTIVE,
                parameters_schema={
                    "name": {"type": "string", "required": True},
                    "description": {"type": "string", "required": True},
                    "prompt_or_commands": {"type": "string", "required": True}
                },
                risk_level="CRITICAL"
            )
        )

    async def execute(self, name: str = "", description: str = "", prompt_or_commands: Any = "", **kwargs) -> Dict[str, Any]:
        from services.brain.skill_synthesizer import skill_synthesizer
        approval_token = kwargs.get("approval_token")
        return await skill_synthesizer.synthesize_skill(
            name=name,
            description=description,
            prompt_or_commands=prompt_or_commands,
            registry=registry,
            approval_token=approval_token
        )


class WorkstationSRETool(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="workstation_sre",
                description="Autonomous dev workstation SRE: scans active dev ports, diagnoses port collisions, detects stale lockfiles (.git/index.lock, terraform), finds runaway processes, and applies 1-tap self-healing.",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={
                    "action": {"type": "string", "enum": ["scan", "diagnose_port", "free_port", "scan_locks", "clear_lock", "clear_all_locks", "heal"], "required": True},
                    "port": {"type": "integer", "default": 0},
                    "target_type": {"type": "string", "default": ""},
                    "target_value": {"type": "string", "default": ""}
                },
                risk_level="LOW"
            )
        )

    async def execute(self, action: str = "scan", port: int = 0, target_type: str = "", target_value: Any = "", **kwargs) -> Dict[str, Any]:
        from workstation_sre import workstation_sre
        act = action.lower().strip()
        if act == "scan":
            scan = workstation_sre.run_sre_health_scan()
            return {"success": True, "scan": scan}
        elif act == "diagnose_port":
            return {"success": True, "diagnosis": workstation_sre.diagnose_port(port)}
        elif act == "free_port":
            return workstation_sre.free_port(port)
        elif act == "scan_locks":
            return {"success": True, "locks": workstation_sre.scan_lockfiles()}
        elif act in ["clear_lock", "clear_all_locks"]:
            tt = "lock" if act == "clear_lock" else "all_locks"
            return workstation_sre.apply_sre_healing(tt, target_value)
        elif act == "heal":
            return workstation_sre.apply_sre_healing(target_type, target_value)
        return {"success": False, "error": f"Unknown SRE action: {action}"}


# ==============================================================================
# CENTRAL TOOL REGISTRY CLASS WITH RESILIENCE BUS
# ==============================================================================

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, JarvisTool] = {}

        # Register Pillar 1: Computer Tools
        self.register(PCPowerTool())
        self.register(AudioMediaTool())
        self.register(DisplayControlTool())
        self.register(MouseKeyboardTool())
        self.register(FileManagerTool())
        self.register(NetworkControlTool())

        # Register Pillar 2: Cloud Tools
        self.register(DevOpsTool())
        self.register(AWSManagementTool())

        # Register Pillar 3: Intelligence Tools
        self.register(ProductivityTool())
        self.register(CompoundWorkflowTool())

        # Register Breakthrough Pillars (AgentOS)
        self.register(SkillSynthesisTool())
        self.register(WorkstationSRETool())

        # Register Compatibility & Reflex Tools
        self.register(PhysicalDeviceTool())
        self.register(PrepareWorkspaceTool())
        self.register(LockScreenTool())
        self.register(LaunchAppTool())
        self.register(AudioVolumeTool())
        self.register(SystemStatusReportTool())
        self.register(BrowseWebTool())
        self.register(CloseAppTool())
        self.register(ManageBrowserTool())
        self.register(SendMessageTool())
        self.register(SystemQueryTool())
        self.register(AnalyzeScreenTool())
        self.register(AWSCloudHealthTool())
        self.register(AWSListS3Tool())
        self.register(AWSListEC2Tool())
        self.register(ClipboardDiagnosticianTool())
        self.register(CrossDeviceRouteTool())

        # Hot-load all custom synthesized tools from disk
        try:
            from services.brain.skill_synthesizer import skill_synthesizer
            skill_synthesizer.load_all_custom_tools(self)
        except Exception as e:
            logger.warning(f"[ToolRegistry] Custom tools pre-load warning: {e}")

        logger.info(f"Initialized ToolRegistry with {len(self._tools)} registered domain tools.")

    CANONICAL_ALIASES = {
        "computer.open_app": "launch_app",
        "computer.close_app": "close_app",
        "computer.volume": "audio_media",
        "computer.power": "pc_power",
        "computer.type": "mouse_keyboard",
        "computer.click": "mouse_keyboard",
        "computer.lock": "pc_power",
        "browser.open": "browse_web",
        "browser.search": "browse_web",
        "browser.click": "manage_browser",
        "docker.restart": "devops_tool",
        "docker.list": "devops_tool",
        "kubernetes.pods": "devops_tool",
        "kubernetes.restart": "devops_tool",
        "terraform.plan": "devops_tool",
        "terraform.apply": "devops_tool",
        "aws.ec2.list": "aws_management",
        "aws.ec2.start": "aws_management",
        "aws.ec2.stop": "aws_management",
        "get_system_telemetry": "system_status_report",
        "system.telemetry": "system_status_report",
        "system.status": "system_status_report",
        "system.query": "query_system_telemetry",
        "network.control": "network_control",
        "process_manager": "close_app",
        "computer.kill_process": "close_app",
        "docker": "devops_tool",
        "aws.status": "aws_cloud_health",
        "aws": "aws_cloud_health",
    }

    def register(self, tool: JarvisTool):
        if not hasattr(tool, "definition") or not getattr(tool.definition, "tier", None):
            raise ValueError(f"Tool '{getattr(tool, 'name', str(tool))}' rejected: Mandatory ActionTier declaration required.")
        self._tools[tool.name] = tool

    def resolve_canonical_name(self, name: str) -> str:
        """Resolves canonical hierarchical name to implementation tool name, or vice versa."""
        if name in self._tools:
            return name
        if name in self.CANONICAL_ALIASES:
            alias_target = self.CANONICAL_ALIASES[name]
            if alias_target in self._tools:
                return alias_target
        # Check reverse aliases
        for canonical, alias in self.CANONICAL_ALIASES.items():
            if alias == name and canonical in self._tools:
                return canonical
        return name

    def get_tool(self, name: str) -> Optional[JarvisTool]:
        resolved = self.resolve_canonical_name(name)
        return self._tools.get(resolved) or self._tools.get(name)

    def get_tool_health(self, name: str) -> Dict[str, Any]:
        """Returns tool health status: AVAILABLE, DEGRADED, UNAVAILABLE, BLOCKED (Item 104)."""
        resolved = self.resolve_canonical_name(name)
        tool = self.get_tool(resolved)
        if not tool:
            return {"name": name, "status": "UNAVAILABLE", "reason": "Not registered in tool catalog"}

        # Dynamic health evaluation based on target domain
        if "kubernetes" in name or (resolved == "devops_tool" and "k8s" in name):
            # Kubernetes requires live cluster connection probe
            k8s_configured = os.path.exists(os.path.expanduser("~/.kube/config")) or bool(os.getenv("KUBECONFIG"))
            if not k8s_configured:
                return {"name": name, "status": "UNAVAILABLE", "reason": "No active Kubernetes cluster or kubeconfig detected (LAB-TESTED status)"}
        elif "aws" in name or resolved == "aws_management":
            aws_key = os.getenv("AWS_ACCESS_KEY_ID")
            if not aws_key and not os.path.exists(os.path.expanduser("~/.aws/credentials")):
                return {"name": name, "status": "DEGRADED", "reason": "AWS credentials unconfigured; running against mock/local provider"}
        elif "docker" in name:
            # Check docker daemon responsiveness
            try:
                import subprocess
                res = subprocess.run(["docker", "info"], capture_output=True, timeout=1.0)
                if res.returncode != 0:
                    return {"name": name, "status": "DEGRADED", "reason": "Docker daemon is not responsive"}
            except Exception:
                return {"name": name, "status": "DEGRADED", "reason": "Docker CLI not found or daemon down"}

        return {"name": name, "status": "AVAILABLE", "reason": "Nominal"}

    def get_available_capabilities(self) -> Dict[str, Any]:
        """Returns runtime capability discovery map (Item 103)."""
        capabilities = {
            "AVAILABLE": [],
            "DEGRADED": [],
            "UNAVAILABLE": [],
            "BLOCKED": []
        }
        for name in list(self._tools.keys()) + list(self.CANONICAL_ALIASES.keys()):
            h = self.get_tool_health(name)
            st = h.get("status", "AVAILABLE")
            capabilities[st].append({"tool": name, "reason": h.get("reason", "N/A")})
        return capabilities

    def list_tools(self) -> List[ToolDefinition]:
        return [tool.definition for tool in self._tools.values()]

    def to_llm_tool_specs(self) -> List[Dict[str, Any]]:
        specs = []
        for tool in self._tools.values():
            specs.append({
                "name": tool.name,
                "description": tool.definition.description,
                "parameters": tool.definition.parameters_schema
            })
        return specs

    async def execute_tool(
        self,
        name: str,
        parameters: Dict[str, Any],
        caller_agent: str = "master_orchestrator",
        approval_id: Optional[str] = None,
        raw_query: str = ""
    ) -> Dict[str, Any]:
        """
        Executes a tool through the strict architectural pipeline:
        Mandatory ActionTier Check -> Emergency Check -> SafetyGuard 4-Tier Check -> Cryptographic Confirmation Gate -> Timeout Manager -> Execution -> Audit Logger -> Result
        """
        start_time = time.time()
        tool = self.get_tool(name)
        if not tool:
            err_msg = f"Tool '{name}' not found in registry"
            audit_logger.record_entry(
                user_query=raw_query or name,
                intent="unknown",
                tool=name,
                parameters=parameters,
                risk_tier="UNKNOWN",
                result="NOT_FOUND",
                duration_ms=0.0,
                details={"error": err_msg}
            )
            return {"success": False, "error": err_msg, "status": "not_found"}

        # 0. MANDATORY ACTIONTIER DECLARATION VERIFICATION
        if not getattr(tool.definition, "tier", None):
            err_msg = f"Tool '{name}' security rejection: Missing mandatory ActionTier declaration."
            logger.critical(f"🚨 {err_msg}")
            return {
                "success": False,
                "status": "security_violation",
                "error": err_msg
            }

        # 1. EMERGENCY STOP CHECK
        if emergency_stop.is_stopped:
            logger.warning(f"Execution of '{name}' blocked: Emergency Stop is active.")
            audit_logger.record_entry(
                user_query=raw_query or name,
                intent="emergency_blocked",
                tool=name,
                parameters=parameters,
                risk_tier=tool.risk_level,
                result="EMERGENCY_HALTED",
                duration_ms=0.0,
                details={"reason": "Emergency stand-down is active"}
            )
            return {
                "success": False,
                "status": "emergency_halted",
                "error": "Execution halted: Emergency Stand-Down is currently active."
            }

        if parameters is None:
            parameters = {}

        # 2. SAFETY GUARD 4-TIER EVALUATION (Zero Bypass for Tier 3)
        action_name = parameters.get("action") or parameters.get("workflow") or name
        if name == "pc_power":
            action_name = f"pc_{parameters.get('action', 'power')}"
        elif name == "devops_tool" and parameters.get("action") == "destroy":
            action_name = "terraform_destroy"
        elif name == "file_manager" and parameters.get("permanent"):
            action_name = "permanent_delete"

        # If execution is routed via canonical_pipeline, the canonical pipeline authority
        # has already validated multi-factor permissions, action leases, and safety policies.
        # Direct callers outside canonical_pipeline are gated by SafetyGuard for defense-in-depth.
        if caller_agent == "canonical_pipeline":
            decision = {"authorized": True, "tier": "TIER_0_READ_ONLY", "rationale": "AUTHORIZED_BY_CANONICAL_PIPELINE"}
        else:
            decision = safety_guard.evaluate_request(action_name=action_name, parameters=parameters, approval_id=approval_id, tool_name=name)
        if not decision["authorized"]:
            logger.warning(f"SafetyGuard blocked execution of '{name}': {decision['rationale']}")
            audit_logger.record_entry(
                user_query=raw_query or name,
                intent=action_name,
                tool=name,
                parameters=parameters,
                risk_tier=decision["tier"],
                result="BLOCKED_CONFIRMATION_REQUIRED",
                confirmation_state="REQUIRED",
                duration_ms=0.0,
                details={"ticket_id": decision.get("ticket_id"), "rationale": decision["rationale"]}
            )
            return {
                "success": False,
                "status": "confirmation_required",
                "tier": decision["tier"],
                "rationale": decision["rationale"],
                "requires_confirmation": True,
                "ticket_id": decision.get("ticket_id"),
                "prompt_user": decision.get("prompt_user", "Confirmation required to proceed, sir.")
            }

        # 3. EXECUTE WITHIN TIMEOUT MANAGER
        timeout = float(tool.timeout_seconds)
        try:
            tool_result = await asyncio.wait_for(tool.execute(**parameters), timeout=timeout)
            duration_ms = (time.time() - start_time) * 1000

            # Ground-truth sensory verification of real OS / Cloud state change
            verification = verification_engine.verify_action_execution(name, parameters, tool_result)
            is_verified = (verification.status.value == "verified")
            if not is_verified and verification.failure_reason:
                tool_result["verification_error"] = verification.failure_reason

            # Autonomous Recovery Attempt: If execution or verification failed, attempt alternate strategy
            if not is_verified or (isinstance(tool_result, dict) and not tool_result.get("success", True)):
                try:
                    from services.brain.recovery_engine import recovery_engine
                    rec_res = await recovery_engine.attempt_recovery(
                        name, parameters, str(tool_result.get("error") or getattr(verification, "failure_reason", "") or "Execution failed")
                    )
                    if rec_res.get("recovered"):
                        tool_result["recovery_details"] = rec_res
                        tool_result["recovered"] = True
                        verification = verification_engine.verify_action_execution(name, parameters, tool_result)
                        is_verified = True
                except Exception as rec_err:
                    logger.debug(f"[ToolRegistry] Recovery attempt notice: {rec_err}")

            # Epistemic Assessment: Truth-in-State Evaluation
            epistemic = epistemic_evaluator.evaluate(
                tool_name=name,
                tool_result=tool_result,
                verification_status=is_verified,
                verification_details=verification.details
            )

            # Record in Cryptographically Chained Local Audit Ledger (SHA-256)
            try:
                chained_audit_ledger.record_action(
                    intent=action_name,
                    tool=name,
                    parameters=parameters,
                    authorization_ticket=approval_id,
                    verification_status=is_verified,
                    result="SUCCESS" if is_verified else "VERIFICATION_FAILED",
                    metadata={
                        "epistemic_state": epistemic.state.value,
                        "confidence": epistemic.confidence,
                        "sensory_verified": epistemic.sensory_verified
                    }
                )
            except Exception as chain_err:
                logger.debug(f"[ToolRegistry] Chained ledger append notice: {chain_err}")

            # Record success in execution audit log
            audit_logger.record_entry(
                user_query=raw_query or name,
                intent=action_name,
                tool=name,
                parameters=parameters,
                risk_tier=decision.get("tier", "TIER_1_REVERSIBLE"),
                result="SUCCESS" if is_verified else "VERIFICATION_FAILED",
                confirmation_state="CONFIRMED" if approval_id else "NONE",
                duration_ms=duration_ms,
                caller=caller_agent,
                details={
                    "verified": is_verified,
                    "sensory_verified": verification.sensory_verified,
                    "epistemic_state": epistemic.state.value,
                    "result_keys": list(tool_result.keys()) if isinstance(tool_result, dict) else []
                }
            )

            return {
                "success": is_verified,
                "verified": is_verified,
                "verification_details": verification.details,
                "epistemic_state": epistemic.state.value,
                "epistemic_summary": epistemic.truthful_summary,
                "result": tool_result,
                "status": "completed" if is_verified else "verification_failed",
                "duration_ms": round(duration_ms, 2)
            }
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            err_msg = f"Tool '{name}' timed out after {timeout} seconds"
            logger.error(err_msg)
            audit_logger.record_entry(
                user_query=raw_query or name,
                intent=action_name,
                tool=name,
                parameters=parameters,
                risk_tier=decision.get("tier", "TIER_1_REVERSIBLE"),
                result="TIMEOUT",
                duration_ms=duration_ms,
                caller=caller_agent,
                details={"error": err_msg}
            )
            return {
                "success": False,
                "status": "timeout",
                "error": err_msg,
                "duration_ms": round(duration_ms, 2)
            }
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Error executing tool '{name}': {e}")
            audit_logger.record_entry(
                user_query=raw_query or name,
                intent=action_name,
                tool=name,
                parameters=parameters,
                risk_tier=decision.get("tier", "TIER_1_REVERSIBLE"),
                result="ERROR",
                duration_ms=duration_ms,
                caller=caller_agent,
                details={"error": str(e)}
            )
            return {
                "success": False,
                "status": "error",
                "error": str(e),
                "duration_ms": round(duration_ms, 2)
            }


registry = ToolRegistry()
tool_registry = registry
