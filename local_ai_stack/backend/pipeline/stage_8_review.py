"""Stage 8 — REVIEW (Plan 5C stub, implémentation complète en Plan 5D).

Stub minimal qui retourne ``approved=True`` pour que les modes MEDIUM/COMPLEX
puissent tourner sans crash. Plan 5D Task 2 fera vraiment Gemini Pro review
du diff complet.
"""
from dataclasses import dataclass, field
from typing import Optional

from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext


@dataclass
class ReviewResult:
    """Output structuré du Stage8Review (stub Plan 5C)."""

    approved: bool = True
    blockers: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class Stage8Review(Stage):
    """Stub minimal pour Plan 5C (Plan 5D étendra)."""

    name = "review"

    def _llm_for_stage(self) -> Optional[str]:
        # Plan 5D : Gemini Pro (1M ctx pour review du diff complet).
        return None

    async def _execute(self, ctx: PipelineContext) -> ReviewResult:
        # Stub : approved=True systématiquement.
        return ReviewResult(approved=True, blockers=[], suggestions=[])
