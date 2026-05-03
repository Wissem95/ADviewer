"""Stage 7 — VERIFY (Plan 5B Task 2, version étendue).

Étape mécanique : pas de LLM. Lance en parallèle (asyncio.gather) :
1. ``run_lint`` sur chaque .py / .ts / .tsx / .js / .jsx modifié.
2. ``run_cargo_check`` si au moins un .rs modifié.
3. ``run_pytest`` pour chaque test du plan situé hors ``ui/``.
4. ``run_vitest`` pour chaque test du plan sous ``ui/``.

Agrège les résultats : ``all_green = True`` ssi exit_code=0 partout.

VerifyResult expose ``lint_errors``, ``test_errors``, ``all_green``,
``attempts_used``, ``runners_summary`` pour faciliter le retry de
Stage5Execute (Plan 5B Task 3).

Sécurité : appels via subprocess argv-list, sans shell.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext
from backend.tools.run_tests import (
    run_cargo_check,
    run_lint,
    run_pytest,
    run_vitest,
)


_LINT_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx")


@dataclass
class VerifyResult:
    """Output structuré du Stage7Verify."""

    lint_errors: list[str] = field(default_factory=list)
    test_errors: list[str] = field(default_factory=list)
    all_green: bool = True
    attempts_used: int = 1
    runners_summary: dict = field(default_factory=dict)


class Stage7Verify(Stage):
    """Lint + tests pytest/vitest + cargo check en parallèle."""

    name = "verify"

    def _llm_for_stage(self) -> Optional[str]:
        return None

    async def _execute(self, ctx: PipelineContext) -> VerifyResult:
        files_modified = self._files_modified(ctx)
        tests_to_run = self._tests_to_run(ctx)

        if not files_modified and not tests_to_run:
            return VerifyResult(all_green=True, attempts_used=1)

        tasks: list = []
        kinds: list[str] = []  # tag aligné sur tasks pour dispatch des résultats

        for path in files_modified:
            if path.endswith(_LINT_EXTENSIONS):
                tasks.append(run_lint(path=path, workspace_root=ctx.workspace_root))
                kinds.append("lint")

        if any(p.endswith(".rs") for p in files_modified):
            tasks.append(run_cargo_check(workspace_root=ctx.workspace_root))
            kinds.append("cargo")

        for test_path in tests_to_run:
            if test_path.startswith("ui/") or test_path.endswith((".test.ts", ".test.tsx")):
                tasks.append(
                    run_vitest(target=test_path, workspace_root=ctx.workspace_root)
                )
                kinds.append("vitest")
            else:
                tasks.append(
                    run_pytest(target=test_path, workspace_root=ctx.workspace_root)
                )
                kinds.append("pytest")

        results = await asyncio.gather(*tasks)

        lint_errors: list[str] = []
        test_errors: list[str] = []
        summary = {"lint_passed": 0, "lint_failed": 0, "tests_passed": 0, "tests_failed": 0}

        for kind, r in zip(kinds, results):
            failed = r.get("failed", 0) or (1 if r.get("exit_code", 0) != 0 else 0)
            tail = (r.get("stdout_tail") or "").strip()
            if kind in ("lint", "cargo"):
                summary["lint_passed"] += r.get("passed", 0)
                summary["lint_failed"] += failed
                if r.get("exit_code", 0) != 0 and tail:
                    lint_errors.extend(tail.splitlines())
            else:  # pytest / vitest
                summary["tests_passed"] += r.get("passed", 0)
                summary["tests_failed"] += failed
                if r.get("exit_code", 0) != 0 and tail:
                    test_errors.extend(tail.splitlines())

        all_green = not lint_errors and not test_errors
        return VerifyResult(
            lint_errors=lint_errors,
            test_errors=test_errors,
            all_green=all_green,
            attempts_used=1,
            runners_summary=summary,
        )

    # ── Internals ────────────────────────────────────────────────────────────

    @staticmethod
    def _files_modified(ctx: PipelineContext) -> list[str]:
        execute_output = ctx.get_stage_output("execute")
        if execute_output is None:
            return []
        return list(getattr(execute_output, "files_modified", []) or [])

    @staticmethod
    def _tests_to_run(ctx: PipelineContext) -> list[str]:
        plan_output = ctx.get_stage_output("plan")
        if plan_output is None:
            return []
        return list(getattr(plan_output, "tests_to_run", []) or [])
