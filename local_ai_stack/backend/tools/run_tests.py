"""Wrappers asynchrones autour des runners de tests/lint (Plan 5B Task 1).

Tous les wrappers retournent un dict standardisé ::

    {
        "exit_code": int,           # 0 = vert, != 0 = rouge, -1 = timeout
        "passed": int,
        "failed": int,
        "stdout_tail": str,         # tronqué à 3000 chars
        "duration_s": float,
        "error": str | None,        # rempli si timeout / runner manquant
    }

Sécurité : tous les appels passent par subprocess argv-list, sans shell.
"""
import asyncio
import re
import shutil
from pathlib import Path
from time import perf_counter

_STDOUT_TRUNCATE = 3000

_PASSED_RE = re.compile(r"(\d+)\s+passed")
_FAILED_RE = re.compile(r"(\d+)\s+failed")


def _truncate(text: str) -> str:
    if len(text) <= _STDOUT_TRUNCATE:
        return text
    prefix = "...[truncated]...\n"
    keep = _STDOUT_TRUNCATE - len(prefix)
    return prefix + text[-keep:]


async def _run(argv: list[str], cwd: Path, timeout: int) -> dict:
    """Helper interne. Lance argv via subprocess argv-list, parse le retour."""
    start = perf_counter()
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError as e:
        return {
            "exit_code": 127,
            "passed": 0,
            "failed": 0,
            "stdout_tail": "",
            "duration_s": 0.0,
            "error": f"runner not found: {e}",
        }
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.communicate()
        except Exception:
            pass
        return {
            "exit_code": -1,
            "passed": 0,
            "failed": 0,
            "stdout_tail": "",
            "duration_s": float(timeout),
            "error": "timeout",
        }
    duration = perf_counter() - start
    text = (stdout or b"").decode("utf-8", errors="ignore")
    passed = sum(int(m.group(1)) for m in _PASSED_RE.finditer(text))
    failed = sum(int(m.group(1)) for m in _FAILED_RE.finditer(text))
    return {
        "exit_code": proc.returncode if proc.returncode is not None else 1,
        "passed": passed,
        "failed": failed,
        "stdout_tail": _truncate(text),
        "duration_s": duration,
        "error": None,
    }


async def run_pytest(target: str, workspace_root: Path, timeout: int = 60) -> dict:
    return await _run(
        ["python", "-m", "pytest", target, "--tb=short", "-q", "--no-header"],
        cwd=workspace_root,
        timeout=timeout,
    )


async def run_vitest(target: str, workspace_root: Path, timeout: int = 60) -> dict:
    if shutil.which("npx") is None:
        return {
            "exit_code": 127,
            "passed": 0,
            "failed": 0,
            "stdout_tail": "",
            "duration_s": 0.0,
            "error": "npx not found",
        }
    return await _run(
        ["npx", "vitest", "run", target],
        cwd=workspace_root,
        timeout=timeout,
    )


async def run_cargo_check(workspace_root: Path, timeout: int = 120) -> dict:
    cargo_dir = workspace_root / "ui" / "src-tauri"
    if not cargo_dir.exists():
        cargo_dir = workspace_root
    if not (cargo_dir / "Cargo.toml").exists():
        return {
            "exit_code": 1,
            "passed": 0,
            "failed": 1,
            "stdout_tail": "no Cargo.toml found",
            "duration_s": 0.0,
            "error": "no Cargo.toml",
        }
    return await _run(
        ["cargo", "check", "--quiet"],
        cwd=cargo_dir,
        timeout=timeout,
    )


async def run_lint(path: str, workspace_root: Path, timeout: int = 30) -> dict:
    """Dispatch ruff/eslint selon extension. ``path`` relatif au workspace."""
    ext = Path(path).suffix.lower()
    if ext == ".py":
        return await _run(
            ["ruff", "check", "--no-cache", path],
            cwd=workspace_root,
            timeout=timeout,
        )
    if ext in (".ts", ".tsx", ".js", ".jsx"):
        if shutil.which("npx") is None:
            return {
                "exit_code": 127,
                "passed": 0,
                "failed": 0,
                "stdout_tail": "",
                "duration_s": 0.0,
                "error": "npx not found",
            }
        return await _run(
            ["npx", "eslint", path],
            cwd=workspace_root,
            timeout=timeout,
        )
    return {
        "exit_code": 0,
        "passed": 0,
        "failed": 0,
        "stdout_tail": f"no linter for extension {ext}",
        "duration_s": 0.0,
        "error": None,
    }
