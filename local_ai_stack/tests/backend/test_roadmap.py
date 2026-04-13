# tests/backend/test_roadmap.py
import pytest
from pathlib import Path
from backend.roadmap import ProjectRoadmap, Task, SubTask, Decision


def _make_roadmap() -> ProjectRoadmap:
    rm = ProjectRoadmap(project="test-project")
    rm.tasks = [
        Task(id="T-001", title="Setup base", status="done", assigned_to="minimax"),
        Task(
            id="T-002",
            title="Endpoint login JWT",
            status="in_progress",
            assigned_to="minimax",
            subtasks=[
                SubTask(id="T-002-1", text="User model", done=True),
                SubTask(id="T-002-2", text="POST /auth/login", done=False),
            ],
            github_issue=42,
            sprint="Sprint 1",
            estimated_complexity=5,
        ),
    ]
    rm.do_not_touch = ["_validate_scope()", "Redis config"]
    rm.decisions = [Decision(by="deepseek_r1", content="auth.py splitté en 3")]
    return rm


def test_roadmap_get_done_summary():
    rm = _make_roadmap()
    summary = rm.get_done_summary()
    assert "T-001" in summary
    assert "Setup base" in summary
    assert "Terminé" in summary


def test_roadmap_get_do_not_touch():
    rm = _make_roadmap()
    txt = rm.get_do_not_touch()
    assert "_validate_scope()" in txt
    assert "Redis config" in txt


def test_roadmap_get_do_not_touch_empty():
    rm = ProjectRoadmap(project="empty")
    txt = rm.get_do_not_touch()
    assert "aucune restriction" in txt.lower()


def test_roadmap_get_locked_files_empty():
    rm = _make_roadmap()
    txt = rm.get_locked_files()
    assert "Aucun" in txt or "aucun" in txt


def test_roadmap_lock_and_unlock_file():
    rm = _make_roadmap()
    rm.lock_file("auth.py", "minimax")
    txt = rm.get_locked_files()
    assert "auth.py" in txt
    assert "minimax" in txt
    rm.unlock_file("auth.py")
    txt2 = rm.get_locked_files()
    assert "Aucun" in txt2 or "aucun" in txt2


def test_roadmap_update_task_status():
    rm = _make_roadmap()
    rm.update_task_status("T-002", "done")
    task = next(t for t in rm.tasks if t.id == "T-002")
    assert task.status == "done"


def test_roadmap_mark_subtask_done():
    rm = _make_roadmap()
    rm.mark_subtask_done("T-002", "T-002-2")
    task = next(t for t in rm.tasks if t.id == "T-002")
    st = next(st for st in task.subtasks if st.id == "T-002-2")
    assert st.done is True


def test_roadmap_get_relevant_decisions():
    rm = _make_roadmap()
    txt = rm.get_relevant_decisions("implémenter auth")
    assert "auth.py splitté" in txt
    assert "deepseek_r1" in txt


def test_roadmap_add_decision():
    rm = ProjectRoadmap(project="test")
    rm.add_decision("minimax", "Utiliser JWT avec python-jose")
    assert len(rm.decisions) == 1
    assert rm.decisions[0].by == "minimax"


def test_roadmap_json_roundtrip():
    rm = _make_roadmap()
    serialized = rm.to_json()
    restored = ProjectRoadmap.from_json(serialized)
    assert restored.project == "test-project"
    assert len(restored.tasks) == 2
    assert restored.tasks[1].subtasks[0].done is True
    assert restored.tasks[1].github_issue == 42
    assert restored.decisions[0].content == "auth.py splitté en 3"


def test_roadmap_save_and_load(tmp_path):
    rm = _make_roadmap()
    path = tmp_path / "roadmap.json"
    rm.save(path)
    assert path.exists()
    loaded = ProjectRoadmap.load(path)
    assert loaded.project == "test-project"
    assert loaded.do_not_touch == ["_validate_scope()", "Redis config"]


def test_roadmap_get_next_pending_task_respects_dependencies():
    rm = ProjectRoadmap(project="test")
    rm.tasks = [
        Task(id="T-001", title="Base", status="pending", blocked_by=[]),
        Task(id="T-002", title="Après base", status="pending", blocked_by=["T-001"]),
    ]
    # T-001 pas encore done → T-001 retourné (pas T-002)
    next_task = rm.get_next_pending_task()
    assert next_task.id == "T-001"

    rm.update_task_status("T-001", "done")
    next_task = rm.get_next_pending_task()
    assert next_task.id == "T-002"
