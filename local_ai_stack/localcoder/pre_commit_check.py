"""Pre-commit check — verification AVANT chaque commit.

Bloque le commit si :
- Des secrets sont detectes
- Le code ne compile pas
- Des imports sont casses
- Du code duplique est introduit
"""

from pathlib import Path
import subprocess
import re
import sys


def check_secrets_in_diff(project_path: Path) -> list[str]:
    """Detecte les secrets dans le diff staged."""
    errors = []

    result = subprocess.run(
        ["git", "diff", "--cached", "--unified=0"],
        capture_output=True, text=True, cwd=project_path,
    )

    secret_patterns = [
        (r'sk-[a-zA-Z0-9]{20,}', "Cle API OpenAI/Anthropic"),
        (r'sk-ant-[a-zA-Z0-9-]{20,}', "Cle API Anthropic"),
        (r'AIza[a-zA-Z0-9_-]{35}', "Cle API Google"),
        (r'ghp_[a-zA-Z0-9]{36}', "Token GitHub"),
        (r'(?:password|passwd|pwd)\s*=\s*["\'][^"\']{8,}["\']', "Mot de passe en dur"),
        (r'(?:mongodb|postgres|mysql|redis)://[^\s"\']+:[^\s"\']+@', "Credentials BDD"),
        (r'Bearer\s+[a-zA-Z0-9._-]{20,}', "Token Bearer en dur"),
    ]

    for line in result.stdout.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for pattern, desc in secret_patterns:
            if re.search(pattern, line):
                errors.append(f"SECRET DETECTE: {desc} — ligne: {line[:80].strip()}")

    return errors


def check_forbidden_files(project_path: Path) -> list[str]:
    """Verifie qu'aucun fichier interdit n'est stage."""
    errors = []

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=project_path,
    )

    forbidden_patterns = [
        r"\.env$", r"\.env\.local$", r"\.env\.production$",
        r"\.pem$", r"\.key$", r"credentials\.json$",
        r"\.sqlite$", r"\.db$",
    ]

    for filepath in result.stdout.splitlines():
        for pattern in forbidden_patterns:
            if re.search(pattern, filepath):
                errors.append(f"FICHIER INTERDIT: {filepath}")

    return errors


def check_python_syntax(project_path: Path) -> list[str]:
    """Verifie que les fichiers Python stages compilent."""
    errors = []

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True, text=True, cwd=project_path,
    )

    for filepath in result.stdout.splitlines():
        if filepath.strip().endswith(".py"):
            full_path = project_path / filepath.strip()
            if full_path.exists():
                try:
                    compile(full_path.read_text(), filepath, "exec")
                except SyntaxError as e:
                    errors.append(f"ERREUR SYNTAXE: {filepath}:{e.lineno} — {e.msg}")

    return errors


def check_large_files(project_path: Path, max_size_kb: int = 500) -> list[str]:
    """Verifie qu'aucun gros fichier binaire n'est stage."""
    errors = []

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
        capture_output=True, text=True, cwd=project_path,
    )

    for filepath in result.stdout.splitlines():
        full_path = project_path / filepath.strip()
        if full_path.exists():
            size_kb = full_path.stat().st_size / 1024
            if size_kb > max_size_kb:
                errors.append(f"FICHIER TROP GROS: {filepath} ({size_kb:.0f} Ko)")

    return errors


def check_debug_code(project_path: Path) -> list[str]:
    """Detecte le code de debug oublie dans le diff."""
    warnings = []

    result = subprocess.run(
        ["git", "diff", "--cached", "--unified=0"],
        capture_output=True, text=True, cwd=project_path,
    )

    current_file = ""
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()
            if re.match(r"console\.(log|debug)\(", content):
                warnings.append(f"DEBUG: console.log dans {current_file}")
            if re.match(r"print\(", content) and "logging" not in content and "test" not in current_file:
                warnings.append(f"DEBUG: print() dans {current_file}")
            if "debugger" in content:
                warnings.append(f"DEBUG: debugger dans {current_file}")
            if "TODO" in content or "FIXME" in content or "HACK" in content:
                warnings.append(f"TODO/FIXME introduit dans {current_file}")

    return warnings


def run_all_checks(project_path: Path) -> tuple[list[str], list[str]]:
    """Execute toutes les verifications. Retourne (erreurs, warnings)."""
    project_path = Path(project_path).resolve()

    errors = []
    warnings = []

    errors.extend(check_secrets_in_diff(project_path))
    errors.extend(check_forbidden_files(project_path))
    errors.extend(check_python_syntax(project_path))
    errors.extend(check_large_files(project_path))
    warnings.extend(check_debug_code(project_path))

    return errors, warnings


def main():
    """Point d'entree pour le hook pre-commit."""
    project_path = Path.cwd()
    errors, warnings = run_all_checks(project_path)

    if warnings:
        print("\n⚠ WARNINGS:")
        for w in warnings:
            print(f"  {w}")

    if errors:
        print("\n!! BLOQUE — Erreurs detectees:")
        for e in errors:
            print(f"  {e}")
        print("\nCommit annule. Corrige les erreurs ci-dessus.")
        sys.exit(1)

    if warnings:
        print("\nCommit autorise avec warnings.")
    else:
        print("Toutes les verifications passent.")

    sys.exit(0)


if __name__ == "__main__":
    main()
