import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.orchestrator import Orchestrator, OrchestratorRequest, OrchestratorResponse
from backend.models import LLMRole
from backend.roadmap import ProjectRoadmap


def _make_orchestrator(tmp_path) -> Orchestrator:
    """Factory : Orchestrator avec dépendances mockées + DB temporaire."""
    from backend.llm_manager import LLMManager
    from backend.file_lock import FileLock
    from backend.task_queue import LLMTaskQueue
    from backend.ws_streamer import WSStreamer

    llm_manager = LLMManager()
    ws_streamer = WSStreamer()
    file_lock = FileLock()
    task_queue = LLMTaskQueue()

    return Orchestrator(
        llm_manager=llm_manager,
        ws_streamer=ws_streamer,
        file_lock=file_lock,
        task_queue=task_queue,
        db_path=str(tmp_path / "orch.db"),
    )


@pytest.mark.asyncio
async def test_orchestrator_handle_returns_response(tmp_path):
    """handle() retourne OrchestratorResponse avec les champs attendus."""
    orch = _make_orchestrator(tmp_path)
    await orch.long_memory.init()
    await orch.router.init_db()

    # Mock task_queue.submit pour retourner un AgentResult fictif
    fake_result = MagicMock()
    fake_result.content = "Voici le code corrigé"
    fake_result.tokens = 150

    with patch.object(orch.task_queue, "submit", new=AsyncMock(return_value=fake_result)):
        request = OrchestratorRequest(
            user_id="user-1",
            prompt="Corrige un typo dans bouton.py",
        )
        response = await orch.handle(request)

    assert isinstance(response, OrchestratorResponse)
    assert response.content == "Voici le code corrigé"
    assert response.tokens == 150
    assert response.duration > 0
    assert "minimax" in response.llm_used  # Typo → MiniMax (simple)


@pytest.mark.asyncio
async def test_orchestrator_emits_routing_event(tmp_path):
    """handle() appelle ws.emit_routing avec la décision."""
    orch = _make_orchestrator(tmp_path)
    await orch.long_memory.init()
    await orch.router.init_db()

    fake_result = MagicMock(content="Code", tokens=50)

    with patch.object(orch.task_queue, "submit", new=AsyncMock(return_value=fake_result)):
        with patch.object(orch.ws, "emit_routing", new=AsyncMock()) as mock_emit:
            await orch.handle(OrchestratorRequest(user_id="u1", prompt="Fix typo"))

    mock_emit.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_mention_override(tmp_path):
    """@deepseek dans la requête → routage forcé vers DeepSeek."""
    orch = _make_orchestrator(tmp_path)
    await orch.long_memory.init()
    await orch.router.init_db()

    fake_result = MagicMock(content="Plan archi", tokens=300)

    with patch.object(orch.task_queue, "submit", new=AsyncMock(return_value=fake_result)):
        request = OrchestratorRequest(
            user_id="u1",
            prompt="Refactore tout le module auth",
            mention="deepseek",
        )
        response = await orch.handle(request)

    assert "deepseek" in response.llm_used.lower()
    assert response.role == LLMRole.ARCHITECTURE


@pytest.mark.asyncio
async def test_orchestrator_set_and_clear_roadmap(tmp_path):
    """set_roadmap active le mode projet, clear_roadmap le désactive."""
    orch = _make_orchestrator(tmp_path)
    assert orch.roadmap is None

    rm = ProjectRoadmap(project="mon-projet")
    await orch.set_roadmap(rm)
    assert orch.roadmap is not None
    assert orch.roadmap.project == "mon-projet"

    await orch.clear_roadmap()
    assert orch.roadmap is None


@pytest.mark.asyncio
async def test_orchestrator_records_action_in_short_memory(tmp_path):
    """Chaque handle() enregistre une action dans la mémoire courte."""
    orch = _make_orchestrator(tmp_path)
    await orch.long_memory.init()
    await orch.router.init_db()

    fake_result = MagicMock(content="Code", tokens=50)

    with patch.object(orch.task_queue, "submit", new=AsyncMock(return_value=fake_result)):
        await orch.handle(OrchestratorRequest(user_id="u1", prompt="Fix typo"))

    assert len(orch.short_memory.actions) == 1
    assert orch.short_memory.actions[0]["action"] == "handle"


@pytest.mark.asyncio
async def test_orchestrator_saves_decision_in_long_memory(tmp_path):
    """Chaque handle() persiste la décision en mémoire longue."""
    orch = _make_orchestrator(tmp_path)
    await orch.long_memory.init()
    await orch.router.init_db()

    fake_result = MagicMock(content="Voici une réponse", tokens=50)

    with patch.object(orch.task_queue, "submit", new=AsyncMock(return_value=fake_result)):
        await orch.handle(OrchestratorRequest(user_id="u1", prompt="Fix typo"))

    decisions = await orch.long_memory.get_recent_decisions()
    assert len(decisions) >= 1
    assert "Voici une réponse" in decisions[0]["content"] or decisions[0]["type"] == "routing"
