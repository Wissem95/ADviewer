"""
Service GitHub — Issues, Milestones, PRs, GitHub Actions.
Wrap PyGithub avec une interface orientée roadmap.

Règle : ce service est appelé UNIQUEMENT par l'orchestrateur et project_mode.py.
Les LLMs ne touchent pas GitHub directement.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from github import Github, GithubException

from backend.project_slug import slugify_task_branch
from backend.roadmap import Task


class GitHubServiceError(Exception):
    """Erreur GitHub non récupérable."""


class GitHubService:
    """Service GitHub. GITHUB_TOKEN et GITHUB_REPO via env ou paramètres."""

    def __init__(self, token: Optional[str] = None, repo_name: Optional[str] = None):
        self._token = token or os.environ.get("GITHUB_TOKEN")
        if not self._token:
            raise GitHubServiceError(
                "GITHUB_TOKEN manquant. Définir la variable d'environnement "
                "ou passer token=."
            )
        self._repo_name = repo_name or os.environ.get("GITHUB_REPO")
        if not self._repo_name:
            raise GitHubServiceError(
                "GITHUB_REPO manquant. Format attendu : 'owner/repo'."
            )
        gh = Github(self._token)
        self._repo = gh.get_repo(self._repo_name)

    # ── Issues ───────────────────────────────────────────────────────────────

    def create_issue_from_task(self, task: Task) -> int:
        """Crée une Issue GitHub depuis un Task roadmap. Retourne le numéro."""
        criteria_lines = (
            "\n".join(f"- [ ] {c}" for c in task.acceptance_criteria)
            or "- [ ] À définir"
        )
        subtask_lines = (
            "\n".join(
                f"- [{'x' if st.done else ' '}] {st.id} — {st.text}"
                for st in task.subtasks
            )
            or "- [ ] Aucune sous-tâche"
        )
        tests_lines = (
            "\n".join(f"- `{t}`" for t in task.tests_required)
            or "- Aucun test spécifié"
        )
        branch_name = slugify_task_branch(task.id, task.title)
        blocked = ", ".join(task.blocked_by) or "Aucune"

        body = (
            f"## {task.id} — {task.title}\n\n"
            f"**Sprint :** {task.sprint} | **Complexité :** "
            f"{task.estimated_complexity}/10\n\n"
            f"### Critères d'acceptation\n{criteria_lines}\n\n"
            f"### Sous-tâches\n{subtask_lines}\n\n"
            f"### Tests requis\n{tests_lines}\n\n"
            f"**Branch :** `{branch_name}`\n"
            f"**Bloqué par :** {blocked}\n\n"
            f"---\n*Généré automatiquement par LocalCoder IDE v2*\n"
        )
        labels = self._ensure_labels(
            [task.sprint.lower().replace(" ", "-"), "pending"]
        )
        try:
            issue = self._repo.create_issue(
                title=f"[{task.id}] {task.title}",
                body=body,
                labels=labels,
            )
            return issue.number
        except GithubException as e:
            raise GitHubServiceError(
                f"Impossible de créer l'issue {task.id}: {e}"
            ) from e

    def close_issue(self, issue_number: int, comment: str) -> None:
        """Ferme une issue avec un commentaire final."""
        try:
            issue = self._repo.get_issue(issue_number)
            issue.create_comment(comment)
            issue.edit(state="closed")
        except GithubException as e:
            raise GitHubServiceError(
                f"Impossible de fermer l'issue #{issue_number}: {e}"
            ) from e

    def comment_issue(self, issue_number: int, comment: str) -> None:
        """Ajoute un commentaire à une issue."""
        try:
            issue = self._repo.get_issue(issue_number)
            issue.create_comment(comment)
        except GithubException as e:
            raise GitHubServiceError(
                f"Impossible de commenter l'issue #{issue_number}: {e}"
            ) from e

    def add_label_to_issue(self, issue_number: int, label: str) -> None:
        """Ajoute un label à une issue."""
        try:
            issue = self._repo.get_issue(issue_number)
            issue.add_to_labels(label)
        except GithubException as e:
            raise GitHubServiceError(
                f"Impossible d'ajouter le label à #{issue_number}: {e}"
            ) from e

    # ── Milestones ───────────────────────────────────────────────────────────

    def create_milestone(
        self, title: str, due_date: Optional[str] = None
    ) -> int:
        """Crée un Milestone GitHub. due_date au format ISO 8601."""
        kwargs: dict = {"title": title, "state": "open"}
        if due_date:
            kwargs["due_on"] = datetime.fromisoformat(due_date)
        try:
            ms = self._repo.create_milestone(**kwargs)
            return ms.number
        except GithubException as e:
            raise GitHubServiceError(
                f"Impossible de créer le milestone '{title}': {e}"
            ) from e

    # ── Pull Requests ────────────────────────────────────────────────────────

    def create_pr(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> int:
        """
        Crée une Pull Request. Le titre doit suivre le format
        "[T-003] Endpoint login JWT (#42)" pour que le workflow extract l'issue.
        """
        try:
            pr = self._repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch,
            )
            return pr.number
        except GithubException as e:
            raise GitHubServiceError(f"Impossible de créer la PR: {e}") from e

    # ── GitHub Actions ───────────────────────────────────────────────────────

    def generate_ticket_validation_workflow(self) -> str:
        """Contenu du fichier .github/workflows/ticket-validation.yml."""
        return """\
