import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(db_path=str(tmp_path / "test.db"))


@pytest_asyncio.fixture
async def client(app):
    """Client HTTP asynchrone avec lifespan FastAPI activé (init_db inclus)."""
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "llms" in data


@pytest.mark.asyncio
async def test_route_endpoint(client):
    resp = await client.post("/route", json={"prompt": "Corrige un typo"})
    assert resp.status_code == 200
    data = resp.json()
    assert "llm" in data
    assert "score" in data
    assert "mode" in data


@pytest.mark.asyncio
async def test_llms_list_endpoint(client):
    resp = await client.get("/llms")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 5  # 5 LLMs configurés


@pytest.mark.asyncio
async def test_disable_enable_llm(client):
    # Disable
    resp = await client.post("/llms/minimax/minimax-m2.5/disable")
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"

    # Enable
    resp = await client.post("/llms/minimax/minimax-m2.5/enable")
    assert resp.status_code == 200
    assert resp.json()["status"] == "enabled"


@pytest.mark.asyncio
async def test_route_with_mention(client):
    resp = await client.post("/route", json={
        "prompt": "Corrige un typo",
        "mention": "deepseek"
    })
    data = resp.json()
    assert "deepseek" in data["llm"]
