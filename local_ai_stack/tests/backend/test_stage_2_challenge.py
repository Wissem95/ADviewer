"""Tests pour backend/pipeline/stage_2_challenge.py (Plan 5C Task 1)."""
from pathlib import Path

import pytest

from backend.pipeline.stage_2_challenge import (
    ChallengeResult,
    Stage2Challenge,
)
from backend.pipeline.types import PipelineContext, PipelineMode


class _FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    async def call_with_fallback(self, *, role, messages, **kwargs) -> str:
        self.calls.append({"role": role, "messages": messages})
        return self.response


class _FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


def _make_ctx(tmp_path: Path, prompt: str = "Refactor auth") -> PipelineContext:
    return PipelineContext(
        prompt=prompt,
        workspace_root=tmp_path,
        session_id="t",
        mode=PipelineMode.COMPLEX,
    )


@pytest.mark.asyncio
async def test_stage_2_minor_non_blocking(tmp_path):
    llm = _FakeLLM(
        '{"risks":["r1","r2"],"edge_cases":["e1"],"alternatives":["a1"],'
        '"severity":"minor","blocking":false}'
    )
    ws = _FakeWS()
    stage = Stage2Challenge(llm_manager=llm, ws_streamer=ws)
    result = await stage.run(_make_ctx(tmp_path))

    assert result.success is True
    output: ChallengeResult = result.output
    assert output.severity == "minor"
    assert output.blocking is False
    assert output.risks == ["r1", "r2"]
    # Pas d'event challenge_blocking émis.
    types = [e.type for e in ws.events]
    assert "challenge_blocking" not in types


@pytest.mark.asyncio
async def test_stage_2_blocking_emits_ws_event(tmp_path):
    llm = _FakeLLM(
        '{"risks":["critical risk"],"edge_cases":[],"alternatives":[],'
        '"severity":"critical","blocking":true}'
    )
    ws = _FakeWS()
    stage = Stage2Challenge(llm_manager=llm, ws_streamer=ws)
    result = await stage.run(_make_ctx(tmp_path))

    assert result.success is True
    assert result.output.blocking is True
    assert result.output.severity == "critical"
    # Event WS challenge_blocking émis.
    types = [e.type for e in ws.events]
    assert "challenge_blocking" in types


@pytest.mark.asyncio
async def test_stage_2_invalid_severity_falls_back_to_minor(tmp_path):
    llm = _FakeLLM(
        '{"risks":["r"],"edge_cases":[],"alternatives":[],'
        '"severity":"WUT","blocking":false}'
    )
    stage = Stage2Challenge(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    assert result.output.severity == "minor"


@pytest.mark.asyncio
async def test_stage_2_caps_risks_and_edge_cases(tmp_path):
    """Liste à 10 risks → tronquée à 5 max."""
    big = [f"r{i}" for i in range(10)]
    llm = _FakeLLM(
        '{"risks":' + str(big).replace("'", '"') + ','
        '"edge_cases":[],"alternatives":[],"severity":"minor","blocking":false}'
    )
    stage = Stage2Challenge(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    assert len(result.output.risks) <= 5


@pytest.mark.asyncio
async def test_stage_2_invalid_json_raises_stage_error(tmp_path):
    llm = _FakeLLM("not json at all")
    stage = Stage2Challenge(llm_manager=llm, ws_streamer=_FakeWS())
    result = await stage.run(_make_ctx(tmp_path))
    # Stage.run capture l'exception → success=False.
    assert result.success is False
    assert "json" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_stage_2_reads_intake_from_ctx(tmp_path):
    """Si intake disponible, son content apparaît dans le user message."""
    llm = _FakeLLM(
        '{"risks":["r"],"edge_cases":[],"alternatives":[],'
        '"severity":"minor","blocking":false}'
    )
    stage = Stage2Challenge(llm_manager=llm, ws_streamer=_FakeWS())
    ctx = _make_ctx(tmp_path)
    # Simule un Stage1Intake.
    from backend.pipeline.types import StageResult
    ctx.stage_results["intake"] = StageResult(
        stage_name="intake",
        duration_ms=0,
        success=True,
        output={
            "prompt_cleaned": "refactor auth properly",
            "target_files_hint": ["auth.py"],
            "action_verbs": ["refactor"],
            "needs_clarification": False,
            "clarification_questions": [],
        },
    )
    await stage.run(ctx)
    user_msg = llm.calls[0]["messages"][1]["content"]
    assert "refactor auth properly" in user_msg
    assert "auth.py" in user_msg


def test_stage_2_name_and_llm():
    stage = Stage2Challenge(llm_manager=None, ws_streamer=_FakeWS())
    assert stage.name == "challenge"
    assert stage._llm_for_stage() == "gemini/gemini-2.5-pro"
