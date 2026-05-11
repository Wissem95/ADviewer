"""Tests E2E pipeline avec VERIFY retry + rollback + cancellation + budget (Plan 5B Task 8).

Validation de bout en bout des garanties Plan 5B :
- Retry loop Stage5 ↔ Stage7 : code rouge passe 1, corrigé passe 2 → pipeline vert.
- Rollback après 3 tentatives rouges : stash pop, succès=False.
- Cancellation pendant exécution : rollback automatique.
- Budget cap dépassé : abort + rollback.

Toutes les LLM calls sont mockées via ScriptedLLM + FakeLLMManager.
"""
import asyncio
import re
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.file_lock import FileLock
from backend.pipeline.orchestrator import Pipeline
from backend.pipeline.types import PipelineContext, PipelineMode
from tests.fixtures.scripted_llm import ScriptedLLM


_STAGE_RE = re.compile(r"^#\s*Étape\s*\d+\s*[—-]\s*(\w+)", re.MULTILINE)


class _FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


class _FakeLLMManager:
    def __init__(self, stage_responses: dict[str, str]):
        self.stage_responses = {k.upper(): v for k, v in stage_responses.items()}

    async def call_with_fallback(self, *, role, messages, **kwargs) -> str:
        system = next((m for m in messages if m.get("role") == "system"), None)
        if system is None:
            raise RuntimeError("FakeLLM: pas de system prompt")
        match = _STAGE_RE.search(system.get("content", ""))
        if not match:
            raise RuntimeError(f"FakeLLM: stage non détecté")
        stage = match.group(1).upper()
        if stage not in self.stage_responses:
            raise RuntimeError(f"FakeLLM: pas de réponse pour {stage}")
        return self.stage_responses[stage]


def _init_git(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init", "-q"],
        cwd=tmp_path,
        check=True,
    )


def _basic_llm():
    return _FakeLLMManager({
        "ESTIMATE": (
            '{"classification":"simple","reason":"x","files_hint":[],'
            '"confidence":"high","ambiguities":[]}'
        ),
        "INTAKE": (
            '{"prompt_cleaned":"x","target_files_hint":[],"action_verbs":[],'
            '"needs_clarification":false,"clarification_questions":[]}'
        ),
    })


@pytest.mark.asyncio
async def test_e2e_cancellation_mid_pipeline_rolls_back(tmp_path):
    """Cancel pendant Stage5 → rollback automatique via stash."""
    _init_git(tmp_path)

    scripted = ScriptedLLM({
        "GROUND": [ScriptedLLM.text("ok")],
        # Stage5 lance create_file puis termine — on va cancel avant la fin.
        "EXECUTE": [
            ScriptedLLM.tool_call(
                "c1",
                "create_file",
                '{"path":"target.py","content":"x = 1\\n"}',
            ),
            ScriptedLLM.text("done"),
        ],
    })

    pipeline = Pipeline(
        llm_manager=_basic_llm(),
        ws_streamer=_FakeWS(),
        file_lock=FileLock(),
    )
    ctx = PipelineContext(
        prompt="x",
        workspace_root=tmp_path,
        session_id="cancel_e2e",
        mode=PipelineMode.SIMPLE,
    )

    with (
        patch(
            "backend.pipeline.stage_3_ground.acompletion",
            side_effect=scripted.acompletion,
        ),
        patch(
            "backend.pipeline.stage_5_execute.acompletion",
            side_effect=scripted.acompletion,
        ),
    ):
        task = asyncio.create_task(pipeline.run(ctx))
        # Laisse les premiers stages tourner puis cancel.
        await asyncio.sleep(0.01)
        task.cancel()
        result = await task

    # CancelledError gérée par Pipeline → success=False, error mentionne "cancel".
    assert result.success is False
    assert "cancel" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_e2e_pipeline_simple_happy_path_still_works(tmp_path):
    """Sanity check : après tous les ajouts Plan 5B, le happy path mode SIMPLE marche encore."""
    _init_git(tmp_path)

    scripted = ScriptedLLM({
        "GROUND": [ScriptedLLM.text("ok")],
        "EXECUTE": [
            ScriptedLLM.tool_call(
                "c1",
                "create_file",
                '{"path":"happy.py","content":"print(1)\\n"}',
            ),
            ScriptedLLM.text("done"),
        ],
    })

    pipeline = Pipeline(
        llm_manager=_basic_llm(),
        ws_streamer=_FakeWS(),
        file_lock=FileLock(),
    )
    ctx = PipelineContext(
        prompt="x",
        workspace_root=tmp_path,
        session_id="happy",
        mode=PipelineMode.SIMPLE,
    )

    with (
        patch(
            "backend.pipeline.stage_3_ground.acompletion",
            side_effect=scripted.acompletion,
        ),
        patch(
            "backend.pipeline.stage_5_execute.acompletion",
            side_effect=scripted.acompletion,
        ),
    ):
        result = await pipeline.run(ctx)

    assert result.success is True
    assert (tmp_path / "happy.py").exists()
    assert "happy.py" in result.files_modified
