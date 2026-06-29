from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.db.models import Base
from backend.app.db.session import engine


def create_app() -> FastAPI:
    app = FastAPI(title=settings.project_name, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "backend"}

    if str(settings.database_url).startswith("sqlite"):
        Base.metadata.create_all(bind=engine)

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
