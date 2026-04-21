"""Tests pour backend/tools/registry.py (Plan 5A Task 5).

Le registry expose les schemas JSON (format OpenAI/Anthropic function-calling)
et le dispatcher ``execute_tool`` que l'orchestrator appelle quand un LLM
répond avec un tool_call.

Garanties testées :
- TOOLS_SCHEMA_READ contient exactement les tools read-only (pas d'écriture).
- TOOLS_SCHEMA_WRITE est un surensemble (read + write).
- execute_tool dispatche correctement par nom.
- Tool inconnu → {success: False, error: "..."} sans crash.
"""
import pytest

from backend.file_lock import FileLock
from backend.tools.registry import (
    TOOLS_SCHEMA_READ,
    TOOLS_SCHEMA_WRITE,
    execute_tool,
)


# ── TOOLS_SCHEMA_READ ───────────────────────────────────────────────────────

def test_schema_read_has_expected_tools():
    names = {t["name"] for t in TOOLS_SCHEMA_READ}
    assert {"read_file", "list_files", "grep_codebase"} <= names


def test_schema_read_does_not_contain_write_tools():
    """Garantit qu'on ne peut pas appeler edit_file via le schema read-only."""
    names = {t["name"] for t in TOOLS_SCHEMA_READ}
    for writer in ("edit_file", "patch_file", "create_file", "delete_file"):
        assert writer not in names, f"{writer} ne doit pas être dans SCHEMA_READ"


def test_schema_entries_have_required_fields():
    """Chaque entry respecte le format OpenAI function-calling."""
    for schema in (TOOLS_SCHEMA_READ, TOOLS_SCHEMA_WRITE):
        for tool in schema:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            input_schema = tool["input_schema"]
            assert input_schema["type"] == "object"
            assert "properties" in input_schema


# ── TOOLS_SCHEMA_WRITE ──────────────────────────────────────────────────────

def test_schema_write_is_superset_of_read():
    read_names = {t["name"] for t in TOOLS_SCHEMA_READ}
    write_names = {t["name"] for t in TOOLS_SCHEMA_WRITE}
    assert read_names <= write_names


def test_schema_write_contains_all_write_tools():
    names = {t["name"] for t in TOOLS_SCHEMA_WRITE}
    for writer in ("edit_file", "patch_file", "create_file", "delete_file"):
        assert writer in names


# ── execute_tool ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_tool_dispatches_read_file(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    lock = FileLock()
    result = await execute_tool(
        "read_file",
        {"path": "a.txt"},
        file_lock=lock,
        workspace_root=tmp_path,
    )
    assert result["success"] is True
    assert "hello" in result["content"]


@pytest.mark.asyncio
async def test_execute_tool_dispatches_edit_file(tmp_path):
    (tmp_path / "x.py").write_text("old")
    lock = FileLock()
    result = await execute_tool(
        "edit_file",
        {"path": "x.py", "content": "new"},
        file_lock=lock,
        workspace_root=tmp_path,
    )
    assert result["success"] is True
    assert (tmp_path / "x.py").read_text() == "new"


@pytest.mark.asyncio
async def test_execute_tool_dispatches_grep_codebase(tmp_path):
    (tmp_path / "a.py").write_text("def foo(): pass\n")
    lock = FileLock()
    result = await execute_tool(
        "grep_codebase",
        {"pattern": "foo"},
        file_lock=lock,
        workspace_root=tmp_path,
    )
    assert result["success"] is True
    assert len(result["matches"]) == 1
    assert result["matches"][0]["line"] == 1


@pytest.mark.asyncio
async def test_execute_tool_unknown_returns_success_false(tmp_path):
    lock = FileLock()
    result = await execute_tool(
        "unknown_tool_xyz",
        {},
        file_lock=lock,
        workspace_root=tmp_path,
    )
    assert result["success"] is False
    assert "unknown" in result["error"].lower()


@pytest.mark.asyncio
async def test_execute_tool_propagates_path_outside_workspace(tmp_path):
    """Tentative d'accès hors workspace → {success: False, error: ...}.

    L'orchestrator n'a pas besoin de catch l'exception : execute_tool la
    convertit en result pour que le LLM puisse corriger son approche.
    """
    lock = FileLock()
    result = await execute_tool(
        "read_file",
        {"path": "/etc/passwd"},
        file_lock=lock,
        workspace_root=tmp_path,
    )
    assert result["success"] is False
    assert "workspace" in result["error"].lower()
