"""
Docker & Container Agent for J.A.R.V.I.S. (Cloud Pillar).
Inspects containers, starts/stops services, retrieves logs, and monitors container health.
"""

from __future__ import annotations
import subprocess
import json
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisDockerAgent")


class DockerAgent:
    def list_containers(self, all_containers: bool = False) -> List[Dict[str, Any]]:
        """Lists containers via docker ps"""
        logger.info("[DockerAgent] Listing Docker containers...")
        cmd = ["docker", "ps", "--format", "{{json .}}"]
        if all_containers:
            cmd.append("-a")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            containers = []
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.strip().split("\n"):
                    if line:
                        try:
                            containers.append(json.loads(line))
                        except Exception:
                            pass
            return containers
        except Exception as e:
            logger.warning(f"Docker command failed: {e}")
            return []

    def is_daemon_running(self) -> bool:
        """Checks if Docker engine daemon is responsive"""
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False

    def start_container(self, container_name: str) -> Dict[str, Any]:
        """Starts a target container"""
        logger.info(f"[DockerAgent] Starting container: {container_name}")
        try:
            res = subprocess.run(["docker", "start", container_name], capture_output=True, text=True, timeout=30)
            return {"success": res.returncode == 0, "container": container_name, "output": res.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_container(self, container_name: str) -> Dict[str, Any]:
        """Stops a target container (Tier 2 Disruptive)"""
        logger.info(f"[DockerAgent] Stopping container: {container_name}")
        try:
            res = subprocess.run(["docker", "stop", container_name], capture_output=True, text=True, timeout=30)
            return {"success": res.returncode == 0, "container": container_name, "output": res.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restart_container(self, container_name: str) -> Dict[str, Any]:
        """Restarts a target container"""
        logger.info(f"[DockerAgent] Restarting container: {container_name}")
        try:
            res = subprocess.run(["docker", "restart", container_name], capture_output=True, text=True, timeout=30)
            return {"success": res.returncode == 0, "container": container_name, "output": res.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_container_logs(self, container_name: str, tail: int = 50) -> Dict[str, Any]:
        """Retrieves stdout/stderr logs from a container"""
        try:
            res = subprocess.run(["docker", "logs", "--tail", str(tail), container_name], capture_output=True, text=True, timeout=10)
            return {"success": res.returncode == 0, "container": container_name, "logs": res.stdout.strip() or res.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def build_image(self, path: str = ".", tag: str = "latest") -> Dict[str, Any]:
        """Builds a Docker image from a Dockerfile"""
        logger.info(f"[DockerAgent] Building image {tag} from {path}")
        try:
            res = subprocess.run(["docker", "build", "-t", tag, path], capture_output=True, text=True, timeout=120)
            return {"success": res.returncode == 0, "tag": tag, "output": res.stdout[-500:]}
        except Exception as e:
            return {"success": False, "error": str(e)}


docker_agent = DockerAgent()
