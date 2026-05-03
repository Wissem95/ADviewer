"""Tests pour backend/pipeline/stage_3_ground.py (Plan 5A Task 9).

Stage3 utilise tool-calling (TOOLS_SCHEMA_READ) en boucle. On mock litellm
acompletion pour qu'il retourne une séquence de tool_calls puis un message
final. Le stage doit :
- Exécuter chaque tool_call via execute_tool.
- Accumuler files_read / greps_performed.
- S'arrêter à 20 itérations max.
- Retourner un GroundedContext avec citations.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.file_lock import FileLock
from backend.pipeline.stage_3_ground import GroundedContext, Stage3Ground
from backend.pipeline.types import PipelineContext, PipelineMode


class _FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


def _make_ctx(tmp_path: Path, prompt: str = "Refactor auth") -> PipelineContext:
    return PipelineContext(
        prompt=prompt,
        workspace_root=tmp_path,
        session_id="test",
        mode=PipelineMode.SIMPLE,
    )


def _tool_call(call_id: str, name: str, arguments_json: str):
    """Construit un objet simulant la shape d'un tool_call litellm."""
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments_json),
    )


def _mock_response(tool_calls=None, content=""):
    """Construit une réponse litellm avec ou sans tool_calls."""
    msg = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        # model_dump pour pouvoir append messages
        model_dump=lambda: {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in (tool_calls or [])
            ],
        },
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


@pytest.mark.asyncio
async def test_stage_3_executes_read_file_tool_call(tmp_path):
    (tmp_path / "auth.py").write_text("def login(): return 'jwt'\n")

    # Séquence : 1) read_file auth.py, 2) message final
    responses = iter([
        _mock_response(tool_calls=[
            _tool_call("c1", "read_file", '{"path": "auth.py"}')
        ]),
        _mock_response(content="GROUNDED_CONTEXT\nauth.py lu, login retourne jwt"),
    ])

    async def fake_acompletion(**kwargs):
        return next(responses)

    with patch("backend.pipeline.stage_3_ground.acompletion", side_effect=fake_acompletion):
        stage = Stage3Ground(llm_manager=None, ws_streamer=_FakeWS())
        stage.file_lock = FileLock()
        result = await stage.run(_make_ctx(tmp_path))

    assert result.success is True
    grounded: GroundedContext = result.output
    assert "auth.py" in grounded.files_read
    assert "login" in grounded.files_read["auth.py"]
    assert grounded.summary  # le message final est conservé


@pytest.mark.asyncio
async def test_stage_3_executes_grep_tool_call(tmp_path):
    (tmp_path / "main.py").write_text("from auth import login\nlogin()\n")

    responses = iter([
        _mock_response(tool_calls=[
            _tool_call("c1", "grep_codebase", '{"pattern": "login"}')
        ]),
        _mock_response(content="found callers"),
    ])

    async def fake_acompletion(**kwargs):
        return next(responses)

    with patch("backend.pipeline.stage_3_ground.acompletion", side_effect=fake_acompletion):
        stage = Stage3Ground(llm_manager=None, ws_streamer=_FakeWS())
        stage.file_lock = FileLock()
        result = await stage.run(_make_ctx(tmp_path))

    assert result.success is True
    grounded = result.output
    assert len(grounded.greps_performed) == 1
    assert grounded.greps_performed[0]["pattern"] == "login"


@pytest.mark.asyncio
async def test_stage_3_no_tool_calls_returns_immediately(tmp_path):
    """Si le LLM répond directement sans tool_calls, on retourne le summary."""
    responses = iter([
        _mock_response(content="rien à grounder"),
    ])

    async def fake_acompletion(**kwargs):
        return next(responses)

    with patch("backend.pipeline.stage_3_ground.acompletion", side_effect=fake_acompletion):
        stage = Stage3Ground(llm_manager=None, ws_streamer=_FakeWS())
        stage.file_lock = FileLock()
        result = await stage.run(_make_ctx(tmp_path))

    assert result.success is True
    assert result.output.files_read == {}
    assert result.output.greps_performed == []
    assert result.output.summary == "rien à grounder"


@pytest.mark.asyncio
async def test_stage_3_budget_exceeded_after_20_iterations(tmp_path):
    """Si le LLM boucle sans s'arrêter, on stoppe à 20 et on retourne quand même."""
    (tmp_path / "x.py").write_text("x = 1")

    # Toujours retourner un tool_call (boucle infinie côté LLM)
    def make_response():
        return _mock_response(tool_calls=[
            _tool_call("c1", "read_file", '{"path": "x.py"}')
        ])

    async def fake_acompletion(**kwargs):
        return make_response()

    with patch("backend.pipeline.stage_3_ground.acompletion", side_effect=fake_acompletion):
        stage = Stage3Ground(llm_manager=None, ws_streamer=_FakeWS())
        stage.file_lock = FileLock()
        result = await stage.run(_make_ctx(tmp_path))

    # Le stage retourne success=False car budget dépassé.
    assert result.success is False
    assert "budget" in result.error.lower()


@pytest.mark.asyncio
async def test_stage_3_propagates_tool_error_to_llm(tmp_path):
    """Un tool_call vers un fichier hors workspace doit être renvoyé au LLM
    sous forme de tool_call_result(success=False), pas crasher le stage."""
    responses = iter([
        _mock_response(tool_calls=[
            _tool_call("c1", "read_file", '{"path": "/etc/passwd"}')
        ]),
        # Le LLM voit l'erreur et abandonne
        _mock_response(content="ne peut pas lire hors workspace"),
    ])

    async def fake_acompletion(**kwargs):
        return next(responses)

    with patch("backend.pipeline.stage_3_ground.acompletion", side_effect=fake_acompletion):
        stage = Stage3Ground(llm_manager=None, ws_streamer=_FakeWS())
        stage.file_lock = FileLock()
        result = await stage.run(_make_ctx(tmp_path))

    # Le stage termine avec succès (pas de crash), le LLM a vu l'erreur tool.
    assert result.success is True
    assert "/etc/passwd" not in result.output.files_read


def test_stage_3_name():
    assert Stage3Ground.name == "ground"


def test_stage_3_uses_minimax():
    stage = Stage3Ground(llm_manager=None, ws_streamer=_FakeWS())
    assert stage._llm_for_stage() == "minimax/minimax-m2.5"
