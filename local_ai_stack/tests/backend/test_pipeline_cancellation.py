"""Tests pour Pipeline cancellation (Plan 5B Task 6).

Comportement attendu :
- Pipeline.run() wrappe son corps en try/except asyncio.CancelledError.
- Sur CancelledError : si stash_ref est présent (Stage5 a tourné), git_stash_pop
  → success=False, rollback_performed=True, error="cancelled by user".
- Si CancelledError avant Stage5 : pas de rollback, juste success=False, error="cancelled by user".
- Stage5/Stage7 (en cours) propagent CancelledError naturellement via asyncio.

Pour le test, on simule une cancellation en faisant `task.cancel()` après
un délai pour intercepter pendant un stage donné.
"""
import asyncio
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.file_lock import FileLock
from backend.pipeline.orchestrator import Pipeline
from backend.pipeline.stage_5_execute import ExecuteResult
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


def _init_git(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=str(tmp_path), check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=str(tmp_path), check=True
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init", "-q"],
        cwd=str(tmp_path),
        check=True,
    )


def _make_ctx(tmp_path: Path) -> PipelineContext:
    return PipelineContext(
        prompt="x",
        workspace_root=tmp_path,
        session_id="cancel",
        mode=PipelineMode.SIMPLE,
    )


def _stage_class_that_sleeps(name: str, output=None):
    """Construit une classe Stage qui dort pour permettre une cancellation
    en cours. Si output fourni, écrit dans ctx.stage_results pour tester
    la branche post-Stage5."""

    class _SleepingStage:
        pass

    _SleepingStage.name = name

    def _init(self, llm, ws):
        pass

    async def _run(self, ctx):
        # Si output spécifié, on s'enregistre AVANT de dormir → simule
        # qu'on a déjà commencé à écrire des fichiers / créé un stash.
        if output is not None:
            sr = StageResult(
                stage_name=name, duration_ms=0, success=True, output=output,
            )
            ctx.stage_results[name] = sr
        await asyncio.sleep(10)  # Sera annulé.
        return None  # pragma: no cover

    _SleepingStage.__init__ = _init
    _SleepingStage.run = _run
    return _SleepingStage


def _stage_class_that_succeeds(name: str, output=None):
    class _OkStage:
        pass

    _OkStage.name = name

    def _init(self, llm, ws):
        pass

    async def _run(self, ctx):
        sr = StageResult(stage_name=name, duration_ms=1, success=True, output=output)
        ctx.stage_results[name] = sr
        return sr

    _OkStage.__init__ = _init
    _OkStage.run = _run
    return _OkStage


@pytest.mark.asyncio
async def test_pipeline_cancel_before_execute_no_rollback(tmp_path):
    """Cancel pendant Stage1 (avant Stage5) → success=False, pas de rollback."""
    _init_git(tmp_path)

    pipeline = Pipeline(llm_manager=None, ws_streamer=_FakeWS(), file_lock=FileLock())
    pipeline.stages_by_mode[PipelineMode.SIMPLE] = [
        _stage_class_that_succeeds("estimate"),
        _stage_class_that_sleeps("intake"),  # ← se fait cancel ici
        _stage_class_that_succeeds("ground"),
        _stage_class_that_succeeds("execute"),
        _stage_class_that_succeeds("verify"),
    ]

    pop_called = []

    async def fake_pop(*args, **kwargs):
        pop_called.append(True)
        return True

    with patch("backend.pipeline.orchestrator.git_stash_pop", side_effect=fake_pop):
        task = asyncio.create_task(pipeline.run(_make_ctx(tmp_path)))
        await asyncio.sleep(0.05)
        task.cancel()
        result = await task

    assert result.success is False
    assert "cancel" in (result.error or "").lower()
    assert result.rollback_performed is False
    assert pop_called == []  # Pas de stash à popper.


@pytest.mark.asyncio
async def test_pipeline_cancel_after_execute_triggers_rollback(tmp_path):
    """Cancel pendant Stage7 (après Stage5 stash) → rollback via stash_pop."""
    _init_git(tmp_path)

    execute_output = ExecuteResult(
        files_modified=["x.py"],
        stash_ref="stash@{0}",
        summary="done",
    )

    pipeline = Pipeline(llm_manager=None, ws_streamer=_FakeWS(), file_lock=FileLock())
    pipeline.stages_by_mode[PipelineMode.SIMPLE] = [
        _stage_class_that_succeeds("estimate"),
        _stage_class_that_succeeds("intake"),
        _stage_class_that_succeeds("ground"),
        _stage_class_that_succeeds("execute", output=execute_output),
        _stage_class_that_sleeps("verify"),  # ← cancel ici
    ]

    pop_called = []

    async def fake_pop(workspace_root, stash_ref):
        pop_called.append(stash_ref)
        return True

    with patch("backend.pipeline.orchestrator.git_stash_pop", side_effect=fake_pop):
        task = asyncio.create_task(pipeline.run(_make_ctx(tmp_path)))
        await asyncio.sleep(0.05)
        task.cancel()
        result = await task

    assert result.success is False
    assert "cancel" in (result.error or "").lower()
    assert result.rollback_performed is True
    assert pop_called == ["stash@{0}"]


@pytest.mark.asyncio
async def test_pipeline_cancel_during_execute_rollbacks(tmp_path):
    """Cancel pendant Stage5 → rollback (Stage5 a déjà créé son stash)."""
    _init_git(tmp_path)

    # Stage5 enregistre son output (avec stash_ref) AVANT le sleep, comme
    # _stage_class_that_sleeps avec output fourni.
    execute_output = ExecuteResult(
        files_modified=[],
        stash_ref="stash@{0}",
        summary="",
    )

    pipeline = Pipeline(llm_manager=None, ws_streamer=_FakeWS(), file_lock=FileLock())
    pipeline.stages_by_mode[PipelineMode.SIMPLE] = [
        _stage_class_that_succeeds("estimate"),
        _stage_class_that_succeeds("intake"),
        _stage_class_that_succeeds("ground"),
        _stage_class_that_sleeps("execute", output=execute_output),
        _stage_class_that_succeeds("verify"),
    ]

    pop_called = []

    async def fake_pop(workspace_root, stash_ref):
        pop_called.append(stash_ref)
        return True

    with patch("backend.pipeline.orchestrator.git_stash_pop", side_effect=fake_pop):
        task = asyncio.create_task(pipeline.run(_make_ctx(tmp_path)))
        await asyncio.sleep(0.05)
        task.cancel()
        result = await task

    assert result.success is False
    assert result.rollback_performed is True
    assert pop_called == ["stash@{0}"]
