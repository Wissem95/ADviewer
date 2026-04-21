"""Tests pour backend/tools/search.py (Plan 5A Task 5).

``grep_codebase`` est l'outil read-only donné au Stage3Ground pour retrouver
les appelants d'une fonction, les patterns existants, etc. Il ignore les
mêmes dossiers que ``list_files`` et respecte le workspace_root.
"""
import pytest

from backend.tools.exceptions import PathOutsideWorkspace
from backend.tools.search import grep_codebase


@pytest.mark.asyncio
async def test_grep_finds_matches_with_file_line_excerpt(tmp_path):
    (tmp_path / "a.py").write_text("def foo():\n    pass\n")
    (tmp_path / "b.py").write_text("foo()\nbar()\n")
    results = await grep_codebase(
        pattern=r"\bfoo\b",
        path_glob="**/*.py",
        workspace_root=tmp_path,
    )
    assert len(results) == 2
    for r in results:
        assert "file" in r
        assert "line" in r
        assert "excerpt" in r
        assert r["line"] >= 1


@pytest.mark.asyncio
async def test_grep_returns_empty_list_if_no_match(tmp_path):
    (tmp_path / "a.py").write_text("hello")
    results = await grep_codebase(
        pattern="absent_pattern", workspace_root=tmp_path,
    )
    assert results == []


@pytest.mark.asyncio
async def test_grep_respects_path_glob(tmp_path):
    (tmp_path / "a.py").write_text("foo")
    (tmp_path / "b.ts").write_text("foo")
    py_results = await grep_codebase(
        pattern="foo", path_glob="**/*.py", workspace_root=tmp_path,
    )
    assert len(py_results) == 1
    assert py_results[0]["file"].endswith(".py")


@pytest.mark.asyncio
async def test_grep_ignores_excluded_dirs(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("foo")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("foo")
    (tmp_path / "venv").mkdir()
    (tmp_path / "venv" / "lib.py").write_text("foo")
    (tmp_path / "src.py").write_text("foo")
    results = await grep_codebase(
        pattern="foo", workspace_root=tmp_path,
    )
    files = [r["file"] for r in results]
    assert "src.py" in files
    for excluded in ("node_modules/x.js", ".git/HEAD", "venv/lib.py"):
        assert excluded not in files


@pytest.mark.asyncio
async def test_grep_respects_max_results(tmp_path):
    for i in range(20):
        (tmp_path / f"f{i}.py").write_text("foo\n")
    results = await grep_codebase(
        pattern="foo", workspace_root=tmp_path, max_results=5,
    )
    assert len(results) == 5


@pytest.mark.asyncio
async def test_grep_handles_binary_files_gracefully(tmp_path):
    """Fichier avec bytes non-UTF8 ne doit pas crasher le grep."""
    (tmp_path / "bin.dat").write_bytes(b"\xff\xfe\x00binary")
    (tmp_path / "text.py").write_text("hello world")
    # N'explose pas, retourne simplement les matches du fichier texte
    results = await grep_codebase(
        pattern="hello", workspace_root=tmp_path,
    )
    assert len(results) == 1
    assert results[0]["file"] == "text.py"


@pytest.mark.asyncio
async def test_grep_rejects_path_outside_workspace(tmp_path):
    # path_glob absolu hors workspace est refusé via workspace_root check
    # (le glob est appliqué depuis workspace_root donc un ../../ est traité
    # comme un glob curieux qui ne match rien ; par contre un path_glob
    # explicitement absolu doit déclencher PathOutsideWorkspace côté résolution
    # si un jour on l'ajoute, pour l'instant on vérifie que workspace_root
    # inexistant lève FileNotFoundError propre)
    with pytest.raises(PathOutsideWorkspace):
        await grep_codebase(
            pattern="x",
            workspace_root=tmp_path,
            start_path="../../etc",
        )
