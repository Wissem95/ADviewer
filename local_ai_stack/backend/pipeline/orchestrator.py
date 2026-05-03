"""Pipeline orchestrator (Plan 5A Task 11 + Plan 5B Task 3).

Dispatche les ``Stage`` selon le ``PipelineMode``. En Plan 5A, seul SIMPLE
est rempli. Mode MEDIUM/COMPLEX viendront en Plans 5C/5D.

Garanties :
- Sur échec post-stash (Stage5+), invoque ``git_stash_pop`` puis renvoie
  ``PipelineResult(success=False, rollback_performed=True)``.
- Avant que stash ne soit créé (Stages 0/1/3), pas de rollback nécessaire.
- Accumule cost/tokens/duration au fur et à mesure des stages.
- Plan 5B : si Stage7Verify retourne ``all_green=False``, boucle vers
  Stage5Execute avec ``ctx.retry_context`` (max 3 tentatives, sinon rollback).
"""
from time import perf_counter
from typing import Optional

from backend.pipeline.stage_0_estimate import Stage0Estimate
from backend.pipeline.stage_1_intake import Stage1Intake
from backend.pipeline.stage_3_ground import Stage3Ground
from backend.pipeline.stage_5_execute import Stage5Execute, git_stash_pop
from backend.pipeline.stage_7_verify import Stage7Verify
from backend.pipeline.types import (
    PipelineContext,
    PipelineMode,
    PipelineResult,
)


_MAX_VERIFY_RETRIES = 3


class Pipeline:
    """Orchestrateur de stages — un seul point d'entrée pour ``run(ctx)``."""

    def __init__(self, llm_manager, ws_streamer, file_lock):
        self.llm = llm_manager
        self.ws = ws_streamer
        self.file_lock = file_lock
        self.stages_by_mode: dict[PipelineMode, list[type]] = {
            PipelineMode.SIMPLE: [
                Stage0Estimate,
                Stage1Intake,
                Stage3Ground,
                Stage5Execute,
                Stage7Verify,
            ],
            PipelineMode.MEDIUM: [],
            PipelineMode.COMPLEX: [],
        }

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        start = perf_counter()
        stages_classes = self.stages_by_mode.get(ctx.mode, [])

        result = PipelineResult(success=True)

        for stage_cls in stages_classes:
            stage_result = await self._run_stage(stage_cls, ctx)
            result.stages.append(stage_result)

            if not stage_result.success:
                result.success = False
                result.error = stage_result.error
                stash_ref = self._stash_ref_from_ctx(ctx)
                if stash_ref:
                    await git_stash_pop(ctx.workspace_root, stash_ref)
                    result.rollback_performed = True
                self._finalize(result, ctx, start)
                return result

        # Plan 5B Task 3 : retry loop Stage5 ← Stage7 si verify rouge.
        attempts_used = await self._retry_until_green_or_max(ctx, result)
        verify_output = ctx.get_stage_output("verify")
        if verify_output is not None and getattr(verify_output, "all_green", True) is False:
            # 3 tentatives échouées → rollback.
            stash_ref = self._stash_ref_from_ctx(ctx)
            if stash_ref:
                await git_stash_pop(ctx.workspace_root, stash_ref)
                result.rollback_performed = True
            result.success = False
            result.error = f"verify failed after {attempts_used} retries"
        else:
            # all_green : on patch attempts_used dans VerifyResult final.
            if verify_output is not None and hasattr(verify_output, "attempts_used"):
                verify_output.attempts_used = attempts_used

        self._finalize(result, ctx, start)
        return result

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _run_stage(self, stage_cls, ctx):
        stage = stage_cls(self.llm, self.ws)
        if hasattr(stage, "file_lock"):
            stage.file_lock = self.file_lock
        return await stage.run(ctx)

    async def _retry_until_green_or_max(
        self, ctx: PipelineContext, result: PipelineResult
    ) -> int:
        """Boucle Stage5 → Stage7 jusqu'à all_green ou ``_MAX_VERIFY_RETRIES``.

        Retourne le nombre total de tentatives Stage7 effectuées (≥ 1).
        """
        attempts = 1
        while attempts < _MAX_VERIFY_RETRIES:
            verify_output = ctx.get_stage_output("verify")
            if verify_output is None or getattr(verify_output, "all_green", True):
                break

            attempts += 1
            ctx.retry_context = {
                "previous_verify_errors": list(
                    getattr(verify_output, "lint_errors", []) or []
                ) + list(
                    getattr(verify_output, "test_errors", []) or []
                ),
                "attempt": attempts,
            }

            execute_sr = await self._run_stage(Stage5Execute, ctx)
            result.stages.append(execute_sr)
            if not execute_sr.success:
                result.success = False
                result.error = execute_sr.error
                return attempts

            verify_sr = await self._run_stage(Stage7Verify, ctx)
            result.stages.append(verify_sr)
            if not verify_sr.success:
                result.success = False
                result.error = verify_sr.error
                return attempts

        ctx.retry_context = None
        return attempts

    def _finalize(self, result, ctx, start) -> None:
        result.total_cost_usd = ctx.total_cost_usd
        result.total_duration_ms = int((perf_counter() - start) * 1000)
        execute_output = ctx.get_stage_output("execute")
        if execute_output is not None:
            result.files_modified = list(
                getattr(execute_output, "files_modified", []) or []
            )

    @staticmethod
    def _stash_ref_from_ctx(ctx: PipelineContext) -> Optional[str]:
        execute_output = ctx.get_stage_output("execute")
        if execute_output is None:
            return None
        return getattr(execute_output, "stash_ref", "") or None
