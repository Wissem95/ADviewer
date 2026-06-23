"""Pont chat ↔ Pipeline (Plan 5D Task 11.3).

Branche le pipeline multi-LLM/consensus sur le handler WebSocket ``chat``.
Avant ce module, un prompt UI partait dans ``Orchestrator.handle`` (AgentLoop
legacy) et tout le travail des Plans 5A-5C (stages + consensus) restait
invisible côté UI. Ce runner :

- construit un ``Pipeline`` à partir des composants partagés de ``app.state`` ;
- exécute ``pipeline.run(ctx)`` (les stages émettent eux-mêmes leurs events WS
  ``stage_complete`` / consensus via ``ws_streamer.broadcast``) ;
- émet un event final ``pipeline_done`` récapitulatif vers le client demandeur.

Conçu pour être *additif* : le handler n'appelle ce chemin que lorsque l'UI
envoie ``data.usePipeline = true`` ; le chemin AgentLoop reste inchangé.
"""
from __future__ import annotations

from backend.models import WSEvent
from backend.pipeline.orchestrator import Pipeline
from backend.pipeline.types import PipelineContext, PipelineMode, PipelineResult


def select_mode(mode_str: str | None) -> PipelineMode:
    """Mappe une chaîne UI ("simple"/"medium"/"complex") vers ``PipelineMode``.

    Tolérant : casse ignorée, valeur inconnue/None → SIMPLE (le mode le moins
    coûteux, choix sûr par défaut).
    """
    if not mode_str:
        return PipelineMode.SIMPLE
    try:
        return PipelineMode(mode_str.strip().lower())
    except ValueError:
        return PipelineMode.SIMPLE


def make_pipeline(state) -> Pipeline:
    """Construit un ``Pipeline`` à partir des composants partagés d'``app.state``.

    Réutilise les mêmes ``llm_manager`` / ``ws_streamer`` / ``file_lock`` que
    l'orchestrateur legacy, donc aucune ressource n'est dupliquée.
    """
    return Pipeline(
        llm_manager=state.llm_manager,
        ws_streamer=state.ws_streamer,
        file_lock=state.file_lock,
    )


async def run_chat_pipeline(*, pipeline: Pipeline, ws_streamer, ctx: PipelineContext) -> PipelineResult:
    """Exécute le pipeline pour un prompt chat et émet l'event final.

    ``pipeline.run`` absorbe lui-même ``CancelledError`` (bouton Stop) et renvoie
    un ``PipelineResult`` avec ``success=False`` ; on émet ``pipeline_done`` dans
    tous les cas pour que l'UI sorte de l'état "en cours".
    """
    result = await pipeline.run(ctx)
    await ws_streamer.send_to(
        ctx.session_id,
        WSEvent(
            type="pipeline_done",
            data={
                "success": result.success,
                "mode": ctx.mode.value,
                "filesModified": result.files_modified,
                "costUsd": result.total_cost_usd,
                "durationMs": result.total_duration_ms,
                "rollbackPerformed": result.rollback_performed,
                "error": result.error,
            },
            session_id=ctx.session_id,
        ),
    )
    return result
