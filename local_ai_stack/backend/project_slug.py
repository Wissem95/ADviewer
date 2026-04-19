"""Nom de branche canonique pour une Task (source unique de vérité).

Partagé entre GitHubService (affichage dans le body de l'issue) et
ProjectMode (checkout/push réel), pour éviter les divergences de slug.
"""
from __future__ import annotations

import re

# Longueur max du slug du titre (après normalisation) dans le nom de branche.
MAX_TITLE_SLUG_LENGTH = 30


def slugify_task_branch(task_id: str, title: str) -> str:
    """Retourne ``feature/<id>-<slug>`` canonique pour une task.

    - id en minuscules.
    - Titre normalisé : minuscules, caractères non-word → tirets, tirets
      multiples compactés, tronqué à MAX_TITLE_SLUG_LENGTH et strippé des
      tirets en bordure.
    """
    slug = title.lower()
    # Remplace toute séquence non-[a-z0-9] par un seul tiret.
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")[:MAX_TITLE_SLUG_LENGTH].rstrip("-")
    return f"feature/{task_id.lower()}-{slug}" if slug else f"feature/{task_id.lower()}"
