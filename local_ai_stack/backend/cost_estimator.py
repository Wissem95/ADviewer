"""Cost estimator — étape 0 ESTIMATE du pipeline rigoureux (Plan 5A Task 3).

Expose :
- ``PRICING`` : prix par LLM en USD par million de tokens (in / out).
- ``STAGE_LLM_MAP`` : mapping nom d'étape → LLM dédié (voir spec §2.2).
- ``STAGE_TOKEN_ESTIMATES`` : estimations tokens in/out par étape par mode.
- ``estimate_cost(llm, tokens_in, tokens_out)`` : conversion tokens → USD.
- ``estimate_pipeline_cost(prompt, mode, files_hint)`` : breakdown total pour
  alimenter le modal ESTIMATE de l'UI.

Prix de référence : septembre 2025.
"""
from typing import Optional


# ── Prix par LLM (USD / 1M tokens) ──────────────────────────────────────────

PRICING: dict[str, dict[str, float]] = {
    "minimax/minimax-m2.5":     {"input_per_million": 0.118, "output_per_million": 0.99},
    "gemini/gemini-2.5-pro":    {"input_per_million": 1.25,  "output_per_million": 10.00},
    "gemini/gemini-2.5-flash":  {"input_per_million": 0.075, "output_per_million": 0.30},
    "deepseek/deepseek-r1":     {"input_per_million": 0.55,  "output_per_million": 2.19},
    "deepseek/deepseek-chat":   {"input_per_million": 0.27,  "output_per_million": 1.10},
    "mistral/codestral-2":      {"input_per_million": 0.30,  "output_per_million": 0.90},
}


# ── Dispatch multi-LLM par étape du pipeline (spec §2.2) ────────────────────

STAGE_LLM_MAP: dict[str, Optional[str]] = {
    "estimate":      "gemini/gemini-2.5-flash",
    "intake":        "gemini/gemini-2.5-flash",
    "challenge":     "gemini/gemini-2.5-pro",
    "ground":        "minimax/minimax-m2.5",
    "plan":          "deepseek/deepseek-r1",
    "plan_review":   "gemini/gemini-2.5-pro",
    "execute":       "minimax/minimax-m2.5",
    "self_check":    "minimax/minimax-m2.5",
    "verify":        None,  # étape mécanique (pytest/vitest/cargo), pas de LLM
    "review":        "gemini/gemini-2.5-pro",
    "second_review": "deepseek/deepseek-r1",
}


# ── Estimations tokens par étape par mode ────────────────────────────────────
# Valeurs heuristiques moyennées sur des prompts représentatifs. Ajustées au
# fil du temps via le mécanisme de calibration (Plan 5E Task 1 : comparaison
# estimé/réel stockée en table ``pipeline_runs``).

STAGE_TOKEN_ESTIMATES: dict[str, dict[str, dict[str, int]]] = {
    "simple": {
        "estimate": {"in": 300, "out": 200},
        "intake":   {"in": 400, "out": 200},
        "ground":   {"in": 1500, "out": 400},
        "execute":  {"in": 2500, "out": 1500},
    },
    "medium": {
        "estimate":   {"in": 300, "out": 200},
        "intake":     {"in": 400, "out": 200},
        "ground":     {"in": 2500, "out": 500},
        "execute":    {"in": 4000, "out": 2000},
        "self_check": {"in": 3000, "out": 600},
        "review":     {"in": 3500, "out": 1200},
    },
    "complex": {
        "estimate":      {"in": 300, "out": 200},
        "intake":        {"in": 500, "out": 300},
        "challenge":     {"in": 800, "out": 1000},
        "ground":        {"in": 3500, "out": 800},
        "plan":          {"in": 4500, "out": 2500},
        "plan_review":   {"in": 4500, "out": 1500},
        "execute":       {"in": 6000, "out": 3500},
        "self_check":    {"in": 4500, "out": 1000},
        "review":        {"in": 5500, "out": 1800},
        "second_review": {"in": 5500, "out": 1200},
    },
}


# Durée indicative totale du pipeline en secondes (alimente le modal ESTIMATE).
_DURATION_BY_MODE: dict[str, int] = {
    "simple": 15,
    "medium": 40,
    "complex": 180,
}


def estimate_cost(llm: str, input_tokens: int, output_tokens: int) -> float:
    """Convertit un nombre de tokens en coût USD selon ``PRICING[llm]``.

    Retourne 0.0 si le LLM est inconnu (évite les exceptions dans l'UI).
    """
    if llm not in PRICING:
        return 0.0
    prices = PRICING[llm]
    return (
        (input_tokens / 1_000_000) * prices["input_per_million"]
        + (output_tokens / 1_000_000) * prices["output_per_million"]
    )


def estimate_pipeline_cost(
    prompt_text: str,
    mode: str,
    files_hint: Optional[list[str]] = None,
) -> dict:
    """Estimation totale du coût d'un pipeline pour un mode donné.

    Retourne un dict compatible avec l'event WS ``pipeline_estimate`` :
    - ``classification`` : le mode passé en entrée.
    - ``estimated_cost_usd`` : somme arrondie des coûts par étape.
    - ``estimated_tokens_in`` / ``estimated_tokens_out`` : somme tokens.
    - ``stage_estimates`` : dict {stage_name: {llm, tokens_in, tokens_out, cost_usd}}.
    - ``estimated_duration_seconds`` : indicatif.
    - ``estimated_files_touched`` : passthrough du hint fourni.
    """
    base = STAGE_TOKEN_ESTIMATES.get(mode, {})
    stage_estimates: dict[str, dict] = {}
    total_cost = 0.0
    total_in = 0
    total_out = 0

    for stage_name, tokens in base.items():
        llm = STAGE_LLM_MAP.get(stage_name)
        if llm is None:
            continue  # étape mécanique → pas de coût
        c = estimate_cost(llm, tokens["in"], tokens["out"])
        stage_estimates[stage_name] = {
            "llm": llm,
            "tokens_in": tokens["in"],
            "tokens_out": tokens["out"],
            "cost_usd": round(c, 5),
        }
        total_cost += c
        total_in += tokens["in"]
        total_out += tokens["out"]

    return {
        "classification": mode,
        "estimated_cost_usd": round(total_cost, 4),
        "estimated_tokens_in": total_in,
        "estimated_tokens_out": total_out,
        "stage_estimates": stage_estimates,
        "estimated_duration_seconds": _DURATION_BY_MODE.get(mode, 60),
        "estimated_files_touched": files_hint or [],
    }
