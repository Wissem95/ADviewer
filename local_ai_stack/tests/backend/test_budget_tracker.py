"""Tests pour backend/budget_tracker.py (Plan 5B Task 7).

BudgetTracker accumule le coût USD d'un pipeline et permet de :
- Détecter un dépassement de cap (``would_exceed(additional_usd)``).
- Lire le cumul (``current_usd()``).
- Tracker incrémentalement par appel LLM (``track(llm, tokens_in, tokens_out)``).
"""
import pytest

from backend.budget_tracker import BudgetTracker


def test_budget_tracker_starts_empty():
    tracker = BudgetTracker(cap_usd=1.0)
    assert tracker.current_usd() == 0.0
    assert tracker.cap_usd == 1.0
    assert tracker.would_exceed(0.5) is False


def test_track_accumulates_cost():
    tracker = BudgetTracker(cap_usd=1.0)
    tracker.track(llm="minimax/minimax-m2.5", tokens_in=1_000_000, tokens_out=0)
    # 1M input MiniMax = $0.118
    assert tracker.current_usd() == pytest.approx(0.118, abs=0.001)


def test_track_multiple_calls_accumulate():
    tracker = BudgetTracker(cap_usd=1.0)
    tracker.track(llm="gemini/gemini-2.5-flash", tokens_in=500_000, tokens_out=0)
    tracker.track(llm="gemini/gemini-2.5-flash", tokens_in=500_000, tokens_out=0)
    # 1M input Flash = $0.075
    assert tracker.current_usd() == pytest.approx(0.075, abs=0.001)


def test_would_exceed_detects_overrun():
    tracker = BudgetTracker(cap_usd=0.10)
    tracker.track(llm="minimax/minimax-m2.5", tokens_in=500_000, tokens_out=0)
    # current ~= $0.059
    assert tracker.would_exceed(0.05) is True
    assert tracker.would_exceed(0.01) is False


def test_unknown_llm_falls_back_to_zero():
    """Tarif inconnu → coût=0, pas de crash."""
    tracker = BudgetTracker(cap_usd=1.0)
    tracker.track(llm="unknown/model", tokens_in=10_000, tokens_out=10_000)
    assert tracker.current_usd() == 0.0


def test_cap_exceeded_returns_true_exact_match():
    tracker = BudgetTracker(cap_usd=0.05)
    tracker.track(llm="gemini/gemini-2.5-flash", tokens_in=1_000_000, tokens_out=0)
    # 0.075 > 0.05
    assert tracker.cap_exceeded() is True


def test_track_with_explicit_cost_skips_pricing_lookup():
    """track_cost(usd) permet d'ajouter un coût déjà calculé (par stage)."""
    tracker = BudgetTracker(cap_usd=1.0)
    tracker.track_cost(0.42)
    assert tracker.current_usd() == pytest.approx(0.42)
