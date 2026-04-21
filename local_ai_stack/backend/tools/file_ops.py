"""File operations — outils exposés aux LLMs (Plan 5A Task 4).

Toutes les fonctions sont async et retournent un ``dict`` compatible avec la
payload ``tool_call_result`` des providers LiteLLM :
``{success: bool, ...}``. En cas de violation de sécurité (path hors
workspace), on lève ``PathOutsideWorkspace`` — l'orchestrator transforme
l'exception en tool_call_result(success=False) pour que le LLM corrige son
approche.

Toutes les écritures passent par ``FileLock`` pour éviter que deux LLMs
concurrents (Stage5Execute + tâche de background) touchent le même fichier.
"""
from pathlib import Path
from typing import Optional

from backend.file_lock import FileLock
from backend.tools.exceptions import PathOutsideWorkspace, ToolError


# Dossiers ignorés par list_files (et plus tard par grep_codebase).
_EXCLUDED_DIRS = {".git", "node_modules", "venv", "__pycache__", "dist", "build"}


def _resolve(path: str, workspace_root: Path) -> Path:
    """Résout ``path`` relativement au workspace, refuse les sorties.

    Lève ``PathOutsideWorkspace`` si le path résolu n'est pas dans
    workspace_root (absolus, ``../..`` traversals, etc).
    """
    root = Path(workspace_root).resolve()
    p = Path(path)
    candidate = (p if p.is_absolute() else root / p).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise PathOutsideWorkspace(
            f"Path {path!r} résout hors du workspace {root}"
        )
    return candidate


# ── read_file ────────────────────────────────────────────────────────────────

async def read_file(
    path: str,
    workspace_root: Path,
    max_bytes: int = 100_000,
) -> dict:
    """Lit un fichier texte, tronque si > ``max_bytes``.

    Ne demande pas de ``file_lock`` car c'est une lecture seule.
    """
    resolved = _resolve(path, workspace_root)
    if not resolved.exists():
        return {"success": False, "error": f"file not found: {path}"}
    if not resolved.is_file():
        return {"success": False, "error": f"not a file: {path}"}
    try:
        raw = resolved.read_bytes()
    except (OSError, PermissionError) as e:
        return {"success": False, "error": f"read error: {e}"}
    truncated = len(raw) > max_bytes
    content = raw[:max_bytes].decode("utf-8", errors="replace")
    return {
        "success": True,
        "content": content,
        "truncated": truncated,
        "bytes_read": min(len(raw), max_bytes),
    }


# ── edit_file ────────────────────────────────────────────────────────────────

async def edit_file(
    path: str,
    content: str,
    file_lock: FileLock,
    workspace_root: Path,
    llm_id: str = "pipeline",
) -> dict:
    """Remplace intégralement le contenu d'un fichier.

    Acquiert le lock avant l'écriture, le libère après.
    Si le lock est détenu par un autre LLM : retourne ``success=False`` sans
    écraser le fichier.
    """
    resolved = _resolve(path, workspace_root)
    acquired = await file_lock.acquire(path, llm_id)
    if not acquired:
        return {
            "success": False,
            "error": f"file {path!r} is locked by another caller",
        }
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "bytes_written": len(content.encode("utf-8")),
        }
    except (OSError, PermissionError) as e:
        return {"success": False, "error": f"write error: {e}"}
    finally:
        await file_lock.release(path, llm_id)


# ── patch_file ───────────────────────────────────────────────────────────────

