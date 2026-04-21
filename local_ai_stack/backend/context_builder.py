"""Context Builder — construit ~2-3K tokens ciblés pour chaque appel LLM.

Règle : JAMAIS injecter le contexte brut complet de la session.
Le Context Builder compresse l'information à l'essentiel.

Deux modes :
- Conversation simple (roadmap=None) : CONVENTIONS.md + AGENT_RULES.md
- Mode projet (roadmap != None) : roadmap.get_*() sections ciblées

Expose aussi ``count_tokens`` utilisé par le cost estimator (Plan 5A Task 3)
et par toutes les étapes du pipeline rigoureux pour mesurer leurs budgets.
"""
from pathlib import Path
from typing import Optional

import tiktoken

from backend.roadmap import ProjectRoadmap


# Cache par modèle pour éviter de recharger l'encodeur tiktoken.
# Valeur None = modèle inconnu → on fallback sur len//4.
_ENC_CACHE: dict[str, Optional["tiktoken.Encoding"]] = {}


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Compte le nombre de tokens dans ``text`` pour un modèle donné.

    - Utilise ``tiktoken.encoding_for_model`` quand possible (précis).
    - Fallback sur ``len(text) // 4`` si le modèle est inconnu de tiktoken
      (DeepSeek, MiniMax, Gemini n'ont pas d'encodeur officiel — l'approx
      4 chars/token reste raisonnable sur du texte latin).
    - Retourne 0 pour une chaîne vide.
    """
    if not text:
        return 0
    if model not in _ENC_CACHE:
        try:
            _ENC_CACHE[model] = tiktoken.encoding_for_model(model)
        except KeyError:
            _ENC_CACHE[model] = None
    enc = _ENC_CACHE[model]
    if enc is None:
        return len(text) // 4
    return len(enc.encode(text))


def load_project_conventions() -> str:
    """Charge CONVENTIONS.md et AGENT_RULES.md du CWD.

    Limite chaque fichier à 800 chars pour rester dans le budget.
    Retourne un message minimal si aucun fichier n'existe.
    """
    parts = []
    for filename in ("CONVENTIONS.md", "AGENT_RULES.md"):
        p = Path(filename)
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")[:800]
                parts.append(f"## {filename}\n{content}")
            except (OSError, PermissionError):
                continue
    if not parts:
        return "## Conventions\nAucune convention définie pour ce projet."
    return "\n\n".join(parts)


def build_context_for(
    llm: str,
    task: str,
    roadmap: Optional[ProjectRoadmap],
) -> str:
    """Construit le contexte ciblé à injecter dans le prochain appel LLM.

    Budget cible : ~2-3K tokens (~2500 chars).

    Args:
        llm: Identifiant du LLM cible (non utilisé en v1, réservé pour prompts par LLM)
        task: Description de la tâche (utilisée pour filtrer les décisions pertinentes)
        roadmap: ProjectRoadmap active, ou None si mode conversation simple

    Returns:
        Chaîne structurée prête à injecter dans le system prompt.
    """
    if roadmap is None:
        return load_project_conventions()

    sections = [
        roadmap.get_done_summary(),
        roadmap.get_do_not_touch(),
        roadmap.get_locked_files(),
        roadmap.get_relevant_decisions(task),
        roadmap.get_known_patterns(),
    ]
    return "\n\n".join(sections)
