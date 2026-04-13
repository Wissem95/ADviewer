import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import create_app


@pytest.fixture
def app(tmp_path):
    """Crée une instance FastAPI pour les tests avec DB temporaire."""
    return create_app(db_path=str(tmp_path / "test.db"))


@pytest_asyncio.fixture
async def client(app):
    """Client HTTP asynchrone avec lifespan FastAPI activé (init_db inclus)."""
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