async def patch_file(
    path: str,
    old_str: str,
    new_str: str,
    file_lock: FileLock,
    workspace_root: Path,
    llm_id: str = "pipeline",
) -> dict:
    """Edit chirurgical : remplace ``old_str`` par ``new_str`` dans le fichier.

    Échoue si ``old_str`` est absent ou apparaît plus d'une fois. C'est la
    contrainte d'unicité qui garantit qu'on modifie bien l'endroit attendu
    (et pas 12 occurrences au hasard).
    """
    resolved = _resolve(path, workspace_root)
    if not resolved.exists():
        return {"success": False, "error": f"file not found: {path}"}

    acquired = await file_lock.acquire(path, llm_id)
    if not acquired:
        return {
            "success": False,
            "error": f"file {path!r} is locked by another caller",
        }
    try:
        original = resolved.read_text(encoding="utf-8")
        count = original.count(old_str)
        if count == 0:
            return {"success": False, "error": "old_str not found in file"}
        if count > 1:
            return {
                "success": False,
                "error": f"old_str not unique (found {count} occurrences)",
            }
        patched = original.replace(old_str, new_str, 1)
        resolved.write_text(patched, encoding="utf-8")
        return {"success": True, "replacements": 1}
    except (OSError, PermissionError) as e:
        return {"success": False, "error": f"patch error: {e}"}
    finally:
        await file_lock.release(path, llm_id)


# ── create_file ──────────────────────────────────────────────────────────────

async def create_file(
    path: str,
    content: str,
    file_lock: FileLock,
    workspace_root: Path,
    llm_id: str = "pipeline",
) -> dict:
    """Crée un nouveau fichier. Échec si un fichier du même nom existe déjà.

    Crée les dossiers parents si nécessaire.
    """
    resolved = _resolve(path, workspace_root)
    if resolved.exists():
        return {"success": False, "error": f"file already exists: {path}"}

    acquired = await file_lock.acquire(path, llm_id)
    if not acquired:
        return {
            "success": False,
            "error": f"file {path!r} is locked by another caller",
        }
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "bytes_written": len(content.encode("utf-8")),
        }
    except (OSError, PermissionError) as e:
        return {"success": False, "error": f"create error: {e}"}
    finally:
        await file_lock.release(path, llm_id)


# ── delete_file ──────────────────────────────────────────────────────────────

async def delete_file(
    path: str,
    file_lock: FileLock,
    workspace_root: Path,
    llm_id: str = "pipeline",
) -> dict:
    """Supprime un fichier du workspace."""
    resolved = _resolve(path, workspace_root)
    if not resolved.exists():
        return {"success": False, "error": f"file not found: {path}"}
    if not resolved.is_file():
        return {"success": False, "error": f"not a file: {path}"}

    acquired = await file_lock.acquire(path, llm_id)
    if not acquired:
        return {
            "success": False,
            "error": f"file {path!r} is locked by another caller",
        }
    try:
        resolved.unlink()
        return {"success": True}
    except (OSError, PermissionError) as e:
        return {"success": False, "error": f"delete error: {e}"}
    finally:
        await file_lock.release(path, llm_id)


# ── list_files ───────────────────────────────────────────────────────────────

async def list_files(
    path: str,
    workspace_root: Path,
    recursive: bool = False,
) -> dict:
    """Liste le contenu d'un dossier (non-récursif par défaut).

    Ignore les dossiers standards non-pertinents (``.git``, ``node_modules``,
    etc.). En mode récursif, les paths retournés sont relatifs au dossier
    demandé (pas à workspace_root).
    """
    resolved = _resolve(path, workspace_root)
    if not resolved.exists():
        return {"success": False, "error": f"directory not found: {path}"}
    if not resolved.is_dir():
        return {"success": False, "error": f"not a directory: {path}"}

    files: list[str] = []
    try:
        if recursive:
            for child in resolved.rglob("*"):
                if any(part in _EXCLUDED_DIRS for part in child.parts):
                    continue
                files.append(str(child.relative_to(resolved)))
        else:
            for child in sorted(resolved.iterdir()):
                if child.name in _EXCLUDED_DIRS:
                    continue
                files.append(child.name)
        return {"success": True, "files": files}
    except (OSError, PermissionError) as e:
        return {"success": False, "error": f"list error: {e}"}
