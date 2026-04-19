"""
Service git local — branch, stage, commit, push, diff.
Wrap GitPython avec une interface simple et synchrone.
"""
from pathlib import Path
from typing import Optional

import git
from git import InvalidGitRepositoryError, NoSuchPathError, Repo


class GitServiceError(Exception):
    """Erreur git non récupérable."""


class GitService:
    """Service git local. Une instance par workspace ouvert."""

    def __init__(self, repo_path: str = "."):
        try:
            self.repo = Repo(repo_path, search_parent_directories=True)
        except (InvalidGitRepositoryError, NoSuchPathError) as e:
            raise GitServiceError(f"Pas de repo git dans {repo_path}") from e
        self.repo_path = Path(self.repo.working_dir)

    def get_current_branch(self) -> str:
        """Retourne le nom de la branche active."""
        return self.repo.active_branch.name

    def create_branch(self, name: str) -> None:
        """Crée et checkout une nouvelle branche depuis HEAD."""
        self.repo.git.checkout("-b", name)

    def checkout(self, branch: str) -> None:
        """Checkout une branche existante."""
        self.repo.git.checkout(branch)

    def get_modified_files(self) -> list[str]:
        """
        Retourne les fichiers modifiés (staged + unstaged + untracked).
        Chemins relatifs à la racine du repo.
        """
        modified: set[str] = set()
        for item in self.repo.index.diff(None):
            modified.add(item.a_path)
        try:
            for item in self.repo.index.diff("HEAD"):
                modified.add(item.a_path)
        except git.BadName:
            # Repo sans commit initial : index.diff("HEAD") échoue.
            pass
        for path in self.repo.untracked_files:
            modified.add(path)
        return sorted(modified)

    def stage(self, files: list[str]) -> None:
        """Stage les fichiers spécifiés."""
        self.repo.index.add(files)

    def commit(self, message: str) -> str:
        """Commit les fichiers stagés. Retourne le hash court du commit."""
        commit_obj = self.repo.index.commit(message)
        return commit_obj.hexsha[:8]

    def push(self, remote: str = "origin", branch: Optional[str] = None) -> None:
        """Push vers le remote. Crée la branche upstream si nécessaire."""
        target = branch or self.get_current_branch()
        self.repo.git.push("--set-upstream", remote, target)

    def get_staged_diff(self) -> str:
        """Retourne le diff des fichiers stagés (HEAD vs index)."""
        try:
            return self.repo.git.diff("--cached")
        except git.GitCommandError:
            return self.repo.git.diff()

    def get_last_commit_message(self) -> str:
        """Retourne le message du dernier commit."""
        return self.repo.head.commit.message.strip()

    def branch_exists_remote(self, branch: str, remote: str = "origin") -> bool:
        """Vérifie si une branche existe sur le remote."""
        refs = [ref.name for ref in self.repo.remotes[remote].refs]
        return f"{remote}/{branch}" in refs

    def get_status_for_ui(self) -> dict:
        """Retourne un dict compatible avec l'event git_status WebSocket."""
        return {
            "branch": self.get_current_branch(),
            "modifiedFiles": len(self.get_modified_files()),
        }
