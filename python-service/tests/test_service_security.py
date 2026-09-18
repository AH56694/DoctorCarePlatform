from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from core.lazy_resource import LazyResource
from fastapi import FastAPI
from fastapi.testclient import TestClient
from service_security import ServiceAuthMiddleware, service_token


@pytest.mark.parametrize("path", ["/api/agent/run", "/api/v1/knowledge/ingest", "/api/parse"])
def test_internal_routes_reject_missing_and_wrong_tokens(path):
    app = FastAPI()
    app.add_middleware(ServiceAuthMiddleware, token="test-service-token")

    @app.post(path)
    def operation():
        return {"ok": True}

    with TestClient(app) as client:
        assert client.post(path).status_code == 401
        assert client.post(path, headers={"X-Service-Token": "wrong"}).status_code == 401
        assert client.post(path, headers={"X-Service-Token": "test-service-token"}).status_code == 200


def test_production_requires_non_demo_service_token(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("RAG_SERVICE_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="RAG_SERVICE_TOKEN"):
        service_token()
    monkeypatch.setenv("RAG_SERVICE_TOKEN", "a7c9b2d4" * 8)
    assert len(service_token()) == 64


def test_production_disables_arbitrary_path_ingestion(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    app = FastAPI()
    app.add_middleware(ServiceAuthMiddleware, token="test-service-token")
    with TestClient(app) as client:
        assert client.post(
            "/api/parse", headers={"X-Service-Token": "test-service-token"},
            json={"file_path": "/etc/passwd", "doc_id": 1},
        ).status_code == 403


def test_lazy_resource_loads_once_under_concurrent_access():
    calls = []

    def create():
        calls.append(1)
        return SimpleNamespace(value="ready")

    resource = LazyResource(create)
    assert calls == []
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(lambda _: resource.value, range(40))) == ["ready"] * 40
    assert calls == [1]


def test_failed_resource_initialization_can_retry():
    attempts = []

    def create():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("resource unavailable")
        return SimpleNamespace(value="ready")

    resource = LazyResource(create)
    with pytest.raises(RuntimeError):
        resource.get()
    assert resource.value == "ready"


def test_production_application_wires_security_before_real_routes(monkeypatch):
    import importlib.util
    from pathlib import Path

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RAG_SERVICE_TOKEN", "secure-test-token-" * 4)
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL_PATH", "")
    spec = importlib.util.spec_from_file_location(
        "production_ai_app", Path(__file__).resolve().parents[1] / "main.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with TestClient(module.app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert "environment" not in health.json()
        assert client.get("/api/agent/tools").status_code == 401
        assert client.post("/api/v1/knowledge/ingest", json={}).status_code == 401
        auth = {"X-Service-Token": "secure-test-token-" * 4}
        assert client.get("/api/agent/tools", headers=auth).status_code == 200
        assert client.get("/docs", headers=auth).status_code == 404
        assert client.get("/ready", headers=auth).status_code == 503
        assert client.post("/api/parse", headers=auth, json={}).status_code == 403
