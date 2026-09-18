"""Backend ASGI entry point; run with ``uvicorn main:app``."""

from backend.app.main import app

__all__ = ["app"]
