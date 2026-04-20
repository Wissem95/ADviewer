"""Analyseur Git — lit les commits, PRs, branches, diffs.

Fournit des donnees REELLES, pas des suppositions.
"""

from pathlib import Path
import subprocess
import re
from dataclasses import dataclass, field


@dataclass
class CommitInfo:
    hash: str
    author: str
    date: str
    message: str
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0


@dataclass
class BranchInfo:
    name: str
    is_current: bool
    ahead: int = 0
    behind: int = 0
    last_commit: str = ""


@dataclass
class GitReport:
    """Rapport complet de l'etat Git."""
    current_branch: str = ""
    is_clean: bool = True
    uncommitted_files: list[str] = field(default_factory=list)
    staged_files: list[str] = field(default_factory=list)
    recent_commits: list[CommitInfo] = field(default_factory=list)
    branches: list[BranchInfo] = field(default_factory=list)
    files_at_risk: list[dict] = field(default_factory=list)


def run_git(args: list[str], cwd: Path) -> str:
    """Execute une commande git et retourne stdout."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True, cwd=cwd, timeout=30,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_current_branch(project_path: Path) -> str:
    return run_git(["branch", "--show-current"], project_path)


def get_uncommitted_files(project_path: Path) -> tuple[list[str], list[str]]:
    """Retourne (staged, unstaged+untracked)."""
    staged = []
    unstaged = []

    output = run_git(["status", "--porcelain"], project_path)
    for line in output.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        filepath = line[3:].strip()

        if status[0] in "MADR":
            staged.append(filepath)
        if status[1] in "MADR?":
            unstaged.append(filepath)

    return staged, unstaged


def get_recent_commits(project_path: Path, count: int = 20) -> list[CommitInfo]:
    """Recupere les N derniers commits avec details."""
    output = run_git(
        ["log", f"-{count}", "--format=%H|%an|%ad|%s", "--date=short"],
        project_path,
    )

    commits = []
    for line in output.splitlines():
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue

        commit_hash = parts[0]

        # Fichiers modifies par ce commit
        files_output = run_git(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
            project_path,
        )
        files = [f.strip() for f in files_output.splitlines() if f.strip()]

        # Stats (insertions/deletions)
        stat_output = run_git(
            ["diff-tree", "--no-commit-id", "--shortstat", "-r", commit_hash],
            project_path,
        )
        insertions = 0
        deletions = 0
        ins_match = re.search(r"(\d+) insertion", stat_output)
        del_match = re.search(r"(\d+) deletion", stat_output)
        if ins_match:
            insertions = int(ins_match.group(1))
        if del_match:
            deletions = int(del_match.group(1))

        commits.append(CommitInfo(
            hash=commit_hash[:8],
            author=parts[1],
            date=parts[2],
            message=parts[3],
            files_changed=files,
            insertions=insertions,
            deletions=deletions,
        ))

    return commits


def get_branches(project_path: Path) -> list[BranchInfo]:
    """Liste les branches avec leur statut."""
    current = get_current_branch(project_path)
    output = run_git(["branch", "-a", "--format=%(refname:short)"], project_path)

    branches = []
    for line in output.splitlines():
        name = line.strip()
        if not name or "HEAD" in name:
            continue
        branches.append(BranchInfo(
            name=name,
            is_current=(name == current),
        ))

    return branches


def get_file_history(project_path: Path, filepath: str, count: int = 5) -> list[CommitInfo]:
    """Historique des commits pour un fichier specifique."""
    output = run_git(
        ["log", f"-{count}", "--follow", "--format=%H|%an|%ad|%s", "--date=short", "--", filepath],
        project_path,
    )

    commits = []
    for line in output.splitlines():
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        commits.append(CommitInfo(
            hash=parts[0][:8],
            author=parts[1],
            date=parts[2],
            message=parts[3],
            files_changed=[filepath],
        ))

    return commits


def get_diff_stat(project_path: Path, ref: str = "HEAD") -> list[dict]:
    """Resume du diff par rapport a une reference."""
    output = run_git(["diff", "--stat", ref], project_path)
    files = []

    for line in output.splitlines():
        match = re.match(r"\s*(.+?)\s+\|\s+(\d+)\s+(\+*)(-*)", line)
        if match:
            files.append({
                "file": match.group(1).strip(),
                "changes": int(match.group(2)),
                "insertions": len(match.group(3)),
                "deletions": len(match.group(4)),
            })

    return files


def find_files_at_risk(project_path: Path, commits: list[CommitInfo]) -> list[dict]:
    """Identifie les fichiers frequemment modifies (points chauds / hotspots).

    Un fichier modifie souvent = risque de bugs, code instable.
    """
    file_counts: dict[str, int] = {}
    for commit in commits:
        for f in commit.files_changed:
            file_counts[f] = file_counts.get(f, 0) + 1

    # Fichiers modifies > 3 fois dans les N derniers commits
    hotspots = [
        {"file": f, "modifications": count, "risk": "eleve" if count > 5 else "moyen"}
        for f, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        if count >= 3
    ]

    return hotspots[:20]


def analyze_pr_diff(project_path: Path, base_branch: str = "main") -> dict:
    """Analyse le diff de la branche actuelle par rapport a la branche de base.

    Utilise pour la review de PR avant merge.
    """
    current = get_current_branch(project_path)
    if current == base_branch:
        return {"error": f"Tu es deja sur {base_branch}. Change de branche d'abord."}

    # Commits dans la PR
    pr_commits_output = run_git(
        ["log", f"{base_branch}..{current}", "--format=%H|%an|%ad|%s", "--date=short"],
        project_path,
    )
    pr_commits = []
    for line in pr_commits_output.splitlines():
        parts = line.split("|", 3)
        if len(parts) >= 4:
            pr_commits.append({
                "hash": parts[0][:8],
                "author": parts[1],
                "date": parts[2],
                "message": parts[3],
            })

    # Fichiers modifies dans la PR
    files_output = run_git(
        ["diff", "--name-status", f"{base_branch}...{current}"],
        project_path,
    )
    changed_files = []
    for line in files_output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changed_files.append({
                "status": {"A": "ajoute", "M": "modifie", "D": "supprime"}.get(parts[0], parts[0]),
                "file": parts[1],
            })

    # Stats globales
    stat_output = run_git(
        ["diff", "--shortstat", f"{base_branch}...{current}"],
        project_path,
    )

    return {
        "branch": current,
        "base": base_branch,
        "commits": pr_commits,
        "files_changed": changed_files,
        "total_files": len(changed_files),
        "stats": stat_output,
    }


def full_git_report(project_path: Path) -> GitReport:
    """Rapport Git complet — donnees reelles du repo."""
    project_path = Path(project_path).resolve()

    staged, unstaged = get_uncommitted_files(project_path)
    commits = get_recent_commits(project_path, count=20)
    hotspots = find_files_at_risk(project_path, commits)

    return GitReport(
        current_branch=get_current_branch(project_path),
        is_clean=(not staged and not unstaged),
        uncommitted_files=unstaged,
        staged_files=staged,
        recent_commits=commits,
        branches=get_branches(project_path),
        files_at_risk=hotspots,
    )


def format_git_report(report: GitReport) -> str:
    """Formate le rapport Git en texte."""
    lines = []
    lines.append("# Rapport Git")
    lines.append(f"\nBranche: {report.current_branch}")
    lines.append(f"Etat: {'propre' if report.is_clean else 'modifications non commitees'}")

    if report.uncommitted_files:
        lines.append(f"\n## Fichiers non commites ({len(report.uncommitted_files)})")
        for f in report.uncommitted_files[:20]:
            lines.append(f"  ! {f}")

    if report.staged_files:
        lines.append(f"\n## Fichiers stages ({len(report.staged_files)})")
        for f in report.staged_files:
            lines.append(f"  + {f}")

    lines.append(f"\n## Derniers commits ({len(report.recent_commits)})")
    for c in report.recent_commits[:15]:
        lines.append(f"  {c.hash} {c.date} — {c.message} (+{c.insertions}/-{c.deletions})")

    if report.files_at_risk:
        lines.append(f"\n## Hotspots — fichiers frequemment modifies ({len(report.files_at_risk)})")
        for h in report.files_at_risk:
            lines.append(f"  [{h['risk']}] {h['file']} ({h['modifications']} modifications)")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    report = full_git_report(path)
    print(format_git_report(report))
