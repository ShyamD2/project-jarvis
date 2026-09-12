"""
Specialized Autonomous Swarm Fabric for Project J.A.R.V.I.S.
Manages 12 specialized persona agents with shared memory, status tracking, and delegation.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

try:
    from services.observability import obs_recorder, obs_metrics
except ImportError:
    obs_recorder = None
    obs_metrics = None


@dataclass
class SwarmAgent:
    id: str
    name: str
    role: str
    capabilities: List[str]
    status: str = "IDLE"  # IDLE, WORKING, VERIFYING, ERROR
    current_task: Optional[str] = None
    tasks_completed: int = 0
    avatar: str = "🤖"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SwarmManager:
    def __init__(self):
        self._agents: Dict[str, SwarmAgent] = {}
        self._init_swarm()

    def _init_swarm(self):
        personas = [
            ("planner", "Master Planner", "Decomposes high-level objectives into dependency DAGs", ["dag_generation", "task_scheduling", "dependency_check"], "🧭"),
            ("coding", "Coding Agent", "Writes, edits, and refactors Python, JS, HTML, and Shell code", ["code_write", "refactor", "syntax_check", "test_runner"], "💻"),
            ("devops", "DevOps & CI/CD", "Manages Docker containers, Git workflows, and builds", ["docker_ops", "git_commit", "ci_pipeline", "rollback"], "🛠️"),
            ("cloud", "Cloud Architect", "Provisions and inspects AWS EC2, S3, Lambda, and Terraform", ["aws_ec2", "s3_buckets", "lambda_exec", "terraform_apply"], "☁️"),
            ("security", "Security Sentinel", "Performs port scans, zero-trust policy checks, and threat mitigation", ["port_scan", "policy_eval", "vulnerability_check"], "🔐"),
            ("computer", "Computer Control", "Directs Windows applications, process lifecycle, and desktop windows", ["app_launch", "process_kill", "window_manager", "opera_gx"], "🖥️"),
            ("vision", "Computer Vision", "Captures desktop screen frames, OCR, and multimodal UI analysis", ["screen_grab", "multimodal_qa", "ocr", "layout_reasoning"], "👁️"),
            ("web", "Web Researcher", "Navigates websites, scrapes documentation, and checks news/APIs", ["browse_url", "scrape_content", "news_weather_fetch"], "🌐"),
            ("sre", "SRE & Self-Healing", "Monitors crash logs, analyzes tracebacks, and applies auto-patches", ["trace_analysis", "auto_patch", "remediation", "health_watch"], "🩹"),
            ("iot", "IoT & Physical", "Controls ESP32 relays, ambient lux/temp sensors, and serial devices", ["esp32_relay", "lux_sensor", "ambient_reading", "robot_bridge"], "🏠"),
            ("productivity", "Productivity Agent", "Manages calendar, Pomodoro focus sessions, and smart notes", ["task_list", "time_blocking", "notes_sync"], "📋"),
            ("finops", "FinOps & Cost", "Monitors AWS spending, resource scaling, and project budgets", ["cost_estimation", "budget_alert", "resource_pruning"], "📈")
        ]

        for aid, name, role, caps, av in personas:
            self._agents[aid] = SwarmAgent(
                id=aid,
                name=name,
                role=role,
                capabilities=caps,
                avatar=av,
                status="IDLE"
            )

    def get_all_agents(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self._agents.values()]

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        a = self._agents.get(agent_id)
        return a.to_dict() if a else None

    def dispatch_task(self, agent_id: str, task: str) -> bool:
        a = self._agents.get(agent_id)
        if not a:
            return False
        a.status = "WORKING"
        a.current_task = task
        if obs_recorder:
            obs_recorder.record_agent_event(a.name, "TASK_DISPATCHED", task)
        return True

    def complete_task(self, agent_id: str) -> bool:
        a = self._agents.get(agent_id)
        if not a:
            return False
        a.status = "IDLE"
        a.tasks_completed += 1
        if obs_recorder:
            obs_recorder.record_agent_event(a.name, "TASK_COMPLETED", a.current_task)
        a.current_task = None
        return True


swarm_manager = SwarmManager()
