"""Tests pour backend/pipeline/stage_4b_plan_review.py (Plan 5C Task 5)."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.pipeline.stage_4a_plan import PlanResult
from backend.pipeline.stage_4b_plan_review import (
    PlanReview,
    Stage4bPlanReview,
)
from backend.pipeline.types import PipelineContext, PipelineMode, StageResult


class _FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    async def call_with_fallback(self, *, role, messages, **kwargs) -> str:
        self.calls.append({"role": role, "messages": messages})
        return self.response


class _FakeWS:
    async def broadcast(self, event):
        pass


def _make_ctx_with_plan(tmp_path: Path) -> PipelineContext:
    from backend.pipeline.stage_4a_plan import PlanChange
    ctx = PipelineContext(
        prompt="Refactor auth",
        workspace_root=tmp_path,
        session_id="t",
        mode=PipelineMode.COMPLEX,
    )
    ctx.stage_results["plan"] = StageResult(
        stage_name="plan",
        duration_ms=0,
        success=True,
        output=PlanResult(
            changes=[
                PlanChange(
                    file="backend/auth.py",
                    operation="patch",
                    description="Use new helper",
                )
            ],
            tests_to_run=["tests/backend/test_auth.py::test_login"],
            rollback_strategy="git stash pop",
            rationale="auth.py:42 calls encode",
            estimated_risk="medium",
            complexity_confirm=5,
        ),
    )
    return ctx


@pytest.mark.asyncio
async def test_stage_4b_approve(tmp_path):
    llm = _FakeLLM('{"verdict":"approve","concerns":[],"suggested_changes":[]}')
    stage = Stage4bPlanReview(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx_with_plan(tmp_path))

    assert result.success is True
    review: PlanReview = result.output
    assert review.verdict == "approve"
    assert review.merged_plan is None


@pytest.mark.asyncio
async def test_stage_4b_revise_returns_merged_plan(tmp_path):
    llm = _FakeLLM(
        '{"verdict":"revise","concerns":["missing tests"],'
        '"suggested_changes":["add edge case test"],'
        '"merged_plan":{"changes":[{"file":"backend/auth.py","operation":"patch","description":"x"}],'
        '"tests_to_run":["tests/edge.py::test"],"rollback_strategy":"stash","rationale":"r",'
        '"estimated_risk":"low","complexity_confirm":3}}'
    )
    stage = Stage4bPlanReview(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx_with_plan(tmp_path))

    review: PlanReview = result.output
    assert review.verdict == "revise"
    assert review.merged_plan is not None
    assert len(review.merged_plan.changes) == 1
    assert "tests/edge.py::test" in review.merged_plan.tests_to_run


@pytest.mark.asyncio
async def test_stage_4b_reject_with_concerns(tmp_path):
    llm = _FakeLLM(
        '{"verdict":"reject","concerns":["misses crucial file","breaks contract"],'
        '"suggested_changes":[],"merged_plan":null}'
    )
    stage = Stage4bPlanReview(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx_with_plan(tmp_path))

    review = result.output
    assert review.verdict == "reject"
    assert len(review.concerns) == 2
    assert review.merged_plan is None


@pytest.mark.asyncio
async def test_stage_4b_invalid_verdict_falls_back_to_approve(tmp_path):
    llm = _FakeLLM('{"verdict":"WUT","concerns":[],"suggested_changes":[]}')
    stage = Stage4bPlanReview(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx_with_plan(tmp_path))
    assert result.output.verdict == "approve"


@pytest.mark.asyncio
async def test_stage_4b_revise_without_merged_plan_keeps_none(tmp_path):
    """verdict=revise mais merged_plan absent → merged_plan reste None."""
    llm = _FakeLLM('{"verdict":"revise","concerns":["c1"],"suggested_changes":["s1"]}')
    stage = Stage4bPlanReview(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx_with_plan(tmp_path))
    assert result.output.verdict == "revise"
    assert result.output.merged_plan is None


@pytest.mark.asyncio
async def test_stage_4b_includes_plan_in_user_message(tmp_path):
    llm = _FakeLLM('{"verdict":"approve","concerns":[],"suggested_changes":[]}')
    stage = Stage4bPlanReview(llm_manager=llm, ws_streamer=_FakeWS())
    await stage.run(_make_ctx_with_plan(tmp_path))

    user_msg = llm.calls[0]["messages"][1]["content"]
    assert "PLAN R1" in user_msg
    assert "backend/auth.py" in user_msg


@pytest.mark.asyncio
async def test_stage_4b_invalid_json_fails(tmp_path):
    llm = _FakeLLM("not json")
    stage = Stage4bPlanReview(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx_with_plan(tmp_path))
    assert result.success is False


def test_stage_4b_name_and_llm():
    stage = Stage4bPlanReview(llm_manager=None, ws_streamer=_FakeWS())
    assert stage.name == "plan_review"
    assert stage._llm_for_stage() == "gemini/gemini-2.5-pro"
