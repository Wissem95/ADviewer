"""Tests pour backend/pipeline/stage_1_intake.py (Plan 5A Task 8).

Stage1 valide la non-ambiguïté du prompt. Si le LLM remonte
``needs_clarification=true``, le _execute lève ``ClarificationNeeded`` qui
sera capturée par Stage.run et transformée en ``StageResult(success=False)``
pour que le Pipeline orchestrator stoppe et remonte les questions à l'user.
"""
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.models import LLMRole
from backend.pipeline.stage_1_intake import (
    ClarificationNeeded,
    Stage1Intake,
)
from backend.pipeline.types import PipelineContext, PipelineMode


class _FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


def _make_ctx(tmp_path: Path, prompt: str = "Fix typo in auth.py") -> PipelineContext:
    return PipelineContext(
        prompt=prompt,
        workspace_root=tmp_path,
        session_id="test",
        mode=PipelineMode.SIMPLE,
    )


@pytest.mark.asyncio
async def test_stage_1_returns_intake_when_clear(tmp_path):
    fake_llm = type(
        "F", (),
        {"call_with_fallback": AsyncMock(return_value=(
            '{"prompt_cleaned": "Fix typo in auth.py", '
            '"target_files_hint": ["auth.py"], '
            '"action_verbs": ["fix"], '
            '"needs_clarification": false, '
            '"clarification_questions": []}'
        ))},
    )()
    stage = Stage1Intake(llm_manager=fake_llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    assert result.success is True
    assert result.output["prompt_cleaned"] == "Fix typo in auth.py"
    assert result.output["target_files_hint"] == ["auth.py"]
    assert result.output["action_verbs"] == ["fix"]
    assert result.output["needs_clarification"] is False


@pytest.mark.asyncio
async def test_stage_1_raises_clarification_needed(tmp_path):
    """Si needs_clarification=true → exception capturée par Stage.run."""
    fake_llm = type(
        "F", (),
        {"call_with_fallback": AsyncMock(return_value=(
            '{"prompt_cleaned": "Optimize perf (target unspecified)", '
            '"target_files_hint": [], '
            '"action_verbs": ["optimize"], '
            '"needs_clarification": true, '
            '"clarification_questions": ["Quelle zone ?", "Quel critère ?"]}'
        ))},
    )()
    stage = Stage1Intake(llm_manager=fake_llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path, prompt="Améliore la perf"))
    # Stage.run capture l'exception → success=False, error contient le mot-clé.
    assert result.success is False
    assert "clarification" in result.error.lower()


@pytest.mark.asyncio
async def test_stage_1_clarification_needed_exception_carries_questions():
    """L'exception elle-même expose les questions pour que l'orchestrator
    puisse les remonter dans le PipelineResult."""
    questions = ["Q1?", "Q2?"]
    exc = ClarificationNeeded(questions=questions)
    assert exc.questions == questions
    assert "Q1?" in str(exc) or "clarification" in str(exc).lower()


@pytest.mark.asyncio
async def test_stage_1_invalid_json_returns_failure(tmp_path):
    fake_llm = type(
        "F", (),
        {"call_with_fallback": AsyncMock(return_value="pas de JSON")},
    )()
    stage = Stage1Intake(llm_manager=fake_llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    assert result.success is False
    assert "json" in result.error.lower()


@pytest.mark.asyncio
async def test_stage_1_calls_llm_with_routing_role(tmp_path):
    mock = AsyncMock(return_value=(
        '{"prompt_cleaned": "x", "target_files_hint": [], '
        '"action_verbs": [], "needs_clarification": false, '
        '"clarification_questions": []}'
    ))
    fake_llm = type("F", (), {"call_with_fallback": mock})()
    stage = Stage1Intake(llm_manager=fake_llm, ws_streamer=_FakeWS())
    await stage.run(_make_ctx(tmp_path))
    assert mock.call_args.kwargs["role"] == LLMRole.ROUTING


def test_stage_1_name_is_intake():
    assert Stage1Intake.name == "intake"


def test_stage_1_uses_gemini_flash():
    stage = Stage1Intake(llm_manager=None, ws_streamer=_FakeWS())
    assert stage._llm_for_stage() == "gemini/gemini-2.5-flash"
