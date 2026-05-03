"""Stage 7 — VERIFY (Plan 5A Task 11, version minimale).

Étape mécanique : pas de LLM. Lance ``ruff check`` sur les .py modifiés et
``cargo check`` sur ``ui/src-tauri/`` si au moins un .rs a été touché.

Retourne ``VerifyResult(lint_errors, all_green, attempts_used=1)``. Pas de
retry interne à ce stade — Plan 5B étendra cette étape avec pytest/vitest et
boucle de retry (max 3) qui déclenche un rollback via stash_ref si tout est
rouge.

Sécurité : appels via subprocess argv-list, pas de shell, pas
d'interpolation utilisateur dans la commande.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext


@dataclass
class VerifyResult:
    """Output structuré du Stage7Verify."""

    lint_errors: list[str] = field(default_factory=list)
    all_green: bool = True
    attempts_used: int = 1


class Stage7Verify(Stage):
    """Lint mécanique post-EXECUTE."""

    name = "verify"

    def _llm_for_stage(self) -> Optional[str]:
        return None

    async def _execute(self, ctx: PipelineContext) -> VerifyResult:
        execute_output = ctx.get_stage_output("execute")
        files_modified: list[str] = []
        if execute_output is not None:
            files_modified = list(getattr(execute_output, "files_modified", []) or [])

        if not files_modified:
            return VerifyResult(lint_errors=[], all_green=True, attempts_used=1)

        py_files = [f for f in files_modified if f.endswith(".py")]
        rs_touched = any(f.endswith(".rs") for f in files_modified)

        lint_errors: list[str] = []

        if py_files:
            errors = await self._run_ruff(ctx.workspace_root, py_files)
            lint_errors.extend(errors)

        if rs_touched:
            errors = await self._run_cargo_check(ctx.workspace_root)
            lint_errors.extend(errors)

        return VerifyResult(
            lint_errors=lint_errors,
            all_green=len(lint_errors) == 0,
            attempts_used=1,
        )

    # ── Internals ────────────────────────────────────────────────────────────

    @staticmethod
    async def _run_ruff(workspace_root, py_files: list[str]) -> list[str]:
        proc = await asyncio.create_subprocess_exec(
            "ruff", "check", "--no-cache", *py_files,
            cwd=str(workspace_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return []
        text = (stdout or b"").decode("utf-8", errors="ignore")
        text += (stderr or b"").decode("utf-8", errors="ignore")
        return [line for line in text.splitlines() if line.strip()]

    @staticmethod
    async def _run_cargo_check(workspace_root) -> list[str]:
        cargo_dir = workspace_root / "ui" / "src-tauri"
        proc = await asyncio.create_subprocess_exec(
            "cargo", "check", "--quiet",
            cwd=str(cargo_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return []
        text = (stdout or b"").decode("utf-8", errors="ignore")
        text += (stderr or b"").decode("utf-8", errors="ignore")
        return [line for line in text.splitlines() if line.strip()]
