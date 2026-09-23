"""
Browser Automation Security Guard for Project J.A.R.V.I.S. (Phase 36 Stage 36.7 Item 119).
Enforces:
  1. Strict URL validation & SSRF prevention (blocks private subnets, cloud metadata, loopback).
  2. Protocol restrictions (blocks file://, javascript:, data: URIs).
  3. Form submission protection on payment, banking, and credential pages.
  4. Ephemeral browser profile arguments for session isolation.
"""

from __future__ import annotations
import urllib.parse
import ipaddress
import socket
import re
from typing import Dict, Any, List, Optional
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisBrowserGuard")

# Cloud metadata IP (AWS, GCP, Azure, OpenStack)
CLOUD_METADATA_IPS = {"169.254.169.254", "fd00:ec2::254"}

# Prohibited URL schemes for automated browsing
DISALLOWED_SCHEMES = {"file", "javascript", "data", "vbscript", "gopher", "dict", "ftp"}

# Sensitive URL keywords requiring interactive operator review before form actions
SENSITIVE_URL_KEYWORDS = [
    "checkout", "payment", "pay", "billing", "bank", "transfer",
    "wire", "wallet", "crypto", "signin", "login", "password"
]


class BrowserSecurityGuard:
    def __init__(self, allow_local_dev: bool = False):
        self.allow_local_dev = allow_local_dev

    def validate_url(self, url: str, resolve_dns: bool = True) -> Dict[str, Any]:
        """
        Validates target URL against SSRF and dangerous protocols.
        Resolves hostname to ensure DNS rebinding cannot reach private IPs or metadata.
        """
        if not url or not isinstance(url, str):
            return {"valid": False, "reason": "URL must be a non-empty string."}

        parsed = urllib.parse.urlparse(url.strip())
        scheme = parsed.scheme.lower()

        if scheme in DISALLOWED_SCHEMES:
            return {"valid": False, "reason": f"Disallowed URL scheme '{scheme}:'. Automated navigation blocked."}

        if scheme not in ["http", "https"]:
            return {"valid": False, "reason": f"Unsupported protocol '{scheme}:'. Only http and https allowed."}

        hostname = parsed.hostname
        if not hostname:
            return {"valid": False, "reason": "Target URL is missing a valid hostname."}

        # IP and DNS Rebinding Protection
        ips = set()
        if resolve_dns:
            try:
                addr_info = socket.getaddrinfo(hostname, None)
                ips = {info[4][0] for info in addr_info}
            except socket.gaierror:
                # If hostname is an IP string
                try:
                    ipaddress.ip_address(hostname)
                    ips = {hostname}
                except ValueError:
                    ips = set()
        else:
            try:
                ipaddress.ip_address(hostname)
                ips = {hostname}
            except ValueError:
                ips = set()

        for ip_str in ips:
            if ip_str in CLOUD_METADATA_IPS:
                return {"valid": False, "reason": "Access to Cloud Metadata service is strictly prohibited (SSRF Guard)."}

            try:
                ip = ipaddress.ip_address(ip_str)
                if not self.allow_local_dev:
                    if ip.is_loopback:
                        return {"valid": False, "reason": f"Loopback address '{ip_str}' is blocked (SSRF Guard)."}
                    if ip.is_private:
                        return {"valid": False, "reason": f"Private RFC1918 subnet '{ip_str}' is blocked (SSRF Guard)."}
                    if ip.is_link_local:
                        return {"valid": False, "reason": f"Link-local address '{ip_str}' is blocked (SSRF Guard)."}
            except ValueError:
                pass

        return {"valid": True, "hostname": hostname, "scheme": scheme, "resolved_ips": list(ips)}

    def check_form_action(self, url: str, action_type: str = "submit", resolve_dns: bool = False) -> Dict[str, Any]:
        """
        Evaluates risk of filling or submitting forms on the target page.
        Requires operator confirmation on checkout, payment, or banking portals.
        """
        val = self.validate_url(url, resolve_dns=resolve_dns)
        if not val["valid"]:
            return {"allowed": False, "requires_confirmation": True, "risk": "INVALID_URL", "reason": val["reason"]}

        url_lower = url.lower()
        is_sensitive = any(kw in url_lower for kw in SENSITIVE_URL_KEYWORDS)

        if is_sensitive:
            logger.warning(f"🛡️ [BrowserGuard] Sensitive portal detected: '{url}'. Interactive operator review required.")
            return {
                "allowed": False,
                "requires_confirmation": True,
                "risk": "HIGH_FINANCIAL_OR_CREDENTIAL",
                "reason": f"Automated {action_type} on sensitive/payment portal requires explicit operator approval."
            }

        return {"allowed": True, "requires_confirmation": False, "risk": "LOW"}

    def get_isolated_profile_args(self, temp_profile_dir: Optional[str] = None) -> List[str]:
        """Returns browser launch arguments for strict ephemeral session isolation."""
        args = [
            "--incognito",
            "--no-default-browser-check",
            "--disable-sync",
            "--disable-background-networking",
            "--disable-features=Translate",
            "--disable-save-password-bubble",
        ]
        if temp_profile_dir:
            args.append(f"--user-data-dir={temp_profile_dir}")
        return args


browser_guard = BrowserSecurityGuard()
