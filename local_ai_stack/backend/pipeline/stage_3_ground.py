"""Stage 3 — GROUND (Plan 5A Task 9).

Première étape avec tool-calling. MiniMax reçoit TOOLS_SCHEMA_READ et
boucle jusqu'à ce qu'il ait assez de contexte (ou que le budget de 20
tool_calls soit épuisé).

Chaque tool_call → execute_tool → result encapsulé dans message role="tool"
réinjecté pour la prochaine itération. Quand le LLM arrête les tool_calls
et envoie un message texte, on extrait :
- ``files_read`` : dict path → contenu (depuis les read_file).
- ``greps_performed`` : liste {pattern, results}.
- ``summary`` : le message final du LLM (recap GROUNDED_CONTEXT).

Garantie : le stage ne CRASHE jamais sur un tool_call qui échoue. Les
erreurs (path hors workspace, fichier absent, tool inconnu) sont injectées
dans le contexte LLM pour qu'il corrige son approche.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from litellm import acompletion

from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext
from backend.tools.registry import TOOLS_SCHEMA_READ, execute_tool


_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_PROMPT_FILE = _PROMPTS_DIR / "stage_3_ground.md"

_MAX_ITERATIONS = 20
_TOOL_RESULT_TRUNCATE = 2000  # chars max par tool_result réinjecté


@dataclass
class GroundedContext:
    """Output structuré du Stage3Ground."""

    files_read: dict[str, str] = field(default_factory=dict)
    greps_performed: list[dict] = field(default_factory=list)
    summary: str = ""
    iterations_used: int = 0


class Stage3Ground(Stage):
    """Boucle tool-calling read-only pour ancrer factuellement le contexte."""

    name = "ground"

    def __init__(self, llm_manager, ws_streamer):
        super().__init__(llm_manager, ws_streamer)
        # Injecté par le Pipeline orchestrator avant run().
        self.file_lock = None

    def _llm_for_stage(self) -> Optional[str]:
        return "minimax/minimax-m2.5"

    async def _execute(self, ctx: PipelineContext) -> GroundedContext:
        system_prompt = self._load_system_prompt()
        intake_summary = self._intake_hint(ctx)
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"PROMPT UTILISATEUR:\n{ctx.prompt}\n\n"
                    f"{intake_summary}\n\n"
                    "GROUND-toi factuellement avant que les étapes suivantes décident."
                ),
            },
        ]

        files_read: dict[str, str] = {}
        greps: list[dict] = []
        llm_id = self._llm_for_stage()

        for iteration in range(_MAX_ITERATIONS):
            response = await acompletion(
                model=llm_id,
                messages=messages,
                tools=TOOLS_SCHEMA_READ,
                temperature=0.0,
                timeout=60,
            )
            msg = response.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None) or []

            # Pas de tool_calls → le LLM a fini, on retourne le summary.
            if not tool_calls:
                return GroundedContext(
                    files_read=files_read,
                    greps_performed=greps,
                    summary=msg.content or "",
                    iterations_used=iteration,
                )

            # Append le message assistant (avec ses tool_calls) à l'historique.
            messages.append(msg.model_dump())

            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                result = await execute_tool(
                    tool_name,
                    args,
                    file_lock=self.file_lock,
                    workspace_root=ctx.workspace_root,
                )

                # Tracking par type de tool.
                if tool_name == "read_file" and result.get("success"):
                    files_read[args.get("path", "?")] = result.get("content", "")
                elif tool_name == "grep_codebase" and result.get("success"):
                    greps.append({
                        "pattern": args.get("pattern", ""),
                        "matches": result.get("matches", []),
                    })

                # Réinjection du result au LLM (tronqué).
                content_str = json.dumps(result)[:_TOOL_RESULT_TRUNCATE]
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": content_str,
                })

        # Budget épuisé.
        raise RuntimeError(
            f"GROUND: budget de {_MAX_ITERATIONS} tool_calls épuisé sans message final"
        )

    # ── Internals ────────────────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        if _PROMPT_FILE.exists():
            return _PROMPT_FILE.read_text(encoding="utf-8")
        return (
            "Tu es l'étape GROUND. Lis le code via les tools, cite chaque fait "
            "(file:line), pas d'hypothèse. Termine par un message texte récap."
        )

    @staticmethod
    def _intake_hint(ctx: PipelineContext) -> str:
        """Récupère target_files_hint depuis Stage1Intake si disponible."""
        intake = ctx.get_stage_output("intake")
        if not isinstance(intake, dict):
            return "INTAKE: aucun (mode dégradé)"
        return (
            f"INTAKE:\n"
            f"- prompt_cleaned: {intake.get('prompt_cleaned', ctx.prompt)}\n"
            f"- target_files_hint: {intake.get('target_files_hint', [])}\n"
            f"- action_verbs: {intake.get('action_verbs', [])}"
        )
