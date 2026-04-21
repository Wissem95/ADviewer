"""Stage 0 — ESTIMATE (Plan 5A Task 7).

Première étape du pipeline : appelle Gemini Flash pour classifier le prompt
(simple / medium / complex), puis enrichit avec ``estimate_pipeline_cost``
pour produire le payload ``pipeline_estimate`` alimentant le modal UI de
confirmation avant lancement.

Coût Flash : ~$0.0001-$0.0002 par classification. Temps < 1s en général.
"""
import json
import re
from pathlib import Path
from typing import Optional

from backend.cost_estimator import estimate_pipeline_cost
from backend.models import LLMRole
from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext


_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_PROMPT_FILE = _PROMPTS_DIR / "stage_0_estimate.md"


class Stage0Estimate(Stage):
    """Classification + estimation coût par appel à Gemini Flash."""

    name = "estimate"

    def _llm_for_stage(self) -> Optional[str]:
        return "gemini/gemini-2.5-flash"

    async def _execute(self, ctx: PipelineContext) -> dict:
        system_prompt = self._load_system_prompt()
        user_msg = f"PROMPT UTILISATEUR:\n{ctx.prompt}\n\nCLASSIFIE."

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
        cost_breakdown = estimate_pipeline_cost(
            prompt_text=ctx.prompt,
            mode=data["classification"],
            files_hint=data.get("files_hint", []),
        )
        # Merge : la classification du LLM prime, le cost_breakdown enrichit.
        return {**data, **cost_breakdown}

    # ── Internals ────────────────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        if _PROMPT_FILE.exists():
            return _PROMPT_FILE.read_text(encoding="utf-8")
        # Fallback minimal si le MD est absent (ne doit pas arriver en prod).
        return (
            'Classifie le prompt en JSON : {"classification": '
            '"simple"|"medium"|"complex", "reason": "...", "files_hint": [], '
            '"confidence": "low"|"medium"|"high", "ambiguities": []}. '
            "Retourne UNIQUEMENT le JSON."
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Extrait le premier objet JSON trouvé dans ``raw``.

        Certains LLMs encapsulent leur JSON dans un bloc ``` ou ajoutent du
        texte avant/après. On extrait la première accolade ouvrante et sa
        fermeture correspondante via regex greedy.
        """
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"Pas de JSON dans la réponse LLM: {raw[:200]!r}")
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON invalide: {e}: {match.group()[:200]!r}")
