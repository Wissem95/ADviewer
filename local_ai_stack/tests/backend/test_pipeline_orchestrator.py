"""Tests pour backend/pipeline/orchestrator.py (Plan 5A Task 11).

Pipeline orchestrator dispatche les stages selon le PipelineMode :
- SIMPLE : [Stage0Estimate, Stage1Intake, Stage3Ground, Stage5Execute, Stage7Verify].

Tests :
- Mock tous les stages OK → success=True, files_modified correct, accumulation cost.
- Stage5 échoue → rollback via git_stash_pop, success=False, rollback_performed=True.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.pipeline.orchestrator import Pipeline
from backend.pipeline.types import (
    PipelineContext,
    PipelineMode,
    PipelineResult,
    StageResult,
)


class _FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


def _make_ctx(tmp_path: Path) -> PipelineContext:
    return PipelineContext(
        prompt="Crée hello.py",
        workspace_root=tmp_path,
        session_id="test",
        mode=PipelineMode.SIMPLE,
    )


def _ok_stage(name: str, output=None, cost=0.001, tokens=(100, 50)):
    """Construit une classe Stage qui retourne success=True."""

    class _MockStage:
        # name doit être attribut classe pour être lu par orchestrator
        pass

    _MockStage.name = name

    async def _run(self, ctx):
        sr = StageResult(
            stage_name=name,
            duration_ms=10,
            success=True,
            tokens_in=tokens[0],
            tokens_out=tokens[1],
            cost_usd=cost,
            output=output,
        )
        ctx.stage_results[name] = sr
        ctx.total_cost_usd += cost
        ctx.total_tokens_in += tokens[0]
        ctx.total_tokens_out += tokens[1]
        return sr

    _MockStage.__init__ = lambda self, llm_manager, ws_streamer: None
    _MockStage.run = _run
    return _MockStage


def _failing_stage(name: str, output=None):
    class _MockStage:
        pass

    _MockStage.name = name

    async def _run(self, ctx):
        sr = StageResult(
            stage_name=name,
            duration_ms=10,
            success=False,
            output=output,
            error="boom",
        )
        ctx.stage_results[name] = sr
        return sr

    _MockStage.__init__ = lambda self, llm_manager, ws_streamer: None
    _MockStage.run = _run
    return _MockStage


@pytest.mark.asyncio
async def test_pipeline_simple_all_stages_ok(tmp_path):
    """Mode SIMPLE avec stages mockés OK → PipelineResult success=True."""
    execute_output = SimpleNamespace(
        files_modified=["hello.py"],
        stash_ref="stash@{0}",
    )
    verify_output = SimpleNamespace(all_green=True, lint_errors=[], attempts_used=1)

    stages = [
        _ok_stage("estimate", output={"mode": "simple"}, cost=0.0001),
        _ok_stage("intake", output={"prompt_cleaned": "x"}, cost=0.0002),
        _ok_stage("ground", output=SimpleNamespace(summary="..."), cost=0.001),
        _ok_stage("execute", output=execute_output, cost=0.005),
        _ok_stage("verify", output=verify_output, cost=0.0),
    ]

    pipeline = Pipeline(llm_manager=None, ws_streamer=_FakeWS(), file_lock=None)
    pipeline.stages_by_mode[PipelineMode.SIMPLE] = stages

    result = await pipeline.run(_make_ctx(tmp_path))

    assert result.success is True
    assert result.files_modified == ["hello.py"]
    assert len(result.stages) == 5
    # Accumulation cost
    assert result.total_cost_usd == pytest.approx(0.0001 + 0.0002 + 0.001 + 0.005 + 0.0)
    assert result.rollback_performed is False


@pytest.mark.asyncio
async def test_pipeline_execute_fails_triggers_rollback(tmp_path):
    """Si Stage5 échoue après que stash a été créé → rollback via git_stash_pop."""
    execute_output_with_stash = SimpleNamespace(
        files_modified=[],
        stash_ref="stash@{0}",
    )
    stages = [
        _ok_stage("estimate"),
        _ok_stage("intake"),
        _ok_stage("ground"),
        _failing_stage("execute", output=execute_output_with_stash),
        _ok_stage("verify"),
    ]

    pipeline = Pipeline(llm_manager=None, ws_streamer=_FakeWS(), file_lock=None)
    pipeline.stages_by_mode[PipelineMode.SIMPLE] = stages

    pop_mock = AsyncMock(return_value=True)
    with patch("backend.pipeline.orchestrator.git_stash_pop", pop_mock):
        result = await pipeline.run(_make_ctx(tmp_path))

    assert result.success is False
    assert result.rollback_performed is True
    pop_mock.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_first_stage_fails_no_rollback_needed(tmp_path):
    """Si Stage0/1/3 échoue avant Stage5, pas de stash à pop."""
    stages = [
        _ok_stage("estimate"),
        _failing_stage("intake"),
        _ok_stage("ground"),
        _ok_stage("execute"),
        _ok_stage("verify"),
    ]

    pipeline = Pipeline(llm_manager=None, ws_streamer=_FakeWS(), file_lock=None)
    pipeline.stages_by_mode[PipelineMode.SIMPLE] = stages

    pop_mock = AsyncMock(return_value=True)
    with patch("backend.pipeline.orchestrator.git_stash_pop", pop_mock):
        result = await pipeline.run(_make_ctx(tmp_path))

    assert result.success is False
    assert result.rollback_performed is False
    pop_mock.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_simple_mode_default_stages(tmp_path):
    """En mode SIMPLE, la liste par défaut contient bien 5 classes."""
    pipeline = Pipeline(llm_manager=None, ws_streamer=_FakeWS(), file_lock=None)
    stages = pipeline.stages_by_mode[PipelineMode.SIMPLE]
    # 5 stages : estimate, intake, ground, execute, verify.
    assert len(stages) == 5
    names = [s.name for s in stages]
    assert names == ["estimate", "intake", "ground", "execute", "verify"]


@pytest.mark.asyncio
async def test_pipeline_injects_file_lock_when_supported(tmp_path):
    """Pipeline doit injecter file_lock dans les stages qui ont l'attribut."""
    received: dict = {}

    class _Stage:
        name = "execute"

        def __init__(self, llm_manager, ws_streamer):
            self.file_lock = None

        async def run(self, ctx):
            received["file_lock"] = self.file_lock
            sr = StageResult(stage_name=self.name, duration_ms=1, success=True,
                             output=SimpleNamespace(files_modified=[], stash_ref=""))
            ctx.stage_results[self.name] = sr
            return sr

    sentinel = object()
    pipeline = Pipeline(
        llm_manager=None, ws_streamer=_FakeWS(), file_lock=sentinel
    )
    pipeline.stages_by_mode[PipelineMode.SIMPLE] = [_Stage]

    await pipeline.run(_make_ctx(tmp_path))

    assert received["file_lock"] is sentinel
