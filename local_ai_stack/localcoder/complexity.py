"""Analyseur de complexite — decide quel modele utiliser.

Evalue la complexite d'une tache utilisateur et recommande
le mode optimal (local / gemini / deepseek).
"""

import re
from dataclasses import dataclass


@dataclass
class ComplexityResult:
    """Resultat de l'analyse de complexite."""
    level: str         # "simple", "medium", "complex"
    score: int         # 1-10
    reason: str        # Explication
    model: str         # Modele recommande
    mode: str          # "local", "gemini", "deepseek"


# Indicateurs de complexite dans la description de la tache
COMPLEX_PATTERNS = [
    (r"refactor\w*", 6, "Refactoring"),
    (r"refactor\w*\s+(?:tout|all|entire|global)", 8, "Refacto globale"),
    (r"migr(?:er|ation|ate)", 7, "Migration"),
    (r"architect\w*", 8, "Architecture"),
    (r"multi[\s-]?fichier", 7, "Multi-fichier"),
    (r"(?:debug|fix)\s+.*(?:stripe|webhook|auth|payment)", 7, "Debug service complexe"),
    (r"(?:analyser?|review|analys)\s+(?:tout|all|entire|les|le)", 7, "Analyse globale"),
    (r"(?:supprimer?|remove|trouv|find|cherch)\s+.*(?:doublon|duplicat|duplicate)", 6, "Deduplication"),
    (r"(?:reorganis|restructur)", 7, "Restructuration"),
    (r"(?:optimis|performance)", 5, "Optimisation"),
    (r"(?:test|spec)\s+(?:e2e|integration|end.to.end)", 6, "Tests E2E"),
    (r"(?:security|securit|vulnerabilit)", 7, "Securite"),
    (r"(?:prioris|triage|class)\w*\s+.*(?:todo|bug|issue)", 6, "Triage"),
    (r"\d{3,}\s*lignes", 7, "Fichier tres gros"),
    (r"(?:tous|toutes|all)\s+(?:les|the)", 6, "Scope large"),
    (r"(?:extract|extraire|deplacer?|move|partag)", 5, "Extraction/refacto"),
    (r"(?:module|shared|commun|partage|mutualis)", 5, "Modularisation"),
    (r"(?:base.class|classe.de.base|abstract|interface|factory)", 6, "Abstraction"),
    (r"(?:decouper?|split|separer?|decompos)", 6, "Decoupage"),
]

SIMPLE_PATTERNS = [
    (r"(?:fix|corrig)\w*\s+(?:un|a|le|la|ce|cette)\s+\w+", 2, "Fix simple"),
    (r"(?:ajout|add)\w*\s+(?:un|a|le|la)\s+(?:champ|field|bouton|button)", 2, "Ajout simple"),
    (r"(?:rename|renomm)", 1, "Renommage"),
    (r"(?:comment|expliqu)", 2, "Explication"),
    (r"(?:typ[oe]|faute|spelling)", 1, "Typo"),
]


def analyze_task_complexity(task_description: str, file_count: int = 0) -> ComplexityResult:
    """Analyse la complexite d'une tache et recommande le mode."""
    description = task_description.lower()
    max_score = 1
    reason = "Tache simple par defaut"

    # Verifier les patterns complexes
    for pattern, score, label in COMPLEX_PATTERNS:
        if re.search(pattern, description, re.IGNORECASE):
            if score > max_score:
                max_score = score
                reason = label

    # Verifier les patterns simples (peut reduire le score)
    for pattern, score, label in SIMPLE_PATTERNS:
        if re.search(pattern, description, re.IGNORECASE):
            if score < max_score:
                max_score = min(max_score, score + 1)
                reason = label

    # Ajuster selon le nombre de fichiers impliques
    if file_count > 5:
        max_score = max(max_score, 6)
        reason += f" ({file_count} fichiers)"
    elif file_count > 10:
        max_score = max(max_score, 8)
        reason += f" ({file_count} fichiers)"

    # Determiner le niveau et le modele
    if max_score <= 3:
        return ComplexityResult(
            level="simple",
            score=max_score,
            reason=reason,
            model="ollama_chat/qwen2.5-coder:14b",
            mode="local",
        )
    elif max_score <= 6:
        return ComplexityResult(
            level="medium",
            score=max_score,
            reason=reason,
            model="gemini/gemini-2.5-flash",
            mode="gemini",
        )
    else:
        return ComplexityResult(
            level="complex",
            score=max_score,
            reason=reason,
            model="deepseek/deepseek-reasoner",
            mode="deepseek",
        )


def format_recommendation(result: ComplexityResult) -> str:
    """Formate la recommandation pour l'utilisateur."""
    icons = {"simple": "1", "medium": "2", "complex": "3"}
    colors = {"simple": "vert", "medium": "jaune", "complex": "rouge"}

    lines = [
        f"Complexite: {result.level.upper()} ({result.score}/10)",
        f"Raison: {result.reason}",
        f"Mode recommande: {icons[result.level]}) {result.mode}",
        f"Modele: {result.model}",
    ]

    if result.mode == "local":
        lines.append("Cout: 0E (local, fonctionne en avion)")
    elif result.mode == "gemini":
        lines.append("Cout: 0E (Gemini free tier)")
    else:
        lines.append("Cout: ~0.005$ (DeepSeek API)")

    return "\n".join(lines)


if __name__ == "__main__":
    # Tests
    tasks = [
        "Corrige un typo dans le bouton de login",
        "Ajoute un champ email au formulaire",
        "Refactore tout le module d'authentification",
        "Debug le webhook Stripe qui ne fonctionne pas avec les subscriptions",
        "Analyse tout le projet et trouve les doublons",
        "Migrer de REST a GraphQL",
        "Renomme la variable foo en bar",
        "Optimise les performances du dashboard",
    ]

    for task in tasks:
        result = analyze_task_complexity(task)
        print(f"\nTache: {task}")
        print(format_recommendation(result))
        print("---")
