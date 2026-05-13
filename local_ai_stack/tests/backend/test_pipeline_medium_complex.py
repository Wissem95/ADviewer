"""Tests Pipeline modes MEDIUM et COMPLEX (Plan 5C Task 8).

Vérifient que stages_by_mode contient les bons stages dans le bon ordre et
qu'un pipeline complet (mocks) tourne sans crash.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.file_lock import FileLock
from backend.pipeline.orchestrator import Pipeline
from backend.pipeline.stage_4a_plan import PlanChange, PlanResult
from backend.pipeline.stage_4b_plan_review import PlanReview
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


def _make_ctx(tmp_path: Path, mode: PipelineMode) -> PipelineContext:
    return PipelineContext(
        prompt="x",
        workspace_root=tmp_path,
        session_id="t",
        mode=mode,
    )


def _ok_stage(stage_name: str, *, output=None, cost: float = 0.0):
    """Wrapper qui fabrique une classe Stage stub retournant StageResult OK."""
    if output is None:
        output = SimpleNamespace()

    captured_name = stage_name
    captured_output = output
    captured_cost = cost

    class _StubStage:
        name = captured_name

        def __init__(self, llm, ws):
            self.llm = llm
            self.ws = ws

        async def run(self, ctx: PipelineContext) -> StageResult:
            sr = StageResult(
                stage_name=captured_name,
                duration_ms=0,
                success=True,
                cost_usd=captured_cost,
                output=captured_output,
            )
            ctx.stage_results[captured_name] = sr
            return sr

    _StubStage.__name__ = f"Stub_{captured_name}"
    return _StubStage


def test_stages_by_mode_simple_has_5_stages():
    pipeline = Pipeline(
        llm_manager=None, ws_streamer=_FakeWS(), file_lock=FileLock()
    )
    stages = pipeline.stages_by_mode[PipelineMode.SIMPLE]
    names = [s.name for s in stages]
    assert names == ["estimate", "intake", "ground", "execute", "verify"]


def test_stages_by_mode_medium_includes_plan_self_check_review():
    pipeline = Pipeline(
        llm_manager=None, ws_streamer=_FakeWS(), file_lock=FileLock()
    )
    stages = pipeline.stages_by_mode[PipelineMode.MEDIUM]
    names = [s.name for s in stages]
    # Mode MEDIUM = SIMPLE + PLAN (R1 seul) + SELF-CHECK + REVIEW.
    assert names == [
        "estimate", "intake", "ground", "plan",
        "execute", "self_check", "verify", "review",
    ]
    assert "challenge" not in names  # CHALLENGE uniquement en COMPLEX


def test_stages_by_mode_complex_includes_challenge_consensus_second_review():
    pipeline = Pipeline(
        llm_manager=None, ws_streamer=_FakeWS(), file_lock=FileLock()
    )
    stages = pipeline.stages_by_mode[PipelineMode.COMPLEX]
    names = [s.name for s in stages]
    # Mode COMPLEX = SIMPLE + CHALLENGE + PLAN_CONSENSUS + SELF-CHECK + REVIEW + SECOND-REVIEW.
    assert names == [
        "estimate", "intake", "challenge", "ground", "plan",
        "execute", "self_check", "verify", "review", "second_review",
    ]


@pytest.mark.asyncio
async def test_pipeline_medium_mode_runs_full_chain(tmp_path, monkeypatch):
    """Un pipeline MEDIUM tourne avec tous ses stages mockés OK."""
    pipeline = Pipeline(
        llm_manager=None, ws_streamer=_FakeWS(), file_lock=FileLock()
    )
    # Remplace chaque stage par un stub qui retourne success.
    execute_output = SimpleNamespace(files_modified=["a.py"], stash_ref="")
    verify_output = SimpleNamespace(all_green=True, attempts_used=1)
    pipeline.stages_by_mode[PipelineMode.MEDIUM] = [
        _ok_stage("estimate"),
        _ok_stage("intake"),
        _ok_stage("ground"),
        _ok_stage("plan"),
        _ok_stage("execute", output=execute_output),
        _ok_stage("self_check"),
        _ok_stage("verify", output=verify_output),
        _ok_stage("review"),
    ]

    result = await pipeline.run(_make_ctx(tmp_path, PipelineMode.MEDIUM))

    assert result.success is True
    names = [s.stage_name for s in result.stages]
    assert "challenge" not in names
    assert "plan" in names
    assert "self_check" in names
    assert "review" in names
    assert result.files_modified == ["a.py"]


@pytest.mark.asyncio
async def test_pipeline_complex_mode_runs_full_chain(tmp_path):
    """Un pipeline COMPLEX inclut challenge, plan_consensus, second_review."""
    pipeline = Pipeline(
        llm_manager=None, ws_streamer=_FakeWS(), file_lock=FileLock()
    )
    execute_output = SimpleNamespace(files_modified=["b.py"], stash_ref="")
    verify_output = SimpleNamespace(all_green=True, attempts_used=1)
    pipeline.stages_by_mode[PipelineMode.COMPLEX] = [
        _ok_stage("estimate"),
        _ok_stage("intake"),
        _ok_stage("challenge"),
        _ok_stage("ground"),
        _ok_stage("plan"),
        _ok_stage("execute", output=execute_output),
        _ok_stage("self_check"),
        _ok_stage("verify", output=verify_output),
        _ok_stage("review"),
        _ok_stage("second_review"),
    ]

    result = await pipeline.run(_make_ctx(tmp_path, PipelineMode.COMPLEX))

    assert result.success is True
    names = [s.stage_name for s in result.stages]
    assert "challenge" in names
    assert "plan" in names
    assert "second_review" in names
    assert result.files_modified == ["b.py"]


@pytest.mark.asyncio
async def test_pipeline_complex_with_consensus_deadlock_rolls_back(tmp_path):
    """Stage4Consensus deadlock → success=False, rollback via stash."""
    from backend.pipeline.consensus import PlanConsensusResult

    pipeline = Pipeline(
        llm_manager=None, ws_streamer=_FakeWS(), file_lock=FileLock()
    )

    plan1 = PlanResult(
        changes=[PlanChange(file="a.py", operation="edit", description="a")],
        tests_to_run=[],
        rollback_strategy="",
        rationale="r1",
    )
    plan2 = PlanResult(
        changes=[PlanChange(file="a.py", operation="edit", description="b")],
        tests_to_run=[],
        rollback_strategy="",
        rationale="r2",
    )

    async def fake_consensus(*args, **kwargs):
        return PlanConsensusResult(
            plan=None,
            rounds=2,
            deadlock=True,
            plans=[plan1, plan2],
            reviews=[PlanReview(verdict="reject"), PlanReview(verdict="reject")],
        )

    # Remplace les stages amont par stubs OK pour atteindre Stage4Consensus.
    pipeline.stages_by_mode[PipelineMode.COMPLEX] = [
        _ok_stage("estimate"),
        _ok_stage("intake"),
        _ok_stage("challenge"),
        _ok_stage("ground"),
        pipeline.stages_by_mode[PipelineMode.COMPLEX][4],  # Stage4Consensus
    ]

    pop_mock = AsyncMock(return_value=True)
    with (
        patch("backend.pipeline.stage_4_consensus.run_plan_consensus", side_effect=fake_consensus),
        patch("backend.pipeline.orchestrator.git_stash_pop", pop_mock),
    ):
        result = await pipeline.run(_make_ctx(tmp_path, PipelineMode.COMPLEX))

    assert result.success is False
    assert "deadlock" in (result.error or "").lower()


def test_stage_stubs_have_correct_names():
    """Les stubs 5C/5D exposent bien leur name."""
    from backend.pipeline.stage_6_self_check import Stage6SelfCheck
    from backend.pipeline.stage_8_review import Stage8Review
    from backend.pipeline.stage_9_second_review import Stage9SecondReview

    assert Stage6SelfCheck.name == "self_check"
    assert Stage8Review.name == "review"
    assert Stage9SecondReview.name == "second_review"
