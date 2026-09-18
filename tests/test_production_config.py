import pytest

from backend.app.core.config import Settings
from backend.app.main import expected_database_heads


def production_settings(**overrides):
    return Settings(_env_file=None, **{
        "app_env": "production",
        "auth_secret_key": "9ca437de" * 8,
        "rag_service_token": "82bf6a01" * 8,
        "database_url": "mysql+pymysql://application:secure-password@mysql/db",
        "cors_origins": ["https://care.example.org"],
        **overrides,
    })


@pytest.mark.parametrize("overrides,match", [
    ({"auth_secret_key": "replace-with-at-least-32-random-characters"}, "AUTH_SECRET_KEY"),
    ({"rag_service_token": "development-service-token"}, "RAG_SERVICE_TOKEN"),
    ({"rag_service_token": "9ca437de" * 8}, "differ"),
    ({"database_url": "mysql+pymysql://root:secure-password@mysql/db"}, "dedicated user"),
    ({"database_url": "sqlite:///production.db"}, "MySQL"),
    ({"cors_origins": ["*"]}, "CORS_ORIGINS"),
    ({"auth_rate_limit_enabled": False}, "rate limiting"),
])
def test_production_rejects_unsafe_configuration(overrides, match):
    with pytest.raises(RuntimeError, match=match):
        production_settings(**overrides).validate_production()


def test_production_settings_and_migration_head():
    production_settings().validate_production()
    assert expected_database_heads() == {"20260905_mysql_0001"}
