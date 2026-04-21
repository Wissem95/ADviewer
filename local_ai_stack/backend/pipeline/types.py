"""Types partagés du pipeline (Plan 5A Task 6).

Aligné sur la spec §2 et §3 : PipelineMode détermine quelles étapes sont
activées, PipelineContext voyage entre les stages, StageResult capture
output/duration/cost par étape, PipelineResult agrège le tout.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class PipelineMode(str, Enum):
    """Trois modes de pipeline (cf. spec §2.3).

    - SIMPLE  : 0/1/3/5/7 (~3 LLM calls, ~$0.002).
    - MEDIUM  : +2 étapes (self-check + review), ~5 calls, ~$0.02.
    - COMPLEX : tout (challenge + consensus plan + consensus review),
      ~9-10 calls, ~$0.08-0.15.
    """

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class PipelineContext:
    """Contexte voyageant entre toutes les étapes du pipeline.

    Rempli incrémentalement par chaque stage : après Stage3Ground, le champ
    ``stage_results["ground"]`` contient le GroundedContext, etc. Les stages
    suivants lisent les résultats précédents depuis ``stage_results``.
    """

    prompt: str
    workspace_root: Path
    session_id: str
    mode: PipelineMode = PipelineMode.SIMPLE
    mention: Optional[str] = None
    stage_results: dict[str, "StageResult"] = field(default_factory=dict)
    total_cost_usd: float = 0.0
    total_tokens_in: int = 0
    total_tokens_out: int = 0

    def get_stage_output(self, stage_name: str) -> Any:
        """Raccourci : retourne le ``output`` d'un stage précédent, ou None."""
        sr = self.stage_results.get(stage_name)
        return sr.output if sr else None


@dataclass
class StageResult:
    """Résultat d'une étape, émis via event WS ``stage_complete``."""

    stage_name: str
    duration_ms: int
    success: bool = True
    llm_used: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    output: Any = None  # type spécifique selon le stage
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """Agrégat final retourné au caller (orchestrator → UI)."""

    success: bool
    files_modified: list[str] = field(default_factory=list)
    stages: list[StageResult] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    rollback_performed: bool = False
    error: Optional[str] = None
