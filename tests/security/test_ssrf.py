"""
Security Regression Test: SSRF & Cloud Metadata Protection
Guarantees permanent remediation for SSRF via port scanner, webhooks, and URL fetchers.
"""

import unittest
from services.security.prompt_shield import prompt_shield


class TestSSRFSecurity(unittest.TestCase):
    def test_localhost_and_loopback_blocked(self):
        """Invariant: Requests to 127.0.0.1, localhost, and 0.0.0.0 are strictly blocked."""
        loopback_urls = [
            "http://127.0.0.1:8080/admin",
            "http://localhost:5000/api",
            "http://0.0.0.0:8000/metrics",
            "http://[::1]:8080/debug"
        ]
        for url in loopback_urls:
            is_valid, reason = prompt_shield.validate_url_ssrf(url)
            self.assertFalse(is_valid, f"Expected {url} to be blocked for SSRF, but was allowed.")
            self.assertIn("BLOCKED_SSRF", reason)

    def test_cloud_metadata_service_blocked(self):
        """Invariant: Requests to AWS/GCP/Azure link-local metadata endpoints are blocked."""
        metadata_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.169.254/computeMetadata/v1/",
            "http://[fd00:ec2::254]/latest/meta-data/"
        ]
        for url in metadata_urls:
            is_valid, reason = prompt_shield.validate_url_ssrf(url)
            self.assertFalse(is_valid, f"Cloud metadata URL {url} must be blocked.")
            self.assertIn("BLOCKED_SSRF", reason)

    def test_rfc1918_private_ip_space_blocked(self):
        """Invariant: Requests to internal RFC 1918 network ranges are blocked."""
        internal_urls = [
            "http://10.0.0.1/router",
            "http://172.16.0.5:9090",
            "http://192.168.1.1/setup.cgi"
        ]
        for url in internal_urls:
            is_valid, reason = prompt_shield.validate_url_ssrf(url)
            self.assertFalse(is_valid, f"Private RFC 1918 URL {url} must be blocked.")
            self.assertIn("BLOCKED_SSRF", reason)

    def test_non_http_schemes_blocked(self):
        """Invariant: Schemes other than http/https are blocked from URL processing."""
        forbidden_schemes = [
            "file:///etc/passwd",
            "file:///C:/Windows/win.ini",
            "gopher://127.0.0.1:70",
            "dict://127.0.0.1:2628",
            "ftp://anonymous@internal.corp"
        ]
        for url in forbidden_schemes:
            is_valid, reason = prompt_shield.validate_url_ssrf(url)
            self.assertFalse(is_valid, f"Disallowed scheme {url} must be blocked.")

    def test_public_fqdn_allowed(self):
        """Invariant: Standard public HTTPS domains resolve successfully."""
        is_valid, reason = prompt_shield.validate_url_ssrf("https://api.github.com/zen")
        self.assertTrue(is_valid)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
