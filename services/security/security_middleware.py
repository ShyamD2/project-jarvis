"""
Production Zero-Trust Security Middleware for Project J.A.R.V.I.S. (Phase 1 Security Hardening).
Enforces cryptographically verified Bearer tokens and ActionLeases across all mutating REST endpoints,
while preserving high-performance public telemetry for health probes and static assets.
"""

from __future__ import annotations
import os
import secrets
from typing import Set, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("JarvisSecurityMiddleware")

EXEMPT_PATHS: Set[str] = {
    "/",
    "/index.html",
    "/favicon.ico",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/health/live",
    "/health/ready",
    "/metrics",
    "/api/v1/health",
    "/api/v1/metrics",
    "/api/v1/status",
}

EXEMPT_PREFIXES: Tuple[str, ...] = (
    "/static/",
    "/ws",
)


class SecurityGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, master_secret: str | None = None):
        super().__init__(app)
        self.master_secret = (
            master_secret
            or os.getenv("JARVIS_MASTER_SECRET")
            or os.getenv("JARVIS_API_KEY")
        )
        self.env_mode = os.getenv("JARVIS_ENV", "development").lower().strip()

    async def dispatch(self, request: Request, call_next):
        # 1. Allow CORS Preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # 2. Check Public Exemption Whitelist
        if path in EXEMPT_PATHS or path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)

        # 3. Extract Token from Headers or Query
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif "X-Jarvis-Key" in request.headers:
            token = request.headers.get("X-Jarvis-Key", "").strip()
        elif "X-API-Key" in request.headers:
            token = request.headers.get("X-API-Key", "").strip()
        elif "token" in request.query_params:
            token = request.query_params.get("token", "").strip()
        elif "api_key" in request.query_params:
            token = request.query_params.get("api_key", "").strip()

        # 4. Enforce Token Presence
        if not token:
            logger.warning(f"🔒 [SecurityGuard] Rejected unauthenticated {request.method} request to {path}")
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "error": "UNAUTHORIZED",
                    "detail": "Authentication required. Provide 'Authorization: Bearer <token>' or 'X-Jarvis-Key' header."
                }
            )

        # 5. Cryptographic Validation
        is_valid = False

        # 5a. Compare with Master Secret / API Key
        valid_secrets = set()
        env_secret = os.getenv("JARVIS_MASTER_SECRET")
        if env_secret:
            valid_secrets.add(env_secret.strip())
        env_api_key = os.getenv("JARVIS_API_KEY")
        if env_api_key:
            valid_secrets.add(env_api_key.strip())
        if self.master_secret:
            valid_secrets.add(self.master_secret.strip())

        for sec in valid_secrets:
            if secrets.compare_digest(token, sec):
                is_valid = True
                break

        # 5b. Validate ActionLease Capability Tokens
        if not is_valid and token.startswith("lease_"):
            try:
                from services.permission_engine.engine import permission_engine
                lease = permission_engine.active_leases.get(token)
                if lease and not lease.is_expired() and not lease.consumed:
                    is_valid = True
            except Exception:
                pass

        if not is_valid:
            logger.warning(f"🔒 [SecurityGuard] Rejected invalid token for {request.method} request to {path}")
            return JSONResponse(
                status_code=403,
                content={
                    "status": "error",
                    "error": "FORBIDDEN",
                    "detail": "Invalid or expired authentication credentials."
                }
            )

        # 6. Proceed with authenticated context
        request.state.authenticated = True
        return await call_next(request)
