"""Stage 4a — PLAN (Plan 5C Task 3).

Architecte planificateur. DeepSeek R1 produit un plan structuré ancré dans
les facts du GROUNDED_CONTEXT et qui intègre les mitigations CHALLENGE le
cas échéant.

Output JSON strict → ``PlanResult`` dataclass exposée comme
``ctx.stage_results["plan"].output``. Stage5Execute lira ce plan pour
exécuter les changes.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.models import LLMRole
from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext


_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_PROMPT_FILE = _PROMPTS_DIR / "stage_4a_plan.md"

_VALID_OPS = ("edit", "create", "patch", "delete")
_VALID_RISKS = ("low", "medium", "high")


@dataclass
class PlanChange:
    """Un change précis du plan."""

    file: str
    operation: str  # edit | create | patch | delete
    description: str
    intended_diff_summary: str = ""


@dataclass
class PlanResult:
    """Output structuré du Stage4aPlan."""

    changes: list[PlanChange] = field(default_factory=list)
    tests_to_run: list[str] = field(default_factory=list)
    rollback_strategy: str = ""
    rationale: str = ""
    estimated_risk: str = "low"
    complexity_confirm: int = 0


class Stage4aPlan(Stage):
    """Planification architecturale par DeepSeek R1."""

    name = "plan"

    def _llm_for_stage(self) -> Optional[str]:
        return "deepseek/deepseek-r1"

    async def _execute(self, ctx: PipelineContext) -> PlanResult:
        system_prompt = self._load_system_prompt()
        user_msg = self._build_user_message(ctx)

        raw = await self.llm.call_with_fallback(
            role=LLMRole.ARCHITECTURE,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            timeout=60,
        )

        data = self._parse_json(raw)
        return self._coerce(data)

    # ── Internals ────────────────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        if _PROMPT_FILE.exists():
            return _PROMPT_FILE.read_text(encoding="utf-8")
        return (
            "Produire un plan JSON : changes[], tests_to_run[], "
            "rollback_strategy, rationale, estimated_risk, complexity_confirm."
        )

    @staticmethod
    def _build_user_message(ctx: PipelineContext) -> str:
        parts: list[str] = [f"PROMPT UTILISATEUR:\n{ctx.prompt}"]

        intake = ctx.get_stage_output("intake")
        if isinstance(intake, dict):
            parts.append(
                f"INTAKE:\n"
                f"- prompt_cleaned: {intake.get('prompt_cleaned', ctx.prompt)}\n"
                f"- target_files_hint: {intake.get('target_files_hint', [])}\n"
                f"- action_verbs: {intake.get('action_verbs', [])}"
            )

        challenge = ctx.get_stage_output("challenge")
        if challenge is not None:
            risks = getattr(challenge, "risks", [])[:5]
            edge_cases = getattr(challenge, "edge_cases", [])[:5]
            severity = getattr(challenge, "severity", "minor")
            parts.append(
                f"CHALLENGE (severity={severity}):\n"
                f"- risks: {risks}\n"
                f"- edge_cases: {edge_cases}"
            )

        ground = ctx.get_stage_output("ground")
        if ground is not None:
            files_read = list(getattr(ground, "files_read", {}) or {})
            summary = getattr(ground, "summary", "")[:2000]
            parts.append(
                f"GROUNDED_CONTEXT:\n"
                f"- files_read: {files_read}\n"
                f"- summary: {summary}"
            )

        parts.append("PRODUIS LE PLAN JSON.")
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
    def _coerce(data: dict) -> PlanResult:
        raw_changes = data.get("changes", []) or []
        changes: list[PlanChange] = []
        for c in raw_changes:
            if not isinstance(c, dict):
                continue
            op = c.get("operation", "")
            if op not in _VALID_OPS:
                continue
            file = c.get("file", "")
            if not file:
                continue
            changes.append(
                PlanChange(
                    file=str(file),
                    operation=op,
                    description=str(c.get("description", ""))[:400],
                    intended_diff_summary=str(c.get("intended_diff_summary", ""))[:300],
                )
            )

        risk = data.get("estimated_risk", "low")
        if risk not in _VALID_RISKS:
            risk = "low"

        try:
            complexity_confirm = int(data.get("complexity_confirm", 0))
        except (ValueError, TypeError):
            complexity_confirm = 0
        complexity_confirm = max(0, min(10, complexity_confirm))

        return PlanResult(
            changes=changes,
            tests_to_run=[
                str(t) for t in (data.get("tests_to_run", []) or []) if isinstance(t, str)
            ][:30],
            rollback_strategy=str(data.get("rollback_strategy", ""))[:300],
            rationale=str(data.get("rationale", ""))[:1500],
            estimated_risk=risk,
            complexity_confirm=complexity_confirm,
        )
