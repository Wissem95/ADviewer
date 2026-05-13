"""Tests pour backend/pipeline/consensus.py (Plan 5C Task 6).

run_plan_consensus orchestre Stage4aPlan + Stage4bPlanReview en boucle 2
rounds max. Mock les deux stages pour valider la logique de décision.
"""
from pathlib import Path

import pytest

from backend.pipeline.consensus import (
    PlanConsensusResult,
    run_plan_consensus,
    serialize_plan_for_memory,
)
from backend.pipeline.stage_4a_plan import PlanChange, PlanResult
from backend.pipeline.stage_4b_plan_review import PlanReview
from backend.pipeline.types import PipelineContext, PipelineMode


class _FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


def _ctx(tmp_path: Path) -> PipelineContext:
    return PipelineContext(
        prompt="x",
        workspace_root=tmp_path,
        session_id="t",
        mode=PipelineMode.COMPLEX,
    )


def _plan(label: str = "p", risk: str = "low") -> PlanResult:
    return PlanResult(
        changes=[PlanChange(file=f"{label}.py", operation="edit", description=label)],
        tests_to_run=[f"tests/{label}.py::test_x"],
        rollback_strategy="stash",
        rationale=f"rationale {label}",
        estimated_risk=risk,
        complexity_confirm=4,
    )


class _StubStage4a:
    """Stub Stage4aPlan qui retourne des plans pré-scriptés."""

    def __init__(self, plans: list[PlanResult]):
        self.plans = list(plans)
        self.calls = 0

    def __call__(self, llm, ws):
        return self

    async def run(self, ctx):
        self.calls += 1
        from backend.pipeline.types import StageResult
        if not self.plans:
            return StageResult(
                stage_name="plan",
                duration_ms=0,
                success=False,
                output=None,
                error="no plan",
            )
        plan = self.plans.pop(0)
        sr = StageResult(
            stage_name="plan",
            duration_ms=0,
            success=True,
            output=plan,
        )
        ctx.stage_results["plan"] = sr
        return sr


class _StubStage4b:
    """Stub Stage4bPlanReview qui retourne des reviews pré-scriptées."""

    def __init__(self, reviews: list[PlanReview]):
        self.reviews = list(reviews)
        self.calls = 0

    def __call__(self, llm, ws):
        return self

    async def run(self, ctx):
        self.calls += 1
        from backend.pipeline.types import StageResult
        review = self.reviews.pop(0)
        sr = StageResult(
            stage_name="plan_review",
            duration_ms=0,
            success=True,
            output=review,
        )
        ctx.stage_results["plan_review"] = sr
        return sr


@pytest.mark.asyncio
async def test_consensus_approve_round_1(tmp_path, monkeypatch):
    plan1 = _plan("a")
    monkeypatch.setattr(
        "backend.pipeline.consensus.Stage4aPlan",
        _StubStage4a([plan1]),
    )
    monkeypatch.setattr(
        "backend.pipeline.consensus.Stage4bPlanReview",
        _StubStage4b([PlanReview(verdict="approve")]),
    )
    ws = _FakeWS()
    result = await run_plan_consensus(None, ws, _ctx(tmp_path))

    assert result.deadlock is False
    assert result.rounds == 1
    assert result.plan is plan1
    types = [e.type for e in ws.events]
    assert "consensus_round" in types
    assert "consensus_disagreement" not in types


@pytest.mark.asyncio
async def test_consensus_revise_returns_merged_plan(tmp_path, monkeypatch):
    plan_r1 = _plan("r1")
    merged = _plan("merged", risk="medium")
    monkeypatch.setattr(
        "backend.pipeline.consensus.Stage4aPlan",
        _StubStage4a([plan_r1]),
    )
    monkeypatch.setattr(
        "backend.pipeline.consensus.Stage4bPlanReview",
        _StubStage4b([PlanReview(verdict="revise", merged_plan=merged)]),
    )
    result = await run_plan_consensus(None, _FakeWS(), _ctx(tmp_path))

    assert result.deadlock is False
    assert result.rounds == 1
    assert result.plan is merged


