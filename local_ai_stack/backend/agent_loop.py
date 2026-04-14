"""Agent Loop universel — 5 étapes pour toute tâche LLM.

PLAN    → LLM liste ce qu'il va faire (pas de code encore)
VERIFY  → Orchestrateur vérifie fichiers, locks, do_not_touch
EXECUTE → Un fichier à la fois, orchestrateur écrit physiquement
CHECK   → Lint (ruff Python / eslint JS/TS) — 3 retries max (Niveau 1)
CONFIRM → Diff présenté à l'UI, roadmap mise à jour

Niveau 1 (ici) : retry interne sur erreur lint, 3 tentatives max.
Niveau 2 (Plan 4 ProjectMode) : retry CI complet — ne jamais cascader.

Correction C6 : les locks sont libérés avant retry pour permettre ré-acquisition.
"""
import asyncio
import json
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

from backend.models import LLMRole, RoutingDecision
from backend.llm_manager import LLMManager
from backend.file_lock import FileLock
from backend.ws_streamer import WSStreamer


class AgentLoopError(Exception):
    """Erreur non récupérable après MAX_RETRIES tentatives."""

    def __init__(self, message: str, step: str, attempts: int):
        super().__init__(message)
        self.step = step
        self.attempts = attempts


@dataclass
class PlanStep:
    """Un pas du plan LLM."""
    description: str
    files: list[str]
    action: str  # "read" | "write" | "bash" | "git_diff"


@dataclass
class AgentResult:
    """Résultat d'une exécution agent loop réussie."""
    content: str
    files_modified: list[str]
    tokens: int
    attempts: int  # 1, 2 ou 3


