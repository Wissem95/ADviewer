"""Stage 6 — SELF-CHECK (Plan 5C stub, implémentation complète en Plan 5D).

Pour ce Plan 5C, on expose un stub qui retourne ``success=True`` avec
``SelfCheckResult(internal_issues=[])`` afin que les modes MEDIUM/COMPLEX
puissent inclure cette étape sans crash. Plan 5D Task 1 fera relire au LLM
son propre diff pour remonter les erreurs internes.
"""
from dataclasses import dataclass, field
from typing import Optional

from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext


@dataclass
class SelfCheckResult:
    """Output structuré du Stage6SelfCheck (stub Plan 5C)."""

    internal_issues: list[str] = field(default_factory=list)
    approved: bool = True


class Stage6SelfCheck(Stage):
    """Stub minimal pour Plan 5C (Plan 5D étendra)."""

    name = "self_check"

    def _llm_for_stage(self) -> Optional[str]:
        # Plan 5D : MiniMax (le même LLM qui a écrit relit son diff).
        return None

    async def _execute(self, ctx: PipelineContext) -> SelfCheckResult:
        # Stub : ne lit pas le diff, retourne approved=True systématiquement.
        # Plan 5D Task 1 remplacera par un vrai appel LLM avec relecture.
        return SelfCheckResult(internal_issues=[], approved=True)
