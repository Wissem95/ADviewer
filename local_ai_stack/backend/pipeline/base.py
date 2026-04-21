"""Classe abstraite Stage — template method pour toutes les étapes (Plan 5A Task 6).

Chaque étape concrète (Stage0Estimate, Stage1Intake, ...) hérite de ``Stage``
et implémente ``_execute(ctx)``. La méthode publique ``run(ctx)`` s'occupe
de :
- émettre l'event WS ``stage_start`` (l'UI peut afficher l'étape en cours),
- mesurer la durée via perf_counter,
- appeler ``_execute`` et capturer toute exception (jamais de crash qui
  remonterait dans le pipeline orchestrator sans trace),
- émettre ``stage_complete`` avec duration_ms + cost,
- construire un ``StageResult`` homogène.

Les payloads retournés par ``_execute`` peuvent exposer optionnellement les
attributs ``tokens_in``, ``tokens_out``, ``cost_usd`` : s'ils existent, ils
sont copiés dans le StageResult pour alimenter le CostTracker (Plan 5E).
"""
from abc import ABC, abstractmethod
from time import perf_counter
from typing import Any, Optional

from backend.models import WSEvent
from backend.pipeline.types import PipelineContext, StageResult


class Stage(ABC):
    """Base abstraite pour toutes les étapes du pipeline.

    Sous-classes : override ``name``, ``_execute``, et optionnellement
    ``_llm_for_stage`` si l'étape utilise un LLM.
    """

    name: str = "base"

    def __init__(self, llm_manager, ws_streamer):
        self.llm = llm_manager
        self.ws = ws_streamer

    # ── Interface publique ───────────────────────────────────────────────────

    async def run(self, ctx: PipelineContext) -> StageResult:
        """Template method : start → execute → complete.

        Garantie : ne lève JAMAIS. Toute exception dans ``_execute`` est
        capturée et retournée dans ``StageResult.error``. C'est au Pipeline
        orchestrator d'interpréter ``success=False`` pour déclencher un
        rollback si nécessaire.
        """
        llm_id = self._llm_for_stage()
        start = perf_counter()

        await self._emit_start(ctx.session_id, llm_id)

        try:
            output = await self._execute(ctx)
            duration_ms = int((perf_counter() - start) * 1000)
            tokens_in = getattr(output, "tokens_in", 0) if output is not None else 0
            tokens_out = getattr(output, "tokens_out", 0) if output is not None else 0
            cost_usd = getattr(output, "cost_usd", 0.0) if output is not None else 0.0
            result = StageResult(
                stage_name=self.name,
                duration_ms=duration_ms,
                success=True,
                llm_used=llm_id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                output=output,
            )
        except Exception as e:
            duration_ms = int((perf_counter() - start) * 1000)
            result = StageResult(
                stage_name=self.name,
                duration_ms=duration_ms,
                success=False,
                llm_used=llm_id,
                output=None,
                error=str(e)[:300],
            )

        await self._emit_complete(ctx.session_id, result)
        return result

    # ── Méthodes à override ──────────────────────────────────────────────────

    @abstractmethod
    async def _execute(self, ctx: PipelineContext) -> Any:
        """Implémentation spécifique de l'étape. À override obligatoirement."""

    def _llm_for_stage(self) -> Optional[str]:
        """Nom du LLM utilisé par cette étape (format litellm).

        Override par les sous-classes LLM-based. Retourne None par défaut
        (étapes mécaniques comme Stage7Verify).
        """
        return None

    # ── Internals ────────────────────────────────────────────────────────────

    async def _emit_start(self, session_id: str, llm_id: Optional[str]) -> None:
        if self.ws is None:
            return
        await self.ws.broadcast(WSEvent(
            type="stage_start",
            data={"stage": self.name, "llm": llm_id},
            session_id=session_id,
        ))

    async def _emit_complete(self, session_id: str, result: StageResult) -> None:
        if self.ws is None:
            return
        await self.ws.broadcast(WSEvent(
            type="stage_complete",
            data={
                "stage": self.name,
                "success": result.success,
                "duration_ms": result.duration_ms,
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
                "cost_usd": result.cost_usd,
                "error": result.error,
            },
            session_id=session_id,
        ))
