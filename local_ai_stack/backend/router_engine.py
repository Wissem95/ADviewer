"""Router Engine — sélection du LLM par complexité + feedback loop.

Étend `localcoder/complexity.py` existant (réutilisé tel quel) en alignant
les seuils sur la logique `level` (simple/medium/complex) plutôt que le
score brut, ce qui est plus robuste.

Corrections Opus :
- C2 : signature route(prompt, file_count, mention)
- C4 : décision basée sur result.level
- C3 : feedback loop SQLite (sera déplacé dans LongTermMemory en Plan 2)
"""
import hashlib
import re
from typing import Optional

import aiosqlite

from backend.models import LLMRole, RoutingDecision
from localcoder.complexity import analyze_task_complexity


# ── Mapping rôle → LLM par défaut ────────────────────────────────────────────

ROLE_MODELS: dict[LLMRole, str] = {
    LLMRole.CODING: "minimax/minimax-m2.5",
    LLMRole.ARCHITECTURE: "deepseek/deepseek-r1",
    LLMRole.ANALYSIS: "gemini/gemini-2.5-pro",
    LLMRole.TESTING: "mistral/codestral-2",
    LLMRole.ROUTING: "gemini/gemini-2.5-flash",
}


# ── Override manuel via @mention ─────────────────────────────────────────────

MENTION_MAP: dict[str, tuple[str, LLMRole]] = {
    "minimax": ("minimax/minimax-m2.5", LLMRole.CODING),
    "gemini": ("gemini/gemini-2.5-pro", LLMRole.ANALYSIS),
    "deepseek": ("deepseek/deepseek-r1", LLMRole.ARCHITECTURE),
    "codestral": ("mistral/codestral-2", LLMRole.TESTING),
}


# ── Mots-clés déclenchant le Mode Projet ─────────────────────────────────────

PROJECT_KEYWORDS = [
    r"crée\s+une\s+app",
    r"créer\s+une\s+app",
    r"je\s+veux\s+construire",
    r"nouveau\s+projet",
    r"génère?\s+le\s+cdc",
    r"génère?\s+le\s+cahier",
    r"build.*app",
    r"new.*project",
    r"start.*project",
]


def _hash_prompt(prompt: str) -> str:
    """Hash court et déterministe pour indexer les feedbacks."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _is_project_request(prompt: str) -> bool:
    """Détecte si le prompt déclenche le Mode Projet."""
    prompt_lower = prompt.lower()
    return any(re.search(kw, prompt_lower) for kw in PROJECT_KEYWORDS)


# ── Router Engine ────────────────────────────────────────────────────────────

class RouterEngine:
    """Décide quel LLM appeler pour une requête donnée."""

    def __init__(self, db_path: str = "localcoder.db"):
        self.db_path = db_path

    async def init_db(self) -> None:
        """No-op — le schéma routing_feedback est créé par LongTermMemory.init().

        Cette méthode est gardée pour compat avec le code appelant (main.py lifespan).
        """
        pass

    # ── Méthode principale ───────────────────────────────────────────────────

    async def route(
        self,
        prompt: str,
        file_count: int = 0,
        mention: Optional[str] = None,
    ) -> RoutingDecision:
        """
        Analyse le prompt et retourne une RoutingDecision.

        Ordre de priorité :
        1. Override @mention si fourni
        2. Feedback correction stocké en DB
        3. Mots-clés projet → mode multi_agent forcé
        4. Analyse de complexité standard (simple/medium/complex)
        """
        # 1. Override manuel via @mention
        if mention and mention.lower() in MENTION_MAP:
            llm, role = MENTION_MAP[mention.lower()]
            return RoutingDecision(
                prompt=prompt,
                score=5,
                llm=llm,
                role=role,
                mode="medium",
                reason=f"Override manuel @{mention}",
            )

        # 2. Feedback correction (apprentissage)
        corrected_llm = await self.get_feedback_correction(prompt)
        if corrected_llm:
            role = self._role_for_llm(corrected_llm)
            return RoutingDecision(
                prompt=prompt,
                score=5,
                llm=corrected_llm,
                role=role,
                mode="medium",
                reason=f"Correction de feedback appliquée (→ {corrected_llm})",
            )

        # 3. Analyse de complexité
        result = analyze_task_complexity(prompt, file_count=file_count)
        score = result.score
        reason = result.reason

        # Mode Projet forcé
        if _is_project_request(prompt):
            return RoutingDecision(
                prompt=prompt,
                score=max(score, 9),
                llm=ROLE_MODELS[LLMRole.ARCHITECTURE],
                role=LLMRole.ARCHITECTURE,
                mode="multi_agent",
                reason=f"Mode Projet détecté ({reason})",
            )

        # 4. Décision basée sur level (plus robuste que score pur)
        # Les seuils de complexity.py sont 3/6. On les aligne via level.
        if result.level == "simple" or score <= 4:
            return RoutingDecision(
                prompt=prompt,
                score=score,
                llm=ROLE_MODELS[LLMRole.CODING],
                role=LLMRole.CODING,
                mode="simple",
                reason=reason,
            )
        if result.level == "medium" or score <= 7:
            return RoutingDecision(
                prompt=prompt,
                score=score,
                llm=ROLE_MODELS[LLMRole.CODING],
                role=LLMRole.CODING,
                mode="medium",
                reason=reason,
            )
        # Complexe
        return RoutingDecision(
            prompt=prompt,
            score=score,
            llm=ROLE_MODELS[LLMRole.ARCHITECTURE],
            role=LLMRole.ARCHITECTURE,
            mode="multi_agent",
            reason=reason,
        )

    # ── Feedback loop ────────────────────────────────────────────────────────

    async def save_feedback(
        self,
        prompt: str,
        routed_to: str,
        corrected_to: str,
        pattern: str = "",
    ) -> None:
        """Stocke une correction de routage pour apprentissage futur.

        Raises:
            ValueError: Si corrected_to n'est pas un LLM connu.
        """
        # P2 : valider que corrected_to est un LLM connu
        valid_llms = set(ROLE_MODELS.values())
        if corrected_to not in valid_llms:
            raise ValueError(
                f"LLM inconnu pour feedback: {corrected_to}. "
                f"Valeurs valides: {list(valid_llms)}"
            )
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO routing_feedback
                   (prompt_hash, routed_to, corrected_to, pattern)
                   VALUES (?, ?, ?, ?)""",
                (_hash_prompt(prompt), routed_to, corrected_to, pattern),
            )
            await db.commit()

    async def get_feedback_correction(self, prompt: str) -> Optional[str]:
        """Retourne le LLM corrigé pour un prompt similaire (hash exact)."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT corrected_to FROM routing_feedback
                   WHERE prompt_hash = ? ORDER BY created_at DESC LIMIT 1""",
                (_hash_prompt(prompt),),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    # ── Helpers internes ─────────────────────────────────────────────────────

    def _role_for_llm(self, llm: str) -> LLMRole:
        """Retrouve le rôle par défaut d'un LLM (pour feedback override)."""
        reverse = {v: k for k, v in ROLE_MODELS.items()}
        return reverse.get(llm, LLMRole.CODING)