# .github/workflows/ticket-validation.yml
# Généré automatiquement par LocalCoder IDE v2 — NE PAS MODIFIER À LA MAIN
name: Ticket Validation

on:
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: pip install -e .

      - name: Run tests
        run: pytest tests/ -v --tb=short

      - name: Extract GitHub Issue number from PR title
        # PR title format: "[T-003] Endpoint login JWT (#42)"
        run: |
          ISSUE_NUMBER=$(echo "${{ github.event.pull_request.title }}" \\
            | grep -oP '(?<=#)\\d+(?=\\))')
          if [ -z "$ISSUE_NUMBER" ]; then
            echo "Pas de numéro d'issue dans le titre — skip close/comment."
            echo "ISSUE_NUMBER=" >> $GITHUB_ENV
          else
            echo "ISSUE_NUMBER=$ISSUE_NUMBER" >> $GITHUB_ENV
          fi

      - name: Close Issue on CI success
        if: success() && env.ISSUE_NUMBER != ''
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh issue close $ISSUE_NUMBER \\
            --comment "✅ CI vert. Tous les tests passent. PR mergée."
          gh issue edit $ISSUE_NUMBER \\
            --add-label "validated" --remove-label "in-progress" \\
            --remove-label "pending"

      - name: Flag Issue on CI failure
        if: failure() && env.ISSUE_NUMBER != ''
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh issue comment $ISSUE_NUMBER \\
            --body "❌ CI échoue. Agent loop retry en cours (max 3 tentatives)."
          gh issue edit $ISSUE_NUMBER --add-label "blocked"

      - name: Auto-merge on success
        if: success()
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh pr merge ${{ github.event.pull_request.number }} \\
            --squash --auto

      # NB : en option, configurer un webhook repo Settings > Webhooks vers
      # votre backend local (via tunnel) pour POST /ci-webhook recevoir
      # check_run / check_suite events et déclencher un retry Niveau 2.
"""

    def get_pr_check_status(self, pr_number: int) -> str:
        """Retourne le statut agrégé des check runs pour le HEAD de la PR.

        Mapping :
          - aucun run, ou au moins un run pas encore "completed" -> "pending"
          - tous "completed" ET un ou plusieurs "failure"/"cancelled" -> "failure"
          - tous "completed" ET tous "success"/"neutral"/"skipped" -> "success"
        """
        try:
            pr = self._repo.get_pull(pr_number)
            commit = self._repo.get_commit(pr.head.sha)
            runs = list(commit.get_check_runs())
        except GithubException as e:
            raise GitHubServiceError(
                f"Impossible de lire les check runs de la PR #{pr_number}: {e}"
            ) from e

        if not runs:
            return "pending"
        if any(r.status != "completed" for r in runs):
            return "pending"
        # #IMP3 : action_required attend une intervention humaine (ex: approval).
        # Ne pas retourner failure -> sinon retry infini. Rester en pending.
        if any(r.conclusion == "action_required" for r in runs):
            return "pending"
        if any(
            r.conclusion in ("failure", "cancelled", "timed_out")
            for r in runs
        ):
            return "failure"
        return "success"

    def write_workflow_file(self, repo_path: str = ".") -> None:
        """Écrit ticket-validation.yml dans .github/workflows/ du repo local."""
        workflow_dir = Path(repo_path) / ".github" / "workflows"
        workflow_dir.mkdir(parents=True, exist_ok=True)
        (workflow_dir / "ticket-validation.yml").write_text(
            self.generate_ticket_validation_workflow()
        )

    # ── Helpers internes ─────────────────────────────────────────────────────

    def _ensure_labels(self, label_names: list[str]) -> list[str]:
        """Retourne les labels qui existent dans le repo (ignore les autres)."""
        try:
            existing = {label.name for label in self._repo.get_labels()}
            return [name for name in label_names if name in existing]
        except GithubException:
            return []
