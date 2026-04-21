"""Tests pour backend/tools/file_ops.py (Plan 5A Task 4).

Toutes les opérations sont async, refusent les paths hors workspace_root via
``_resolve``, et utilisent un FileLock partagé pour éviter les conflits entre
Stage3Ground (read-only) et Stage5Execute (write).
"""
import pytest

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


# ── read_file ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_read_file_returns_content(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    result = await read_file("a.txt", workspace_root=tmp_path)
    assert result["success"] is True
    assert result["content"] == "hello"
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_read_file_truncates_if_over_max_bytes(tmp_path):
    (tmp_path / "big.txt").write_text("x" * 500)
    result = await read_file("big.txt", workspace_root=tmp_path, max_bytes=100)
    assert result["success"] is True
    assert len(result["content"]) == 100
    assert result["truncated"] is True


@pytest.mark.asyncio
async def test_read_file_missing_returns_success_false(tmp_path):
    result = await read_file("absent.txt", workspace_root=tmp_path)
    assert result["success"] is False
    assert "not found" in result["error"].lower() or "no such" in result["error"].lower()


@pytest.mark.asyncio
async def test_read_file_rejects_path_outside_workspace(tmp_path):
    # /etc/passwd est hors de tmp_path
    with pytest.raises(PathOutsideWorkspace):
        await read_file("/etc/passwd", workspace_root=tmp_path)


@pytest.mark.asyncio
async def test_read_file_rejects_parent_traversal(tmp_path):
    with pytest.raises(PathOutsideWorkspace):
        await read_file("../../etc/passwd", workspace_root=tmp_path)


# ── edit_file ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_file_writes_content(tmp_path):
    lock = FileLock()
    (tmp_path / "x.py").write_text("old")
    result = await edit_file("x.py", "new content", lock, workspace_root=tmp_path, llm_id="pipeline")
    assert result["success"] is True
    assert (tmp_path / "x.py").read_text() == "new content"


@pytest.mark.asyncio
async def test_edit_file_rejects_path_outside_workspace(tmp_path):
    lock = FileLock()
    with pytest.raises(PathOutsideWorkspace):
        await edit_file("/etc/passwd", "hacked", lock, workspace_root=tmp_path, llm_id="pipeline")


@pytest.mark.asyncio
async def test_edit_file_releases_lock_after_write(tmp_path):
    lock = FileLock()
    (tmp_path / "x.py").write_text("old")
    await edit_file("x.py", "v2", lock, workspace_root=tmp_path, llm_id="pipeline")
    # Un autre caller peut ré-acquérir le lock
    assert await lock.acquire("x.py", "other") is True


@pytest.mark.asyncio
async def test_edit_file_fails_if_locked_by_other_llm(tmp_path):
    lock = FileLock()
    (tmp_path / "x.py").write_text("old")
    await lock.acquire("x.py", "other")
    result = await edit_file("x.py", "v2", lock, workspace_root=tmp_path, llm_id="pipeline")
    assert result["success"] is False
    assert "locked" in result["error"].lower()


# ── patch_file ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_file_replaces_unique_occurrence(tmp_path):
    lock = FileLock()
    (tmp_path / "x.py").write_text("foo = 1\nbar = 2\n")
    result = await patch_file(
        "x.py", old_str="foo = 1", new_str="foo = 42",
        file_lock=lock, workspace_root=tmp_path, llm_id="pipeline",
    )
    assert result["success"] is True
    assert (tmp_path / "x.py").read_text() == "foo = 42\nbar = 2\n"


@pytest.mark.asyncio
async def test_patch_file_fails_if_old_str_not_unique(tmp_path):
    lock = FileLock()
    (tmp_path / "x.py").write_text("foo\nfoo\n")
    result = await patch_file(
        "x.py", old_str="foo", new_str="bar",
        file_lock=lock, workspace_root=tmp_path, llm_id="pipeline",
    )
    assert result["success"] is False
    assert "not unique" in result["error"].lower()


@pytest.mark.asyncio
async def test_patch_file_fails_if_old_str_absent(tmp_path):
    lock = FileLock()
    (tmp_path / "x.py").write_text("hello")
    result = await patch_file(
        "x.py", old_str="absent", new_str="x",
        file_lock=lock, workspace_root=tmp_path, llm_id="pipeline",
    )
    assert result["success"] is False
    assert "not found" in result["error"].lower()


# ── create_file ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_file_creates_new(tmp_path):
    lock = FileLock()
    result = await create_file(
        "new.py", "print('hi')", lock, workspace_root=tmp_path, llm_id="pipeline",
    )
    assert result["success"] is True
    assert (tmp_path / "new.py").read_text() == "print('hi')"


@pytest.mark.asyncio
async def test_create_file_fails_if_exists(tmp_path):
    lock = FileLock()
    (tmp_path / "x.py").write_text("already")
    result = await create_file(
        "x.py", "new", lock, workspace_root=tmp_path, llm_id="pipeline",
    )
    assert result["success"] is False
    assert "exists" in result["error"].lower()


@pytest.mark.asyncio
async def test_create_file_makes_parent_dirs(tmp_path):
    lock = FileLock()
    result = await create_file(
        "sub/nested/file.py", "content", lock, workspace_root=tmp_path, llm_id="pipeline",
    )
    assert result["success"] is True
    assert (tmp_path / "sub" / "nested" / "file.py").read_text() == "content"


# ── delete_file ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_file_removes_file(tmp_path):
    lock = FileLock()
    (tmp_path / "gone.py").write_text("bye")
    result = await delete_file(
        "gone.py", lock, workspace_root=tmp_path, llm_id="pipeline",
    )
    assert result["success"] is True
    assert not (tmp_path / "gone.py").exists()


@pytest.mark.asyncio
async def test_delete_file_missing_returns_success_false(tmp_path):
    lock = FileLock()
    result = await delete_file(
        "nope.py", lock, workspace_root=tmp_path, llm_id="pipeline",
    )
    assert result["success"] is False


# ── list_files ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_files_non_recursive(tmp_path):
    (tmp_path / "a.py").write_text("a")
    (tmp_path / "b.py").write_text("b")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.py").write_text("c")
    result = await list_files(".", workspace_root=tmp_path)
    assert result["success"] is True
    files = set(result["files"])
    assert "a.py" in files
    assert "b.py" in files
    assert "sub" in files  # dossier listé tel quel
    assert "sub/c.py" not in files  # non récursif


@pytest.mark.asyncio
async def test_list_files_ignores_excluded_dirs(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "venv").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "dist").mkdir()
    (tmp_path / "build").mkdir()
    (tmp_path / "ok.py").write_text("ok")
    result = await list_files(".", workspace_root=tmp_path)
    assert result["success"] is True
    files = set(result["files"])
    assert "ok.py" in files
    for excluded in (".git", "node_modules", "venv", "__pycache__", "dist", "build"):
        assert excluded not in files


@pytest.mark.asyncio
async def test_list_files_rejects_path_outside_workspace(tmp_path):
    with pytest.raises(PathOutsideWorkspace):
        await list_files("../../etc", workspace_root=tmp_path)


@pytest.mark.asyncio
async def test_list_files_missing_dir_returns_success_false(tmp_path):
    result = await list_files("absent_dir", workspace_root=tmp_path)
    assert result["success"] is False
