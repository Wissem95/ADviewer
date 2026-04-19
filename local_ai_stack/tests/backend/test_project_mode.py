import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.project_mode import CdC, ProjectMode, SprintPlan
from backend.roadmap import ProjectRoadmap, Task


def _sample_cdc_json() -> str:
    return json.dumps(
        {
            "project_name": "todo-app",
            "title": "Application Todo",
            "context": "Gestion de tâches personnelles.",
            "objectives": ["Créer des tâches", "Les marquer comme terminées"],
            "features": {
                "must_have": [
                    {"id": "F-001", "title": "Créer une tâche", "description": "POST /tasks", "complexity": 3},
                    {"id": "F-002", "title": "Lister les tâches", "description": "GET /tasks", "complexity": 2},
                ],
                "should_have": [],
                "could_have": [],
            },
            "stack": {
                "backend": "FastAPI",
                "frontend": "React",
                "database": "SQLite",
                "auth": "JWT",
                "deployment": "Docker",
            },
            "constraints": ["Pas de dépendances externes"],
            "success_criteria": ["CRUD complet", "CI vert"],
            "estimated_sprints": 1,
        }
    )


def _sample_sprint_json() -> str:
    return json.dumps(
        [
            {
                "sprint_name": "Sprint 1",
                "tickets": [
                    {
                        "id": "T-001",
                        "title": "Endpoint POST /tasks",
                        "description": "Crée une tâche",
                        "acceptance_criteria": ["Retourne 201", "Body JSON valide"],
                        "subtasks": [{"id": "T-001-1", "text": "Model Task", "done": False}],
                        "tests_required": ["test_create_task()"],
                        "blocked_by": [],
                        "estimated_complexity": 3,
                    }
                ],
            }
        ]
    )


def _make_project_mode() -> ProjectMode:
    llm_manager = MagicMock()
    ws = AsyncMock()
    ws.emit_step = AsyncMock()
    github = MagicMock()
    github.create_issue_from_task = MagicMock(return_value=42)
    github.create_milestone = MagicMock(return_value=1)
    github.write_workflow_file = MagicMock()
    git_svc = MagicMock()
    git_svc.get_current_branch = MagicMock(return_value="main")
    return ProjectMode(
        llm_manager=llm_manager,
        ws_streamer=ws,
        github_service=github,
        git_service=git_svc,
    )


def test_cdc_parse_from_json():
    pm = _make_project_mode()
    cdc = pm._parse_cdc(_sample_cdc_json())
    assert cdc.project_name == "todo-app"
    assert len(cdc.features_must) == 2
    assert cdc.estimated_sprints == 1


def test_cdc_parse_invalid_json_raises():
    pm = _make_project_mode()
    with pytest.raises(ValueError, match="CdC JSON invalide"):
        pm._parse_cdc("pas du json valide ici")


def test_sprint_parse_from_json():
    pm = _make_project_mode()
    sprints = pm._parse_sprints(_sample_sprint_json())
    assert len(sprints) == 1
    assert sprints[0].sprint_name == "Sprint 1"
    assert len(sprints[0].tickets) == 1
    assert sprints[0].tickets[0].id == "T-001"


@pytest.mark.asyncio
async def test_generate_cdc_calls_architecture():
    pm = _make_project_mode()
    pm.llm.call_with_fallback = AsyncMock(return_value=_sample_cdc_json())
    cdc = await pm.generate_cdc("Je veux une app todo simple")
    assert cdc.project_name == "todo-app"
    kwargs = pm.llm.call_with_fallback.call_args[1]
    assert kwargs["role"].value == "architecture"


@pytest.mark.asyncio
async def test_generate_sprints_calls_r1():
    pm = _make_project_mode()
    pm.llm.call_with_fallback = AsyncMock(return_value=_sample_sprint_json())
    cdc = pm._parse_cdc(_sample_cdc_json())
    sprints = await pm.generate_sprints(cdc)
    assert len(sprints) == 1


@pytest.mark.asyncio
async def test_create_github_structure_returns_roadmap():
    pm = _make_project_mode()
    cdc = pm._parse_cdc(_sample_cdc_json())
    sprints = pm._parse_sprints(_sample_sprint_json())
    roadmap = await pm.create_github_structure(cdc, sprints)
    assert isinstance(roadmap, ProjectRoadmap)
    assert len(roadmap.tasks) == 1
    assert roadmap.tasks[0].github_issue == 42
    pm.github.write_workflow_file.assert_called_once()


def test_is_project_request():
    pm = _make_project_mode()
    assert pm.is_project_request("crée une app de gestion de stocks") is True
    assert pm.is_project_request("je veux construire un blog") is True
    assert pm.is_project_request("corrige le typo dans bouton.py") is False
    assert pm.is_project_request("génère le CdC pour mon projet") is True


@pytest.mark.asyncio
async def test_execute_ticket_c9_restore_initial_branch():
    """C9 : execute_ticket doit mémoriser la branche initiale et y revenir."""
    pm = _make_project_mode()
    pm.git.get_current_branch = MagicMock(return_value="develop")
    pm.git.get_modified_files = MagicMock(return_value=["foo.py"])
    pm.git.stage = MagicMock()
    pm.git.commit = MagicMock()
    pm.git.push = MagicMock()
    pm.git.create_branch = MagicMock()
    pm.git.checkout = MagicMock()

    task = Task(
        id="T-001",
        title="Endpoint",
        status="pending",
        assigned_to="minimax",
        github_issue=42,
    )
    roadmap = ProjectRoadmap(project="demo")
    roadmap.tasks.append(task)

    fake_result = MagicMock(content="ok")

    async def fake_coro():
        return fake_result

    success = await pm.execute_ticket(task, roadmap, fake_coro())
    assert success is True
    # C9 : checkout appelé avec la branche initiale exacte, pas repo.heads[0].
    pm.git.checkout.assert_any_call("develop")


@pytest.mark.asyncio
async def test_execute_ticket_c10_push_uses_branch_name_directly():
    """C10 : push(branch=branch_name) et pas de re-split en "feature/..."."""
    pm = _make_project_mode()
    pm.git.get_current_branch = MagicMock(return_value="main")
    pm.git.get_modified_files = MagicMock(return_value=["a.py"])
    pm.git.stage = MagicMock()
    pm.git.commit = MagicMock()
    pm.git.push = MagicMock()
    pm.git.create_branch = MagicMock()
    pm.git.checkout = MagicMock()

    task = Task(id="T-007", title="Login", status="pending", github_issue=99)
    roadmap = ProjectRoadmap(project="demo")
    roadmap.tasks.append(task)

    async def fake_coro():
        return MagicMock(content="ok")

    await pm.execute_ticket(task, roadmap, fake_coro())
    push_kwargs = pm.git.push.call_args[1]
    expected_branch = "feature/t-007-login"
    assert push_kwargs["branch"] == expected_branch
    assert not push_kwargs["branch"].startswith("feature/feature/")


@pytest.mark.asyncio
async def test_execute_ticket_marks_done_on_success():
    pm = _make_project_mode()
    pm.git.get_current_branch = MagicMock(return_value="main")
    pm.git.get_modified_files = MagicMock(return_value=[])
    pm.git.create_branch = MagicMock()
    pm.git.checkout = MagicMock()

    task = Task(id="T-007", title="Login", status="pending", github_issue=99)
    roadmap = ProjectRoadmap(project="demo")
    roadmap.tasks.append(task)

    async def fake_coro():
        return MagicMock(content="ok")

    await pm.execute_ticket(task, roadmap, fake_coro())
    assert roadmap.tasks[0].status == "done"
