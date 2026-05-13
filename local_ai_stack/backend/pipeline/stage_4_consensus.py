"""Stage 4 — PLAN CONSENSUS wrapper (Plan 5C Task 8).

Wrappe ``run_plan_consensus`` (R1 + Pro, 2 rounds max) dans une ``Stage``
pour que le Pipeline orchestrator puisse l'inclure dans ``stages_by_mode``
comme un stage classique.

En cas de deadlock : Stage retourne ``success=False`` avec error explicite ;
le Pipeline orchestrator gérera le rollback + event WS user_decision
(Plan 5C Task 8.5 / Task 7 UI).
"""
from typing import Optional

from backend.pipeline.base import Stage
from backend.pipeline.consensus import (
    PlanConsensusResult,
    run_plan_consensus,
)
from backend.pipeline.types import PipelineContext, StageResult


class Stage4Consensus(Stage):
    """Stage qui wrappe le consensus 2/2 PLAN ↔ PLAN-REVIEW."""

    name = "plan"  # même name que Stage4aPlan pour que les downstream lisent ctx.stage_results["plan"]

    def _llm_for_stage(self) -> Optional[str]:
        # Multi-LLM : R1 + Pro. On n'expose pas un LLM unique.
        return None

    async def run(self, ctx: PipelineContext) -> StageResult:
        # Override de run() pour gérer le format spécifique du consensus.
        # On contourne le template method standard car on a 2 LLMs et un
        # output dataclass spécifique (PlanConsensusResult + PlanResult).
        from time import perf_counter
        from backend.models import WSEvent

        start = perf_counter()
        if self.ws is not None:
            await self.ws.broadcast(WSEvent(
                type="stage_start",
                data={"stage": self.name, "llm": "consensus(r1+pro)"},
                session_id=ctx.session_id,
            ))

        try:
            consensus: PlanConsensusResult = await run_plan_consensus(
                self.llm, self.ws, ctx
            )
        except Exception as e:
            duration_ms = int((perf_counter() - start) * 1000)
            result = StageResult(
                stage_name=self.name,
                duration_ms=duration_ms,
                success=False,
                output=None,
                error=str(e)[:300],
            )
            ctx.stage_results[self.name] = result
            if self.ws is not None:
                await self.ws.broadcast(WSEvent(
                    type="stage_complete",
                    data={
                        "stage": self.name,
                        "success": False,
                        "duration_ms": duration_ms,
                        "error": result.error,
                    },
                    session_id=ctx.session_id,
                ))
            return result

        duration_ms = int((perf_counter() - start) * 1000)

        if consensus.deadlock or consensus.plan is None:
            # Le Pipeline orchestrator interprétera success=False pour rollback.
            result = StageResult(
                stage_name=self.name,
                duration_ms=duration_ms,
                success=False,
                output=consensus,  # On garde le PlanConsensusResult pour debug
                error=f"plan consensus deadlock after {consensus.rounds} rounds",
            )
        else:
            # Succès : output est le PlanResult (downstream Stage5 le lit).
            result = StageResult(
                stage_name=self.name,
                duration_ms=duration_ms,
                success=True,
                output=consensus.plan,
            )

        ctx.stage_results[self.name] = result

        if self.ws is not None:
            await self.ws.broadcast(WSEvent(
                type="stage_complete",
                data={
                    "stage": self.name,
                    "success": result.success,
                    "duration_ms": duration_ms,
                    "rounds": consensus.rounds,
                    "deadlock": consensus.deadlock,
                    "error": result.error,
                },
                session_id=ctx.session_id,
            ))

        return result

    async def _execute(self, ctx: PipelineContext):
        # Pas utilisé car on a override run() directement.
        raise NotImplementedError("Stage4Consensus override run() directly")
