import subprocess

import pytest

from backend.git_service import GitService


@pytest.fixture
def git_repo(tmp_path):
    """Crée un vrai repo git temporaire avec un commit initial."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    (tmp_path / "README.md").write_text("# Test repo")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


def test_git_service_get_current_branch(git_repo):
    svc = GitService(repo_path=str(git_repo))
    assert svc.get_current_branch() in ("main", "master")


def test_git_service_create_branch(git_repo):
    svc = GitService(repo_path=str(git_repo))
    svc.create_branch("feature/T-001-login")
    assert svc.get_current_branch() == "feature/T-001-login"


def test_git_service_get_modified_files(git_repo):
    svc = GitService(repo_path=str(git_repo))
    (git_repo / "auth.py").write_text("def login(): pass")
    modified = svc.get_modified_files()
    assert "auth.py" in modified


def test_git_service_stage_and_commit(git_repo):
    svc = GitService(repo_path=str(git_repo))
    (git_repo / "auth.py").write_text("def login(): pass")
    svc.stage(["auth.py"])
    svc.commit("[T-001] Endpoint login JWT")
    assert "T-001" in svc.get_last_commit_message()


def test_git_service_get_staged_diff(git_repo):
    svc = GitService(repo_path=str(git_repo))
    (git_repo / "auth.py").write_text("def login(): pass\n")
    svc.stage(["auth.py"])
    diff = svc.get_staged_diff()
    assert "auth.py" in diff or "login" in diff


def test_git_service_checkout_returns_to_default_branch(git_repo):
    svc = GitService(repo_path=str(git_repo))
    default = svc.get_current_branch()
    svc.create_branch("feature/T-002-test")
    assert svc.get_current_branch() == "feature/T-002-test"
    svc.checkout(default)
    assert svc.get_current_branch() == default


def test_git_service_status_for_ui(git_repo):
    svc = GitService(repo_path=str(git_repo))
    (git_repo / "a.txt").write_text("hello")
    (git_repo / "b.txt").write_text("world")
    status = svc.get_status_for_ui()
    assert status["branch"] in ("main", "master")
    assert status["modifiedFiles"] == 2


def test_git_service_invalid_repo_raises(tmp_path):
    from backend.git_service import GitServiceError

    with pytest.raises(GitServiceError):
        GitService(repo_path=str(tmp_path / "does-not-exist"))


def test_create_or_reset_branch_idempotent_on_existing(git_repo):
    """#CRIT1 : re-créer une branche existante doit la reset, pas échouer."""
    svc = GitService(repo_path=str(git_repo))
    default = svc.get_current_branch()
    svc.create_or_reset_branch("feature/retry")
    assert svc.get_current_branch() == "feature/retry"
    # Retour et re-création : doit passer (alors que create_branch échouerait).
    svc.checkout(default)
    svc.create_or_reset_branch("feature/retry")
    assert svc.get_current_branch() == "feature/retry"


def test_get_current_branch_handles_detached_head(git_repo):
    """#IMP2 : detached HEAD → retourne HEAD@<short sha>, ne plante pas."""
    svc = GitService(repo_path=str(git_repo))
    sha = svc.repo.head.commit.hexsha
    svc.repo.git.checkout(sha)  # detached HEAD
    branch = svc.get_current_branch()
    assert branch.startswith("HEAD@")
    assert sha.startswith(branch.split("@", 1)[1])


def test_stage_handles_deletions(git_repo):
    """#IMP1 : stage doit gérer les fichiers supprimés via index.remove."""
    svc = GitService(repo_path=str(git_repo))
    # README.md existe depuis le commit initial (fixture)
    (git_repo / "README.md").unlink()
    # Le fichier absent doit être stagé comme deleted, pas crash.
    svc.stage(["README.md"])
    svc.commit("chore: delete README")
    # Après commit, il n'est plus dans l'index ni dans le disque.
    assert not (git_repo / "README.md").exists()
    # Et le HEAD tree ne contient plus README.md.
    tree_files = {b.path for b in svc.repo.head.commit.tree.traverse()}
    assert "README.md" not in tree_files
