"""Tests pour Stage7Verify étendu (Plan 5B Task 2).

Stage7Verify lance maintenant en parallèle (asyncio.gather) :
- ``run_lint`` sur chaque .py / .ts / .tsx / .js / .jsx modifié.
- ``run_cargo_check`` si au moins un .rs modifié.
- ``run_pytest`` pour chaque test listé dans ``ctx.stage_results["plan"].output.tests_to_run``.
- ``run_vitest`` pour chaque test du plan situé sous ``ui/``.

VerifyResult expose maintenant :
- ``lint_errors``: list[str]
- ``test_errors``: list[str]
- ``all_green``: bool
- ``attempts_used``: int
- ``runners_summary``: dict (compteur passed/failed agrégé)
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.pipeline.stage_7_verify import Stage7Verify, VerifyResult
from backend.pipeline.types import (
    PipelineContext,
    PipelineMode,
    StageResult,
)


class _FakeWS:
    def __init__(self):
        self.events = []

    async def broadcast(self, event):
        self.events.append(event)


def _ctx_with(tmp_path: Path, files_modified: list[str], tests_to_run=None):
    ctx = PipelineContext(
        prompt="x",
        workspace_root=tmp_path,
        session_id="t",
        mode=PipelineMode.SIMPLE,
    )
    ctx.stage_results["execute"] = StageResult(
        stage_name="execute",
        duration_ms=0,
        success=True,
        output=SimpleNamespace(files_modified=files_modified, stash_ref=""),
    )
    if tests_to_run is not None:
        ctx.stage_results["plan"] = StageResult(
            stage_name="plan",
            duration_ms=0,
            success=True,
            output=SimpleNamespace(tests_to_run=list(tests_to_run)),
        )
    return ctx


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
async def test_stage_7_lint_ok_test_ok(tmp_path):
    """Tout vert → all_green=True."""
    with (
        patch("backend.pipeline.stage_7_verify.run_lint", return_value=_ok()),
        patch("backend.pipeline.stage_7_verify.run_pytest", return_value=_ok()),
    ):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        ctx = _ctx_with(
            tmp_path,
            files_modified=["app.py"],
            tests_to_run=["tests/test_app.py"],
        )
        result = await stage.run(ctx)

    assert result.success is True
    output: VerifyResult = result.output
    assert output.all_green is True
    assert output.lint_errors == []
    assert output.test_errors == []


@pytest.mark.asyncio
async def test_stage_7_test_red(tmp_path):
    """run_pytest rouge → all_green=False + test_errors contient stdout."""
    with (
        patch("backend.pipeline.stage_7_verify.run_lint", return_value=_ok()),
        patch(
            "backend.pipeline.stage_7_verify.run_pytest",
            return_value=_fail("AssertionError in test_foo"),
        ),
    ):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        ctx = _ctx_with(
            tmp_path,
            files_modified=["app.py"],
            tests_to_run=["tests/test_app.py"],
        )
        result = await stage.run(ctx)

    output: VerifyResult = result.output
    assert output.all_green is False
    assert any("AssertionError" in e for e in output.test_errors)


@pytest.mark.asyncio
async def test_stage_7_lint_red(tmp_path):
    """run_lint rouge → all_green=False + lint_errors rempli."""
    with (
        patch(
            "backend.pipeline.stage_7_verify.run_lint",
            return_value=_fail("F401 unused import"),
        ),
    ):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        ctx = _ctx_with(tmp_path, files_modified=["app.py"])
        result = await stage.run(ctx)

    output: VerifyResult = result.output
    assert output.all_green is False
    assert any("F401" in e for e in output.lint_errors)


@pytest.mark.asyncio
async def test_stage_7_dispatch_eslint_on_ts(tmp_path):
    """Fichier .ts modifié → run_lint appelé avec ce path."""
    invocations = []

    async def fake_lint(*, path, workspace_root, **kw):
        invocations.append(path)
        return _ok()

    with patch("backend.pipeline.stage_7_verify.run_lint", side_effect=fake_lint):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        ctx = _ctx_with(tmp_path, files_modified=["src/app.ts", "src/util.py"])
        await stage.run(ctx)

    assert "src/app.ts" in invocations
    assert "src/util.py" in invocations


@pytest.mark.asyncio
async def test_stage_7_runs_cargo_when_rs(tmp_path):
    """Au moins un .rs modifié → run_cargo_check appelé."""
    cargo_called = []

    async def fake_cargo(*, workspace_root, **kw):
        cargo_called.append(True)
        return _ok()

    with (
        patch("backend.pipeline.stage_7_verify.run_lint", return_value=_ok()),
        patch(
            "backend.pipeline.stage_7_verify.run_cargo_check",
            side_effect=fake_cargo,
        ),
    ):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        ctx = _ctx_with(tmp_path, files_modified=["src-tauri/src/main.rs"])
        await stage.run(ctx)

    assert cargo_called == [True]


@pytest.mark.asyncio
async def test_stage_7_skips_cargo_without_rs(tmp_path):
    cargo_called = []

    async def fake_cargo(**kw):
        cargo_called.append(True)
        return _ok()

    with (
        patch("backend.pipeline.stage_7_verify.run_lint", return_value=_ok()),
        patch(
            "backend.pipeline.stage_7_verify.run_cargo_check",
            side_effect=fake_cargo,
        ),
    ):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        ctx = _ctx_with(tmp_path, files_modified=["app.py"])
        await stage.run(ctx)

    assert cargo_called == []


@pytest.mark.asyncio
async def test_stage_7_dispatches_vitest_on_ui_path(tmp_path):
    """Tests dans ui/ → run_vitest. Tests ailleurs → run_pytest."""
    pytest_calls = []
    vitest_calls = []

    async def fake_pytest(*, target, workspace_root, **kw):
        pytest_calls.append(target)
        return _ok()

    async def fake_vitest(*, target, workspace_root, **kw):
        vitest_calls.append(target)
        return _ok()

    with (
        patch("backend.pipeline.stage_7_verify.run_lint", return_value=_ok()),
        patch("backend.pipeline.stage_7_verify.run_pytest", side_effect=fake_pytest),
        patch("backend.pipeline.stage_7_verify.run_vitest", side_effect=fake_vitest),
    ):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        ctx = _ctx_with(
            tmp_path,
            files_modified=["x.py"],
            tests_to_run=["tests/test_x.py", "ui/src/__tests__/X.test.tsx"],
        )
        await stage.run(ctx)

    assert "tests/test_x.py" in pytest_calls
    assert "ui/src/__tests__/X.test.tsx" in vitest_calls


@pytest.mark.asyncio
async def test_stage_7_no_plan_runs_no_tests(tmp_path):
    """Sans Stage4Plan → pas de pytest/vitest, juste lint."""
    pytest_calls = []
    vitest_calls = []

    async def fake_pytest(**kw):
        pytest_calls.append(True)
        return _ok()

    async def fake_vitest(**kw):
        vitest_calls.append(True)
        return _ok()

    with (
        patch("backend.pipeline.stage_7_verify.run_lint", return_value=_ok()),
        patch("backend.pipeline.stage_7_verify.run_pytest", side_effect=fake_pytest),
        patch("backend.pipeline.stage_7_verify.run_vitest", side_effect=fake_vitest),
    ):
        stage = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
        ctx = _ctx_with(tmp_path, files_modified=["app.py"])
        result = await stage.run(ctx)

    assert pytest_calls == []
    assert vitest_calls == []
    assert result.success is True
    assert result.output.all_green is True


def test_stage_7_name_and_no_llm():
    s = Stage7Verify(llm_manager=None, ws_streamer=_FakeWS())
    assert s.name == "verify"
    assert s._llm_for_stage() is None