class AgentLoop:
    """Agent loop universel — une instance par tâche, jetée après.

    Usage:
        loop = AgentLoop(llm_manager, file_lock, ws_streamer, decision, context)
        result = await loop.run(task_prompt)
    """
    MAX_RETRIES = 3

    def __init__(
        self,
        llm_manager: LLMManager,
        file_lock: FileLock,
        ws_streamer: WSStreamer,
        decision: RoutingDecision,
        context: str,
    ):
        self.llm = llm_manager
        self.file_lock = file_lock
        self.ws = ws_streamer
        self.decision = decision
        self.context = context
        self._locked_files: list[str] = []

    async def run(self, task: str) -> AgentResult:
        """Exécute les 5 étapes avec retry intelligent sur erreur CHECK."""
        try:
            # Étape 1 — PLAN
            await self.ws.emit_step("PLAN", self.decision.llm)
            plan = await self._step_plan(task)

            # Étape 2 — VERIFY
            await self.ws.emit_step("VERIFY", self.decision.llm)
            self._step_verify(plan)

            # Étape 3 — EXECUTE
            await self.ws.emit_step("EXECUTE", self.decision.llm)
            content, files_modified, tokens = await self._step_execute(task, plan)

            last_attempt = 1
            # Étape 4 — CHECK avec retry
            for attempt in range(1, self.MAX_RETRIES + 1):
                last_attempt = attempt
                await self.ws.emit_step("CHECK", self.decision.llm, attempt=attempt)
                errors = self._step_check(files_modified)

                if not errors:
                    break

                if attempt == self.MAX_RETRIES:
                    raise AgentLoopError(
                        message=f"Lint échoue après {self.MAX_RETRIES} tentatives : {errors[0][:200]}",
                        step="CHECK",
                        attempts=attempt,
                    )

                # Correction C6 : libérer les locks avant retry
                await self._release_all_locks()

                retry_task = (
                    f"{task}\n\n"
                    f"ERREUR LINT (tentative {attempt}) — corrige ces erreurs :\n"
                    + "\n".join(errors[:3])
                )
                content, files_modified, tokens = await self._step_execute(retry_task, plan)

            # Étape 5 — CONFIRM
            await self.ws.emit_step("CONFIRM", self.decision.llm)
            self._step_confirm(files_modified)

            return AgentResult(
                content=content,
                files_modified=files_modified,
                tokens=tokens,
                attempts=last_attempt,
            )
        finally:
            # Toujours libérer les locks à la fin (succès ou erreur)
            await self._release_all_locks()

    # ── Étapes internes ──────────────────────────────────────────────────────

    async def _step_plan(self, task: str) -> list[PlanStep]:
        """LLM liste ses intentions — pas de code."""
        prompt = (
            f"TÂCHE : {task}\n\n"
            f"CONTEXTE :\n{self.context}\n\n"
            "Liste EXACTEMENT ce que tu vas faire.\n"
            "Format JSON strict :\n"
            '{"steps": [{"description": "...", "files": [...], "action": "write|read|bash"}]}\n'
            "Ne génère PAS de code dans cette réponse."
        )
        raw = await self.llm.call_with_fallback(
            role=self.decision.role,
            messages=[{"role": "user", "content": prompt}],
        )
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return [PlanStep(**s) for s in data.get("steps", [])]
            except (json.JSONDecodeError, TypeError):
                pass
        # Fallback : plan minimal si JSON mal formé
        return [PlanStep(description=task, files=[], action="write")]

    def _step_verify(self, plan: list[PlanStep]) -> None:
        """Vérifie que les fichiers cibles ne sont pas verrouillés par un autre LLM."""
        for step in plan:
            for filepath in step.files:
                holder = self.file_lock.who_has(filepath)
                if holder and holder != self.decision.llm:
                    raise AgentLoopError(
                        message=f"{filepath} est verrouillé par {holder}",
                        step="VERIFY",
                        attempts=0,
                    )

    async def _step_execute(
        self, task: str, plan: list[PlanStep]
    ) -> tuple[str, list[str], int]:
        """Génère le code et verrouille les fichiers cibles.

        L'orchestrateur (Plan 2 T5) sera responsable d'écrire physiquement les fichiers.
        """
        files_modified = []
        prompt = (
            f"TÂCHE : {task}\n\n"
            f"CONTEXTE :\n{self.context}\n\n"
            "Génère le code complet pour chaque fichier à modifier.\n"
            "Inclus le chemin du fichier en commentaire au début de chaque bloc."
        )
        response = await self.llm.call_with_fallback(
            role=self.decision.role,
            messages=[{"role": "user", "content": prompt}],
        )
        # Verrouiller les fichiers write du plan
        for step in plan:
            if step.action == "write":
                for filepath in step.files:
                    acquired = await self.file_lock.acquire(filepath, self.decision.llm)
                    if acquired and filepath not in self._locked_files:
                        self._locked_files.append(filepath)
                        files_modified.append(filepath)
        return response, files_modified, 0  # tokens = 0 (litellm n'expose pas toujours)

    def _step_check(self, files_modified: list[str]) -> list[str]:
        """Lint : ruff pour .py, eslint pour .ts/.tsx/.js/.jsx. Retourne les erreurs.

        Timeout 30s par fichier pour éviter les blocages.
        """
        errors = []
        for filepath in files_modified:
            if filepath.endswith(".py"):
                try:
                    result = subprocess.run(
                        ["ruff", "check", filepath, "--output-format=text"],
                        capture_output=True, text=True, timeout=30,
                    )
                    if result.returncode != 0:
                        errors.append(result.stdout[:500])
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
            elif filepath.endswith((".ts", ".tsx", ".js", ".jsx")):
                try:
                    result = subprocess.run(
                        ["npx", "eslint", filepath, "--format=compact"],
                        capture_output=True, text=True, timeout=30,
                    )
                    if result.returncode != 0:
                        errors.append(result.stdout[:500])
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
        return errors

    def _step_confirm(self, files_modified: list[str]) -> str:
        """Génère un git diff pour les fichiers modifiés (affiché dans l'UI)."""
        diffs = []
        for filepath in files_modified:
            try:
                result = subprocess.run(
                    ["git", "diff", filepath],
                    capture_output=True, text=True, timeout=10,
                )
                if result.stdout:
                    diffs.append(result.stdout[:2000])
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        return "\n".join(diffs)

    async def _release_all_locks(self) -> None:
        """Libère tous les verrous acquis par cette instance."""
        for filepath in list(self._locked_files):
            await self.file_lock.release(filepath, self.decision.llm)
        self._locked_files.clear()
