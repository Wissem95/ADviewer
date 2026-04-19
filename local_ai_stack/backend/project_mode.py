"""
Mode Projet — circuit fermé CdC → Sprints → GitHub → CI → Auto-merge.

Flux :
  1. generate_cdc(description)         → CdC validé par DeepSeek R1
  2. generate_sprints(cdc)             → Liste de SprintPlan avec tickets
  3. create_github_structure(cdc, sprints) → Issues + Milestones + Actions + ProjectRoadmap
  4. execute_ticket(task, roadmap)     → Branch + Agent Loop + Commit + Push + PR

Retry CI (Niveau 2) : stub MVP pour l'instant — voir I11.
Ne pas confondre avec le retry Niveau 1 (lint, interne à agent_loop.py).
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from backend.git_service import GitService
from backend.github_service import GitHubService
from backend.llm_manager import LLMManager
from backend.models import LLMRole
from backend.roadmap import ProjectRoadmap, SubTask, Task
from backend.ws_streamer import WSStreamer


# ── Structures de données du Mode Projet ─────────────────────────────────────


@dataclass
class FeatureSpec:
    id: str
    title: str
    description: str
    complexity: int


@dataclass
class CdC:
    project_name: str
    title: str
    context: str
    objectives: list[str]
    features_must: list[FeatureSpec]
    features_should: list[FeatureSpec]
    features_could: list[FeatureSpec]
    stack: dict
    constraints: list[str]
    success_criteria: list[str]
    estimated_sprints: int


@dataclass
class TicketPlan:
    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    subtasks: list[dict]
    tests_required: list[str]
    blocked_by: list[str]
    estimated_complexity: int


@dataclass
class SprintPlan:
    sprint_name: str
    tickets: list[TicketPlan]


# ── Mots-clés de détection Mode Projet ───────────────────────────────────────

PROJECT_KEYWORDS = [
    r"crée une app",
    r"créer une app",
    r"je veux construire",
    r"nouveau projet",
    r"génère le cdc",
    r"génère le cahier",
    r"build.*app",
    r"new.*project",
    r"start.*project",
]


# ── ProjectMode ───────────────────────────────────────────────────────────────


class ProjectMode:
    """Orchestrateur du Mode Projet. Utilisé par l'Orchestrateur principal."""

    # Niveau 2 — retries CI (pas les retries lint d'agent_loop).
    MAX_CI_RETRIES = 3
    # Polling par défaut du CI GitHub Actions (secondes).
    CI_POLL_INTERVAL = 30
    CI_TIMEOUT = 600  # 10 minutes max par PR

    def __init__(
        self,
        llm_manager: LLMManager,
        ws_streamer: WSStreamer,
        github_service: GitHubService,
        git_service: GitService,
    ):
        self.llm = llm_manager
        self.ws = ws_streamer
        self.github = github_service
        self.git = git_service

    def is_project_request(self, prompt: str) -> bool:
        """Détecte si un prompt déclenche le Mode Projet."""
        prompt_lower = prompt.lower()
        return any(re.search(kw, prompt_lower) for kw in PROJECT_KEYWORDS)

    # ── Étape 1 : Génération CdC ─────────────────────────────────────────────

    async def generate_cdc(self, description: str) -> CdC:
        """Génère un CdC structuré depuis la description utilisateur via DeepSeek R1."""
        prompt_path = Path(__file__).parent / "prompts" / "cdc_generation.md"
        system_prompt = prompt_path.read_text() if prompt_path.exists() else ""

        await self.ws.emit_step("CDC_GENERATION", "deepseek/deepseek-r1")
        raw_cdc = await self.llm.call_with_fallback(
            role=LLMRole.ARCHITECTURE,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Description du projet :\n{description}"},
            ],
        )
        return self._parse_cdc(raw_cdc)

    def _parse_cdc(self, raw: str) -> CdC:
        """Parse le JSON retourné par le LLM en CdC structuré."""
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("CdC JSON invalide — pas de JSON trouvé dans la réponse LLM")
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"CdC JSON invalide — erreur de parsing: {e}") from e

        def parse_features(items: list) -> list[FeatureSpec]:
            return [
                FeatureSpec(
                    id=f["id"],
                    title=f["title"],
                    description=f["description"],
                    complexity=f.get("complexity", 5),
                )
                for f in items
            ]

        features = data.get("features", {})
        return CdC(
            project_name=data["project_name"],
            title=data["title"],
            context=data["context"],
            objectives=data.get("objectives", []),
            features_must=parse_features(features.get("must_have", [])),
            features_should=parse_features(features.get("should_have", [])),
            features_could=parse_features(features.get("could_have", [])),
            stack=data.get("stack", {}),
            constraints=data.get("constraints", []),
            success_criteria=data.get("success_criteria", []),
            estimated_sprints=data.get("estimated_sprints", 2),
        )

    # ── Étape 2 : Sprints + Tickets ──────────────────────────────────────────

    async def generate_sprints(self, cdc: CdC) -> list[SprintPlan]:
        """Génère le découpage Sprints/Tickets depuis le CdC (DeepSeek R1, JSON strict)."""
        await self.ws.emit_step("SPRINT_GENERATION", "deepseek/deepseek-r1")
        features_str = "\n".join(
            f"- [{f.id}] {f.title} (complexité {f.complexity}): {f.description}"
            for f in cdc.features_must + cdc.features_should
        )

        prompt = f"""Génère le découpage en sprints et tickets pour ce projet.

Projet : {cdc.title}
Stack : {json.dumps(cdc.stack)}
Fonctionnalités must-have + should-have :
{features_str}
Sprints estimés : {cdc.estimated_sprints}

Format JSON strict — tableau de sprints :
[
  {{
    "sprint_name": "Sprint 1",
    "tickets": [
      {{
        "id": "T-001",
        "title": "...",
        "description": "...",
        "acceptance_criteria": ["...", "..."],
        "subtasks": [{{"id": "T-001-1", "text": "...", "done": false}}],
        "tests_required": ["test_nom_test()"],
        "blocked_by": [],
        "estimated_complexity": 4
      }}
    ]
  }}
]

Règles :
- IDs au format T-XXX (3 chiffres, séquence)
- Chaque ticket = 1 endpoint ou 1 composant ou 1 feature atomique
- tests_required = noms des fonctions de test (snake_case)
- blocked_by = IDs des tickets dont celui-ci dépend"""

        raw = await self.llm.call_with_fallback(
            role=LLMRole.ARCHITECTURE,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._parse_sprints(raw)

    def _parse_sprints(self, raw: str) -> list[SprintPlan]:
        """Parse le JSON des sprints retourné par le LLM."""
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            raise ValueError("Sprint JSON invalide — pas de tableau JSON trouvé")
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"Sprint JSON invalide: {e}") from e

        sprints: list[SprintPlan] = []
        for sprint_data in data:
            tickets = [
                TicketPlan(
                    id=t["id"],
                    title=t["title"],
                    description=t.get("description", ""),
                    acceptance_criteria=t.get("acceptance_criteria", []),
                    subtasks=t.get("subtasks", []),
                    tests_required=t.get("tests_required", []),
                    blocked_by=t.get("blocked_by", []),
                    estimated_complexity=t.get("estimated_complexity", 5),
                )
                for t in sprint_data.get("tickets", [])
            ]
            sprints.append(
                SprintPlan(sprint_name=sprint_data["sprint_name"], tickets=tickets)
            )
        return sprints

    # ── Étape 3 : Création structure GitHub ──────────────────────────────────

    async def create_github_structure(
        self, cdc: CdC, sprints: list[SprintPlan]
    ) -> ProjectRoadmap:
        """Crée Milestones + Issues + workflow CI, retourne la ProjectRoadmap."""
        await self.ws.emit_step("GITHUB_SETUP", "orchestrator")

        self.github.write_workflow_file()

        for sprint in sprints:
            self.github.create_milestone(sprint.sprint_name)

        roadmap = ProjectRoadmap(project=cdc.project_name)
        for sprint in sprints:
            for tp in sprint.tickets:
                task = Task(
                    id=tp.id,
                    title=tp.title,
                    status="pending",
                    assigned_to="",
                    subtasks=[
                        SubTask(
                            id=st["id"],
                            text=st["text"],
                            done=st.get("done", False),
                        )
                        for st in tp.subtasks
                    ],
                    blocked_by=tp.blocked_by,
                    sprint=sprint.sprint_name,
                    estimated_complexity=tp.estimated_complexity,
                    tests_required=tp.tests_required,
                    acceptance_criteria=tp.acceptance_criteria,
                )
                issue_number = self.github.create_issue_from_task(task)
                task.github_issue = issue_number
                roadmap.tasks.append(task)

        return roadmap

    # ── Étape 4a : Attente CI GitHub Actions (polling) ───────────────────────

    async def _wait_for_ci(
        self,
        pr_number: int,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> bool:
        """Poll GitHub pour l'état des checks de la PR.

        Retourne True si tous les checks passent, False si échec ou timeout.
        """
        interval = poll_interval if poll_interval is not None else self.CI_POLL_INTERVAL
        max_s = timeout if timeout is not None else self.CI_TIMEOUT
        deadline = time.monotonic() + max_s

        while True:
            status = self.github.get_pr_check_status(pr_number)
            if status == "success":
                return True
            if status == "failure":
                return False
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(interval)

    # ── Étape 4 : Exécution autonome d'un ticket ─────────────────────────────

    async def execute_ticket(
        self,
        task: Task,
        roadmap: ProjectRoadmap,
        agent_loop_factory: Callable[[], Awaitable],
    ) -> bool:
        """Exécute un ticket en circuit fermé avec retry CI réel (Niveau 2).

        Flux :
            1. Sauvegarde la branche initiale (C9)
            2. Crée la branche feature/T-XXX-titre
            3. Agent loop implémente
            4. Commit + push (C10 : push direct, pas de re-split de branch_name)
            5. Crée la PR liée à l'issue GitHub
            6. Poll CI GitHub Actions (30s par défaut, timeout 10 min)
            7a. CI vert → close issue, mark done, return True
            7b. CI rouge → retry (jusqu'à MAX_CI_RETRIES)
        Retourne True si succès, False après MAX_CI_RETRIES échecs.
        """
        # C9 — mémoriser la branche initiale pour tous les checkout de retour.
        initial_branch = self.git.get_current_branch()

        branch_name = (
            f"feature/{task.id.lower()}-"
            + task.title.lower().replace(" ", "-")[:25].rstrip("-")
        )

        for ci_attempt in range(1, self.MAX_CI_RETRIES + 1):
            await self.ws.emit_step(f"TICKET_EXECUTE (CI #{ci_attempt})", task.id)
            pr_number: int | None = None

            try:
                self.git.create_branch(branch_name)
                roadmap.update_task_status(task.id, "in_progress")
                roadmap.lock_file(branch_name, task.assigned_to)

                result = await agent_loop_factory()

                modified = self.git.get_modified_files()
                if modified:
                    self.git.stage(modified)
                    self.git.commit(
                        f"[{task.id}] {task.title} (#{task.github_issue})"
                    )
                    # C10 — push direct, pas de re-split de branch_name.
                    self.git.push(branch=branch_name)

                if task.github_issue:
                    pr_title = f"[{task.id}] {task.title} (#{task.github_issue})"
                    content_preview = str(getattr(result, "content", result))[:500]
                    pr_body = f"Closes #{task.github_issue}\n\n{content_preview}"
                    pr_number = self.github.create_pr(
                        title=pr_title,
                        body=pr_body,
                        head_branch=branch_name,
                    )

                # C9 — retour à la branche initiale avant d'attendre le CI.
                self.git.checkout(initial_branch)
                roadmap.unlock_file(branch_name)

                # Niveau 2 — attente CI GitHub Actions (polling réel).
                if pr_number is not None:
                    await self.ws.emit_step(
                        f"CI_WAIT (#{ci_attempt})", task.id
                    )
                    ci_ok = await self._wait_for_ci(pr_number)
                    if not ci_ok:
                        # CI rouge → on considère cette tentative comme échec
                        # et on laisse la boucle for réessayer.
                        raise RuntimeError(
                            f"CI rouge sur PR #{pr_number} (tentative {ci_attempt})"
                        )

                roadmap.update_task_status(task.id, "done")
                roadmap.add_done(
                    f"[{task.id}] {task.title} — CI vert, PR mergée"
                )
                return True

            except Exception as e:
                await self.ws.emit_step(f"TICKET_RETRY (#{ci_attempt})", task.id)
                if ci_attempt == self.MAX_CI_RETRIES:
                    roadmap.update_task_status(task.id, "failed")
                    if task.github_issue:
                        self.github.comment_issue(
                            task.github_issue,
                            f"❌ Échec total après {self.MAX_CI_RETRIES} tentatives CI.\n"
                            f"Erreur : {str(e)[:200]}\nIntervention humaine requise.",
                        )
                        self.github.add_label_to_issue(
                            task.github_issue, "blocked"
                        )
                    return False
                # C9 — retour à la branche initiale avant retry.
                try:
                    self.git.checkout(initial_branch)
                except Exception:
                    pass

        return False
