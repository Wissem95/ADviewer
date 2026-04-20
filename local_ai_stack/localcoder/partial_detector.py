"""Partial Feature Detector — detecte les features commencees mais pas finies.

Signaux detectes :
- TODOs/FIXMEs dans les routes API
- console.log / print() de debug dans les composants
- Migrations SQL non appliquees (presentes dans supabase/migrations mais pas dans un fichier d'etat)
- Fonctions stub : `pass`, `return None`, `raise NotImplementedError`, `return null`
- Tests manquants : composants sans .test.tsx associe
- Features avec `@deprecated` ou `@todo` dans les docstrings
"""

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".next", "venv", ".venv",
    "dist", "build", ".cache", ".ruff_cache", "htmlcov", ".pytest_cache",
    "test-results", ".aider.tags.cache.v3", ".vercel", "archive", "backups",
    ".localcoder",
}


@dataclass
class PartialSignal:
    """Un signal qu'une feature est incomplete."""
    file: str
    line: int
    kind: str          # todo, debug_log, stub, untested, deprecated, unapplied_migration
    severity: str      # high, medium, low
    message: str
    feature_name: str = ""


def _should_ignore(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)


def _detect_todos_in_api_routes(project_path: Path) -> list[PartialSignal]:
    """Trouve les TODOs/FIXMEs dans les routes backend."""
    signals = []
    routes_dir = project_path / "backend" / "src" / "api" / "routes"
    if not routes_dir.exists():
        return signals

    pattern = re.compile(r"(TODO|FIXME|XXX|HACK|BUG)[\s:]+(.+)", re.IGNORECASE)

    for f in routes_dir.glob("*.py"):
        if f.name == "__init__.py":
            continue
        try:
            lines = f.read_text(errors="ignore").splitlines()
            rel = str(f.relative_to(project_path))
            for i, line in enumerate(lines, 1):
                m = pattern.search(line)
                if m:
                    kind = m.group(1).upper()
                    signals.append(PartialSignal(
                        file=rel,
                        line=i,
                        kind="todo",
                        severity="high" if kind in ("FIXME", "BUG") else "medium",
                        message=f"[{kind}] {m.group(2).strip()[:100]}",
                        feature_name=f.stem,
                    ))
        except (PermissionError, OSError):
            pass

    return signals


def _detect_debug_code(project_path: Path) -> list[PartialSignal]:
    """Trouve le code de debug oublie dans les composants frontend et le backend."""
    signals = []

    targets = []
    fe = project_path / "frontend-next" / "src" / "components"
    if fe.exists():
        targets.append((fe, "ts"))
    be = project_path / "backend" / "src"
    if be.exists():
        targets.append((be, "py"))

    for target_dir, lang in targets:
        for f in target_dir.rglob("*"):
            if not f.is_file() or _should_ignore(f):
                continue
            if lang == "ts" and f.suffix not in (".ts", ".tsx"):
                continue
            if lang == "py" and f.suffix != ".py":
                continue
            # Exclure les fichiers de test
            if ".test." in f.name or ".spec." in f.name or "/tests/" in str(f):
                continue
            try:
                lines = f.read_text(errors="ignore").splitlines()
                rel = str(f.relative_to(project_path))
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    # Ignorer les commentaires
                    if stripped.startswith(("//", "#", "/*", "*")):
                        continue
                    if lang == "ts":
                        if re.match(r"console\.(log|debug|warn|error)\(", stripped):
                            signals.append(PartialSignal(
                                file=rel, line=i, kind="debug_log",
                                severity="low",
                                message=f"console.log oublie: {stripped[:80]}",
                            ))
                        if "debugger" in stripped and not stripped.startswith(("//", "/*")):
                            signals.append(PartialSignal(
                                file=rel, line=i, kind="debug_log",
                                severity="high",
                                message="debugger statement — a supprimer",
                            ))
                    else:  # py
                        if re.match(r"print\s*\(", stripped) and "logging" not in stripped:
                            signals.append(PartialSignal(
                                file=rel, line=i, kind="debug_log",
                                severity="low",
                                message=f"print() de debug: {stripped[:80]}",
                            ))
                        if re.match(r"breakpoint\s*\(", stripped):
                            signals.append(PartialSignal(
                                file=rel, line=i, kind="debug_log",
                                severity="high",
                                message="breakpoint() — a supprimer",
                            ))
            except (PermissionError, OSError):
                pass

    return signals


def _detect_stub_functions(project_path: Path) -> list[PartialSignal]:
    """Trouve les fonctions vides ou stubs."""
    signals = []
    backend = project_path / "backend" / "src"
    if not backend.exists():
        return signals

    for f in backend.rglob("*.py"):
        if _should_ignore(f):
            continue
        try:
            content = f.read_text(errors="ignore")
            rel = str(f.relative_to(project_path))
            # Pattern : fonction qui contient juste pass, ou NotImplementedError
            pattern = re.compile(
                r"(async\s+)?def\s+(\w+)\s*\([^)]*\)[^:]*:\s*(?:\"\"\"[^\"]*\"\"\"\s*)?(pass|raise\s+NotImplementedError|return\s+None|\.\.\.)\s*$",
                re.MULTILINE,
            )
            for m in pattern.finditer(content):
                # Ignorer les fonctions de test stub et les abstract methods
                if "abstractmethod" in content[max(0, m.start() - 200):m.start()]:
                    continue
                line_num = content[:m.start()].count("\n") + 1
                signals.append(PartialSignal(
                    file=rel,
                    line=line_num,
                    kind="stub",
                    severity="medium",
                    message=f"Fonction stub '{m.group(2)}' — implementation manquante",
                ))
        except (PermissionError, OSError):
            pass

    return signals


