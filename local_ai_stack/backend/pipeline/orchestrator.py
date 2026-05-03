"""Pipeline orchestrator (Plan 5A Task 11).

Dispatche les ``Stage`` selon le ``PipelineMode``. En Plan 5A, seul SIMPLE
est rempli. Mode MEDIUM/COMPLEX viendront en Plans 5C/5D.

Garanties :
- Sur échec post-stash (Stage5+), invoque ``git_stash_pop`` puis renvoie
  ``PipelineResult(success=False, rollback_performed=True)``.
- Avant que stash ne soit créé (Stages 0/1/3), pas de rollback nécessaire.
- Accumule cost/tokens/duration au fur et à mesure des stages.
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
            PipelineMode.MEDIUM: [],   # Plan 5C
            PipelineMode.COMPLEX: [],  # Plan 5D
        }

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        start = perf_counter()
        stages_classes = self.stages_by_mode.get(ctx.mode, [])

        result = PipelineResult(success=True)

        for stage_cls in stages_classes:
            stage = stage_cls(self.llm, self.ws)
            if hasattr(stage, "file_lock"):
                stage.file_lock = self.file_lock

            stage_result = await stage.run(ctx)
            result.stages.append(stage_result)

            if not stage_result.success:
                result.success = False
                result.error = stage_result.error
                # Rollback uniquement si stash a été créé (Stage5 a tourné).
                stash_ref = self._stash_ref_from_ctx(ctx)
                if stash_ref:
                    await git_stash_pop(ctx.workspace_root, stash_ref)
                    result.rollback_performed = True
                break

        # Accumulation finale.
        result.total_cost_usd = ctx.total_cost_usd
        result.total_duration_ms = int((perf_counter() - start) * 1000)
        execute_output = ctx.get_stage_output("execute")
        if execute_output is not None:
            result.files_modified = list(
                getattr(execute_output, "files_modified", []) or []
            )

        return result

    @staticmethod
    def _stash_ref_from_ctx(ctx: PipelineContext) -> Optional[str]:
        execute_output = ctx.get_stage_output("execute")
        if execute_output is None:
            return None
        return getattr(execute_output, "stash_ref", "") or None
