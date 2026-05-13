"""Stage 4b — PLAN REVIEW (Plan 5C Task 5).

Reviewer indépendant du plan R1 par Gemini Pro. Verdict : approve / revise /
reject. Si revise, fournit un ``merged_plan`` ajusté qui sera utilisé en
priorité par Stage5Execute (cf. mécanisme consensus en Plan 5C Task 6).

Le consensus 2/2 est implémenté en Task 6 — ici on produit juste l'output
du reviewer.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.models import LLMRole
from backend.pipeline.base import Stage
from backend.pipeline.stage_4a_plan import PlanResult, Stage4aPlan
from backend.pipeline.types import PipelineContext


_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_PROMPT_FILE = _PROMPTS_DIR / "stage_4b_plan_review.md"

_VALID_VERDICTS = ("approve", "revise", "reject")


@dataclass
class PlanReview:
    """Output structuré du Stage4bPlanReview."""

    verdict: str = "approve"  # approve | revise | reject
    concerns: list[str] = field(default_factory=list)
    suggested_changes: list[str] = field(default_factory=list)
    merged_plan: Optional[PlanResult] = None


class Stage4bPlanReview(Stage):
    """Gemini Pro review du plan R1, retourne verdict + éventuel merged_plan."""

    name = "plan_review"

    def _llm_for_stage(self) -> Optional[str]:
        return "gemini/gemini-2.5-pro"

    async def _execute(self, ctx: PipelineContext) -> PlanReview:
        system_prompt = self._load_system_prompt()
        user_msg = self._build_user_message(ctx)

        raw = await self.llm.call_with_fallback(
            role=LLMRole.ANALYSIS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            timeout=60,
        )

        data = self._parse_json(raw)
        return self._coerce(data)

    # ── Internals ────────────────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        if _PROMPT_FILE.exists():
            return _PROMPT_FILE.read_text(encoding="utf-8")
        return (
            "Review le plan R1. JSON: verdict approve|revise|reject, "
            "concerns, suggested_changes, merged_plan (si revise)."
        )

    @staticmethod
    def _build_user_message(ctx: PipelineContext) -> str:
        parts: list[str] = [f"PROMPT UTILISATEUR:\n{ctx.prompt}"]

        intake = ctx.get_stage_output("intake")
        if isinstance(intake, dict):
            parts.append(
                f"INTAKE:\n"
                f"- prompt_cleaned: {intake.get('prompt_cleaned', ctx.prompt)}\n"
                f"- target_files_hint: {intake.get('target_files_hint', [])}"
            )

        challenge = ctx.get_stage_output("challenge")
        if challenge is not None:
            risks = getattr(challenge, "risks", [])[:5]
            severity = getattr(challenge, "severity", "minor")
            parts.append(f"CHALLENGE (severity={severity}): {risks}")

        ground = ctx.get_stage_output("ground")
        if ground is not None:
            summary = getattr(ground, "summary", "")[:1500]
            files_read = list(getattr(ground, "files_read", {}) or {})
            parts.append(
                f"GROUNDED_CONTEXT:\n"
                f"- files_read: {files_read}\n"
                f"- summary: {summary}"
            )

        plan = ctx.get_stage_output("plan")
        if plan is not None:
            changes_json = json.dumps(
                [
                    {
                        "file": c.file,
                        "operation": c.operation,
                        "description": c.description,
                    }
                    for c in getattr(plan, "changes", [])
                ],
                ensure_ascii=False,
            )
            parts.append(
                f"PLAN R1:\n"
                f"- changes: {changes_json}\n"
                f"- tests_to_run: {getattr(plan, 'tests_to_run', [])}\n"
                f"- estimated_risk: {getattr(plan, 'estimated_risk', '?')}\n"
                f"- rationale: {getattr(plan, 'rationale', '')[:800]}"
            )

        parts.append("PRODUIS LE VERDICT JSON.")
        return "\n\n".join(parts)

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
    def _coerce(data: dict) -> PlanReview:
        verdict = data.get("verdict", "approve")
        if verdict not in _VALID_VERDICTS:
            verdict = "approve"

        merged_raw = data.get("merged_plan")
        merged: Optional[PlanResult] = None
        if verdict == "revise" and isinstance(merged_raw, dict):
            merged = Stage4aPlan._coerce(merged_raw)

        return PlanReview(
            verdict=verdict,
            concerns=[
                str(c) for c in (data.get("concerns", []) or []) if isinstance(c, str)
            ][:10],
            suggested_changes=[
                str(s) for s in (data.get("suggested_changes", []) or []) if isinstance(s, str)
            ][:10],
            merged_plan=merged,
        )