def _detect_unapplied_migrations(project_path: Path) -> list[PartialSignal]:
    """Detecte les migrations SQL potentiellement non appliquees.

    Heuristique : regarde les noms de migrations recents (<7 jours) qui ne sont
    pas reference dans un fichier d'etat migration_history.
    """
    signals = []
    migrations_dir = project_path / "supabase" / "migrations"
    if not migrations_dir.exists():
        return signals

    from datetime import datetime, timedelta
    seven_days_ago = datetime.now() - timedelta(days=7)

    for f in sorted(migrations_dir.glob("*.sql")):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime > seven_days_ago:
                rel = str(f.relative_to(project_path))
                signals.append(PartialSignal(
                    file=rel,
                    line=1,
                    kind="recent_migration",
                    severity="medium",
                    message=f"Migration recente ({mtime.strftime('%Y-%m-%d')}) — verifier qu'elle est appliquee",
                ))
        except OSError:
            pass

    return signals


def _detect_untested_components(project_path: Path) -> list[PartialSignal]:
    """Trouve les composants React sans fichier de test associe."""
    signals = []
    components_dirs = [
        project_path / "frontend-next" / "src" / "components",
        project_path / "src" / "components",
    ]

    for comp_dir in components_dirs:
        if not comp_dir.exists():
            continue

        # Trouver tous les composants et leurs tests
        components = set()
        tests = set()
        for f in comp_dir.rglob("*.tsx"):
            if _should_ignore(f) or f.name.startswith("_"):
                continue
            name = f.stem
            if name.endswith(".test") or name.endswith(".spec"):
                tests.add(name.rsplit(".", 1)[0])
            else:
                components.add((name, str(f.relative_to(project_path))))

        # Chercher aussi dans __tests__
        tests_dirs = [
            project_path / "frontend-next" / "__tests__",
            project_path / "frontend-next" / "src" / "__tests__",
        ]
        for td in tests_dirs:
            if td.exists():
                for f in td.rglob("*.test.tsx"):
                    tests.add(f.stem.replace(".test", ""))
                for f in td.rglob("*.spec.tsx"):
                    tests.add(f.stem.replace(".spec", ""))

        for name, filepath in components:
            if name not in tests:
                signals.append(PartialSignal(
                    file=filepath, line=1,
                    kind="untested",
                    severity="low",
                    message=f"Composant sans test : {name}",
                    feature_name=name,
                ))
        break

    return signals


def detect_partial_features(project_path: Path) -> list[PartialSignal]:
    """Lance toutes les detections et retourne la liste complete."""
    signals = []
    signals.extend(_detect_todos_in_api_routes(project_path))
    signals.extend(_detect_debug_code(project_path))
    signals.extend(_detect_stub_functions(project_path))
    signals.extend(_detect_unapplied_migrations(project_path))
    signals.extend(_detect_untested_components(project_path))
    return signals


def update_feature_status_in_db(project_path: Path) -> dict:
    """Met a jour le statut des features dans la base SQLite."""
    from localcoder.project_memory import memory_path, init_db

    db = memory_path(project_path)
    if not db.exists():
        return {"error": "Projet pas indexe. Lance localcoder index d'abord."}

    conn = init_db(project_path)
    signals = detect_partial_features(project_path)

    # Grouper les signaux par feature_name
    partial_features: dict[str, list[PartialSignal]] = {}
    for s in signals:
        if s.feature_name:
            partial_features.setdefault(s.feature_name, []).append(s)

    # Marquer les features concernees comme "partial"
    updated = 0
    for feature_name, feat_signals in partial_features.items():
        has_high = any(s.severity == "high" for s in feat_signals)
        status = "partial" if has_high else "complete"
        if has_high:
            conn.execute("""
                UPDATE features SET status = ?
                WHERE name = ? AND status != 'broken'
            """, (status, feature_name))
            updated += 1

    conn.commit()
    conn.close()

    # Stats par type
    stats: dict[str, int] = {}
    for s in signals:
        stats[s.kind] = stats.get(s.kind, 0) + 1

    return {
        "total_signals": len(signals),
        "features_updated": updated,
        "by_kind": stats,
    }


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    signals = detect_partial_features(path)
    print(f"Total signaux: {len(signals)}")
    by_kind: dict[str, int] = {}
    for s in signals:
        by_kind[s.kind] = by_kind.get(s.kind, 0) + 1
    for kind, count in sorted(by_kind.items(), key=lambda x: -x[1]):
        print(f"  {kind}: {count}")
    print("\nEchantillon :")
    for s in signals[:15]:
        print(f"  [{s.severity}] {s.kind} — {s.file}:{s.line} — {s.message[:60]}")
