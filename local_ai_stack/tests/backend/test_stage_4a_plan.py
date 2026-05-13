"""Tests pour backend/pipeline/stage_4a_plan.py (Plan 5C Task 3)."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.pipeline.stage_4a_plan import (
    PlanChange,
    PlanResult,
    Stage4aPlan,
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


def _make_ctx(tmp_path: Path) -> PipelineContext:
    return PipelineContext(
        prompt="Refactor auth to use new JWT helper",
        workspace_root=tmp_path,
        session_id="t",
        mode=PipelineMode.COMPLEX,
    )


VALID_PLAN_JSON = """
{
  "changes": [
    {"file": "backend/auth.py", "operation": "patch",
     "description": "Use create_token", "intended_diff_summary": "swap encode call"}
  ],
  "tests_to_run": ["tests/backend/test_auth.py::test_login"],
  "rollback_strategy": "git stash pop",
  "rationale": "auth.py:42 calls jwt.encode (vu en GROUND)",
  "estimated_risk": "medium",
  "complexity_confirm": 5
}
"""


@pytest.mark.asyncio
async def test_stage_4a_returns_plan_result(tmp_path):
    llm = _FakeLLM(VALID_PLAN_JSON)
    stage = Stage4aPlan(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))

    assert result.success is True
    plan: PlanResult = result.output
    assert len(plan.changes) == 1
    assert plan.changes[0].file == "backend/auth.py"
    assert plan.changes[0].operation == "patch"
    assert plan.tests_to_run == ["tests/backend/test_auth.py::test_login"]
    assert plan.estimated_risk == "medium"
    assert plan.complexity_confirm == 5


@pytest.mark.asyncio
async def test_stage_4a_invalid_operation_filtered(tmp_path):
    """operation="modify" est invalide → change ignoré."""
    llm = _FakeLLM(
        '{"changes":[{"file":"a.py","operation":"modify","description":"x"}],'
        '"tests_to_run":[],"rollback_strategy":"","rationale":"r","estimated_risk":"low","complexity_confirm":2}'
    )
    stage = Stage4aPlan(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    assert result.success is True
    assert result.output.changes == []


@pytest.mark.asyncio
async def test_stage_4a_invalid_risk_falls_back_to_low(tmp_path):
    llm = _FakeLLM(
        '{"changes":[{"file":"a.py","operation":"create","description":"x"}],'
        '"tests_to_run":[],"rollback_strategy":"","rationale":"r","estimated_risk":"NUKE","complexity_confirm":3}'
    )
    stage = Stage4aPlan(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    assert result.output.estimated_risk == "low"


@pytest.mark.asyncio
async def test_stage_4a_complexity_clamped(tmp_path):
    """complexity_confirm=99 → clampé à 10."""
    llm = _FakeLLM(
        '{"changes":[{"file":"a.py","operation":"edit","description":"x"}],'
        '"tests_to_run":[],"rollback_strategy":"","rationale":"r","estimated_risk":"high","complexity_confirm":99}'
    )
    stage = Stage4aPlan(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    assert result.output.complexity_confirm == 10


@pytest.mark.asyncio
async def test_stage_4a_invalid_json_fails(tmp_path):
    llm = _FakeLLM("not json")
    stage = Stage4aPlan(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    assert result.success is False
    assert "json" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_stage_4a_uses_intake_challenge_ground_in_message(tmp_path):
    """Le user message doit inclure les outputs upstream si présents."""
    llm = _FakeLLM(VALID_PLAN_JSON)
    stage = Stage4aPlan(llm_manager=llm, ws_streamer=_FakeWS())
    ctx = _make_ctx(tmp_path)
    ctx.stage_results["intake"] = StageResult(
        stage_name="intake",
        duration_ms=0,
        success=True,
        output={
            "prompt_cleaned": "refactor auth jwt",
            "target_files_hint": ["backend/auth.py"],
            "action_verbs": ["refactor"],
            "needs_clarification": False,
            "clarification_questions": [],
        },
    )
    ctx.stage_results["challenge"] = StageResult(
        stage_name="challenge",
        duration_ms=0,
        success=True,
        output=SimpleNamespace(
            risks=["risque concret"],
            edge_cases=["cas limite"],
            alternatives=[],
            severity="moderate",
            blocking=False,
        ),
    )
    ctx.stage_results["ground"] = StageResult(
        stage_name="ground",
        duration_ms=0,
        success=True,
        output=SimpleNamespace(
            files_read={"backend/auth.py": "def login(): ..."},
            greps_performed=[],
            summary="auth.py:42 contient login()",
            iterations_used=2,
        ),
    )

    await stage.run(ctx)
    user_msg = llm.calls[0]["messages"][1]["content"]
    assert "refactor auth jwt" in user_msg
    assert "risque concret" in user_msg
    assert "backend/auth.py" in user_msg
    assert "auth.py:42" in user_msg


def test_stage_4a_name_and_llm():
    stage = Stage4aPlan(llm_manager=None, ws_streamer=_FakeWS())
    assert stage.name == "plan"
    assert stage._llm_for_stage() == "deepseek/deepseek-r1"


def test_plan_change_dataclass_defaults():
    c = PlanChange(file="x.py", operation="edit", description="desc")
    assert c.intended_diff_summary == ""
