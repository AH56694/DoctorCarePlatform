from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    project_name: str = "DoctorCarePlatform"
    database_url: str = "mysql+pymysql://root:change-me@127.0.0.1:3306/doctor_care_platform?charset=utf8mb4"
    redis_url: str = "redis://127.0.0.1:6379/0"
    rag_service_url: AnyHttpUrl | str = "http://127.0.0.1:8300"
    rag_service_token: str = "development-service-token"
    rag_stream_timeout_seconds: int = Field(default=120, ge=10, le=600)
    auth_secret_key: str = "development-only-change-me-before-production"
    auth_token_expire_minutes: int = Field(default=120, ge=5, le=1440)
    auth_issuer: str = "doctor-care-platform"
    auth_rate_limit_enabled: bool = True
    auth_rate_limit_attempts: int = Field(default=10, ge=1, le=100)
    auth_rate_limit_window_seconds: int = Field(default=300, ge=10, le=3600)
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    recruitment_model_path: str = ".local-models/recruitment_recommender.pt"
    recruitment_exploration_rate: float = Field(default=0.08, ge=0, le=0.3)

    aliyun_sms_access_key_id: str = ""
    aliyun_sms_access_key_secret: str = ""
    aliyun_sms_sign_name: str = ""
    aliyun_sms_template_code: str = ""

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in {"production", "prod"}

    def validate_production(self) -> None:
        if not self.is_production:
            return
        placeholders = ("development", "replace-with", "change-me", "example")
        for name in ("auth_secret_key", "rag_service_token"):
            value = getattr(self, name)
            if len(value.strip()) < 32 or any(word in value.lower() for word in placeholders):
                raise RuntimeError(f"{name.upper()} must contain at least 32 random characters")
        if self.rag_service_token == self.auth_secret_key:
            raise RuntimeError("RAG_SERVICE_TOKEN must differ from AUTH_SECRET_KEY")
        database = make_url(self.database_url)
        if database.get_backend_name() != "mysql":
            raise RuntimeError("Production DATABASE_URL must use MySQL")
        if database.username == "root" or not database.password or any(
            word in database.password.lower() for word in placeholders
        ):
            raise RuntimeError("Production database requires a dedicated user and a non-demo password")
        if any(origin == "*" or not origin.startswith("https://") for origin in self.cors_origins):
            raise RuntimeError("Production CORS_ORIGINS must contain explicit HTTPS origins")
        if not self.auth_rate_limit_enabled:
            raise RuntimeError("Authentication rate limiting must remain enabled in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
