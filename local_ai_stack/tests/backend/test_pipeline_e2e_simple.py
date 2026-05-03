"""Test E2E pipeline mode SIMPLE (Plan 5A Task 14).

Scénario : un prompt "Crée hello.py qui print 'hi'" → tout le pipeline tourne
en SIMPLE (Stage0 → Stage1 → Stage3 → Stage5 → Stage7), un fichier réel est
créé sur disque, ruff valide, success=True.

Stratégie :
- ``call_with_fallback`` (Stage0/1) : FakeLLMManager qui détecte le stage via
  le system prompt (``# Étape N — XXX``) et retourne le JSON adéquat.
- ``acompletion`` (Stage3/5) : ScriptedLLM patché dans les deux modules.

Ne touche jamais au réseau.
"""
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
    """Mock LLMManager.call_with_fallback : détecte le stage via system prompt."""

    def __init__(self, stage_responses: dict[str, str]):
        self.stage_responses = {k.upper(): v for k, v in stage_responses.items()}

    async def call_with_fallback(self, *, role, messages, **kwargs) -> str:
        system = next((m for m in messages if m.get("role") == "system"), None)
        if system is None:
            raise RuntimeError("FakeLLM: pas de system prompt")
        match = _STAGE_RE.search(system.get("content", ""))
        if not match:
            raise RuntimeError(
                f"FakeLLM: stage non détecté dans system prompt: "
                f"{system['content'][:100]!r}"
            )
        stage = match.group(1).upper()
        if stage not in self.stage_responses:
            raise RuntimeError(f"FakeLLM: pas de réponse scriptée pour {stage}")
        return self.stage_responses[stage]


def _init_git(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test"], cwd=str(tmp_path), check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "test"], cwd=str(tmp_path), check=True
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init", "-q"],
        cwd=str(tmp_path),
        check=True,
    )


@pytest.mark.asyncio
async def test_pipeline_e2e_creates_hello_py(tmp_path):
    """Prompt simple → fichier hello.py réellement créé sur disque."""
    _init_git(tmp_path)

    fake_llm = _FakeLLMManager({
        "ESTIMATE": (
            '{"classification":"simple","reason":"Création directe d\'un fichier",'
            '"files_hint":["hello.py"],"confidence":"high","ambiguities":[]}'
        ),
        "INTAKE": (
            '{"prompt_cleaned":"Créer hello.py qui print(\'hi\')",'
            '"target_files_hint":["hello.py"],"action_verbs":["créer"],'
            '"needs_clarification":false,"clarification_questions":[]}'
        ),
    })

    scripted = ScriptedLLM({
        "GROUND": [
            ScriptedLLM.text(
                "GROUNDED_CONTEXT\nFichier hello.py n'existe pas, à créer."
            ),
        ],
        "EXECUTE": [
            ScriptedLLM.tool_call(
                "c1",
                "create_file",
                '{"path":"hello.py","content":"print(\\"hi\\")\\n"}',
            ),
            ScriptedLLM.text("EXECUTE_DONE\nhello.py créé"),
        ],
    })

    pipeline = Pipeline(
        llm_manager=fake_llm,
        ws_streamer=_FakeWS(),
        file_lock=FileLock(),
    )
    ctx = PipelineContext(
        prompt="Crée un fichier hello.py qui print 'hi'",
        workspace_root=tmp_path,
        session_id="e2e",
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

    # Vérifications E2E.
    assert result.success is True, f"pipeline failed: {result.error}"
    hello = tmp_path / "hello.py"
    assert hello.exists(), "hello.py n'a pas été créé"
    assert hello.read_text() == 'print("hi")\n'

    # Tous les stages ont tourné.
    stage_names = [s.stage_name for s in result.stages]
    assert stage_names == ["estimate", "intake", "ground", "execute", "verify"]
    assert all(s.success for s in result.stages)

    # files_modified contient hello.py.
    assert "hello.py" in result.files_modified
    # Pas de rollback (tout vert).
    assert result.rollback_performed is False


@pytest.mark.asyncio
async def test_pipeline_e2e_propagates_files_modified_to_verify(tmp_path):
    """Stage7Verify reçoit bien la liste files_modified de Stage5Execute."""
    _init_git(tmp_path)

    fake_llm = _FakeLLMManager({
        "ESTIMATE": (
            '{"classification":"simple","reason":"x","files_hint":[],'
            '"confidence":"high","ambiguities":[]}'
        ),
        "INTAKE": (
            '{"prompt_cleaned":"x","target_files_hint":[],"action_verbs":[],'
            '"needs_clarification":false,"clarification_questions":[]}'
        ),
    })

    scripted = ScriptedLLM({
        "GROUND": [ScriptedLLM.text("ok")],
        "EXECUTE": [
            ScriptedLLM.tool_call(
                "c1",
                "create_file",
                '{"path":"a.py","content":"a = 1\\n"}',
            ),
            ScriptedLLM.text("done"),
        ],
    })

    pipeline = Pipeline(
        llm_manager=fake_llm,
        ws_streamer=_FakeWS(),
        file_lock=FileLock(),
    )
    ctx = PipelineContext(
        prompt="x",
        workspace_root=tmp_path,
        session_id="e2e2",
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
    assert "a.py" in result.files_modified
    # Verify a tourné après execute.
    verify_sr = next(s for s in result.stages if s.stage_name == "verify")
    assert verify_sr.success is True
    assert verify_sr.output.attempts_used == 1
