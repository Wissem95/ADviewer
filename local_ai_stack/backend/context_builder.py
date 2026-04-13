"""Context Builder — construit ~2-3K tokens ciblés pour chaque appel LLM.

Règle : JAMAIS injecter le contexte brut complet de la session.
Le Context Builder compresse l'information à l'essentiel.

Deux modes :
- Conversation simple (roadmap=None) : CONVENTIONS.md + AGENT_RULES.md
- Mode projet (roadmap != None) : roadmap.get_*() sections ciblées
"""
from pathlib import Path
from typing import Optional

from backend.roadmap import ProjectRoadmap


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
