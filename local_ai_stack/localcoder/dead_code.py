"""Dead Code Detector — trouve le code defini mais jamais utilise.

Utilise la base .localcoder/memory.sqlite (symboles + calls) pour identifier :
- Fonctions definies mais jamais appelees
- Classes definies mais jamais instanciees
- Exports TypeScript jamais importes
- Composants React jamais utilises

Exclusions intelligentes :
- Entry points (main, __main__, page.tsx, layout.tsx)
- Tests (test_*.py, *.test.tsx)
- Hooks React (usexxx)
- Handlers API FastAPI (decorateurs @router)
- Callbacks de framework (lifecycle React, Pydantic validators, etc.)
"""

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DeadSymbol:
    name: str
    kind: str
    file: str
    line: int
    reason: str
    confidence: str   # high, medium, low


# Noms qui ne sont jamais "dead" (entry points, frameworks)
ALWAYS_ALIVE_NAMES = {
    # Python entry points
    "main", "__init__", "__main__", "__str__", "__repr__", "__eq__",
    "__hash__", "__call__", "__enter__", "__exit__",
    # Django/Flask/FastAPI
    "get", "post", "put", "delete", "patch", "handle",
    # React
    "default",
    # Tests
    "setUp", "tearDown", "setUpClass", "tearDownClass",
}

# Patterns de fichiers ou rien n'est "dead"
ALWAYS_ALIVE_FILES = [
    r"test_", r"_test\.", r"\.test\.", r"\.spec\.",
    r"__init__\.py$", r"conftest\.py$",
    r"page\.tsx$", r"layout\.tsx$", r"loading\.tsx$", r"error\.tsx$",
    r"not-found\.tsx$", r"route\.ts$", r"middleware\.ts$",
    r"config\.", r"settings\.",
]


def _is_always_alive_file(filepath: str) -> bool:
    return any(re.search(p, filepath) for p in ALWAYS_ALIVE_FILES)


def _is_framework_callback(name: str, file: str) -> bool:
    """Detecte les callbacks de framework qui ne sont pas "dead" meme sans appel direct."""
    # FastAPI/Flask/Django route handlers : appeles par le framework
    if "/api/routes/" in file or "/routes/" in file:
        return True

    # Pydantic validators
    if name.startswith("validate_") or name.startswith("_validate"):
        return True

    # React lifecycle, hooks
    if name.startswith("use") and name[3:4].isupper():
        return True
    if name in ("getStaticProps", "getServerSideProps", "generateMetadata", "generateStaticParams"):
        return True

    # SQLAlchemy/Alembic
    if name in ("upgrade", "downgrade"):
        return True

    return False


def find_dead_code(project_path: Path, confidence_min: str = "medium") -> list[DeadSymbol]:
    """Trouve le code defini mais jamais utilise."""
    from localcoder.project_memory import memory_path

    db = memory_path(project_path)
    if not db.exists():
        return []

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    # 1. Construire l'ensemble de tous les noms appeles
    called_names: set[str] = set()
    rows = conn.execute("SELECT calls FROM symbols WHERE calls IS NOT NULL AND calls != '[]'").fetchall()
    for r in rows:
        try:
            calls = json.loads(r["calls"])
            called_names.update(calls)
        except (json.JSONDecodeError, TypeError):
            pass

    # 2. Ajouter les noms utilises dans le code (pour TS/JS et imports)
    # Scan rapide de toutes les references dans les fichiers
    ref_names: set[str] = set()
    for f in project_path.rglob("*"):
        if not f.is_file() or f.suffix not in (".py", ".ts", ".tsx", ".js", ".jsx"):
            continue
        if any(part in {".git", "node_modules", "venv", "__pycache__", ".next", "dist", ".localcoder"}
               for part in f.parts):
            continue
        try:
            content = f.read_text(errors="ignore")
            # Noms en camelCase, PascalCase, snake_case
            for m in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b", content):
                ref_names.add(m.group(1))
        except (PermissionError, OSError):
            pass

    # 3. Recuperer tous les symboles definis
    symbols = conn.execute("""
        SELECT name, kind, file, line_start, parent FROM symbols
    """).fetchall()

    # Construire en UN SEUL PASSAGE : compter toutes les occurrences de chaque nom
    # dans tous les fichiers. Complexite : O(N fichiers), pas O(N fichiers * N symboles).
    symbol_names: set[str] = {s["name"] for s in symbols}
    occurrences_count: dict[str, int] = {n: 0 for n in symbol_names}

    for f in project_path.rglob("*"):
        if not f.is_file() or f.suffix not in (".py", ".ts", ".tsx", ".js", ".jsx"):
            continue
        if any(part in {".git", "node_modules", "venv", "__pycache__", ".next", "dist", ".localcoder"}
               for part in f.parts):
            continue
        try:
            content = f.read_text(errors="ignore")
            # Un seul regex par fichier qui capture tous les mots
            words = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b", content)
            for w in words:
                if w in occurrences_count:
                    occurrences_count[w] += 1
        except (PermissionError, OSError):
            pass

    dead = []
    for s in symbols:
        name = s["name"]
        file = s["file"]

        # Filtres d'exclusion
        if name in ALWAYS_ALIVE_NAMES:
            continue
        if _is_always_alive_file(file):
            continue
        if _is_framework_callback(name, file):
            continue
        if name.startswith("_"):  # Private/internal
            continue

        references_in_calls = name in called_names
        occurrences = occurrences_count.get(name, 0)

        # 1 occurrence = juste la definition = mort
        # 2 occurrences = definition + 1 usage potentiel (faible confiance)
        if occurrences <= 1:
            dead.append(DeadSymbol(
                name=name, kind=s["kind"], file=file, line=s["line_start"],
                reason=f"Aucune reference trouvee (occurrences: {occurrences})",
                confidence="high",
            ))
        elif occurrences == 2 and not references_in_calls:
            dead.append(DeadSymbol(
                name=name, kind=s["kind"], file=file, line=s["line_start"],
                reason=f"Probablement mort (2 occurrences, aucun appel detecte)",
                confidence="medium",
            ))

    conn.close()

    # Filtrer par confiance
    conf_order = {"high": 0, "medium": 1, "low": 2}
    min_level = conf_order[confidence_min]
    dead = [d for d in dead if conf_order[d.confidence] <= min_level]

    return sorted(dead, key=lambda d: (d.file, d.line))


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    dead = find_dead_code(path)
    print(f"Code mort detecte: {len(dead)}")
    for d in dead[:20]:
        print(f"  [{d.confidence:6s}] [{d.kind:8s}] {d.file}:{d.line} — {d.name}")
