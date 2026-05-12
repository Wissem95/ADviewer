"""Stage 2 — CHALLENGE (Plan 5C Task 1).

Avocat du diable. Gemini Pro identifie risks/edge_cases/alternatives avant
que les stages coûteux (GROUND, PLAN, EXECUTE) ne tournent.

Si ``blocking=True`` est remonté, un event WS ``challenge_blocking`` est
émis et l'UI affichera un banner. Le pipeline continue par défaut (c'est
au user de décider via un futur consensus dialog, Plan 5C Task 2).
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.models import LLMRole, WSEvent
from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext


_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_PROMPT_FILE = _PROMPTS_DIR / "stage_2_challenge.md"

_VALID_SEVERITIES = ("minor", "moderate", "critical")


@dataclass
class ChallengeResult:
    """Output structuré du Stage2Challenge."""

    risks: list[str] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    severity: str = "minor"
    blocking: bool = False


class Stage2Challenge(Stage):
    """Identifie angles morts du prompt avant les étapes coûteuses."""

    name = "challenge"

    def _llm_for_stage(self) -> Optional[str]:
        return "gemini/gemini-2.5-pro"

    async def _execute(self, ctx: PipelineContext) -> ChallengeResult:
        system_prompt = self._load_system_prompt()
        intake_hint = self._intake_hint(ctx)

        user_msg = (
            f"PROMPT UTILISATEUR:\n{ctx.prompt}\n\n"
            f"{intake_hint}\n\n"
            "CHALLENGE."
        )

        raw = await self.llm.call_with_fallback(
            role=LLMRole.ANALYSIS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            timeout=20,
        )

        data = self._parse_json(raw)
        result = self._coerce(data)

        # Émet l'event WS challenge_blocking si applicable.
        if result.blocking and self.ws is not None:
            await self.ws.broadcast(WSEvent(
                type="challenge_blocking",
                data={
                    "severity": result.severity,
                    "risks": result.risks[:3],
                },
                session_id=ctx.session_id,
            ))

        return result

    # ── Internals ────────────────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        if _PROMPT_FILE.exists():
            return _PROMPT_FILE.read_text(encoding="utf-8")
        return (
            "Identifie 3 risks, 3 edge_cases, 1-2 alternatives, severity, "
            "blocking. JSON strict uniquement."
        )

    @staticmethod
    def _intake_hint(ctx: PipelineContext) -> str:
        intake = ctx.get_stage_output("intake")
        if not isinstance(intake, dict):
            return "INTAKE: aucun (mode dégradé)"
        return (
            f"INTAKE:\n"
            f"- prompt_cleaned: {intake.get('prompt_cleaned', ctx.prompt)}\n"
            f"- target_files_hint: {intake.get('target_files_hint', [])}\n"
            f"- action_verbs: {intake.get('action_verbs', [])}"
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"Pas de JSON dans la réponse LLM: {raw[:200]!r}")
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON invalide: {e}: {match.group()[:200]!r}")

    @staticmethod
    def _coerce(data: dict) -> ChallengeResult:
        severity = data.get("severity", "minor")
        if severity not in _VALID_SEVERITIES:
            severity = "minor"
        return ChallengeResult(
            risks=list(data.get("risks", []) or [])[:5],
            edge_cases=list(data.get("edge_cases", []) or [])[:5],
            alternatives=list(data.get("alternatives", []) or [])[:3],
            severity=severity,
            blocking=bool(data.get("blocking", False)),
        )
