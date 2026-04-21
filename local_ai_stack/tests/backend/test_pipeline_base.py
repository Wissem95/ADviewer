"""Tests pour backend/pipeline/base.py — classe abstraite Stage (Plan 5A Task 6).

Stage est une template method : sa méthode ``run(ctx)`` émet ``stage_start``,
appelle ``_execute(ctx)`` (implémenté par les sous-classes), mesure la durée,
capture les exceptions, et émet ``stage_complete``.
"""
from dataclasses import dataclass
from pathlib import Path

import pytest

from backend.models import WSEvent
from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext, PipelineMode


class _FakeWS:
    """Mini WSStreamer stub : capture les events émis en liste."""

    def __init__(self):
        self.events: list[WSEvent] = []

    async def broadcast(self, event: WSEvent) -> None:
        self.events.append(event)


@dataclass
class _DummyOutput:
    """Payload retourné par DummyStage._execute."""

    message: str
    tokens_in: int = 100
    tokens_out: int = 50
    cost_usd: float = 0.001


class DummyStage(Stage):
    """Stage minimal pour tester le contrat."""

    name = "dummy"

    async def _execute(self, ctx: PipelineContext) -> _DummyOutput:
        return _DummyOutput(message=f"processed {ctx.prompt}")

    def _llm_for_stage(self) -> str:
        return "minimax/minimax-m2.5"


class FailingStage(Stage):
    name = "failing"

    async def _execute(self, ctx: PipelineContext):
        raise RuntimeError("intentional failure")


def _make_ctx(tmp_path: Path) -> PipelineContext:
    return PipelineContext(
        prompt="hello",
        workspace_root=tmp_path,
        session_id="test-session",
        mode=PipelineMode.SIMPLE,
    )


@pytest.mark.asyncio
async def test_stage_run_returns_stage_result_with_duration(tmp_path):
    ws = _FakeWS()
    stage = DummyStage(llm_manager=None, ws_streamer=ws)
    result = await stage.run(_make_ctx(tmp_path))
    assert result.stage_name == "dummy"
    assert result.success is True
    assert result.duration_ms >= 0
    assert result.llm_used == "minimax/minimax-m2.5"
    assert result.output.message == "processed hello"


@pytest.mark.asyncio
async def test_stage_run_emits_start_and_complete_events(tmp_path):
    ws = _FakeWS()
    stage = DummyStage(llm_manager=None, ws_streamer=ws)
    await stage.run(_make_ctx(tmp_path))
    types = [e.type for e in ws.events]
    assert types == ["stage_start", "stage_complete"]
    # start event contient le nom du stage et le llm
    start = ws.events[0]
    assert start.data["stage"] == "dummy"
    assert start.data["llm"] == "minimax/minimax-m2.5"
    # complete event contient duration_ms
    complete = ws.events[1]
    assert complete.data["stage"] == "dummy"
    assert isinstance(complete.data["duration_ms"], int)


@pytest.mark.asyncio
async def test_stage_run_captures_exception_returns_success_false(tmp_path):
    ws = _FakeWS()
    stage = FailingStage(llm_manager=None, ws_streamer=ws)
    result = await stage.run(_make_ctx(tmp_path))
    assert result.success is False
    assert "intentional failure" in result.error
    # Un stage_complete est quand même émis avec success=False
    assert any(e.type == "stage_complete" for e in ws.events)


@pytest.mark.asyncio
async def test_stage_run_propagates_tokens_cost_from_output(tmp_path):
    """Si le payload retourné par _execute expose tokens_in/out/cost_usd,
    ils sont copiés dans le StageResult pour que le CostTracker puisse les lire."""
    ws = _FakeWS()
    stage = DummyStage(llm_manager=None, ws_streamer=ws)
    result = await stage.run(_make_ctx(tmp_path))
    assert result.tokens_in == 100
    assert result.tokens_out == 50
    assert result.cost_usd == 0.001


def test_stage_requires_name_attribute():
    """Les sous-classes doivent définir name="..." pour identifier l'étape."""
    assert DummyStage.name == "dummy"
    assert FailingStage.name == "failing"


@pytest.mark.asyncio
async def test_stage_llm_for_stage_default_is_none(tmp_path):
    """Les étapes mécaniques (pas de LLM) peuvent ne pas override
    ``_llm_for_stage`` et retourneront None."""

    class NoLLMStage(Stage):
        name = "mechanical"

        async def _execute(self, ctx):
            return None

    ws = _FakeWS()
    stage = NoLLMStage(llm_manager=None, ws_streamer=ws)
    result = await stage.run(_make_ctx(tmp_path))
    assert result.success is True
    assert result.llm_used is None
