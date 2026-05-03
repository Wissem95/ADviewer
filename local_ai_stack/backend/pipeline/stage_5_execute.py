"""Stage 5 — EXECUTE (Plan 5A Task 10).

L'étape qui modifie réellement les fichiers. Préambule : ``git stash`` du
working dir pour permettre le rollback automatique en cas de problème
détecté à Stage7Verify (lint/tests rouges après 3 retries).

Boucle tool-calling avec TOOLS_SCHEMA_WRITE. À chaque itération :
- Si ``tool_calls`` vide → message final, on retourne ExecuteResult.
- Sinon → exécute chaque tool via execute_tool, track les fichiers modifiés.

Sur exception non-tool, rollback immédiat via ``git_stash_pop`` puis re-raise.

Note securité : on utilise ``asyncio.create_subprocess_exec`` (pas shell) avec
arguments en liste. Pas d'interpolation utilisateur dans la commande.
"""
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from litellm import acompletion

from backend.pipeline.base import Stage
from backend.pipeline.types import PipelineContext
from backend.tools.registry import TOOLS_SCHEMA_WRITE, execute_tool


_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_PROMPT_FILE = _PROMPTS_DIR / "stage_5_execute.md"

_MAX_ITERATIONS = 20
_TOOL_RESULT_TRUNCATE = 2000


@dataclass
class ExecuteResult:
    """Output structuré du Stage5Execute."""

    files_modified: list[str] = field(default_factory=list)
    stash_ref: str = ""
    summary: str = ""
    iterations_used: int = 0
    tool_calls_log: list[dict] = field(default_factory=list)


# ── Helpers git stash (subprocess argv-list, pas de shell) ──────────────────

async def git_stash_save(workspace_root: Path, label: str) -> str:
    """Stash le working dir + untracked. Retourne ``stash@{0}`` si stash créé,
    chaîne vide si rien à stash."""
    proc = await asyncio.create_subprocess_exec(
        "git", "stash", "push", "-u", "-m", label,
        cwd=str(workspace_root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    out = stdout.decode("utf-8", errors="ignore")
    if "Saved working directory" in out or "Saved working tree" in out:
        return "stash@{0}"
    return ""


async def git_stash_pop(workspace_root: Path, stash_ref: str) -> bool:
    """Pop le stash référencé. Retourne True si succès, False sinon.

    Si stash_ref est vide (rien stashé), retourne True (no-op).
    """
    if not stash_ref:
        return True
    proc = await asyncio.create_subprocess_exec(
        "git", "stash", "pop", "--quiet",
        cwd=str(workspace_root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    return proc.returncode == 0


# ── Stage ────────────────────────────────────────────────────────────────────

class Stage5Execute(Stage):
    """Boucle tool-calling write avec git stash + rollback automatique."""

    name = "execute"

    def __init__(self, llm_manager, ws_streamer):
        super().__init__(llm_manager, ws_streamer)
        self.file_lock = None

    def _llm_for_stage(self) -> Optional[str]:
        return "minimax/minimax-m2.5"

    async def _execute(self, ctx: PipelineContext) -> ExecuteResult:
        stash_label = f"pipeline_pre_execute_{ctx.session_id}"
        stash_ref = await git_stash_save(ctx.workspace_root, stash_label)

        try:
            return await self._run_tool_loop(ctx, stash_ref)
        except Exception:
            await git_stash_pop(ctx.workspace_root, stash_ref)
            raise

    async def _run_tool_loop(
        self, ctx: PipelineContext, stash_ref: str
    ) -> ExecuteResult:
        system_prompt = self._load_system_prompt()
        plan_hint = self._plan_hint(ctx)

        retry_hint = self._retry_hint(ctx)
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"PROMPT UTILISATEUR:\n{ctx.prompt}\n\n"
                    f"{plan_hint}\n\n"
                    f"{retry_hint}"
                    "Applique les changements via les tools write."
                ),
            },
        ]

        files_modified: set[str] = set()
        tool_log: list[dict] = []
        llm_id = self._llm_for_stage()

        for iteration in range(_MAX_ITERATIONS):
            response = await acompletion(
                model=llm_id,
                messages=messages,
                tools=TOOLS_SCHEMA_WRITE,
                temperature=0.0,
                timeout=60,
            )
            msg = response.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None) or []

            if not tool_calls:
                return ExecuteResult(
                    files_modified=sorted(files_modified),
                    stash_ref=stash_ref,
                    summary=msg.content or "",
                    iterations_used=iteration,
                    tool_calls_log=tool_log,
                )

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

                if result.get("success"):
                    path = args.get("path")
                    if tool_name in ("edit_file", "create_file", "patch_file") and path:
                        files_modified.add(path)
                    elif tool_name == "delete_file" and path:
                        files_modified.discard(path)

                tool_log.append({"tool": tool_name, "args": args, "success": result.get("success")})

                content_str = json.dumps(result)[:_TOOL_RESULT_TRUNCATE]
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": content_str,
                })

        raise RuntimeError(
            f"EXECUTE: budget de {_MAX_ITERATIONS} tool_calls épuisé"
        )

    # ── Internals ────────────────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        if _PROMPT_FILE.exists():
            return _PROMPT_FILE.read_text(encoding="utf-8")
        return (
            "Applique les changements via tools write. Un fichier à la fois. "
            "Termine par un message texte de récap."
        )

    @staticmethod
    def _plan_hint(ctx: PipelineContext) -> str:
        """Récupère le plan depuis Stage4 si disponible (Plan 5C)."""
        plan = ctx.get_stage_output("plan")
        if plan is None:
            ground = ctx.get_stage_output("ground")
            if ground is not None and getattr(ground, "summary", ""):
                return f"GROUNDED_CONTEXT (résumé):\n{ground.summary[:1500]}"
            return "Plan non fourni — exécute selon le prompt utilisateur."
        return f"PLAN:\n{plan}"

    @staticmethod
    def _retry_hint(ctx: PipelineContext) -> str:
        """Si on est en retry, injecte les erreurs VERIFY précédentes."""
        rc = getattr(ctx, "retry_context", None)
        if not rc:
            return ""
        attempt = rc.get("attempt", 2)
        prev = rc.get("previous_verify_errors", [])
        formatted = "\n".join(f"- {e}" for e in prev[:30])
        return (
            f"RETRY (tentative #{attempt}/3) — VERIFY a échoué à la passe "
            f"précédente avec les erreurs suivantes :\n{formatted}\n\n"
            "Corrige le code pour que ces erreurs disparaissent.\n\n"
        )
