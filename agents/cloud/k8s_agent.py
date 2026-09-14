"""
Kubernetes Agent for J.A.R.V.I.S. (Cloud Pillar).
Interacts with Kubernetes clusters via kubectl CLI to inspect pods, nodes, services, and deployments.
"""

from __future__ import annotations
import subprocess
import json
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisK8sAgent")


class K8sAgent:
    def __init__(self):
        pass

    def get_cluster_info(self) -> Dict[str, Any]:
        """Queries cluster master and services status"""
        logger.info("[K8sAgent] Checking Kubernetes cluster info...")
        try:
            res = subprocess.run(["kubectl", "cluster-info"], capture_output=True, text=True, timeout=10)
            return {
                "success": res.returncode == 0,
                "connected": res.returncode == 0,
                "info": res.stdout.strip() if res.returncode == 0 else res.stderr.strip()
            }
        except Exception as e:
            return {"success": False, "connected": False, "error": str(e)}

    def get_pods(self, namespace: str = "default") -> Dict[str, Any]:
        """Lists active pods in a namespace"""
        logger.info(f"[K8sAgent] Querying pods in namespace '{namespace}'...")
        try:
            res = subprocess.run(["kubectl", "get", "pods", "-n", namespace, "-o", "json"], capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                return {"success": False, "error": res.stderr.strip()}
            data = json.loads(res.stdout)
            pods = []
            for item in data.get("items", []):
                pods.append({
                    "name": item.get("metadata", {}).get("name"),
                    "status": item.get("status", {}).get("phase"),
                    "ip": item.get("status", {}).get("podIP", "N/A")
                })
            return {"success": True, "namespace": namespace, "count": len(pods), "pods": pods}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_nodes(self) -> Dict[str, Any]:
        """Lists cluster nodes and status"""
        try:
            res = subprocess.run(["kubectl", "get", "nodes", "-o", "json"], capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                return {"success": False, "error": res.stderr.strip()}
            data = json.loads(res.stdout)
            nodes = [item.get("metadata", {}).get("name") for item in data.get("items", [])]
            return {"success": True, "count": len(nodes), "nodes": nodes}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_deployments(self, namespace: str = "default") -> Dict[str, Any]:
        """Lists deployments in a namespace"""
        try:
            res = subprocess.run(["kubectl", "get", "deployments", "-n", namespace, "-o", "json"], capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                return {"success": False, "error": res.stderr.strip()}
            data = json.loads(res.stdout)
            deps = []
            for item in data.get("items", []):
                deps.append({
                    "name": item.get("metadata", {}).get("name"),
                    "replicas": item.get("status", {}).get("replicas", 0),
                    "ready": item.get("status", {}).get("readyReplicas", 0)
                })
            return {"success": True, "namespace": namespace, "deployments": deps}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restart_deployment(self, deployment_name: str, namespace: str = "default") -> Dict[str, Any]:
        """Performs a rolling restart of a deployment (Tier 2 Disruptive)"""
        logger.info(f"[K8sAgent] Rolling restart of deployment '{deployment_name}' in namespace '{namespace}'")
        try:
            res = subprocess.run(
                ["kubectl", "rollout", "restart", f"deployment/{deployment_name}", "-n", namespace],
                capture_output=True, text=True, timeout=30
            )
            return {"success": res.returncode == 0, "deployment": deployment_name, "output": res.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}


k8s_agent = K8sAgent()
