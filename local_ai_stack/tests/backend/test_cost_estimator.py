"""Tests pour backend/cost_estimator.py (Plan 5A Task 3).

Le cost estimator est utilisé par l'étape 0 ESTIMATE pour produire le modal
de preview coût avant de lancer le pipeline. Il expose ``PRICING`` (prix par
LLM), ``estimate_cost`` (conversion tokens → USD) et ``estimate_pipeline_cost``
(breakdown par étape pour un mode donné).
"""
import pytest

from backend.cost_estimator import (
    PRICING,
    STAGE_LLM_MAP,
    estimate_cost,
    estimate_pipeline_cost,
)


# ── PRICING ──────────────────────────────────────────────────────────────────

def test_pricing_contains_all_five_llms():
    """Les 5 LLMs de DEFAULT_LLMS doivent être dans PRICING."""
    expected = {
        "minimax/minimax-m2.5",
        "gemini/gemini-2.5-pro",
        "gemini/gemini-2.5-flash",
        "deepseek/deepseek-r1",
        "mistral/codestral-2",
    }
    assert expected <= set(PRICING.keys())


def test_pricing_entries_have_input_and_output_keys():
    for llm, prices in PRICING.items():
        assert "input_per_million" in prices, f"missing input_per_million for {llm}"
        assert "output_per_million" in prices, f"missing output_per_million for {llm}"
        assert prices["input_per_million"] > 0
        assert prices["output_per_million"] > 0


# ── estimate_cost ────────────────────────────────────────────────────────────

def test_estimate_cost_gemini_flash_1m_tokens():
    """Gemini Flash : $0.075/M in + $0.30/M out = $0.375 pour 1M+1M."""
    cost = estimate_cost(
        "gemini/gemini-2.5-flash",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert 0.37 <= cost <= 0.38


def test_estimate_cost_unknown_llm_returns_zero():
    """LLM inconnu → 0.0 (pas d'exception)."""
    assert estimate_cost("unknown/model-xyz", 1000, 1000) == 0.0


def test_estimate_cost_scales_linearly():
    """Le coût est linéaire en tokens."""
    small = estimate_cost("minimax/minimax-m2.5", 1000, 1000)
    big = estimate_cost("minimax/minimax-m2.5", 100_000, 100_000)
    assert abs(big - small * 100) < 1e-6


# ── estimate_pipeline_cost ──────────────────────────────────────────────────

def test_estimate_pipeline_cost_simple_mode_returns_breakdown():
    """Mode simple : contient au moins intake, ground, execute ; coût < $0.01."""
    result = estimate_pipeline_cost(
        prompt_text="Crée un fichier hello.py qui print 'hi'",
        mode="simple",
        files_hint=["hello.py"],
    )
    assert result["classification"] == "simple"
    assert result["estimated_cost_usd"] < 0.01
    assert "intake" in result["stage_estimates"]
    assert "ground" in result["stage_estimates"]
    assert "execute" in result["stage_estimates"]
    assert result["estimated_files_touched"] == ["hello.py"]


def test_estimate_pipeline_cost_complex_more_expensive_than_simple():
    """Mode complex coûte plus cher que mode simple sur le même prompt."""
    simple = estimate_pipeline_cost(prompt_text="x", mode="simple")
    complex_ = estimate_pipeline_cost(prompt_text="x", mode="complex")
    assert complex_["estimated_cost_usd"] > simple["estimated_cost_usd"] * 5


def test_estimate_pipeline_cost_complex_includes_challenge_and_consensus():
    """Mode complex inclut challenge, plan (R1), plan_review (Pro), review, second_review."""
    result = estimate_pipeline_cost(prompt_text="refactor X", mode="complex")
    for stage in ("challenge", "plan", "plan_review", "review", "second_review"):
        assert stage in result["stage_estimates"], f"{stage} absent en mode complex"


def test_estimate_pipeline_cost_stage_entry_has_llm_tokens_cost():
    """Chaque stage_estimate a llm, tokens_in, tokens_out, cost_usd."""
    result = estimate_pipeline_cost(prompt_text="x", mode="simple")
    for stage_name, info in result["stage_estimates"].items():
        assert "llm" in info, f"{stage_name} sans llm"
        assert "tokens_in" in info
        assert "tokens_out" in info
        assert "cost_usd" in info


def test_estimate_pipeline_cost_duration_by_mode():
    """Durée estimée croît avec le mode."""
    simple = estimate_pipeline_cost(prompt_text="x", mode="simple")
    medium = estimate_pipeline_cost(prompt_text="x", mode="medium")
    complex_ = estimate_pipeline_cost(prompt_text="x", mode="complex")
    assert simple["estimated_duration_seconds"] < medium["estimated_duration_seconds"]
    assert medium["estimated_duration_seconds"] < complex_["estimated_duration_seconds"]


# ── STAGE_LLM_MAP ───────────────────────────────────────────────────────────

def test_stage_llm_map_routes_stages_to_configured_llms():
    """Chaque étape non-mécanique est mappée sur un LLM présent dans PRICING."""
    for stage, llm in STAGE_LLM_MAP.items():
        if llm is None:
            continue  # étape mécanique (verify)
        assert llm in PRICING, f"stage {stage} → llm {llm} absent de PRICING"
