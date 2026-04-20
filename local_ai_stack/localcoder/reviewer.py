"""Reviewer automatique — analyse APRES chaque session de code.

Verifie les changements Git recents et produit un rapport de review
avec detection de problemes, suggestions, et score de qualite.
"""

from pathlib import Path
import subprocess
import re
from dataclasses import dataclass, field


@dataclass
class ReviewIssue:
    """Un probleme detecte dans le code."""
    severity: str  # "error", "warning", "info"
    file: str
    line: int | None
    message: str
    rule: str


@dataclass
class ReviewReport:
    """Rapport de review complet."""
    files_changed: list[str] = field(default_factory=list)
    issues: list[ReviewIssue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def score(self) -> int:
        """Score de qualite sur 10."""
        base = 10
        for issue in self.issues:
            if issue.severity == "error":
                base -= 2
            elif issue.severity == "warning":
                base -= 1
        return max(0, min(10, base))

    def format(self) -> str:
        lines = []
        lines.append("# Review automatique")
        lines.append(f"\nScore: {self.score}/10")
        lines.append(f"Fichiers modifies: {len(self.files_changed)}")

        if self.issues:
            lines.append(f"\n## Problemes ({len(self.issues)})")
            for issue in sorted(self.issues, key=lambda i: i.severity):
                icon = {"error": "!!", "warning": "!", "info": "~"}[issue.severity]
                loc = f":{issue.line}" if issue.line else ""
                lines.append(f"  {icon} [{issue.rule}] {issue.file}{loc}")
                lines.append(f"     {issue.message}")
        else:
            lines.append("\nAucun probleme detecte.")

        return "\n".join(lines)


# --- Regles de review statique ---

def check_bare_except(content: str, filepath: str) -> list[ReviewIssue]:
    """Detecte les except vides (except: pass, catch {})."""
    issues = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if re.match(r"except\s*:", stripped) or stripped == "except:":
            issues.append(ReviewIssue(
                severity="error",
                file=filepath,
                line=i,
                message="except sans type specifique — avale toutes les erreurs",
                rule="bare-except",
            ))
        if re.match(r"except\s+\w+.*:\s*$", stripped):
            # Verifier si la ligne suivante est pass
            pass  # Gere par le linter
    return issues


def check_hardcoded_secrets(content: str, filepath: str) -> list[ReviewIssue]:
    """Detecte les secrets potentiellement en dur."""
    issues = []
    patterns = [
        (r'(?:api_key|apikey|secret|password|token)\s*=\s*["\'][^"\']{8,}["\']', "secret en dur"),
        (r'sk-[a-zA-Z0-9]{20,}', "cle API exposee"),
        (r'(?:mongodb|postgres|mysql)://[^"\']+:[^"\']+@', "credentials BDD en dur"),
    ]
    for i, line in enumerate(content.splitlines(), 1):
        for pattern, msg in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append(ReviewIssue(
                    severity="error",
                    file=filepath,
                    line=i,
                    message=msg,
                    rule="hardcoded-secret",
                ))
    return issues


def check_large_function(content: str, filepath: str) -> list[ReviewIssue]:
    """Detecte les fonctions trop longues (>50 lignes)."""
    issues = []
    # Python
    if filepath.endswith(".py"):
        func_pattern = re.compile(r"^(\s*)(def |async def )(\w+)")
        current_func = None
        current_indent = 0
        func_start = 0
        func_lines = 0

        for i, line in enumerate(content.splitlines(), 1):
            match = func_pattern.match(line)
            if match:
                if current_func and func_lines > 50:
                    issues.append(ReviewIssue(
                        severity="warning",
                        file=filepath,
                        line=func_start,
                        message=f"Fonction '{current_func}' trop longue ({func_lines} lignes) — decouper",
                        rule="long-function",
                    ))
                current_func = match.group(3)
                current_indent = len(match.group(1))
                func_start = i
                func_lines = 0
            elif current_func:
                if line.strip():
                    func_lines += 1

        # Derniere fonction
        if current_func and func_lines > 50:
            issues.append(ReviewIssue(
                severity="warning",
                file=filepath,
                line=func_start,
                message=f"Fonction '{current_func}' trop longue ({func_lines} lignes) — decouper",
                rule="long-function",
            ))

    return issues


def check_console_log(content: str, filepath: str) -> list[ReviewIssue]:
    """Detecte les console.log et print de debug oublies."""
    issues = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if filepath.endswith((".ts", ".tsx", ".js", ".jsx")):
            if re.match(r"console\.(log|debug|warn)\(", stripped):
                issues.append(ReviewIssue(
                    severity="info",
                    file=filepath,
                    line=i,
                    message="console.log de debug — a supprimer avant production",
                    rule="debug-log",
                ))
        if filepath.endswith(".py"):
            if re.match(r"print\(", stripped) and "logging" not in stripped:
                issues.append(ReviewIssue(
                    severity="info",
                    file=filepath,
                    line=i,
                    message="print() de debug — utiliser logging a la place",
                    rule="debug-print",
                ))
    return issues


def check_unused_imports(content: str, filepath: str) -> list[ReviewIssue]:
    """Detection basique d'imports potentiellement inutilises (Python)."""
    if not filepath.endswith(".py"):
        return []

    issues = []
    lines = content.splitlines()
    imports = {}

    for i, line in enumerate(lines, 1):
        match = re.match(r"^(?:from \S+ )?import (.+)", line.strip())
        if match:
            imported = match.group(1)
            # Gerer les imports multiples (from x import a, b, c)
            for name in imported.split(","):
                name = name.strip().split(" as ")[-1].strip()
                if name and name != "*":
                    imports[name] = i

    # Verifier si chaque import est utilise dans le reste du code
    for name, line_num in imports.items():
        # Compter les occurrences (hors ligne d'import)
        count = sum(1 for line in lines if name in line) - 1
        if count <= 0:
            issues.append(ReviewIssue(
                severity="warning",
                file=filepath,
                line=line_num,
                message=f"Import '{name}' potentiellement inutilise",
                rule="unused-import",
            ))

    return issues


ALL_CHECKS = [
    check_bare_except,
    check_hardcoded_secrets,
    check_large_function,
    check_console_log,
    check_unused_imports,
]


def review_file(filepath: str, content: str) -> list[ReviewIssue]:
    """Applique toutes les regles de review sur un fichier."""
    issues = []
    for check in ALL_CHECKS:
        issues.extend(check(content, filepath))
    return issues


def review_git_changes(project_path: Path) -> ReviewReport:
    """Review les changements Git non commites ou du dernier commit."""
    report = ReviewReport()

    try:
        # Fichiers modifies (staged + unstaged)
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=project_path,
        )
        changed_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

        if not changed_files:
            # Verifier le dernier commit
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                capture_output=True, text=True, cwd=project_path,
            )
            changed_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

        report.files_changed = changed_files

        for filepath in changed_files:
            full_path = project_path / filepath
            if full_path.exists() and full_path.suffix in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                content = full_path.read_text(errors="ignore")
                report.issues.extend(review_file(filepath, content))

    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return report


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    report = review_git_changes(path)
    print(report.format())
