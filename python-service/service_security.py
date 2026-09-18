"""Authentication boundary for the internal AI service, without model imports."""

import os
import secrets

from starlette.datastructures import Headers
from starlette.responses import JSONResponse


def service_token() -> str:
    token = os.getenv("RAG_SERVICE_TOKEN", "development-service-token")
    production = os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}
    if not token.strip() or (production and (
        len(token.strip()) < 32
        or any(word in token.lower() for word in ("development", "replace-with", "change-me", "example"))
    )):
        raise RuntimeError("RAG_SERVICE_TOKEN must contain at least 32 random characters in production")
    return token


class ServiceAuthMiddleware:
    def __init__(self, app, token: str):
        self.app = app
        self.token = token.encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in {"/", "/health"}:
            return await self.app(scope, receive, send)
        supplied = Headers(scope=scope).get("x-service-token", "").encode("utf-8")
        if not secrets.compare_digest(supplied, self.token):
            response = JSONResponse({"detail": "Service authentication required"}, status_code=401)
            return await response(scope, receive, send)
        production = os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}
        if production and scope["path"].rstrip("/") == "/api/parse":
            response = JSONResponse(
                {"detail": "Path-based ingestion is disabled; use the upload ingestion API"},
                status_code=403,
            )
            return await response(scope, receive, send)
        await self.app(scope, receive, send)
