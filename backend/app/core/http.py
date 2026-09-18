"""Request correlation and redacted operational logging, including SSE duration."""

import json
import logging
import re
import time
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders

logger = logging.getLogger("doctorcare.http")
REQUEST_ID = re.compile(r"[a-zA-Z0-9_-]{1,64}\Z")


def configure_http_logging():
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        supplied = Headers(scope=scope).get("x-request-id", "")
        request_id = supplied if REQUEST_ID.fullmatch(supplied) else uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status_code = 500

        async def send_response(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                if scope["path"].startswith("/api/"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        finally:
            route = scope.get("route")
            logger.info(json.dumps({
                "event": "http_request", "request_id": request_id,
                "method": scope["method"], "route": getattr(route, "path", "/unmatched"),
                "status": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }))
