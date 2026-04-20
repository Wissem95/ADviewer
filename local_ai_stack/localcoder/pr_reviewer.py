"""PR Reviewer — analyse complete d'une PR avant merge.

Lit les fichiers modifies, detecte les problemes, verifie les tests,
et produit un rapport de review avec decision go/no-go.
"""

from pathlib import Path
import subprocess
from dataclasses import dataclass, field

from localcoder.git_analyzer import analyze_pr_diff, get_file_history
from localcoder.reviewer import review_file, ReviewIssue
from localcoder.scanner import find_duplicate_blocks, CODE_EXTENSIONS, should_ignore


@dataclass
class PRReviewReport:
    """Rapport de review de PR."""
    branch: str = ""
    base: str = "main"
    commits_count: int = 0
    files_changed: int = 0
    issues: list[ReviewIssue] = field(default_factory=list)
    duplicates_introduced: list[dict] = field(default_factory=list)
    tests_status: str = "non execute"
    lint_status: str = "non execute"
    verdict: str = "en attente"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def can_merge(self) -> bool:
        return len(self.blockers) == 0

    def format(self) -> str:
        lines = []
        lines.append(f"# Review PR : {self.branch} -> {self.base}")
        lines.append(f"\nCommits: {self.commits_count} | Fichiers modifies: {self.files_changed}")
        lines.append(f"Tests: {self.tests_status} | Lint: {self.lint_status}")

        if self.blockers:
            lines.append(f"\n## BLOQUANTS ({len(self.blockers)})")
            for b in self.blockers:
                lines.append(f"  !! {b}")

        if self.issues:
            lines.append(f"\n## Problemes de code ({len(self.issues)})")
            for issue in self.issues:
                loc = f":{issue.line}" if issue.line else ""
                lines.append(f"  [{issue.severity}] {issue.file}{loc} — {issue.message}")

        if self.duplicates_introduced:
            lines.append(f"\n## Doublons introduits ({len(self.duplicates_introduced)})")
            for d in self.duplicates_introduced:
                lines.append(f"  {d['file_a']} <-> {d['file_b']}")

        if self.warnings:
            lines.append(f"\n## Warnings ({len(self.warnings)})")
            for w in self.warnings:
                lines.append(f"  ! {w}")

        if self.recommendations:
            lines.append(f"\n## Recommendations")
            for r in self.recommendations:
                lines.append(f"  > {r}")

        verdict_icon = "OK" if self.can_merge else "BLOQUE"
        lines.append(f"\n## Verdict: {verdict_icon}")
        if self.can_merge:
            lines.append("La PR peut etre mergee.")
        else:
            lines.append("La PR NE PEUT PAS etre mergee. Corrige les bloquants ci-dessus.")

        return "\n".join(lines)


def run_tests(project_path: Path) -> tuple[bool, str]:
    """Lance les tests du projet."""
    # Detecter le type de projet
    if (project_path / "pytest.ini").exists() or (project_path / "backend" / "pytest.ini").exists():
        cmd = ["python", "-m", "pytest", "-x", "-q", "--tb=short"]
        cwd = project_path / "backend" if (project_path / "backend").exists() else project_path
    elif (project_path / "package.json").exists():
        cmd = ["npm", "test", "--", "--passWithNoTests"]
        cwd = project_path
    else:
        return True, "Aucun framework de test detecte"

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=120,
        )
        passed = result.returncode == 0
        output = result.stdout[-500:] if result.stdout else result.stderr[-500:]
        return passed, output
    except subprocess.TimeoutExpired:
        return False, "Tests timeout (>120s)"
    except FileNotFoundError:
        return True, "Commande de test non trouvee"


