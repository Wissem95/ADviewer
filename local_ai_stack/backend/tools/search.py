"""Code search — outil exposé aux LLMs en read-only (Plan 5A Task 5).

Utilisé par Stage3Ground pour retrouver les appelants d'une fonction, les
patterns existants du projet, etc.

Implémentation Python pure (pas de dépendance à ``rg``) pour la portabilité :
- pathlib.glob pour walker.
- re.compile pour matcher.
- errors="ignore" pour skip les fichiers binaires sans crash.
"""
import re
from pathlib import Path

from backend.tools.exceptions import PathOutsideWorkspace


# Dossiers ignorés identiques à ``file_ops._EXCLUDED_DIRS``.
_EXCLUDED_DIRS = {".git", "node_modules", "venv", "__pycache__", "dist", "build"}

# Taille max d'un fichier scanné (évite de grep des blobs 100 MB).
_MAX_FILE_SIZE = 2_000_000


def _resolve_start(start_path: str, workspace_root: Path) -> Path:
    """Résout ``start_path`` sous ``workspace_root`` (refuse les sorties)."""
    root = Path(workspace_root).resolve()
    p = Path(start_path)
    candidate = (p if p.is_absolute() else root / p).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise PathOutsideWorkspace(
            f"start_path {start_path!r} résout hors du workspace {root}"
        )
    return candidate


async def grep_codebase(
    pattern: str,
    workspace_root: Path,
    path_glob: str = "**/*",
    start_path: str = ".",
    max_results: int = 50,
) -> list[dict]:
    """Cherche ``pattern`` (regex) dans tous les fichiers matchant ``path_glob``.

    Retourne une liste de ``{file, line, excerpt}`` où :
    - ``file`` est relatif à ``workspace_root``,
    - ``line`` est 1-indexé,
    - ``excerpt`` est la ligne tronquée à 200 chars.

    Ignore les dossiers de ``_EXCLUDED_DIRS``, les fichiers > 2 MB, et tout
    fichier qu'on ne peut pas décoder proprement (binaires).
    """
    root = Path(workspace_root).resolve()
    start = _resolve_start(start_path, root)

    regex = re.compile(pattern)
    results: list[dict] = []

    for p in start.glob(path_glob):
        if not p.is_file():
            continue
        # Exclusion de dossiers connus.
        rel_parts = p.relative_to(root).parts
        if any(part in _EXCLUDED_DIRS for part in rel_parts):
            continue
        try:
            if p.stat().st_size > _MAX_FILE_SIZE:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            continue

        for i, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                results.append({
                    "file": str(p.relative_to(root)),
                    "line": i,
                    "excerpt": line[:200],
                })
                if len(results) >= max_results:
                    return results
    return results
