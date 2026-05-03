"""Tests pour backend/pipeline/stage_5_execute.py (Plan 5A Task 10).

Stage5 utilise tool-calling write avec git stash en préambule + rollback
automatique sur exception.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.file_lock import FileLock
from backend.pipeline.stage_5_execute import ExecuteResult, Stage5Execute
from backend.pipeline.types import PipelineContext, PipelineMode


class _FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


def _init_git(tmp_path: Path) -> None:
    """Initialise un git repo minimal dans tmp_path."""
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test"], cwd=str(tmp_path), check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "test"], cwd=str(tmp_path), check=True
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init", "-q"],
        cwd=str(tmp_path),
        check=True,
    )


def _make_ctx(tmp_path: Path, prompt: str = "Create hello.py") -> PipelineContext:
    return PipelineContext(
        prompt=prompt,
        workspace_root=tmp_path,
        session_id="test",
        mode=PipelineMode.SIMPLE,
    )


def _tool_call(call_id: str, name: str, arguments_json: str):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments_json),
    )


def _mock_response(tool_calls=None, content=""):
    msg = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
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
async def test_stage_5_creates_file_via_tool_call(tmp_path):
    _init_git(tmp_path)

    responses = iter([
        _mock_response(tool_calls=[
            _tool_call("c1", "create_file",
                       '{"path": "hello.py", "content": "print(\\"hi\\")\\n"}')
        ]),
        _mock_response(content="EXECUTE_DONE\nhello.py créé"),
    ])

    async def fake_acompletion(**kwargs):
        return next(responses)

    with patch("backend.pipeline.stage_5_execute.acompletion", side_effect=fake_acompletion):
        stage = Stage5Execute(llm_manager=None, ws_streamer=_FakeWS())
        stage.file_lock = FileLock()
        result = await stage.run(_make_ctx(tmp_path))

    assert result.success is True
    output: ExecuteResult = result.output
    assert "hello.py" in output.files_modified
    assert (tmp_path / "hello.py").read_text() == 'print("hi")\n'


@pytest.mark.asyncio
async def test_stage_5_tracks_multiple_files_modified(tmp_path):
    _init_git(tmp_path)
    (tmp_path / "existing.py").write_text("old\n")
    import subprocess
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
    subprocess.run(
        ["git", "commit", "-m", "existing", "-q"], cwd=str(tmp_path), check=True
    )

    responses = iter([
        _mock_response(tool_calls=[
            _tool_call("c1", "edit_file",
                       '{"path": "existing.py", "content": "new\\n"}'),
        ]),
        _mock_response(tool_calls=[
            _tool_call("c2", "create_file",
                       '{"path": "added.py", "content": "added\\n"}'),
        ]),
        _mock_response(content="done"),
    ])

    async def fake_acompletion(**kwargs):
        return next(responses)

    with patch("backend.pipeline.stage_5_execute.acompletion", side_effect=fake_acompletion):
        stage = Stage5Execute(llm_manager=None, ws_streamer=_FakeWS())
        stage.file_lock = FileLock()
        result = await stage.run(_make_ctx(tmp_path))

    assert result.success is True
    assert set(result.output.files_modified) == {"existing.py", "added.py"}


@pytest.mark.asyncio
async def test_stage_5_no_tool_calls_returns_empty(tmp_path):
    _init_git(tmp_path)

    responses = iter([
        _mock_response(content="rien à faire"),
    ])

    async def fake_acompletion(**kwargs):
        return next(responses)

    with patch("backend.pipeline.stage_5_execute.acompletion", side_effect=fake_acompletion):
        stage = Stage5Execute(llm_manager=None, ws_streamer=_FakeWS())
        stage.file_lock = FileLock()
        result = await stage.run(_make_ctx(tmp_path))

    assert result.success is True
    assert result.output.files_modified == []


@pytest.mark.asyncio
async def test_stage_5_propagates_tool_error_to_llm(tmp_path):
    """Tool error (path hors workspace) → injecté au LLM, pas de crash."""
    _init_git(tmp_path)

    responses = iter([
        _mock_response(tool_calls=[
            _tool_call("c1", "edit_file",
                       '{"path": "/etc/passwd", "content": "hacked"}'),
        ]),
        _mock_response(content="ne peut pas écrire hors workspace"),
    ])

    async def fake_acompletion(**kwargs):
        return next(responses)

    with patch("backend.pipeline.stage_5_execute.acompletion", side_effect=fake_acompletion):
        stage = Stage5Execute(llm_manager=None, ws_streamer=_FakeWS())
        stage.file_lock = FileLock()
        result = await stage.run(_make_ctx(tmp_path))

    # Le stage termine avec succès (pas de crash), aucun fichier modifié.
    assert result.success is True
    assert result.output.files_modified == []


@pytest.mark.asyncio
async def test_stage_5_budget_exceeded(tmp_path):
    """Boucle infinie → stop à 20 itérations + retour error."""
    _init_git(tmp_path)
    (tmp_path / "x.py").write_text("a")
    import subprocess
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
    subprocess.run(
        ["git", "commit", "-m", "x", "-q"], cwd=str(tmp_path), check=True
    )

    counter = [0]

    async def fake_acompletion(**kwargs):
        counter[0] += 1
        return _mock_response(tool_calls=[
            _tool_call(f"c{counter[0]}", "edit_file",
                       '{"path": "x.py", "content": "always-changing-' + str(counter[0]) + '"}'),
        ])

    with patch("backend.pipeline.stage_5_execute.acompletion", side_effect=fake_acompletion):
        stage = Stage5Execute(llm_manager=None, ws_streamer=_FakeWS())
        stage.file_lock = FileLock()
        result = await stage.run(_make_ctx(tmp_path))

    assert result.success is False
    assert "budget" in result.error.lower()


@pytest.mark.asyncio
async def test_stage_5_stash_ref_set_in_output(tmp_path):
    """Le stash_ref retourné permet à l'orchestrator de rollback."""
    _init_git(tmp_path)

    responses = iter([
        _mock_response(tool_calls=[
            _tool_call("c1", "create_file",
                       '{"path": "a.py", "content": "a\\n"}')
        ]),
        _mock_response(content="done"),
    ])

    async def fake_acompletion(**kwargs):
        return next(responses)

    with patch("backend.pipeline.stage_5_execute.acompletion", side_effect=fake_acompletion):
        stage = Stage5Execute(llm_manager=None, ws_streamer=_FakeWS())
        stage.file_lock = FileLock()
        result = await stage.run(_make_ctx(tmp_path))

    assert result.success is True
    # stash_ref peut être vide si rien à stash, ou non-vide. Test : présent.
    assert hasattr(result.output, "stash_ref")


def test_stage_5_name():
    assert Stage5Execute.name == "execute"


def test_stage_5_uses_minimax():
    stage = Stage5Execute(llm_manager=None, ws_streamer=_FakeWS())
    assert stage._llm_for_stage() == "minimax/minimax-m2.5"
