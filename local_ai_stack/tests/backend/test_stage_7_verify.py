"""Tests pour backend/pipeline/stage_7_verify.py (Plan 5A Task 11).

Stage7Verify minimal :
- ruff check sur chaque .py modifié.
- cargo check sur ui/src-tauri/ si au moins un .rs touché.
- Retourne VerifyResult(lint_errors, all_green, attempts_used=1).
- Pas de retry interne à ce stade (étendu en Plan 5B).
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.pipeline.stage_7_verify import Stage7Verify, VerifyResult
from backend.pipeline.types import (
    PipelineContext,
    PipelineMode,
    StageResult,
)


class _FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


def _make_ctx(tmp_path: Path, files_modified=None) -> PipelineContext:
    ctx = PipelineContext(
        prompt="Crée hello.py",
        workspace_root=tmp_path,
        session_id="test",
        mode=PipelineMode.SIMPLE,
    )
    if files_modified is not None:
        execute_output = SimpleNamespace(
            files_modified=files_modified,
            stash_ref="",
        )
        ctx.stage_results["execute"] = StageResult(
            stage_name="execute",
            duration_ms=0,
            success=True,
            output=execute_output,
        )
    return ctx


class _FakeProc:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_stage_7_no_files_modified_returns_all_green(tmp_path):
    """Aucun fichier modifié → all_green=True, pas d'invocation ruff/cargo."""
    stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path, files_modified=[]))

    assert result.success is True
    output: VerifyResult = result.output
    assert output.all_green is True
    assert output.lint_errors == []
    assert output.attempts_used == 1


@pytest.mark.asyncio
async def test_stage_7_runs_ruff_on_python_files(tmp_path):
    """Stage7 invoque ruff check sur les .py modifiés."""
    (tmp_path / "ok.py").write_text("x = 1\n")

    invocations = []

    async def fake_subprocess(*args, **kwargs):
        invocations.append(args)
        return _FakeProc(returncode=0)

    with patch("backend.pipeline.stage_7_verify.asyncio.create_subprocess_exec",
               side_effect=fake_subprocess):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        result = await stage.run(_make_ctx(tmp_path, files_modified=["ok.py"]))

    assert result.success is True
    assert result.output.all_green is True
    assert any(args[0] == "ruff" for args in invocations)


@pytest.mark.asyncio
async def test_stage_7_captures_ruff_errors(tmp_path):
    """Si ruff retourne != 0, lint_errors capturés et all_green=False."""
    (tmp_path / "bad.py").write_text("import nope\n")

    async def fake_subprocess(*args, **kwargs):
        return _FakeProc(
            returncode=1,
            stdout=b"bad.py:1:8: F401 'nope' imported but unused\n",
            stderr=b"",
        )

    with patch("backend.pipeline.stage_7_verify.asyncio.create_subprocess_exec",
               side_effect=fake_subprocess):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        result = await stage.run(_make_ctx(tmp_path, files_modified=["bad.py"]))

    assert result.success is True
    output: VerifyResult = result.output
    assert output.all_green is False
    assert len(output.lint_errors) >= 1
    assert any("F401" in err for err in output.lint_errors)


@pytest.mark.asyncio
async def test_stage_7_runs_cargo_check_if_rs_modified(tmp_path):
    """Si au moins un .rs touché, cargo check est exécuté sur ui/src-tauri/."""
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "src-tauri").mkdir()
    (tmp_path / "ui" / "src-tauri" / "Cargo.toml").write_text("[package]\nname = \"x\"\n")

    invocations = []

    async def fake_subprocess(*args, **kwargs):
        invocations.append(args)
        return _FakeProc(returncode=0)

    with patch("backend.pipeline.stage_7_verify.asyncio.create_subprocess_exec",
               side_effect=fake_subprocess):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        result = await stage.run(_make_ctx(
            tmp_path, files_modified=["ui/src-tauri/src/main.rs"]
        ))

    assert result.success is True
    assert any(args[0] == "cargo" and "check" in args for args in invocations)


@pytest.mark.asyncio
async def test_stage_7_skips_cargo_when_no_rs(tmp_path):
    """Aucun .rs modifié → cargo check non invoqué."""
    (tmp_path / "x.py").write_text("y=1\n")

    invocations = []

    async def fake_subprocess(*args, **kwargs):
        invocations.append(args)
        return _FakeProc(returncode=0)

    with patch("backend.pipeline.stage_7_verify.asyncio.create_subprocess_exec",
               side_effect=fake_subprocess):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        await stage.run(_make_ctx(tmp_path, files_modified=["x.py"]))

    assert not any(args[0] == "cargo" for args in invocations)


@pytest.mark.asyncio
async def test_stage_7_no_execute_output_returns_all_green(tmp_path):
    """Si Stage5 absent du ctx, on considère all_green (rien à vérifier)."""
    stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
    ctx = PipelineContext(
        prompt="x",
        workspace_root=tmp_path,
        session_id="t",
        mode=PipelineMode.SIMPLE,
    )
    result = await stage.run(ctx)

    assert result.success is True
    assert result.output.all_green is True
    assert result.output.attempts_used == 1


def test_stage_7_name():
    assert Stage7Verify.name == "verify"


def test_stage_7_no_llm():
    """Stage7 est mécanique, pas de LLM."""
    stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
    assert stage._llm_for_stage() is None
