from unittest.mock import MagicMock, patch

import pytest

from backend.github_service import GitHubService, GitHubServiceError
from backend.roadmap import SubTask, Task


def _make_service() -> GitHubService:
    """Crée un GitHubService avec PyGithub mocké."""
    with patch("backend.github_service.Github") as MockGithub:
        mock_repo = MagicMock()
        MockGithub.return_value.get_repo.return_value = mock_repo
        svc = GitHubService(token="fake-token", repo_name="user/repo")
        svc._repo = mock_repo
        return svc


def test_github_service_raises_if_no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    with pytest.raises(GitHubServiceError, match="GITHUB_TOKEN"):
        GitHubService(repo_name="x/y")


def test_github_service_create_issue_returns_number():
    svc = _make_service()
    mock_issue = MagicMock()
    mock_issue.number = 42
    svc._repo.create_issue.return_value = mock_issue
    # Aucun label existant → _ensure_labels renvoie []
    svc._repo.get_labels.return_value = []

    task = Task(
        id="T-003",
        title="Endpoint login JWT",
        status="pending",
        assigned_to="minimax",
        subtasks=[
            SubTask(id="T-003-1", text="User model", done=False),
            SubTask(id="T-003-2", text="POST /auth/login", done=False),
        ],
        acceptance_criteria=["Login valide retourne 200", "Mauvais MDP retourne 401"],
        tests_required=["test_login_success()", "test_login_wrong_password()"],
        sprint="Sprint 1",
        estimated_complexity=5,
    )

    issue_number = svc.create_issue_from_task(task)
    assert issue_number == 42
    svc._repo.create_issue.assert_called_once()
    kwargs = svc._repo.create_issue.call_args[1]
    assert "Login valide retourne 200" in kwargs["body"]
    assert "T-003-1" in kwargs["body"]
    assert "[T-003]" in kwargs["title"]


def test_github_service_create_milestone():
    svc = _make_service()
    mock_ms = MagicMock()
    mock_ms.number = 1
    svc._repo.create_milestone.return_value = mock_ms

    ms_number = svc.create_milestone("Sprint 1", "2026-04-30")
    assert ms_number == 1
    svc._repo.create_milestone.assert_called_once()
    kwargs = svc._repo.create_milestone.call_args[1]
    assert kwargs["title"] == "Sprint 1"
    assert "due_on" in kwargs


def test_github_service_create_pr_links_issue():
    svc = _make_service()
    mock_pr = MagicMock()
    mock_pr.number = 10
    svc._repo.create_pull.return_value = mock_pr

    pr_number = svc.create_pr(
        title="[T-003] Endpoint login JWT (#42)",
        body="Closes #42",
        head_branch="feature/T-003-login-jwt",
        base_branch="main",
    )
    assert pr_number == 10
    kwargs = svc._repo.create_pull.call_args[1]
    assert kwargs["head"] == "feature/T-003-login-jwt"
    assert "Closes #42" in kwargs["body"]


def test_github_service_close_issue():
    svc = _make_service()
    mock_issue = MagicMock()
    svc._repo.get_issue.return_value = mock_issue

    svc.close_issue(42, "✅ CI vert. Tous les tests passent.")
    mock_issue.create_comment.assert_called_once()
    mock_issue.edit.assert_called_with(state="closed")


def test_github_service_comment_and_label_issue():
    svc = _make_service()
    mock_issue = MagicMock()
    svc._repo.get_issue.return_value = mock_issue
    svc.comment_issue(7, "retry")
    svc.add_label_to_issue(7, "blocked")
    mock_issue.create_comment.assert_called_with("retry")
    mock_issue.add_to_labels.assert_called_with("blocked")


def test_github_service_generate_actions_yaml_contains_ticket_extraction():
    svc = _make_service()
    yaml_content = svc.generate_ticket_validation_workflow()
    assert "grep -oP" in yaml_content
    assert "gh issue close" in yaml_content
    assert "gh issue comment" in yaml_content
    assert "GITHUB_TOKEN" in yaml_content


def test_github_service_get_pr_check_status_pending():
    """Aucun run terminé → 'pending'."""
    svc = _make_service()
    mock_pr = MagicMock()
    mock_pr.head.sha = "abc"
    svc._repo.get_pull.return_value = mock_pr
    mock_commit = MagicMock()
    mock_commit.get_check_runs.return_value = []
    svc._repo.get_commit.return_value = mock_commit
    assert svc.get_pr_check_status(10) == "pending"


def test_github_service_get_pr_check_status_success():
    """Tous les runs terminés avec conclusion='success' → 'success'."""
    svc = _make_service()
    mock_pr = MagicMock()
    mock_pr.head.sha = "abc"
    svc._repo.get_pull.return_value = mock_pr

    run = MagicMock(status="completed", conclusion="success")
    mock_commit = MagicMock()
    mock_commit.get_check_runs.return_value = [run]
    svc._repo.get_commit.return_value = mock_commit
    assert svc.get_pr_check_status(10) == "success"


def test_github_service_get_pr_check_status_action_required_stays_pending():
    """#IMP3 : action_required = approbation humaine, pas un failure."""
    svc = _make_service()
    mock_pr = MagicMock()
    mock_pr.head.sha = "abc"
    svc._repo.get_pull.return_value = mock_pr
    run = MagicMock(status="completed", conclusion="action_required")
    mock_commit = MagicMock()
    mock_commit.get_check_runs.return_value = [run]
    svc._repo.get_commit.return_value = mock_commit
    assert svc.get_pr_check_status(10) == "pending"


def test_github_service_get_pr_check_status_failure():
    """Un run avec conclusion='failure' → 'failure' (échec global)."""
    svc = _make_service()
    mock_pr = MagicMock()
    mock_pr.head.sha = "abc"
    svc._repo.get_pull.return_value = mock_pr

    ok = MagicMock(status="completed", conclusion="success")
    ko = MagicMock(status="completed", conclusion="failure")
    mock_commit = MagicMock()
    mock_commit.get_check_runs.return_value = [ok, ko]
    svc._repo.get_commit.return_value = mock_commit
    assert svc.get_pr_check_status(10) == "failure"


def test_ensure_labels_caches_get_labels_call():
    """Cache : get_labels() appelé 1× même sur N create_issue successifs."""
    svc = _make_service()
    # On simule un repo avec 2 labels dispo
    sprint1_label = MagicMock(); sprint1_label.name = "sprint-1"
    pending_label = MagicMock(); pending_label.name = "pending"
    svc._repo.get_labels.return_value = [sprint1_label, pending_label]
    svc._repo.create_issue = MagicMock(return_value=MagicMock(number=1))

    task = Task(
        id="T-001", title="X", status="pending", assigned_to="",
        sprint="Sprint 1", estimated_complexity=3,
    )
    svc.create_issue_from_task(task)
    svc.create_issue_from_task(task)
    svc.create_issue_from_task(task)
    # get_labels ne doit être appelé qu'une seule fois (cache instance).
    assert svc._repo.get_labels.call_count == 1


def test_github_service_write_workflow_file(tmp_path):
    svc = _make_service()
    svc.write_workflow_file(repo_path=str(tmp_path))
    target = tmp_path / ".github" / "workflows" / "ticket-validation.yml"
    assert target.exists()
    content = target.read_text()
    assert "Ticket Validation" in content
