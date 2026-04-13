"""LLM Manager — wrapper LiteLLM avec fallback chain et rate limiting.

Responsabilités :
- Appeler les LLMs via LiteLLM (interface unifiée pour tous les providers)
- Gérer une fallback chain par rôle (si MiniMax down, essayer DeepSeek, etc.)
- Rate limiting par modèle (respecter les RPM des providers)
- Injecter le system prompt MD correspondant au rôle
- Activer/désactiver des LLMs à la volée

Correction I14 : les system prompts MD sont chargés depuis backend/prompts/
                 et injectés automatiquement comme premier message.
"""
import time
from collections import deque
from pathlib import Path
from typing import Optional

from litellm import acompletion

from backend.models import LLMRole


# ── Emplacement des system prompts MD ────────────────────────────────────────

PROMPTS_DIR = Path(__file__).parent / "prompts"


# ── Fallback chains par rôle ─────────────────────────────────────────────────

FALLBACK_CHAINS: dict[LLMRole, list[str]] = {
    LLMRole.CODING: [
        "minimax/minimax-m2.5",
        "deepseek/deepseek-chat",
        "gemini/gemini-2.5-pro",
    ],
    LLMRole.ARCHITECTURE: [
        "deepseek/deepseek-r1",
        "gemini/gemini-2.5-pro",
    ],
    LLMRole.ANALYSIS: [
        "gemini/gemini-2.5-pro",
        "minimax/minimax-m2.5",
    ],
    LLMRole.TESTING: [
        "mistral/codestral-2",         # ID unifié (correction I4)
        "minimax/minimax-m2.5",
    ],
    LLMRole.ROUTING: [
        "gemini/gemini-2.5-flash",
        "minimax/minimax-m2.5",
    ],
}


# Mapping rôle → fichier MD system prompt
_ROLE_TO_PROMPT_FILE: dict[LLMRole, str] = {
    LLMRole.CODING: "system_minimax.md",
    LLMRole.ARCHITECTURE: "system_deepseek_r1.md",
    LLMRole.TESTING: "system_codestral.md",
    LLMRole.ANALYSIS: "system_gemini_pro.md",
    LLMRole.ROUTING: "system_gemini_flash.md",
}


def _load_system_prompt(role: LLMRole) -> str:
    """Charge le system prompt MD du rôle. Retourne '' si absent."""
    filename = _ROLE_TO_PROMPT_FILE.get(role, "")
    if not filename:
        return ""
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        return ""
    try:
        return prompt_path.read_text(encoding="utf-8")
    except (OSError, PermissionError):
        return ""


# ── Rate limiter ──────────────────────────────────────────────────────────────

class RateLimiter:
    """Rate limiter par fenêtre glissante — RPM (requests per minute).

    Thread-safe pour les coroutines (pas besoin de lock car Python asyncio
    est mono-thread par défaut, et try_acquire est synchrone).
    """

    def __init__(self, rpm: int):
        self.rpm = rpm
        self.window_seconds = 60.0
        self._timestamps: deque[float] = deque()

    def try_acquire(self) -> bool:
        """Retourne True si sous la limite, False sinon.

        NOTE : Le slot est consommé dès l'acquire, même si l'appel LLM échoue
        ensuite. Cela permet d'être pessimiste sur les limites du provider
        (préfère refuser un appel légitime que dépasser la limite).
        """
        now = time.time()
        # Nettoyer les timestamps hors de la fenêtre
        while self._timestamps and now - self._timestamps[0] > self.window_seconds:
            self._timestamps.popleft()
        if len(self._timestamps) >= self.rpm:
            return False
        self._timestamps.append(now)
        return True


# ── LLM Manager ──────────────────────────────────────────────────────────────

class LLMManagerError(Exception):
    """Échec total après épuisement de la fallback chain."""


class LLMManager:
    """Interface unifiée pour appeler tous les LLMs via LiteLLM."""

    # Rate limits par modèle (requests/minute)
    DEFAULT_RPM: dict[str, int] = {
        "minimax/minimax-m2.5":     200,
        "gemini/gemini-2.5-pro":     60,
        "gemini/gemini-2.5-flash": 1000,
        "deepseek/deepseek-r1":      50,
        "deepseek/deepseek-chat":    60,
        "mistral/codestral-2":      100,
    }

    def __init__(self) -> None:
        self._disabled: set[str] = set()
        self._rate_limiters: dict[str, RateLimiter] = {
            model: RateLimiter(rpm=rpm)
            for model, rpm in self.DEFAULT_RPM.items()
        }

    # ── Activation / désactivation ───────────────────────────────────────────

    def disable(self, llm: str) -> None:
        self._disabled.add(llm)

    def enable(self, llm: str) -> None:
        self._disabled.discard(llm)

    def is_disabled(self, llm: str) -> bool:
        return llm in self._disabled

    # ── Appel principal ──────────────────────────────────────────────────────

    async def call_with_fallback(
        self,
        role: LLMRole,
        messages: list[dict],
        temperature: float = 0.2,
        timeout: int = 90,
    ) -> str:
        """
        Appelle le premier LLM disponible dans la fallback chain du rôle.

        Injecte automatiquement le system prompt MD si présent et si aucun
        message 'system' n'est déjà en tête.

        Retourne le contenu textuel de la réponse.
        Lève LLMManagerError si toute la chain échoue.
        """
        # Injection du system prompt si absent
        system_prompt = _load_system_prompt(role)
        if system_prompt and (not messages or messages[0].get("role") != "system"):
            messages = [{"role": "system", "content": system_prompt}] + list(messages)

        chain = FALLBACK_CHAINS.get(role, [])
        last_error: Optional[Exception] = None

        for model in chain:
            if self.is_disabled(model):
                continue
            limiter = self._rate_limiters.get(model)
            if limiter and not limiter.try_acquire():
                last_error = LLMManagerError(f"Rate limit dépassé pour {model}")
                continue

            try:
                response = await acompletion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    timeout=timeout,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                continue  # Essaie le suivant

        raise LLMManagerError(
            f"Tous les LLMs de la chain {role.value} ont échoué. "
            f"Dernière erreur : {last_error}"
        )
