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
async def test_route_endpoint(app):
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/route", json={"prompt": "Corrige un typo"})
    assert resp.status_code == 200
    data = resp.json()
    # Typo = simple → minimax
    assert data["llm"] == "minimax/minimax-m2.5"
    assert data["mode"] == "simple"
    assert data["role"] == "coding"
    assert data["score"] <= 4


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


@pytest.mark.asyncio
async def test_chat_endpoint(app):
    """POST /chat passe par l'orchestrateur et retourne le contenu."""
    from unittest.mock import AsyncMock, MagicMock, patch
    transport = ASGITransport(app=app)

    # Mock task_queue.submit pour ne pas lancer un vrai LLM
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            fake_result = MagicMock(content="Voici la réponse", tokens=42, files_modified=[], attempts=1)
            with patch.object(app.state.orchestrator.task_queue, "submit", new=AsyncMock(return_value=fake_result)):
                resp = await client.post("/chat", json={"prompt": "Corrige un typo"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "Voici la réponse"
    assert data["tokens"] == 42
    assert "minimax" in data["llm"]


@pytest.mark.asyncio
async def test_project_status_inactive(app):
    """GET /project/status retourne active=False par défaut."""
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/project/status")
    assert resp.status_code == 200
    assert resp.json()["active"] is False


@pytest.mark.asyncio
async def test_project_feedback_saved(app):
    """POST /project/feedback persiste la correction."""
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/project/feedback", json={
                "prompt": "Refacto module auth",
                "routed_to": "minimax/minimax-m2.5",
                "corrected_to": "deepseek/deepseek-r1",
            })
    assert resp.status_code == 200
    assert resp.json()["saved"] is True
