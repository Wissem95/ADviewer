import pytest
from pathlib import Path
from backend.context_builder import (
    build_context_for,
    count_tokens,
    load_project_conventions,
)
from backend.roadmap import ProjectRoadmap, Task, Decision


def _make_roadmap_with_data() -> ProjectRoadmap:
    rm = ProjectRoadmap(project="my-project")
    rm.tasks = [Task(id="T-001", title="Setup", status="done")]
    rm.decisions = [Decision(by="deepseek_r1", content="Use JWT")]
    rm.do_not_touch = ["legacy_auth()"]
    rm.lock_file("auth.py", "minimax")
    return rm


def test_build_context_no_roadmap_returns_conventions(tmp_path, monkeypatch):
    """Sans roadmap → conventions du projet chargées."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CONVENTIONS.md").write_text("# Conventions\nPas de magic strings.")
    ctx = build_context_for(llm="minimax", task="Corrige un typo", roadmap=None)
    assert "Conventions" in ctx
    assert "magic strings" in ctx


def test_build_context_no_roadmap_no_conventions_file(tmp_path, monkeypatch):
    """Sans roadmap et sans fichier → message minimal."""
    monkeypatch.chdir(tmp_path)
    ctx = build_context_for(llm="minimax", task="Corrige un typo", roadmap=None)
    assert "Aucune convention" in ctx


def test_build_context_with_roadmap_contains_all_sections():
    """Avec roadmap active → toutes les sections présentes."""
    rm = _make_roadmap_with_data()
    ctx = build_context_for(llm="minimax", task="Implémente POST /auth/login", roadmap=rm)
    assert "Terminé" in ctx
    assert "Do Not Touch" in ctx
    assert "legacy_auth()" in ctx
    assert "verrouill" in ctx.lower()
    assert "JWT" in ctx


def test_build_context_token_budget_under_4k_chars():
    """Le contexte avec roadmap reste sous ~4000 chars (proxy pour ~3K tokens)."""
    rm = _make_roadmap_with_data()
    ctx = build_context_for(llm="deepseek", task="Architecture auth", roadmap=rm)
    assert len(ctx) < 4000


def test_load_project_conventions_with_both_files(tmp_path, monkeypatch):
    """Charge CONVENTIONS.md + AGENT_RULES.md si les deux existent."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CONVENTIONS.md").write_text("# Conv\nA")
    (tmp_path / "AGENT_RULES.md").write_text("# Rules\nB")
    ctx = load_project_conventions()
    assert "CONVENTIONS.md" in ctx
    assert "AGENT_RULES.md" in ctx


# ── count_tokens (Plan 5A Task 2) ────────────────────────────────────────────

def test_count_tokens_short_english():
    """Un petit texte en anglais doit compter quelques tokens."""
    n = count_tokens("hello world")
    assert 1 <= n <= 5


def test_count_tokens_long_text():
    """Répétition de phrase classique → 400-800 tokens (borne large)."""
    text = "The quick brown fox jumps over the lazy dog. " * 50
    n = count_tokens(text)
    assert 400 <= n <= 800


def test_count_tokens_fallback_unknown_model():
    """Si le modèle est inconnu de tiktoken, fallback sur len(text) // 4."""
    text = "hello world"
    n = count_tokens(text, model="unknown-model-xyz-12345")
    assert n == len(text) // 4


def test_count_tokens_empty_string_returns_zero():
    """Chaîne vide → 0 tokens, pas d'erreur."""
    assert count_tokens("") == 0