def run_lint(project_path: Path) -> tuple[bool, str]:
    """Lance le linter du projet."""
    results = []

    # Python (ruff)
    backend_path = project_path / "backend"
    if backend_path.exists():
        try:
            result = subprocess.run(
                ["ruff", "check", "."],
                capture_output=True, text=True, cwd=backend_path, timeout=30,
            )
            if result.returncode != 0:
                results.append(("Python/ruff", False, result.stdout[-300:]))
            else:
                results.append(("Python/ruff", True, "OK"))
        except FileNotFoundError:
            results.append(("Python/ruff", True, "ruff non installe"))

    # TypeScript (eslint)
    frontend_path = project_path / "frontend-next"
    if frontend_path.exists():
        try:
            result = subprocess.run(
                ["npx", "eslint", ".", "--max-warnings=0"],
                capture_output=True, text=True, cwd=frontend_path, timeout=60,
            )
            if result.returncode != 0:
                results.append(("TS/eslint", False, result.stdout[-300:]))
            else:
                results.append(("TS/eslint", True, "OK"))
        except FileNotFoundError:
            results.append(("TS/eslint", True, "eslint non installe"))

    all_passed = all(passed for _, passed, _ in results)
    summary = " | ".join(f"{name}: {'OK' if ok else 'ERREURS'}" for name, ok, _ in results)

    return all_passed, summary


def review_pr(project_path: Path, base_branch: str = "main", run_ci: bool = True) -> PRReviewReport:
    """Review complete d'une PR."""
    project_path = Path(project_path).resolve()
    report = PRReviewReport(base=base_branch)

    # 1. Analyser le diff de la PR
    pr_diff = analyze_pr_diff(project_path, base_branch)

    if "error" in pr_diff:
        report.blockers.append(pr_diff["error"])
        return report

    report.branch = pr_diff["branch"]
    report.commits_count = len(pr_diff["commits"])
    report.files_changed = pr_diff["total_files"]

    # 2. Review statique de chaque fichier modifie
    for file_info in pr_diff["files_changed"]:
        filepath = file_info["file"]
        full_path = project_path / filepath

        if full_path.exists() and full_path.suffix in {".py", ".ts", ".tsx", ".js", ".jsx"}:
            try:
                content = full_path.read_text(errors="ignore")
                issues = review_file(filepath, content)
                report.issues.extend(issues)
            except (PermissionError, OSError):
                pass

    # Erreurs de review = bloquants
    for issue in report.issues:
        if issue.severity == "error":
            report.blockers.append(f"[{issue.rule}] {issue.file}:{issue.line} — {issue.message}")

    # 3. Verifier les doublons introduits
    code_files = {}
    for f in project_path.rglob("*"):
        if f.is_file() and f.suffix in CODE_EXTENSIONS and not should_ignore(f):
            try:
                code_files[str(f.relative_to(project_path))] = f.read_text(errors="ignore")
            except (PermissionError, OSError):
                pass

    all_duplicates = find_duplicate_blocks(code_files)
    pr_files = {fi["file"] for fi in pr_diff["files_changed"]}

    for dup in all_duplicates:
        if dup["file_a"] in pr_files or dup["file_b"] in pr_files:
            report.duplicates_introduced.append(dup)
            report.warnings.append(
                f"Doublon entre {dup['file_a']} et {dup['file_b']} ({dup['lines']} lignes)"
            )

    # 4. Lancer les tests et le lint (si demande)
    if run_ci:
        tests_passed, tests_output = run_tests(project_path)
        report.tests_status = "OK" if tests_passed else f"ECHEC: {tests_output[:200]}"
        if not tests_passed:
            report.blockers.append(f"Tests en echec: {tests_output[:200]}")

        lint_passed, lint_output = run_lint(project_path)
        report.lint_status = "OK" if lint_passed else f"ECHEC: {lint_output[:200]}"
        if not lint_passed:
            report.warnings.append(f"Lint: {lint_output[:200]}")

    # 5. Recommendations
    if report.files_changed > 10:
        report.recommendations.append(
            f"PR touche {report.files_changed} fichiers — envisager de decouper en PRs plus petites"
        )

    large_commits = [c for c in pr_diff.get("commits", []) if len(c.get("message", "")) < 10]
    if large_commits:
        report.recommendations.append("Certains commits ont des messages trop courts — ameliorer la clarte")

    # Verdict
    report.verdict = "APPROUVE" if report.can_merge else "BLOQUE"

    return report


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    base = sys.argv[2] if len(sys.argv) > 2 else "main"
    report = review_pr(path, base, run_ci=False)
    print(report.format())
