"""
Git & GitHub CI/CD Agent for J.A.R.V.I.S.
Manages repository state, branches, commits, and pull requests.
"""

from __future__ import annotations
import subprocess
import os
from typing import Dict, Any, List
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisGitAgent")


class GitAgent:
    def __init__(self, repo_dir: str = "."):
        self.repo_dir = repo_dir

    def get_status(self) -> Dict[str, Any]:
        """Runs git status --short"""
        logger.info("[GitAgent] Checking git repository status...")
        try:
            res = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            changes = [line.strip() for line in res.stdout.split("\n") if line.strip()]
            return {
                "success": res.returncode == 0,
                "clean": len(changes) == 0,
                "changed_files_count": len(changes),
                "changes": changes[:20],
                "channel_1_logical": True
            }
        except Exception as e:
            logger.error(f"[GitAgent] git status failed: {e}")
            return {"success": False, "error": str(e)}

    def stage_and_commit(self, message: str) -> Dict[str, Any]:
        """Stages all changes and creates a commit"""
        logger.info(f"[GitAgent] Staging files and creating commit: '{message}'")
        try:
            subprocess.run(["git", "add", "."], cwd=self.repo_dir, check=True)
            res = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_dir,
                capture_output=True,
                text=True
            )
            return {
                "success": res.returncode == 0,
                "output": res.stdout.strip(),
                "channel_1_logical": res.returncode == 0
            }
        except Exception as e:
            logger.error(f"[GitAgent] git commit failed: {e}")
            return {"success": False, "error": str(e)}


git_agent = GitAgent()
