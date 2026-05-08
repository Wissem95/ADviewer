"""Budget tracker par pipeline (Plan 5B Task 7).

Accumule le coût USD pendant un pipeline et permet à l'orchestrator de
décider d'un abort si le cap configuré (par défaut $1.00) est dépassé.

Utilise ``cost_estimator.estimate_cost`` pour la conversion tokens → USD.
"""
from backend.cost_estimator import estimate_cost


class BudgetTracker:
    """Accumulateur de coût USD avec cap configurable."""

    def __init__(self, cap_usd: float = 1.0) -> None:
        self.cap_usd: float = float(cap_usd)
        self._cumulative_usd: float = 0.0

    def track(self, llm: str, tokens_in: int, tokens_out: int) -> float:
        """Ajoute le coût d'un appel LLM. Retourne le nouveau cumul."""
        cost = estimate_cost(llm, tokens_in, tokens_out)
        self._cumulative_usd += cost
        return self._cumulative_usd

    def track_cost(self, usd: float) -> float:
        """Ajoute un coût déjà calculé (utile quand un Stage a déjà fait le calcul)."""
        self._cumulative_usd += float(usd)
        return self._cumulative_usd

    def current_usd(self) -> float:
        """Cumul actuel."""
        return self._cumulative_usd

    def cap_exceeded(self) -> bool:
        """True si le cumul dépasse strictement le cap."""
        return self._cumulative_usd > self.cap_usd

    def would_exceed(self, additional_usd: float) -> bool:
        """True si ``current + additional`` dépasserait le cap."""
        return (self._cumulative_usd + float(additional_usd)) > self.cap_usd
