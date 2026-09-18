from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.core.http import RequestContextMiddleware, configure_http_logging, logger
from backend.app.db.models import Base
from backend.app.db.session import engine, get_db
from backend.app.services.rate_limit import auth_rate_limiter


@lru_cache
def expected_database_heads():
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.mysql.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("version_locations", str(root / "migrations/mysql_versions"))
    return set(ScriptDirectory.from_config(config).get_heads())


def create_app() -> FastAPI:
    settings.validate_production()
    configure_http_logging()
    app = FastAPI(
        title=settings.project_name, version="0.1.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        errors = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.exception_handler(IntegrityError)
    async def data_conflict(request: Request, exc: IntegrityError):
        return JSONResponse({"detail": "数据冲突，请刷新后重试。"}, status_code=409)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("database_error request_id=%s type=%s", request.state.request_id, type(exc).__name__)
        return JSONResponse({"detail": "数据服务暂不可用，请稍后重试。"}, status_code=503)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "")
        logger.error("unexpected_error request_id=%s type=%s", request_id, type(exc).__name__)
        return JSONResponse(
            {"detail": "服务暂不可用，请稍后重试。", "request_id": request_id}, status_code=500,
            headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
        )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "backend"}

    @app.get("/ready", tags=["health"])
    def ready(db: Session = Depends(get_db)):
        try:
            db.execute(text("SELECT 1"))
            if settings.is_production:
                auth_rate_limiter.client.ping()
                revisions = set(db.execute(text("SELECT version_num FROM alembic_version")).scalars())
                if revisions != expected_database_heads():
                    return JSONResponse({"status": "not_ready", "service": "backend"}, status_code=503)
        except (SQLAlchemyError, RedisError):
            return JSONResponse({"status": "not_ready", "service": "backend"}, status_code=503)
        return {"status": "ready", "service": "backend"}

    if str(settings.database_url).startswith("sqlite"):
        Base.metadata.create_all(bind=engine)

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
