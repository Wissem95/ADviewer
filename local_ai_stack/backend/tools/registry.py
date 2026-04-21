"""Registry des tools exposés aux LLMs (Plan 5A Task 5).

Expose deux schemas JSON compatibles OpenAI / Anthropic function-calling :
- ``TOOLS_SCHEMA_READ`` : lecture seule, utilisé par Stage3Ground et les
  reviewers (Stage8, Stage9).
- ``TOOLS_SCHEMA_WRITE`` : read + write, utilisé par Stage5Execute.

La fonction ``execute_tool`` est le dispatcher appelé par l'orchestrator
quand un LLM répond avec un ``tool_call``. Elle transforme les exceptions
``PathOutsideWorkspace`` en ``{success: False, error: ...}`` pour que le
LLM puisse corriger son approche dans l'itération suivante sans crasher
la boucle tool-calling.
"""
from pathlib import Path
from typing import Any

from backend.file_lock import FileLock
from backend.tools.exceptions import PathOutsideWorkspace, ToolError
from backend.tools.file_ops import (
    create_file,
    delete_file,
    edit_file,
    list_files,
    patch_file,
    read_file,
)
from backend.tools.search import grep_codebase


# ── Schemas ──────────────────────────────────────────────────────────────────

_READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": (
        "Lit le contenu d'un fichier relatif au workspace. Tronque à "
        "max_bytes (défaut 100_000). Retourne success, content, truncated."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Chemin relatif au workspace_root.",
            },
            "max_bytes": {
                "type": "integer",
                "default": 100_000,
                "description": "Taille max lue. Au-delà, tronqué.",
            },
        },
        "required": ["path"],
    },
}

_LIST_FILES_SCHEMA = {
    "name": "list_files",
    "description": (
        "Liste le contenu d'un dossier. Ignore .git, node_modules, venv, "
        "__pycache__, dist, build. Non-récursif par défaut."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "recursive": {"type": "boolean", "default": False},
        },
        "required": ["path"],
    },
}

_GREP_SCHEMA = {
    "name": "grep_codebase",
    "description": (
        "Recherche un pattern regex dans les fichiers du workspace. "
        "Retourne les matches sous forme de liste {file, line, excerpt}."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex à matcher par ligne.",
            },
            "path_glob": {
                "type": "string",
                "default": "**/*",
                "description": "Glob des fichiers à scanner.",
            },
            "max_results": {
                "type": "integer",
                "default": 50,
            },
        },
        "required": ["pattern"],
    },
}

_EDIT_FILE_SCHEMA = {
    "name": "edit_file",
    "description": (
        "Remplace intégralement le contenu d'un fichier. Acquiert le "
        "file_lock avant écriture. Échec si locked par un autre caller."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
}

_PATCH_FILE_SCHEMA = {
    "name": "patch_file",
    "description": (
        "Edit chirurgical : remplace old_str par new_str. Échec si old_str "
        "n'est pas unique dans le fichier (garantie anti-erreur)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_str": {
                "type": "string",
                "description": "Chaîne à chercher (doit être unique).",
            },
            "new_str": {"type": "string"},
        },
        "required": ["path", "old_str", "new_str"],
    },
}

_CREATE_FILE_SCHEMA = {
    "name": "create_file",
    "description": (
        "Crée un nouveau fichier. Échec si existe déjà. Les dossiers "
        "parents sont créés automatiquement."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
}

_DELETE_FILE_SCHEMA = {
    "name": "delete_file",
    "description": "Supprime un fichier du workspace.",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}


TOOLS_SCHEMA_READ: list[dict] = [
    _READ_FILE_SCHEMA,
    _LIST_FILES_SCHEMA,
    _GREP_SCHEMA,
]

TOOLS_SCHEMA_WRITE: list[dict] = TOOLS_SCHEMA_READ + [
    _EDIT_FILE_SCHEMA,
    _PATCH_FILE_SCHEMA,
    _CREATE_FILE_SCHEMA,
    _DELETE_FILE_SCHEMA,
]


# ── Dispatcher ───────────────────────────────────────────────────────────────

async def execute_tool(
    name: str,
    args: dict[str, Any],
    file_lock: FileLock,
    workspace_root: Path,
    llm_id: str = "pipeline",
) -> dict:
    """Dispatche un tool_call vers l'implémentation correspondante.

    Contrat :
    - Retourne toujours un dict avec au moins ``success: bool``.
    - ``PathOutsideWorkspace`` → ``{success: False, error: "... workspace ..."}``
      pour permettre au LLM de corriger sans crasher la boucle.
    - Tool inconnu → ``{success: False, error: "unknown tool ..."}``.
    - Pour grep_codebase, retourne ``{success, matches}`` (homogénéise la
      shape avec les autres tools).
    """
    try:
        if name == "read_file":
            return await read_file(
                path=args["path"],
                workspace_root=workspace_root,
                max_bytes=args.get("max_bytes", 100_000),
            )
        if name == "list_files":
            return await list_files(
                path=args["path"],
                workspace_root=workspace_root,
                recursive=args.get("recursive", False),
            )
        if name == "grep_codebase":
            matches = await grep_codebase(
                pattern=args["pattern"],
                workspace_root=workspace_root,
                path_glob=args.get("path_glob", "**/*"),
                max_results=args.get("max_results", 50),
            )
            return {"success": True, "matches": matches}
        if name == "edit_file":
            return await edit_file(
                path=args["path"],
                content=args["content"],
                file_lock=file_lock,
                workspace_root=workspace_root,
                llm_id=llm_id,
            )
        if name == "patch_file":
            return await patch_file(
                path=args["path"],
                old_str=args["old_str"],
                new_str=args["new_str"],
                file_lock=file_lock,
                workspace_root=workspace_root,
                llm_id=llm_id,
            )
        if name == "create_file":
            return await create_file(
                path=args["path"],
                content=args["content"],
                file_lock=file_lock,
                workspace_root=workspace_root,
                llm_id=llm_id,
            )
        if name == "delete_file":
            return await delete_file(
                path=args["path"],
                file_lock=file_lock,
                workspace_root=workspace_root,
                llm_id=llm_id,
            )
        return {"success": False, "error": f"unknown tool: {name}"}
    except PathOutsideWorkspace as e:
        return {"success": False, "error": f"path outside workspace: {e}"}
    except KeyError as e:
        return {"success": False, "error": f"missing required arg: {e}"}
    except ToolError as e:
        return {"success": False, "error": str(e)}
