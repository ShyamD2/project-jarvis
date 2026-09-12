"""
Cybersecurity & Zero-Trust Defense API Router for Project J.A.R.V.I.S.
Exposes real port scanner, IAM wildcard policy scanner, and blast-radius matrix.
"""

import os
import sys
import socket
import time
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, Any, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "agents/cloud"))

from soc_security_agent import soc_agent

sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/gateway"))
try:
    from secure_bridge import secure_bridge
except ImportError:
    secure_bridge = None

router = APIRouter(prefix="/api/v1/security", tags=["Cybersecurity & Defense"])


class PortScanRequest(BaseModel):
    target_host: str = Field(default="127.0.0.1", description="Host or IP to scan")
    ports: List[int] = Field(default=[8000, 1883, 5432, 6379, 22, 80, 443, 3306], description="Target ports")


@router.post("/port-scan")
async def scan_network_ports(req: PortScanRequest):
    """Scans target host for open ports and evaluates exposure risks"""
    results = []
    for port in req.ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        res = s.connect_ex((req.target_host, port))
        s.close()
        is_open = (res == 0)
        results.append({
            "port": port,
            "status": "OPEN" if is_open else "CLOSED",
            "service": {8000: "JARVIS Core API", 1883: "MQTT Broker", 5432: "PostgreSQL", 6379: "Redis", 22: "SSH", 80: "HTTP", 443: "HTTPS", 3306: "MySQL"}.get(port, "Unknown"),
            "risk": "MEDIUM" if is_open and port in [22, 3306] else "LOW"
        })

    return {
        "status": "success",
        "target": req.target_host,
        "scanned_ports": len(req.ports),
        "open_ports_count": len([r for r in results if r["status"] == "OPEN"]),
        "results": results
    }


@router.post("/iam-scan")
async def scan_iam_policies():
    """Scans Terraform IaC configuration for wildcard privilege attachments"""
    tf_dir = os.path.join(PROJECT_ROOT, "infrastructure/terraform")
    scan_res = soc_agent.scan_terraform_iam_policies(tf_dir)
    return {
        "status": "success",
        "scan": scan_res
    }


@router.get("/blast-radius")
@router.get("/threat-matrix")
async def get_blast_radius_matrix():
    """Returns the zero-trust blast radius policy matrix"""
    return {
        "status": "success",
        "tiers": {
            "TIER_0_REFLEX": {"risk": "LOW", "auth": "Instant", "examples": ["read status", "volume", "time", "battery", "app launch"]},
            "TIER_1_SOFT": {"risk": "MEDIUM", "auth": "Soft voice log", "examples": ["desk lamp relay", "non-critical settings", "git commit"]},
            "TIER_2_MUTATING": {"risk": "HIGH", "auth": "Interactive UI Approval", "examples": ["terminate process", "restart container", "terraform apply", "batch delete files"]},
            "TIER_3_DESTRUCTIVE": {"risk": "CRITICAL", "auth": "Cryptographic Token / MFA", "examples": ["terraform destroy", "modify aws iam", "drop database", "system format"]}
        }
    }


class SignatureRequest(BaseModel):
    payload: Dict[str, Any]
    nonce: str = Field(default="nonce_init")


class EnvelopeVerificationRequest(BaseModel):
    payload: Dict[str, Any]
    timestamp: float
    nonce: str
    signature: str


@router.post("/bridge/sign")
async def sign_envelope(req: SignatureRequest):
    """Generates cryptographic HMAC-SHA256 signature for remote message envelope"""
    if not secure_bridge:
        return {"status": "error", "message": "SecureBridge module unavailable"}
    import uuid
    nonce = req.nonce if req.nonce != "nonce_init" else uuid.uuid4().hex
    ts = time.time()
    sig = secure_bridge.generate_signature(req.payload, ts, nonce)
    return {
        "status": "signed",
        "payload": req.payload,
        "timestamp": ts,
        "nonce": nonce,
        "signature": sig
    }


@router.post("/bridge/verify")
async def verify_envelope(req: EnvelopeVerificationRequest):
    """Validates an incoming remote command envelope with anti-replay and HMAC-SHA256 signature verification"""
    if not secure_bridge:
        return {"valid": False, "status": "error", "reason": "SecureBridge module unavailable"}
    valid, reason = secure_bridge.verify_message(req.dict())
    return {
        "valid": valid,
        "status": "verified" if valid else "rejected",
        "reason": reason
    }

