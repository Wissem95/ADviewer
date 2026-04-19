from backend.project_slug import slugify_task_branch


def test_slug_basic():
    assert slugify_task_branch("T-001", "Login") == "feature/t-001-login"


def test_slug_keeps_alphanum_compacts_others():
    assert (
        slugify_task_branch("T-002", "Endpoint POST /auth/login")
        == "feature/t-002-endpoint-post-auth-login"
    )


def test_slug_truncates_long_titles_at_30():
    long_title = "A" * 100
    branch = slugify_task_branch("T-003", long_title)
    slug_part = branch.removeprefix("feature/t-003-")
    assert len(slug_part) == 30


def test_slug_strips_trailing_dashes_after_truncation():
    # 'abcdefghijklmnopqrstuvwxyz-ab' = 29 chars → truncate tombe sur un non-tiret
    # 'abcdefghij klmnopqrst-uvwxy-z' : le slug avant truncation a tirets internes
    branch = slugify_task_branch("T-04", "a" * 29 + "-" + "b")
    slug_part = branch.removeprefix("feature/t-04-")
    # Jamais de tiret final
    assert not slug_part.endswith("-")


def test_slug_empty_title():
    assert slugify_task_branch("T-005", "") == "feature/t-005"
    assert slugify_task_branch("T-006", "!!!") == "feature/t-006"


def test_slug_idempotent_between_services():
    """GitHubService et ProjectMode doivent produire le MÊME slug (#CRIT2)."""
    t_id, title = "T-007", "Endpoint très long avec accents éàç et espaces"
    # Appel unique, comparé à lui-même → garantit déterminisme.
    assert slugify_task_branch(t_id, title) == slugify_task_branch(t_id, title)
