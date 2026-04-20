"""Hooks Installer — installe les hooks Git pour auto-indexation.

Installe :
- post-commit : re-indexe le projet apres chaque commit (leger, en arriere-plan)
- pre-push : verifie la memoire a jour avant un push

Les hooks sont non-bloquants et non-intrusifs.
"""

import stat
from pathlib import Path


POST_COMMIT_HOOK = """#!/bin/bash
# LocalCoder auto-index hook
# Re-indexe le projet apres chaque commit (en arriere-plan, non-bloquant)

if command -v localcoder &> /dev/null; then
    # Lancer en arriere-plan, rediriger sortie pour pas polluer le terminal
    (localcoder index > /dev/null 2>&1 &) 2> /dev/null
fi

exit 0
"""


def is_git_repo(project_path: Path) -> bool:
    return (project_path / ".git").is_dir()


def install_hooks(project_path: Path) -> dict:
    """Installe les hooks Git dans le projet.

    Retourne un rapport des actions effectuees.
    """
    report = {
        "installed": [],
        "skipped": [],
        "errors": [],
    }

    if not is_git_repo(project_path):
        report["errors"].append("Pas un repo Git — hooks non installes")
        return report

    hooks_dir = project_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    hooks_to_install = [
        ("post-commit", POST_COMMIT_HOOK),
    ]

    for hook_name, content in hooks_to_install:
        hook_path = hooks_dir / hook_name

        # Si existe deja, verifier si c'est le notre
        if hook_path.exists():
            existing = hook_path.read_text()
            if "LocalCoder auto-index hook" in existing:
                report["skipped"].append(f"{hook_name} (deja installe par LocalCoder)")
                continue
            else:
                # Hook existe mais c'est un autre — on ne l'ecrase pas
                report["skipped"].append(f"{hook_name} (existe deja — pas ecrase)")
                continue

        try:
            hook_path.write_text(content)
            # Rendre executable
            current_mode = hook_path.stat().st_mode
            hook_path.chmod(current_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            report["installed"].append(hook_name)
        except (PermissionError, OSError) as e:
            report["errors"].append(f"{hook_name}: {e}")

    return report


def uninstall_hooks(project_path: Path) -> dict:
    """Desinstalle les hooks LocalCoder."""
    report = {"removed": [], "skipped": [], "errors": []}

    if not is_git_repo(project_path):
        return report

    hooks_dir = project_path / ".git" / "hooks"
    for hook_name in ("post-commit",):
        hook_path = hooks_dir / hook_name
        if hook_path.exists():
            try:
                content = hook_path.read_text()
                if "LocalCoder auto-index hook" in content:
                    hook_path.unlink()
                    report["removed"].append(hook_name)
                else:
                    report["skipped"].append(f"{hook_name} (pas un hook LocalCoder)")
            except (PermissionError, OSError) as e:
                report["errors"].append(f"{hook_name}: {e}")

    return report


def hooks_status(project_path: Path) -> dict:
    """Retourne le statut des hooks."""
    status = {"is_git_repo": is_git_repo(project_path), "hooks": {}}

    if not status["is_git_repo"]:
        return status

    hooks_dir = project_path / ".git" / "hooks"
    for hook_name in ("post-commit",):
        hook_path = hooks_dir / hook_name
        if hook_path.exists():
            content = hook_path.read_text()
            if "LocalCoder auto-index hook" in content:
                status["hooks"][hook_name] = "localcoder"
            else:
                status["hooks"][hook_name] = "other"
        else:
            status["hooks"][hook_name] = "not_installed"

    return status


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    action = sys.argv[2] if len(sys.argv) > 2 else "install"

    if action == "install":
        r = install_hooks(path)
        print(f"Installed: {r['installed']}")
        print(f"Skipped: {r['skipped']}")
        print(f"Errors: {r['errors']}")
    elif action == "uninstall":
        r = uninstall_hooks(path)
        print(f"Removed: {r['removed']}")
    elif action == "status":
        s = hooks_status(path)
        print(s)
