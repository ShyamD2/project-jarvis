"""
J.A.R.V.I.S. Network & Connectivity Agent (Computer Pillar).
Handles Wi-Fi interfaces, IP resolution (local & public), DNS lookup, ping tests, and network status.
"""

import socket
import subprocess
import urllib.request
import json
import re
from typing import Dict, Any, Optional, List
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisNetworkAgent")


class NetworkAgent:
    def __init__(self):
        pass

    def get_wifi_status(self) -> Dict[str, Any]:
        """Queries active Wi-Fi interface, connected SSID, signal strength, and radio type"""
        logger.info("[NetworkAgent] Querying Wi-Fi interface status")
        try:
            res = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=2)
            output = res.stdout
            
            ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", output, re.MULTILINE)
            signal_match = re.search(r"^\s*Signal\s*:\s*(.+)$", output, re.MULTILINE)
            state_match = re.search(r"^\s*State\s*:\s*(.+)$", output, re.MULTILINE)
            radio_match = re.search(r"^\s*Radio type\s*:\s*(.+)$", output, re.MULTILINE)

            return {
                "success": True,
                "connected": state_match.group(1).strip().lower() == "connected" if state_match else False,
                "state": state_match.group(1).strip() if state_match else "Disconnected",
                "ssid": ssid_match.group(1).strip() if ssid_match else None,
                "signal": signal_match.group(1).strip() if signal_match else None,
                "radio_type": radio_match.group(1).strip() if radio_match else None
            }
        except Exception as e:
            logger.debug(f"[NetworkAgent] Wi-Fi query fallback: {e}")
            return {
                "success": True,
                "connected": False,
                "state": "Unavailable / Disconnected (Virtual or Headless)",
                "ssid": None,
                "signal": None,
                "radio_type": None,
                "notice": str(e)
            }

    def get_ip_addresses(self) -> Dict[str, Any]:
        """Retrieves local IPv4, hostname, and public IP address"""
        logger.info("[NetworkAgent] Resolving IP addresses")
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        public_ip = "Unavailable"

        try:
            req = urllib.request.Request("https://api.ipify.org?format=json", headers={"User-Agent": "JARVIS-Agent"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                public_ip = data.get("ip", "Unavailable")
        except Exception as e:
            logger.debug(f"Public IP lookup error: {e}")

        return {
            "success": True,
            "hostname": hostname,
            "local_ip": local_ip,
            "public_ip": public_ip
        }

    def ping_host(self, host: str = "8.8.8.8", count: int = 2) -> Dict[str, Any]:
        """Pings target host and returns packet statistics and latency"""
        logger.info(f"[NetworkAgent] Pinging {host} ({count} packets)")
        try:
            res = subprocess.run(["ping", "-n", str(count), "-w", "1000", host], capture_output=True, text=True, timeout=3)
            success = res.returncode == 0
            avg_match = re.search(r"Average = (\d+ms)", res.stdout)
            avg_latency = avg_match.group(1) if avg_match else ("<1ms" if success else "N/A")

            return {
                "success": True,
                "host": host,
                "reachable": success,
                "latency": avg_latency,
                "output": res.stdout.strip()
            }
        except subprocess.TimeoutExpired:
            return {
                "success": True,
                "host": host,
                "reachable": False,
                "latency": "Timeout (ICMP dropped or host unreachable)",
                "output": "Ping timed out"
            }
        except Exception as e:
            return {
                "success": True,
                "host": host,
                "reachable": False,
                "latency": "Error",
                "error": str(e)
            }

    def check_internet_status(self) -> Dict[str, Any]:
        """Fast dual-DNS check to verify real internet connectivity"""
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=2)
            return {"success": True, "online": True, "status": "Internet connection is active & healthy"}
        except OSError:
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=2)
                return {"success": True, "online": True, "status": "Internet connection is active & healthy"}
            except OSError:
                return {"success": True, "online": False, "status": "Offline - No internet connection detected"}

    def dns_lookup(self, domain: str) -> Dict[str, Any]:
        """Resolves domain name to IP addresses"""
        try:
            ips = socket.gethostbyname_ex(domain)[2]
            return {"success": True, "domain": domain, "resolved_ips": ips}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_network_adapters(self) -> Dict[str, Any]:
        """Lists active network adapters and statuses with zero subprocess overhead using psutil"""
        try:
            import psutil
            adapters = []
            stats = psutil.net_if_stats()
            for name, stat in stats.items():
                adapters.append({
                    "Name": name,
                    "InterfaceDescription": name,
                    "Status": "Up" if stat.isup else "Down",
                    "LinkSpeed": f"{stat.speed} Mbps" if stat.speed else "Unknown"
                })
            return {"success": True, "adapters": adapters}
        except Exception as e:
            logger.debug(f"[NetworkAgent] psutil adapter query fallback: {e}")
            return {"success": True, "adapters": [{"Name": "Default Loopback", "Status": "Up"}]}


network_agent = NetworkAgent()
