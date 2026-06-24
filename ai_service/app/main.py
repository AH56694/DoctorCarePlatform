from fastapi import FastAPI

from ai_service.app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Service", version="0.1.0")

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "ai-service"}

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
