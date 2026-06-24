from fastapi import FastAPI

from embedding_service.app.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Embedding Service", version="0.1.0")

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "embedding-service"}

    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
