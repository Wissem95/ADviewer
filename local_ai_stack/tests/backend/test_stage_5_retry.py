"""Tests pour le retry loop Stage5 ← Stage7 (Plan 5B Task 3).

Comportement attendu :
- Stage7Verify rouge → Pipeline relance Stage5 avec ``ctx.retry_context``
  qui contient les erreurs VERIFY de la passe précédente.
- Stage5 injecte ces erreurs dans le user message au LLM pour qu'il corrige.
- Max 3 tentatives Stage5→Stage7. Au-delà, rollback via stash_ref +
  PipelineResult(success=False, error="verify failed after 3 retries").

Tests :
1. 1 retry vert : Stage5 appelé 2x, success=True, attempts_used=2.
2. 3 retries rouges : rollback effectué + success=False.
3. ctx.retry_context bien transmis à Stage5 (erreurs VERIFY présentes).
"""
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.file_lock import FileLock
from backend.pipeline.orchestrator import Pipeline
from backend.pipeline.types import PipelineContext, PipelineMode
from tests.fixtures.scripted_llm import ScriptedLLM


class _FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


class _FakeLLM:
    """Mock minimal LLMManager pour Stage0/1 (call_with_fallback)."""

    async def call_with_fallback(self, *, role, messages, **kw):
        content = messages[0]["content"]
        if "ESTIMATE" in content:
            return (
                '{"classification":"simple","reason":"x","files_hint":[],'
                '"confidence":"high","ambiguities":[]}'
            )
        if "INTAKE" in content:
            return (
                '{"prompt_cleaned":"x","target_files_hint":[],"action_verbs":[],'
                '"needs_clarification":false,"clarification_questions":[]}'
            )
        raise RuntimeError(f"unexpected stage: {content[:60]}")


def _init_git(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=str(tmp_path), check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=str(tmp_path), check=True
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init", "-q"],
        cwd=str(tmp_path),
        check=True,
    )


def _make_ctx(tmp_path: Path) -> PipelineContext:
    return PipelineContext(
        prompt="x",
        workspace_root=tmp_path,
        session_id="retry",
        mode=PipelineMode.SIMPLE,
    )


def _ok(passed: int = 1) -> dict:
    return {
        "exit_code": 0,
        "passed": passed,
        "failed": 0,
        "stdout_tail": "",
        "duration_s": 0.01,
        "error": None,
    }


def _fail(reason: str) -> dict:
    return {
        "exit_code": 1,
        "passed": 0,
        "failed": 1,
        "stdout_tail": reason,
        "duration_s": 0.01,
        "error": None,
    }


@pytest.mark.asyncio
async def test_pipeline_retries_on_verify_red_then_green(tmp_path):
    """1ʳᵉ passe : code buggé → Stage7 rouge.
    2ᵉ passe : code corrigé → Stage7 vert.
    => Pipeline success=True, Stage5 appelé 2 fois, attempts_used=2."""
    _init_git(tmp_path)

    # Stage5 passe 1 : crée bad.py, passe 2 : corrige bad.py.
    scripted = ScriptedLLM({
        "GROUND": [
            ScriptedLLM.text("ground"),
            ScriptedLLM.text("ground retry"),  # peut être consommé en retry
        ],
        "EXECUTE": [
            # Passe 1 : create_file syntaxe invalide
            ScriptedLLM.tool_call(
                "c1", "create_file",
                '{"path":"bad.py","content":"def f(\\n"}',
            ),
            ScriptedLLM.text("done passe 1"),
            # Passe 2 : edit_file pour corriger
            ScriptedLLM.tool_call(
                "c2", "edit_file",
                '{"path":"bad.py","content":"def f():\\n    pass\\n"}',
            ),
            ScriptedLLM.text("done passe 2"),
        ],
    })

    # Stage7 : passe 1 rouge, passe 2 vert.
    lint_calls = [_fail("E999 SyntaxError"), _ok()]

    async def fake_lint(**kw):
        return lint_calls.pop(0)

    pipeline = Pipeline(
        llm_manager=_FakeLLM(), ws_streamer=_FakeWS(), file_lock=FileLock()
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
        patch("backend.pipeline.stage_7_verify.run_lint", side_effect=fake_lint),
    ):
        result = await pipeline.run(_make_ctx(tmp_path))

    assert result.success is True, f"got error: {result.error}"
    assert result.rollback_performed is False
    # Le verify final (dernier de la liste) doit être vert et attempts_used=2.
    verify_stages = [s for s in result.stages if s.stage_name == "verify"]
    assert len(verify_stages) == 2  # passe rouge + passe verte
    final_verify = verify_stages[-1]
    assert final_verify.output.all_green is True
    assert final_verify.output.attempts_used == 2
    # Stage5 appelé 2x.
    execute_stages = [s for s in result.stages if s.stage_name == "execute"]
    assert len(execute_stages) == 2


