"""Pipeline orchestrator (Plan 5A Task 11 + Plan 5B Tasks 3 & 6).

Dispatche les ``Stage`` selon le ``PipelineMode``. En Plan 5A, seul SIMPLE
est rempli. Mode MEDIUM/COMPLEX viendront en Plans 5C/5D.

Garanties :
- Sur échec post-stash (Stage5+), invoque ``git_stash_pop`` puis renvoie
  ``PipelineResult(success=False, rollback_performed=True)``.
- Avant que stash ne soit créé (Stages 0/1/3), pas de rollback nécessaire.
- Accumule cost/tokens/duration au fur et à mesure des stages.
- Plan 5B Task 3 : si Stage7Verify retourne ``all_green=False``, boucle vers
  Stage5Execute avec ``ctx.retry_context`` (max 3 tentatives, sinon rollback).
- Plan 5B Task 6 : sur ``asyncio.CancelledError`` (bouton Stop UI), rollback
  via stash_ref si stage5 a déjà tourné, sinon juste exit propre.
"""
import asyncio
from time import perf_counter
from typing import Optional

from backend.budget_tracker import BudgetTracker
from backend.pipeline.stage_0_estimate import Stage0Estimate
from backend.pipeline.stage_1_intake import Stage1Intake
from backend.pipeline.stage_2_challenge import Stage2Challenge
from backend.pipeline.stage_3_ground import Stage3Ground
from backend.pipeline.stage_4_consensus import Stage4Consensus
from backend.pipeline.stage_4a_plan import Stage4aPlan
from backend.pipeline.stage_5_execute import Stage5Execute, git_stash_pop
from backend.pipeline.stage_6_self_check import Stage6SelfCheck
from backend.pipeline.stage_7_verify import Stage7Verify
from backend.pipeline.stage_8_review import Stage8Review
from backend.pipeline.stage_9_second_review import Stage9SecondReview
from backend.pipeline.types import (
    PipelineContext,
    PipelineMode,
    PipelineResult,
)


_MAX_VERIFY_RETRIES = 3
_DEFAULT_BUDGET_CAP_USD = 1.0


class BudgetExceeded(Exception):
    """Levée par Pipeline quand le BudgetTracker dépasse le cap."""


class Pipeline:
    """Orchestrateur de stages — un seul point d'entrée pour ``run(ctx)``."""

    def __init__(self, llm_manager, ws_streamer, file_lock, budget_cap_usd: float = _DEFAULT_BUDGET_CAP_USD):
        self.llm = llm_manager
        self.ws = ws_streamer
        self.file_lock = file_lock
        self.budget_cap_usd = budget_cap_usd
        # Plan 5C Task 8 : MEDIUM et COMPLEX activés.
        # MEDIUM : ajoute Stage4aPlan (R1 seul, pas de consensus), Stage6 SELF-CHECK,
        #          Stage8 REVIEW (stubs Plan 5C, implémentés Plan 5D).
        # COMPLEX : ajoute Stage2 CHALLENGE, Stage4Consensus (R1+Pro 2 rounds),
        #           Stage6/8/9 stubs.
        self.stages_by_mode: dict[PipelineMode, list[type]] = {
            PipelineMode.SIMPLE: [
                Stage0Estimate,
                Stage1Intake,
                Stage3Ground,
                Stage5Execute,
                Stage7Verify,
            ],
            PipelineMode.MEDIUM: [
                Stage0Estimate,
                Stage1Intake,
                Stage3Ground,
                Stage4aPlan,
                Stage5Execute,
                Stage6SelfCheck,
                Stage7Verify,
                Stage8Review,
            ],
            PipelineMode.COMPLEX: [
                Stage0Estimate,
                Stage1Intake,
                Stage2Challenge,
                Stage3Ground,
                Stage4Consensus,
                Stage5Execute,
                Stage6SelfCheck,
                Stage7Verify,
                Stage8Review,
                Stage9SecondReview,
            ],
        }

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        start = perf_counter()
        stages_classes = self.stages_by_mode.get(ctx.mode, [])

        result = PipelineResult(success=True)
        budget = BudgetTracker(cap_usd=self.budget_cap_usd)

        try:
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

                # Plan 5B Task 7 : check budget cap après chaque stage.
                budget.track_cost(stage_result.cost_usd or 0.0)
                if budget.cap_exceeded():
                    raise BudgetExceeded(
                        f"budget cap exceeded: ${budget.current_usd():.4f} > ${budget.cap_usd:.2f}"
                    )

            # Plan 5B Task 3 : retry loop Stage5 ← Stage7 si verify rouge.
            attempts_used = await self._retry_until_green_or_max(ctx, result)
            verify_output = ctx.get_stage_output("verify")
            if verify_output is not None and getattr(verify_output, "all_green", True) is False:
                stash_ref = self._stash_ref_from_ctx(ctx)
                if stash_ref:
                    await git_stash_pop(ctx.workspace_root, stash_ref)
                    result.rollback_performed = True
                result.success = False
                result.error = f"verify failed after {attempts_used} retries"
            else:
                if verify_output is not None and hasattr(verify_output, "attempts_used"):
                    verify_output.attempts_used = attempts_used

        except asyncio.CancelledError:
            # Plan 5B Task 6 : bouton Stop côté UI → rollback si stash existe.
            result.success = False
            result.error = "cancelled by user"
            stash_ref = self._stash_ref_from_ctx(ctx)
            if stash_ref:
                try:
                    await asyncio.shield(
                        git_stash_pop(ctx.workspace_root, stash_ref)
                    )
                    result.rollback_performed = True
                except asyncio.CancelledError:
                    result.rollback_performed = True
            self._finalize(result, ctx, start)
            return result

        except BudgetExceeded as e:
            # Plan 5B Task 7 : cap budget dépassé → abort + rollback si stash.
            result.success = False
            result.error = str(e)
            stash_ref = self._stash_ref_from_ctx(ctx)
            if stash_ref:
                await git_stash_pop(ctx.workspace_root, stash_ref)
                result.rollback_performed = True
            self._finalize(result, ctx, start)
            return result

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
