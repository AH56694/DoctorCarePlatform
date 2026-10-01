import asyncio
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from backend.app.api.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.main import create_app


@pytest.mark.parametrize("path", [
    "/api/v1/ai/sessions",
    "/api/v1/ai/sessions/owned-session/messages",
])
def test_slow_history_query_does_not_block_other_requests(path):
    app = create_app()
    query_started = Event()
    query_finished = Event()
    release_query = Event()

    def slow_query():
        query_started.set()
        # Bound the wait so a regression cannot hang the test process.
        release_query.wait(timeout=5)
        query_finished.set()
        return []

    def database():
        query = Mock()
        for method in ("filter", "order_by", "limit"):
            getattr(query, method).return_value = query
        query.first.return_value = SimpleNamespace(user_id="owner")
        query.all.side_effect = slow_query
        db = Mock()
        db.query.return_value = query
        yield db

    async def current_user():
        return SimpleNamespace(id="owner")

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = current_user

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
        ) as client:
            history = asyncio.create_task(client.get(path))
            try:
                assert await asyncio.to_thread(query_started.wait, 2)
                health = await asyncio.wait_for(client.get("/health"), timeout=2)
                assert health.status_code == 200
                assert not query_finished.is_set(), (
                    "Health must respond while the query is still blocked"
                )
            finally:
                release_query.set()
                response = await history
            assert response.status_code == 200
            assert response.json() == []

    asyncio.run(exercise())
