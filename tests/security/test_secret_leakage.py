"""
Security Regression Test: Secret Leakage & Credential Redaction
Guarantees permanent remediation for credential leakage in logs, console outputs, and fail-closed secret retrieval.
"""

import unittest
from services.security.secret_redactor import secret_redactor
from services.security.secrets_manager import SecretsManager, SecurityError


class TestSecretLeakageSecurity(unittest.TestCase):
    def test_bearer_token_redacted(self):
        """Invariant: Authorization bearer tokens are stripped before logging."""
        log_line = "Incoming request headers: {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'}"
        redacted = secret_redactor.redact(log_line)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", redacted)
        self.assertIn("[REDACTED_BEARER_TOKEN]", redacted)

    def test_aws_credentials_redacted(self):
        """Invariant: AWS Access Key IDs and Secrets are scrubbed."""
        aws_msg = "Configured AWS profile with AKIAIOSFODNN7EXAMPLE and aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'"
        redacted = secret_redactor.redact(aws_msg)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", redacted)
        self.assertNotIn("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", redacted)
        self.assertIn("[REDACTED_AWS_KEY_ID]", redacted)

    def test_api_keys_redacted(self):
        """Invariant: Groq, Gemini, and Telegram API tokens are scrubbed."""
        groq_str = "Connecting to Groq with gsk_99999999999999999999999999999999"
        gemini_str = "Gemini key: AIzaSyD99999999999999999999999999999999"
        tg_str = "Connecting with 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ123456789 to Telegram"

        self.assertIn("[REDACTED_GROQ_KEY]", secret_redactor.redact(groq_str))
        self.assertIn("[REDACTED_GEMINI_KEY]", secret_redactor.redact(gemini_str))
        redacted_tg = secret_redactor.redact(tg_str)
        self.assertNotIn("123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ123456789", redacted_tg)
        self.assertIn("[REDACTED_TELEGRAM_TOKEN]", redacted_tg)

    def test_fail_closed_production_secrets_manager(self):
        """Invariant: In production, missing secrets raise SecurityError rather than falling back to local files."""
        mgr = SecretsManager()
        mgr.env_mode = "production"
        with self.assertRaises(SecurityError):
            mgr.get_secret("UNSET_PRODUCTION_DATABASE_PASSWORD")


if __name__ == "__main__":
    unittest.main()
