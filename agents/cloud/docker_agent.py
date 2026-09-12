"""
Docker & Container Agent for J.A.R.V.I.S.
Inspects containers, manages services, and monitors container health.
"""

from __future__ import annotations
import subprocess
import json
from typing import Dict, Any, List
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisDockerAgent")


class DockerAgent:
    def list_containers(self) -> List[Dict[str, Any]]:
        """Lists running containers via docker ps"""
        logger.info("[DockerAgent] Listing active Docker containers...")
        try:
            res = subprocess.run(
                ["docker", "ps", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
                timeout=15
            )
            containers = []
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.strip().split("\n"):
                    if line:
                        try:
                            containers.append(json.loads(line))
                        except Exception as parse_err:
                            logger.warning(f"Failed to parse docker container JSON '{line}': {parse_err}")
            return containers
        except Exception as e:
            logger.warning(f"Docker command failed: {e}")
            return []

    def is_daemon_running(self) -> bool:
        """Checks if Docker engine daemon is responsive"""
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
            return res.returncode == 0
        except Exception as e:
            logger.debug(f"Docker daemon not running or not found: {e}")
            return False

    def restart_container(self, container_name: str) -> Dict[str, Any]:
        """Restarts a target container"""
        logger.info(f"[DockerAgent] Restarting container: {container_name}")
        try:
            res = subprocess.run(
                ["docker", "restart", container_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "success": res.returncode == 0,
                "container": container_name,
                "channel_1_logical": res.returncode == 0,
                "output": res.stdout.strip()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


docker_agent = DockerAgent()