@pytest.mark.asyncio
async def test_pipeline_3_retries_red_triggers_rollback(tmp_path):
    """Stage7 rouge sur 3 retries → rollback + success=False."""
    _init_git(tmp_path)

    # Stage5 produit le même fichier 3 fois (toujours rouge côté Stage7).
    def execute_passe():
        return [
            ScriptedLLM.tool_call(
                "ck", "create_file",
                '{"path":"bad.py","content":"x = 1\\n"}',
            ),
            ScriptedLLM.text("done"),
        ]

    scripted = ScriptedLLM({
        "GROUND": [ScriptedLLM.text("g")] * 3,
        "EXECUTE": [
            *execute_passe(),
            # passe 2 : edit_file pour ne pas crasher sur "already exists"
            ScriptedLLM.tool_call(
                "c2", "edit_file",
                '{"path":"bad.py","content":"x = 1\\n"}',
            ),
            ScriptedLLM.text("done2"),
            # passe 3
            ScriptedLLM.tool_call(
                "c3", "edit_file",
                '{"path":"bad.py","content":"x = 1\\n"}',
            ),
            ScriptedLLM.text("done3"),
        ],
    })

    async def fake_lint(**kw):
        return _fail("always red")

    pipeline = Pipeline(
        llm_manager=_FakeLLM(), ws_streamer=_FakeWS(), file_lock=FileLock()
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
        patch("backend.pipeline.stage_7_verify.run_lint", side_effect=fake_lint),
    ):
        result = await pipeline.run(_make_ctx(tmp_path))

    assert result.success is False
    assert result.rollback_performed is True
    assert "verify" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_stage_5_uses_retry_context_in_user_message(tmp_path):
    """Quand ctx.retry_context est présent, Stage5 doit injecter les
    erreurs VERIFY dans le user message envoyé au LLM."""
    from backend.pipeline.stage_5_execute import Stage5Execute

    _init_git(tmp_path)

    captured_messages = []

    async def fake_acompletion(**kwargs):
        captured_messages.append(kwargs.get("messages", []))
        # Retourne immédiatement un message final (pas de tool_calls).
        return ScriptedLLM.text("done")

    stage = Stage5Execute(llm_manager=None, ws_streamer=_FakeWS())
    stage.file_lock = FileLock()

    ctx = _make_ctx(tmp_path)
    ctx.retry_context = {
        "previous_verify_errors": ["E999 SyntaxError on line 1"],
        "attempt": 2,
    }

    with patch(
        "backend.pipeline.stage_5_execute.acompletion",
        side_effect=fake_acompletion,
    ):
        await stage.run(ctx)

    # Le user message (rôle user) doit mentionner les erreurs précédentes.
    user_msg_contents = [
        m["content"] for msgs in captured_messages
        for m in msgs if m.get("role") == "user"
    ]
    joined = "\n".join(user_msg_contents)
    assert "E999" in joined or "SyntaxError" in joined
    assert "retry" in joined.lower() or "précédent" in joined.lower() or "previous" in joined.lower()