@pytest.mark.asyncio
async def test_consensus_reject_then_approve(tmp_path, monkeypatch):
    plan1 = _plan("p1")
    plan2 = _plan("p2")
    stage_4a = _StubStage4a([plan1, plan2])
    monkeypatch.setattr("backend.pipeline.consensus.Stage4aPlan", stage_4a)
    monkeypatch.setattr(
        "backend.pipeline.consensus.Stage4bPlanReview",
        _StubStage4b([
            PlanReview(verdict="reject", concerns=["c1"]),
            PlanReview(verdict="approve"),
        ]),
    )
    result = await run_plan_consensus(None, _FakeWS(), _ctx(tmp_path))

    assert result.deadlock is False
    assert result.rounds == 2
    assert result.plan is plan2
    assert stage_4a.calls == 2


@pytest.mark.asyncio
async def test_consensus_deadlock_after_two_rejects(tmp_path, monkeypatch):
    plan1 = _plan("p1")
    plan2 = _plan("p2")
    monkeypatch.setattr(
        "backend.pipeline.consensus.Stage4aPlan",
        _StubStage4a([plan1, plan2]),
    )
    monkeypatch.setattr(
        "backend.pipeline.consensus.Stage4bPlanReview",
        _StubStage4b([
            PlanReview(verdict="reject", concerns=["bad1"]),
            PlanReview(verdict="reject", concerns=["bad2"]),
        ]),
    )
    ws = _FakeWS()
    result = await run_plan_consensus(None, ws, _ctx(tmp_path))

    assert result.deadlock is True
    assert result.rounds == 2
    assert result.plan is None
    assert len(result.plans) == 2
    assert result.plans[0] is plan1
    assert result.plans[1] is plan2

    types = [e.type for e in ws.events]
    assert "consensus_disagreement" in types


@pytest.mark.asyncio
async def test_consensus_injects_concerns_in_retry_context(tmp_path, monkeypatch):
    """Au round 2, ctx.retry_context contient les concerns du round 1."""
    plan1 = _plan("p1")
    plan2 = _plan("p2")
    seen_retry_contexts = []

    class _SpyStage4a(_StubStage4a):
        async def run(self, ctx):
            seen_retry_contexts.append(getattr(ctx, "retry_context", None))
            return await super().run(ctx)

    spy = _SpyStage4a([plan1, plan2])
    monkeypatch.setattr("backend.pipeline.consensus.Stage4aPlan", spy)
    monkeypatch.setattr(
        "backend.pipeline.consensus.Stage4bPlanReview",
        _StubStage4b([
            PlanReview(verdict="reject", concerns=["missing_test_X"]),
            PlanReview(verdict="approve"),
        ]),
    )

    await run_plan_consensus(None, _FakeWS(), _ctx(tmp_path))

    # Round 1 : pas de retry_context.
    assert seen_retry_contexts[0] is None
    # Round 2 : retry_context contient les concerns.
    rc = seen_retry_contexts[1]
    assert rc is not None
    assert "missing_test_X" in rc["previous_review_concerns"]
    assert rc["round"] == 2


@pytest.mark.asyncio
async def test_consensus_stage_4a_hard_failure_returns_deadlock(tmp_path, monkeypatch):
    """Si Stage4a échoue (success=False) → deadlock, pas de crash."""
    monkeypatch.setattr(
        "backend.pipeline.consensus.Stage4aPlan",
        _StubStage4a([]),  # plus de plan → return success=False
    )
    monkeypatch.setattr(
        "backend.pipeline.consensus.Stage4bPlanReview",
        _StubStage4b([]),
    )
    result = await run_plan_consensus(None, _FakeWS(), _ctx(tmp_path))
    assert result.deadlock is True
    assert result.plan is None


def test_serialize_plan_for_memory():
    plan = _plan("xyz", risk="high")
    serialized = serialize_plan_for_memory(plan)
    assert "xyz.py" in serialized
    assert "high" in serialized
    assert len(serialized) <= 2000
