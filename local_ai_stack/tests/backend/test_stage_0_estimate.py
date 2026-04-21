"""Tests pour backend/pipeline/stage_0_estimate.py (Plan 5A Task 7).

Stage0 appelle Gemini Flash pour classifier un prompt et enrichit la réponse
avec ``estimate_pipeline_cost`` pour produire un payload compatible event WS
``pipeline_estimate`` + modal UI.
"""
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.models import LLMRole
from backend.pipeline.stage_0_estimate import Stage0Estimate
from backend.pipeline.types import PipelineContext, PipelineMode


class _FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


def _make_ctx(tmp_path: Path, prompt: str = "Fix typo in main.py") -> PipelineContext:
    return PipelineContext(
        prompt=prompt,
        workspace_root=tmp_path,
        session_id="test",
        mode=PipelineMode.SIMPLE,
    )


@pytest.mark.asyncio
async def test_stage_0_returns_classification_simple(tmp_path):
    fake_llm = type(
        "FakeLLM", (),
        {"call_with_fallback": AsyncMock(return_value=(
            '{"classification": "simple", "reason": "single file typo", '
            '"files_hint": ["main.py"], "confidence": "high", "ambiguities": []}'
        ))},
    )()
    stage = Stage0Estimate(llm_manager=fake_llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    assert result.success is True
    assert result.output["classification"] == "simple"
    assert result.output["files_hint"] == ["main.py"]
    # enrichissement cost présent
    assert "estimated_cost_usd" in result.output
    assert result.output["estimated_cost_usd"] < 0.01
    assert "stage_estimates" in result.output


@pytest.mark.asyncio
async def test_stage_0_parses_json_wrapped_in_text(tmp_path):
    """Si le LLM ajoute du texte autour du JSON, on extrait quand même."""
    noisy = (
        "Voici ma classification :\n\n"
        '{"classification": "complex", "reason": "refactor archi", '
        '"files_hint": [], "confidence": "medium", "ambiguities": []}\n\n'
        "Voilà."
    )
    fake_llm = type(
        "FakeLLM", (),
        {"call_with_fallback": AsyncMock(return_value=noisy)},
    )()
    stage = Stage0Estimate(llm_manager=fake_llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path, prompt="refactor auth JWT"))
    assert result.success is True
    assert result.output["classification"] == "complex"


@pytest.mark.asyncio
async def test_stage_0_complex_has_higher_cost_than_simple(tmp_path):
    """Classification complex → coût estimé nettement supérieur à simple."""
    simple_llm = type(
        "F", (),
        {"call_with_fallback": AsyncMock(return_value=(
            '{"classification": "simple", "reason": "x", '
            '"files_hint": [], "confidence": "high", "ambiguities": []}'
        ))},
    )()
    complex_llm = type(
        "F", (),
        {"call_with_fallback": AsyncMock(return_value=(
            '{"classification": "complex", "reason": "x", '
            '"files_hint": [], "confidence": "high", "ambiguities": []}'
        ))},
    )()
    ws = _FakeWS()
    simple_res = await Stage0Estimate(simple_llm, ws).run(_make_ctx(tmp_path))
    complex_res = await Stage0Estimate(complex_llm, ws).run(_make_ctx(tmp_path))
    assert complex_res.output["estimated_cost_usd"] > simple_res.output["estimated_cost_usd"] * 5


@pytest.mark.asyncio
async def test_stage_0_invalid_json_returns_failure(tmp_path):
    """Si le LLM renvoie un texte sans aucun JSON parseable → success=False,
    jamais de crash (Stage base capture l'exception)."""
    fake_llm = type(
        "F", (),
        {"call_with_fallback": AsyncMock(return_value="pas de JSON ici")},
    )()
    stage = Stage0Estimate(llm_manager=fake_llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    assert result.success is False
    assert "json" in result.error.lower()


@pytest.mark.asyncio
async def test_stage_0_calls_llm_with_routing_role(tmp_path):
    """Stage0 doit router sur LLMRole.ROUTING (Gemini Flash dans FALLBACK_CHAINS)."""
    mock = AsyncMock(return_value=(
        '{"classification": "simple", "reason": "x", '
        '"files_hint": [], "confidence": "high", "ambiguities": []}'
    ))
    fake_llm = type("F", (), {"call_with_fallback": mock})()
    stage = Stage0Estimate(llm_manager=fake_llm, ws_streamer=_FakeWS())
    await stage.run(_make_ctx(tmp_path))
    # Vérifier qu'on a bien appelé avec role=ROUTING
    call_kwargs = mock.call_args.kwargs
    assert call_kwargs["role"] == LLMRole.ROUTING


@pytest.mark.asyncio
async def test_stage_0_preserves_files_hint_in_output(tmp_path):
    fake_llm = type(
        "F", (),
        {"call_with_fallback": AsyncMock(return_value=(
            '{"classification": "medium", "reason": "x", '
            '"files_hint": ["a.py", "b.py"], "confidence": "high", "ambiguities": []}'
        ))},
    )()
    stage = Stage0Estimate(llm_manager=fake_llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    assert result.output["estimated_files_touched"] == ["a.py", "b.py"]


@pytest.mark.asyncio
async def test_stage_0_name_is_estimate():
    assert Stage0Estimate.name == "estimate"


@pytest.mark.asyncio
async def test_stage_0_uses_gemini_flash_llm():
    stage = Stage0Estimate(llm_manager=None, ws_streamer=_FakeWS())
    assert stage._llm_for_stage() == "gemini/gemini-2.5-flash"
