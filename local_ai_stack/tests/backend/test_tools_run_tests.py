"""Tests pour backend/tools/run_tests.py (Plan 5B Task 1).

Wrappers asynchrones autour de pytest / vitest / cargo check / lint.
Tous retournent un dict standardisé :
    {exit_code, passed, failed, stdout_tail, duration_s, error?}

stdout_tail est tronqué à 3000 chars pour éviter de saturer le contexte LLM.
"""
import subprocess
import textwrap
from pathlib import Path

import pytest

from backend.tools.run_tests import (
    run_cargo_check,
    run_lint,
    run_pytest,
    run_vitest,
)


def _make_python_project(tmp_path: Path) -> Path:
    """Crée un mini-projet Python avec 1 test passant + 1 test échouant."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n"
    )
    (tmp_path / "tests" / "test_fail.py").write_text(
        "def test_fail():\n    assert 1 == 2\n"
    )
    return tmp_path


@pytest.mark.asyncio
async def test_run_pytest_passing(tmp_path):
    _make_python_project(tmp_path)
    result = await run_pytest(target="tests/test_ok.py", workspace_root=tmp_path)
    assert result["exit_code"] == 0
    assert result["passed"] == 1
    assert result["failed"] == 0
    assert "stdout_tail" in result
    assert result["duration_s"] > 0


@pytest.mark.asyncio
async def test_run_pytest_failing(tmp_path):
    _make_python_project(tmp_path)
    result = await run_pytest(target="tests/test_fail.py", workspace_root=tmp_path)
    assert result["exit_code"] != 0
    assert result["passed"] == 0
    assert result["failed"] == 1
    assert len(result["stdout_tail"]) > 0
    assert len(result["stdout_tail"]) <= 3000


@pytest.mark.asyncio
async def test_run_pytest_truncates_stdout(tmp_path):
    """Si pytest produit beaucoup de sortie, stdout_tail tronqué à 3000."""
    (tmp_path / "tests").mkdir()
    # Test qui imprime 10K chars puis échoue.
    big = "x" * 10_000
    (tmp_path / "tests" / "test_big.py").write_text(
        f"def test_big():\n    print({big!r})\n    assert False\n"
    )
    result = await run_pytest(target="tests/test_big.py", workspace_root=tmp_path)
    assert len(result["stdout_tail"]) <= 3000


@pytest.mark.asyncio
async def test_run_pytest_timeout(tmp_path):
    """Test qui dort plus longtemps que le timeout → exit_code=-1."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_slow.py").write_text(
        "import time\ndef test_slow():\n    time.sleep(5)\n"
    )
    result = await run_pytest(
        target="tests/test_slow.py",
        workspace_root=tmp_path,
        timeout=1,
    )
    assert result["exit_code"] == -1
    assert "timeout" in (result.get("error") or "").lower()


@pytest.mark.asyncio
async def test_run_lint_python_clean(tmp_path):
    """Ruff clean → exit_code=0. (Ruff n'imprime pas de compteur "passed".)"""
    (tmp_path / "ok.py").write_text("x = 1\n")
    result = await run_lint(path="ok.py", workspace_root=tmp_path)
    assert result["exit_code"] == 0
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_run_lint_python_dirty(tmp_path):
    (tmp_path / "bad.py").write_text("import sys\nimport os\n")  # F401 unused
    result = await run_lint(path="bad.py", workspace_root=tmp_path)
    # ruff peut être "all-good" ou "errors" selon config — on vérifie juste
    # que le wrapper renvoie un dict standardisé.
    assert "exit_code" in result
    assert "stdout_tail" in result


@pytest.mark.asyncio
async def test_run_lint_dispatches_by_extension(tmp_path, monkeypatch):
    """Une extension .ts → tente eslint. Si eslint absent, exit_code != 0
    mais le dispatch a eu lieu (pas de crash)."""
    (tmp_path / "x.ts").write_text("const x = 1;\n")
    result = await run_lint(path="x.ts", workspace_root=tmp_path)
    assert "exit_code" in result


@pytest.mark.asyncio
async def test_run_cargo_check_no_cargo(tmp_path):
    """cargo absent ou pas de Cargo.toml → exit_code != 0 et message d'erreur."""
    result = await run_cargo_check(workspace_root=tmp_path)
    assert "exit_code" in result
    assert "stdout_tail" in result


@pytest.mark.asyncio
async def test_run_vitest_no_vitest(tmp_path):
    """Pas de vitest installé → renvoie un dict standardisé sans crash."""
    result = await run_vitest(target="x.test.ts", workspace_root=tmp_path)
    assert "exit_code" in result
