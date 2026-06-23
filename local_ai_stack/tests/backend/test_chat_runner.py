"""Tests du pont chat ↔ Pipeline (Plan 5D Task 11.3).

Couvre :
- ``select_mode`` : mapping UI → PipelineMode + défaut sûr.
- ``make_pipeline`` : réutilise les composants d'app.state.
- ``run_chat_pipeline`` : E2E SIMPLE → fichier réellement créé + event final
  ``pipeline_done`` émis vers le client, sans toucher au réseau.
"""
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.file_lock import FileLock
from backend.pipeline.chat_runner import make_pipeline, run_chat_pipeline, select_mode
from backend.pipeline.orchestrator import Pipeline
from backend.pipeline.types import PipelineContext, PipelineMode
from tests.fixtures.scripted_llm import ScriptedLLM


_STAGE_RE = re.compile(r"^#\s*Étape\s*\d+\s*[—-]\s*(\w+)", re.MULTILINE)


class _FakeWS:
    """Capture broadcast() (stages) ET send_to() (event final)."""

    def __init__(self):
        self.broadcasts = []
        self.sent = []  # list[(session_id, WSEvent)]

    async def broadcast(self, event):
        self.broadcasts.append(event)

    async def send_to(self, session_id, event):
        self.sent.append((session_id, event))


class _FakeLLMManager:
    def __init__(self, stage_responses: dict[str, str]):
        self.stage_responses = {k.upper(): v for k, v in stage_responses.items()}

    async def call_with_fallback(self, *, role, messages, **kwargs) -> str:
        system = next((m for m in messages if m.get("role") == "system"), None)
        match = _STAGE_RE.search(system.get("content", "")) if system else None
        if not match:
            raise RuntimeError("FakeLLM: stage non détecté")
        stage = match.group(1).upper()
        return self.stage_responses[stage]


def _init_git(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(tmp_path), check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init", "-q"],
        cwd=str(tmp_path), check=True,
    )


# ── select_mode ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("simple", PipelineMode.SIMPLE),
    ("MEDIUM", PipelineMode.MEDIUM),
    ("  Complex ", PipelineMode.COMPLEX),
    (None, PipelineMode.SIMPLE),
    ("", PipelineMode.SIMPLE),
    ("garbage", PipelineMode.SIMPLE),
])
def test_select_mode(raw, expected):
    assert select_mode(raw) == expected


# ── make_pipeline ────────────────────────────────────────────────────────────

def test_make_pipeline_reuses_state_components():
    ws = _FakeWS()
    lock = FileLock()
    state = SimpleNamespace(llm_manager="LLM", ws_streamer=ws, file_lock=lock)
    pipeline = make_pipeline(state)
    assert isinstance(pipeline, Pipeline)
    assert pipeline.llm == "LLM"
    assert pipeline.ws is ws
    assert pipeline.file_lock is lock


# ── run_chat_pipeline E2E SIMPLE ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_chat_pipeline_e2e_simple(tmp_path):
    """Prompt simple → fichier créé + event pipeline_done(success=True) émis."""
    _init_git(tmp_path)

    fake_llm = _FakeLLMManager({
        "ESTIMATE": (
            '{"classification":"simple","reason":"x","files_hint":["hello.py"],'
            '"confidence":"high","ambiguities":[]}'
        ),
        "INTAKE": (
            '{"prompt_cleaned":"Créer hello.py","target_files_hint":["hello.py"],'
            '"action_verbs":["créer"],"needs_clarification":false,'
            '"clarification_questions":[]}'
        ),
    })
    scripted = ScriptedLLM({
        "GROUND": [ScriptedLLM.text("GROUNDED\nhello.py à créer")],
        "EXECUTE": [
            ScriptedLLM.tool_call(
                "c1", "create_file",
                '{"path":"hello.py","content":"print(\\"hi\\")\\n"}',
            ),
            ScriptedLLM.text("done"),
        ],
    })

    ws = _FakeWS()
    state = SimpleNamespace(llm_manager=fake_llm, ws_streamer=ws, file_lock=FileLock())
    pipeline = make_pipeline(state)
    ctx = PipelineContext(
        prompt="Crée hello.py",
        workspace_root=tmp_path,
        session_id="sess-1",
        mode=select_mode("simple"),
    )

    with (
        patch("backend.pipeline.stage_3_ground.acompletion", side_effect=scripted.acompletion),
        patch("backend.pipeline.stage_5_execute.acompletion", side_effect=scripted.acompletion),
    ):
        result = await run_chat_pipeline(pipeline=pipeline, ws_streamer=ws, ctx=ctx)

    # Pipeline a réellement tourné.
    assert result.success is True, f"echec: {result.error}"
    assert (tmp_path / "hello.py").read_text() == 'print("hi")\n'
    assert "hello.py" in result.files_modified

    # Event final pipeline_done émis vers le bon client.
    done = [(sid, ev) for sid, ev in ws.sent if ev.type == "pipeline_done"]
    assert len(done) == 1
    sid, ev = done[0]
    assert sid == "sess-1"
    assert ev.data["success"] is True
    assert ev.data["mode"] == "simple"
    assert "hello.py" in ev.data["filesModified"]
    assert ev.data["error"] is None

    # Les stages ont bien émis leurs events (broadcast non vide).
    assert len(ws.broadcasts) > 0
