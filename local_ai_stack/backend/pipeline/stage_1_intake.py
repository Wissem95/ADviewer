"""Stage 1 — INTAKE (Plan 5A Task 8).

Validation de non-ambiguïté avant les étapes coûteuses. Appelle Gemini Flash
pour reformuler le prompt en impératif clair, extraire les fichiers cibles
probables, les verbes d'action, et détecter si une clarification user est
nécessaire avant de continuer.

Si le LLM remonte ``needs_clarification=true``, on lève
``ClarificationNeeded`` qui sera capturée par Stage.run et transformée en
``StageResult(success=False)``. Le Pipeline orchestrator détectera l'erreur,
renverra les questions à l'UI, et stoppera proprement le pipeline avant
d'engager le moindre coût supplémentaire.
"""
import json
import re
from pathlib import Path
from typing import Optional

from backend.models import LLMRole
from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext


_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_PROMPT_FILE = _PROMPTS_DIR / "stage_1_intake.md"


class ClarificationNeeded(Exception):
    """Levée par Stage1 si le LLM juge le prompt trop ambigu pour continuer.

    L'orchestrator récupère les ``questions`` pour les remonter à l'UI via
    l'event WS ``pipeline_user_decision_needed`` (Plan 5C).
    """

    def __init__(self, questions: list[str], prompt_cleaned: str = ""):
        self.questions = list(questions)
        self.prompt_cleaned = prompt_cleaned
        super().__init__(
            "clarification needed: " + " | ".join(questions[:3])
        )


class Stage1Intake(Stage):
    """Validation et reformulation non-ambiguë du prompt utilisateur."""

    name = "intake"

    def _llm_for_stage(self) -> Optional[str]:
        return "gemini/gemini-2.5-flash"

    async def _execute(self, ctx: PipelineContext) -> dict:
        system_prompt = self._load_system_prompt()
        user_msg = f"PROMPT UTILISATEUR:\n{ctx.prompt}\n\nVALIDE."

        raw = await self.llm.call_with_fallback(
            role=LLMRole.ROUTING,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            timeout=10,
        )

        data = self._parse_json(raw)

        if data.get("needs_clarification"):
            raise ClarificationNeeded(
                questions=data.get("clarification_questions", []),
                prompt_cleaned=data.get("prompt_cleaned", ctx.prompt),
            )

        return data

    # ── Internals ────────────────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        if _PROMPT_FILE.exists():
            return _PROMPT_FILE.read_text(encoding="utf-8")
        return (
            'Valide le prompt en JSON : {"prompt_cleaned": "...", '
            '"target_files_hint": [], "action_verbs": [], '
            '"needs_clarification": bool, "clarification_questions": []}. '
            "Uniquement le JSON."
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
