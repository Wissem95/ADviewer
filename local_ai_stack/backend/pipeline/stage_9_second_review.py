"""Stage 9 — SECOND-REVIEW (Plan 5C stub, implémentation complète en Plan 5D).

Avis indépendant de DeepSeek R1, déclenché uniquement si Stage8 hésite ou
si on est en mode COMPLEX. Stub minimal Plan 5C → approved=True.
"""
from dataclasses import dataclass, field
from typing import Optional

from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext


@dataclass
class SecondReviewResult:
    """Output structuré du Stage9SecondReview (stub Plan 5C)."""

    approved: bool = True
    reasons: list[str] = field(default_factory=list)


class Stage9SecondReview(Stage):
    """Stub minimal pour Plan 5C (Plan 5D étendra)."""

    name = "second_review"

    def _llm_for_stage(self) -> Optional[str]:
        # Plan 5D : DeepSeek R1 (avis indépendant du Stage8 Pro).
        return None

    async def _execute(self, ctx: PipelineContext) -> SecondReviewResult:
        return SecondReviewResult(approved=True, reasons=[])
