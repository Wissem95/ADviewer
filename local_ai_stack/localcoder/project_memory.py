"""Project Memory — base de connaissances persistante par projet.

Stocke dans .localcoder/memory.sqlite :
- Tous les symboles (fonctions, classes, methodes, types)
- Toutes les features detectees (routes, pages, composants, modeles)
- Les integrations (back → front → DB)
- Le journal de bord des sessions

Permet :
- Recherche semantique : "est-ce que X existe deja ?"
- Detection d'orphelins : routes jamais appelees, composants morts
- Suivi des features : complete / partial / broken
- Historique persistent par projet
"""

import ast
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict


IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".next", "venv", ".venv",
    "dist", "build", ".cache", ".ruff_cache", "htmlcov", ".pytest_cache",
    "test-results", ".aider.tags.cache.v3", ".vercel", "archive", "backups",
    ".localcoder",
}


@dataclass
class Symbol:
    """Un symbole de code : fonction, classe, methode, type, etc."""
    file: str
    name: str
    kind: str          # function, class, method, const, interface, type
    signature: str
    docstring: str
    line_start: int
    line_end: int
    parent: str = ""   # Classe parente pour les methodes
    calls: list[str] = field(default_factory=list)


@dataclass
class Feature:
    """Une feature du projet : route API, page, composant, modele BDD."""
    name: str
    kind: str          # api_route, page, component, hook, service, db_model, agent
    files: list[str] = field(default_factory=list)
    description: str = ""
    status: str = "complete"  # complete, partial, broken, orphan
    last_modified: str = ""
    dependencies: list[str] = field(default_factory=list)


@dataclass
class Integration:
    """Lien entre deux parties du code : route <-> fetch, model <-> query."""
    source_kind: str   # api_route, frontend_fetch, db_table
    source_file: str
    source_name: str
    target_kind: str
    target_file: str
    target_name: str
    status: str        # connected, orphan, broken


@dataclass
class Session:
    """Une session de travail sur le projet."""
    started_at: str
    ended_at: str
    goal: str
    mode: str          # local, gemini, deepseek
    files_modified: list[str] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)
    summary: str = ""


# ============================================================
# DATABASE
# ============================================================

def memory_path(project_path: Path) -> Path:
    """Chemin vers la base SQLite du projet."""
    return project_path / ".localcoder" / "memory.sqlite"


def init_db(project_path: Path) -> sqlite3.Connection:
    """Initialise la base SQLite si elle n'existe pas."""
    db_path = memory_path(project_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file TEXT NOT NULL,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            signature TEXT,
            docstring TEXT,
            line_start INTEGER,
            line_end INTEGER,
            parent TEXT,
            calls TEXT,
            indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(file, name, line_start)
        );

        CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
        CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);
        CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file);

        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            files TEXT,
            description TEXT,
            status TEXT DEFAULT 'complete',
            last_modified TEXT,
            dependencies TEXT,
            indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, kind)
        );

        CREATE INDEX IF NOT EXISTS idx_features_kind ON features(kind);
        CREATE INDEX IF NOT EXISTS idx_features_status ON features(status);

        CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_kind TEXT,
            source_file TEXT,
            source_name TEXT,
            target_kind TEXT,
            target_file TEXT,
            target_name TEXT,
            status TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_integ_status ON integrations(status);

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            ended_at TEXT,
            goal TEXT,
            mode TEXT,
            files_modified TEXT,
            commits TEXT,
            summary TEXT
        );

        CREATE TABLE IF NOT EXISTS index_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()
    return conn


def should_ignore(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)


# ============================================================
# EXTRACTION DES SYMBOLES — Python
# ============================================================

def extract_python_symbols(filepath: str, content: str) -> list[Symbol]:
    """Extrait les fonctions, classes, methodes d'un fichier Python via AST."""
    symbols = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return symbols

    def get_signature(node) -> str:
        """Construit la signature d'une fonction."""
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)
        sig = f"{node.name}({', '.join(args)})"
        if node.returns:
            sig += f" -> {ast.unparse(node.returns)}"
        return sig

    def get_calls(node) -> list[str]:
        """Extrait les fonctions appelees dans le corps."""
        calls = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.add(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.add(child.func.attr)
        return sorted(calls)

    def visit(node, parent: str = ""):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "method" if parent else "function"
            symbols.append(Symbol(
                file=filepath,
                name=node.name,
                kind=kind,
                signature=get_signature(node),
                docstring=(ast.get_docstring(node) or "")[:200],
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                parent=parent,
                calls=get_calls(node),
            ))
        elif isinstance(node, ast.ClassDef):
            symbols.append(Symbol(
                file=filepath,
                name=node.name,
                kind="class",
                signature=f"class {node.name}",
                docstring=(ast.get_docstring(node) or "")[:200],
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                parent=parent,
            ))
            for child in node.body:
                visit(child, parent=node.name)

    for node in tree.body:
        visit(node)

    return symbols


# ============================================================
# EXTRACTION DES SYMBOLES — TypeScript/JavaScript
# ============================================================

def extract_ts_symbols(filepath: str, content: str) -> list[Symbol]:
    """Extrait les symboles TS/JS via regex.

    Limitations : pas d'AST complet, mais capture les exports et fonctions nommees.
    """
    symbols = []
    lines = content.splitlines()

    patterns = [
        # export function / export const / export default
        (r"^export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*(\([^)]*\))", "function"),
        (r"^export\s+(?:default\s+)?const\s+(\w+)\s*[=:]", "const"),
        (r"^export\s+(?:default\s+)?class\s+(\w+)", "class"),
        (r"^export\s+interface\s+(\w+)", "interface"),
        (r"^export\s+type\s+(\w+)", "type"),
        (r"^export\s+enum\s+(\w+)", "enum"),
        # hooks React
        (r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(use[A-Z]\w*)\s*(\([^)]*\))", "hook"),
        # arrow functions exportees
        (r"^export\s+const\s+(\w+)\s*[:=]\s*(?:async\s+)?\(", "function"),
    ]

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for pattern, kind in patterns:
            match = re.match(pattern, stripped)
            if match:
                name = match.group(1)
                signature = stripped[:200]
                symbols.append(Symbol(
                    file=filepath,
                    name=name,
                    kind=kind,
                    signature=signature,
                    docstring="",
                    line_start=i,
                    line_end=i,
                ))
                break

    return symbols


# ============================================================
# DETECTION DES FEATURES
# ============================================================

def detect_features(project_path: Path, symbols: list[Symbol]) -> list[Feature]:
    """Detecte les features du projet a partir des symboles et de la structure."""
    features = []
    seen = set()

    def add_feature(name: str, kind: str, files: list[str], description: str = ""):
        key = (name, kind)
        if key in seen:
            return
        seen.add(key)
        features.append(Feature(name=name, kind=kind, files=files, description=description))

    # 1. Routes API FastAPI : dans backend/src/api/routes/*.py
    routes_dir = project_path / "backend" / "src" / "api" / "routes"
    if routes_dir.exists():
        for f in routes_dir.glob("*.py"):
            if f.name != "__init__.py":
                rel = str(f.relative_to(project_path))
                add_feature(
                    name=f.stem,
                    kind="api_route",
                    files=[rel],
                    description=f"Route FastAPI : {f.stem}",
                )

    # 2. Pages Next.js : dans frontend-next/src/app/**/page.tsx
    pages_candidates = [
        project_path / "frontend-next" / "src" / "app",
        project_path / "src" / "app",
        project_path / "app",
    ]
    for pages_dir in pages_candidates:
        if pages_dir.exists():
            for f in pages_dir.rglob("page.tsx"):
                rel = str(f.relative_to(project_path))
                # Le nom de la page est le nom du dossier parent
                page_name = f.parent.name if f.parent.name != "app" else "home"
                add_feature(
                    name=page_name,
                    kind="page",
                    files=[rel],
                    description=f"Page Next.js : {page_name}",
                )
            break

    # 3. Composants React : frontend-next/src/components/**/*.tsx
    comp_candidates = [
        project_path / "frontend-next" / "src" / "components",
        project_path / "src" / "components",
    ]
    for comp_dir in comp_candidates:
        if comp_dir.exists():
            for f in comp_dir.rglob("*.tsx"):
                if not f.name.startswith("_") and ".test." not in f.name and ".spec." not in f.name:
                    rel = str(f.relative_to(project_path))
                    add_feature(
                        name=f.stem,
                        kind="component",
                        files=[rel],
                        description=f"Composant React",
                    )
            break

    # 4. Hooks React : frontend-next/src/hooks/**/*.ts
    hooks_candidates = [
        project_path / "frontend-next" / "src" / "hooks",
        project_path / "src" / "hooks",
    ]
    for hooks_dir in hooks_candidates:
        if hooks_dir.exists():
            for f in hooks_dir.rglob("*.ts"):
                if f.stem.startswith("use"):
                    rel = str(f.relative_to(project_path))
                    add_feature(
                        name=f.stem,
                        kind="hook",
                        files=[rel],
                        description=f"Hook React",
                    )
            break

    # 5. Services backend : backend/src/services/*.py
    services_dir = project_path / "backend" / "src" / "services"
    if services_dir.exists():
        for f in services_dir.rglob("*.py"):
            if f.name != "__init__.py":
                rel = str(f.relative_to(project_path))
                add_feature(
                    name=f.stem,
                    kind="service",
                    files=[rel],
                    description=f"Service backend",
                )

    # 6. Agents LLM : backend/src/agents/*/
    agents_dir = project_path / "backend" / "src" / "agents"
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir():
                files = [str(f.relative_to(project_path)) for f in agent_dir.glob("*.py")]
                if files:
                    add_feature(
                        name=agent_dir.name,
                        kind="agent",
                        files=files,
                        description=f"Agent LLM : {agent_dir.name}",
                    )

    # 7. Migrations BDD : supabase/migrations/*.sql → tables
    migrations_dir = project_path / "supabase" / "migrations"
    if migrations_dir.exists():
        for f in migrations_dir.glob("*.sql"):
            try:
                content = f.read_text(errors="ignore")
                table_matches = re.findall(r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(?:public\.)?(\w+)", content, re.IGNORECASE)
                for table in table_matches:
                    add_feature(
                        name=table,
                        kind="db_table",
                        files=[str(f.relative_to(project_path))],
                        description=f"Table BDD",
                    )
            except (PermissionError, OSError):
                pass

    return features


# ============================================================
# ANALYSE D'INTEGRATION
# ============================================================

def _extract_router_prefixes(project_path: Path) -> dict[str, str]:
    """Extrait les prefixes de routers FastAPI.

    Cherche dans tous les __init__.py et main.py les patterns :
      include_router(xxx_router, prefix="/api/yyy")
      APIRouter(prefix="/api/yyy")

    Retourne un mapping : nom_du_module_route -> prefix complet.
    Ex: {"admin": "/api/admin", "jobs": "/api/jobs", ...}
    """
    prefixes: dict[str, str] = {}

    # Chercher les include_router avec prefix
    candidates = [
        project_path / "backend" / "src" / "api" / "routes" / "__init__.py",
        project_path / "backend" / "src" / "main.py",
        project_path / "backend" / "src" / "api" / "__init__.py",
    ]
    for routes_init in candidates:
        if routes_init.exists():
            try:
                content = routes_init.read_text(errors="ignore")
                # Pattern : include_router(xxx_router, prefix="/api/yyy")
                for match in re.finditer(
                    r'include_router\(\s*(\w+)_router\s*,\s*prefix\s*=\s*["\']([^"\']+)["\']',
                    content,
                ):
                    module_name, prefix = match.groups()
                    prefixes[module_name] = prefix
            except (PermissionError, OSError):
                pass

    # Chercher les APIRouter(prefix=...) directement dans les fichiers de routes
    backend_routes = project_path / "backend" / "src" / "api" / "routes"
    if backend_routes.exists():
        for f in backend_routes.glob("*.py"):
            try:
                content = f.read_text(errors="ignore")
                match = re.search(
                    r'APIRouter\s*\(\s*(?:[^)]*?)prefix\s*=\s*["\']([^"\']+)["\']',
                    content,
                )
                if match:
                    module_name = f.stem
                    # Priorite au prefix local
                    prefixes[module_name] = match.group(1)
            except (PermissionError, OSError):
                pass

    return prefixes


def _normalize_path(url: str) -> str:
    """Normalise un chemin pour le matching.

    - Remplace les parametres {id} ou ${id} ou :id par un placeholder
    - Supprime les query strings
    - Lowercase
    - Supprime le trailing slash
    """
    # Query string
    url = url.split("?")[0]
    # Template literal variables ${xxx}
    url = re.sub(r"\$\{[^}]+\}", "{PARAM}", url)
    # FastAPI {param}
    url = re.sub(r"\{[^}]+\}", "{PARAM}", url)
    # Express/REST :param
    url = re.sub(r":(\w+)", "{PARAM}", url)
    # Trailing slash
    url = url.rstrip("/")
    return url.lower()


def _extract_frontend_calls(project_path: Path) -> list[tuple[str, str]]:
    """Extrait tous les appels API du frontend.

    Capture :
    - fetch('/api/...')
    - fetch(`${BACKEND_URL}/api/...`)
    - axios.get/post/put/delete/patch('/api/...')
    - adminFetch('/api/...')
    - apiClient.xxx('/api/...')
    """
    calls = []
    frontend_candidates = [
        project_path / "frontend-next" / "src",
        project_path / "src",
    ]

    # Pattern capture : fonction d'appel + URL (string simple ou template literal)
    # Couvre : fetch, axios, adminFetch, authenticatedFetch, apiFetch, apiClient,
    # et toute fonction finissant par Fetch/fetch
    CALL_FUNCS = r"(?:fetch|axios\.\w+|\w*[Ff]etch|apiClient\.\w+|api\.\w+)"
    patterns = [
        # Call('...'), Call("...")
        rf'{CALL_FUNCS}\s*\(\s*["\']([^"\']+)["\']',
        # Call(`...`) avec template literals
        rf'{CALL_FUNCS}\s*\(\s*`([^`]+)`',
        # const API_URL = '/api/...'
        r'(?:const|let|var)\s+\w+_(?:URL|ENDPOINT|PATH)\s*[:=]\s*["\'`]([^"\'`]+)',
        # useQuery({ queryKey: [...], queryFn: () => ... }) — capture URLs in queryFn
        r'queryFn[^(]*\(\s*\)\s*=>\s*\w*[Ff]etch\s*\(\s*`?([^`"\')]+)',
    ]

    for frontend_dir in frontend_candidates:
        if not frontend_dir.exists():
            continue
        for f in frontend_dir.rglob("*"):
            if not f.is_file() or f.suffix not in (".ts", ".tsx", ".js", ".jsx"):
                continue
            if should_ignore(f):
                continue
            try:
                content = f.read_text(errors="ignore")
                rel = str(f.relative_to(project_path))
                for pattern in patterns:
                    for match in re.finditer(pattern, content):
                        url = match.group(1)
                        # Nettoyer les prefixes ${BACKEND_URL} etc.
                        cleaned = re.sub(r"\$\{[A-Z_]+_URL\}", "", url)
                        cleaned = re.sub(r"\$\{process\.env\.[A-Z_]+\}", "", cleaned)
                        if cleaned.startswith("/") or "/api/" in cleaned:
                            calls.append((cleaned, rel))
            except (PermissionError, OSError):
                pass
        break

    return calls


def detect_integrations(project_path: Path, features: list[Feature]) -> list[Integration]:
    """Detecte les liens entre backend, frontend, et BDD.

    Algorithme ameliore :
    1. Extraire les prefixes des routers FastAPI (ex: /api/admin pour admin_router)
    2. Extraire les routes avec leur prefix complet
    3. Extraire les appels frontend (fetch, axios, adminFetch, apiClient, template literals)
    4. Normaliser les chemins (params -> {PARAM})
    5. Matcher par chemin normalise exact
    """
    integrations = []
    prefixes = _extract_router_prefixes(project_path)

    # 1. Extraire toutes les routes FastAPI AVEC prefixe complet
    routes = []  # (method, full_path, file)
    backend_routes = project_path / "backend" / "src" / "api" / "routes"
    if backend_routes.exists():
        for f in backend_routes.glob("*.py"):
            if f.name == "__init__.py":
                continue
            try:
                content = f.read_text(errors="ignore")
                rel = str(f.relative_to(project_path))
                module_prefix = prefixes.get(f.stem, "")

                for match in re.finditer(
                    r'@(?:router|app)\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']',
                    content,
                ):
                    method, path = match.groups()
                    # Construire le chemin complet : prefix + path
                    full_path = (module_prefix + path) if not path.startswith(module_prefix) else path
                    # Nettoyer les doubles slashes
                    full_path = re.sub(r"/+", "/", full_path)
                    routes.append((method.upper(), full_path, rel, module_prefix))
            except (PermissionError, OSError):
                pass

    # 2. Extraire les appels frontend (plus complet)
    frontend_calls = _extract_frontend_calls(project_path)

    # 3. Construire un index des appels frontend par chemin normalise
    fe_index: dict[str, list[tuple[str, str]]] = {}  # path_normalise -> [(url_original, file)]
    for url, fe_file in frontend_calls:
        norm = _normalize_path(url)
        if norm:
            fe_index.setdefault(norm, []).append((url, fe_file))

    # 4. Matcher chaque route avec les appels frontend
    for method, full_path, route_file, module_prefix in routes:
        route_norm = _normalize_path(full_path)
        matched = False

        # Match exact sur le chemin normalise
        if route_norm in fe_index:
            url_orig, fe_file = fe_index[route_norm][0]
            integrations.append(Integration(
                source_kind="api_route",
                source_file=route_file,
                source_name=f"{method} {full_path}",
                target_kind="frontend_fetch",
                target_file=fe_file,
                target_name=url_orig,
                status="connected",
            ))
            matched = True
        else:
            # Match partiel : chercher si un appel frontend termine par le path
            # (pour gerer les cas avec prefixes non detectes)
            for fe_norm, fe_list in fe_index.items():
                if fe_norm.endswith(route_norm) and len(route_norm) > 5:
                    url_orig, fe_file = fe_list[0]
                    integrations.append(Integration(
                        source_kind="api_route",
                        source_file=route_file,
                        source_name=f"{method} {full_path}",
                        target_kind="frontend_fetch",
                        target_file=fe_file,
                        target_name=url_orig,
                        status="connected",
                    ))
                    matched = True
                    break

        if not matched:
            integrations.append(Integration(
                source_kind="api_route",
                source_file=route_file,
                source_name=f"{method} {full_path}",
                target_kind="",
                target_file="",
                target_name="",
                status="orphan",
            ))

    return integrations


# ============================================================
# INDEXATION
# ============================================================

def index_project(project_path: Path, verbose: bool = True) -> dict:
    """Indexe tout le projet dans la base de memoire."""
    project_path = Path(project_path).resolve()
    conn = init_db(project_path)

    stats = {
        "files_scanned": 0,
        "symbols": 0,
        "features": 0,
        "integrations": 0,
    }

    # Clear old data
    conn.execute("DELETE FROM symbols")
    conn.execute("DELETE FROM features")
    conn.execute("DELETE FROM integrations")

    all_symbols = []

    # Scan tous les fichiers
    for f in project_path.rglob("*"):
        if not f.is_file() or should_ignore(f):
            continue

        ext = f.suffix.lower()
        if ext not in (".py", ".ts", ".tsx", ".js", ".jsx"):
            continue

        try:
            content = f.read_text(errors="ignore")
        except (PermissionError, OSError):
            continue

        rel_path = str(f.relative_to(project_path))
        stats["files_scanned"] += 1

        # Extract symbols
        if ext == ".py":
            symbols = extract_python_symbols(rel_path, content)
        else:
            symbols = extract_ts_symbols(rel_path, content)

        all_symbols.extend(symbols)

        # Insert symbols
        for s in symbols:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO symbols
                    (file, name, kind, signature, docstring, line_start, line_end, parent, calls)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s.file, s.name, s.kind, s.signature, s.docstring,
                    s.line_start, s.line_end, s.parent, json.dumps(s.calls),
                ))
            except sqlite3.Error:
                pass

    stats["symbols"] = len(all_symbols)

    # Detect features
    features = detect_features(project_path, all_symbols)
    for feat in features:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO features
                (name, kind, files, description, status, dependencies)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                feat.name, feat.kind, json.dumps(feat.files),
                feat.description, feat.status, json.dumps(feat.dependencies),
            ))
        except sqlite3.Error:
            pass

    stats["features"] = len(features)

    # Detect integrations
    integrations = detect_integrations(project_path, features)
    for integ in integrations:
        try:
            conn.execute("""
                INSERT INTO integrations
                (source_kind, source_file, source_name, target_kind, target_file, target_name, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                integ.source_kind, integ.source_file, integ.source_name,
                integ.target_kind, integ.target_file, integ.target_name, integ.status,
            ))
        except sqlite3.Error:
            pass

    stats["integrations"] = len(integrations)

    # Update metadata
    conn.execute("""
        INSERT OR REPLACE INTO index_meta (key, value)
        VALUES ('last_indexed', ?)
    """, (datetime.now().isoformat(),))
    conn.execute("""
        INSERT OR REPLACE INTO index_meta (key, value)
        VALUES ('stats', ?)
    """, (json.dumps(stats),))

    conn.commit()
    conn.close()

    return stats


# ============================================================
# RECHERCHE
# ============================================================

def search_symbols(project_path: Path, query: str, limit: int = 20) -> list[dict]:
    """Recherche des symboles par nom/signature/docstring."""
    conn = init_db(project_path)
    pattern = f"%{query.lower()}%"

    results = conn.execute("""
        SELECT file, name, kind, signature, docstring, line_start, parent
        FROM symbols
        WHERE LOWER(name) LIKE ?
           OR LOWER(signature) LIKE ?
           OR LOWER(docstring) LIKE ?
        ORDER BY
            CASE
                WHEN LOWER(name) = LOWER(?) THEN 0
                WHEN LOWER(name) LIKE ? THEN 1
                ELSE 2
            END,
            file
        LIMIT ?
    """, (pattern, pattern, pattern, query, f"{query.lower()}%", limit)).fetchall()

    conn.close()
    return [dict(r) for r in results]


def search_features(project_path: Path, query: str, kind: str | None = None) -> list[dict]:
    """Recherche des features par nom ou description."""
    conn = init_db(project_path)
    pattern = f"%{query.lower()}%"

    if kind:
        results = conn.execute("""
            SELECT * FROM features
            WHERE (LOWER(name) LIKE ? OR LOWER(description) LIKE ?)
              AND kind = ?
            ORDER BY name
        """, (pattern, pattern, kind)).fetchall()
    else:
        results = conn.execute("""
            SELECT * FROM features
            WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ?
            ORDER BY kind, name
        """, (pattern, pattern)).fetchall()

    conn.close()
    out = []
    for r in results:
        d = dict(r)
        d["files"] = json.loads(d["files"]) if d["files"] else []
        d["dependencies"] = json.loads(d["dependencies"]) if d["dependencies"] else []
        out.append(d)
    return out


def find_orphans(project_path: Path) -> list[dict]:
    """Trouve les routes API orphelines (jamais appelees par le frontend)."""
    conn = init_db(project_path)
    results = conn.execute("""
        SELECT source_kind, source_file, source_name
        FROM integrations
        WHERE status = 'orphan'
        ORDER BY source_file
    """).fetchall()
    conn.close()
    return [dict(r) for r in results]


def get_index_stats(project_path: Path) -> dict:
    """Retourne les stats d'indexation."""
    db_path = memory_path(project_path)
    if not db_path.exists():
        return {"indexed": False}

    conn = init_db(project_path)
    row = conn.execute("SELECT value FROM index_meta WHERE key = 'stats'").fetchone()
    last = conn.execute("SELECT value FROM index_meta WHERE key = 'last_indexed'").fetchone()
    conn.close()

    stats = json.loads(row["value"]) if row else {}
    stats["indexed"] = True
    stats["last_indexed"] = last["value"] if last else "never"
    return stats


def get_features_by_kind(project_path: Path) -> dict[str, int]:
    """Retourne le nombre de features par type."""
    conn = init_db(project_path)
    rows = conn.execute("""
        SELECT kind, COUNT(*) as count FROM features GROUP BY kind
    """).fetchall()
    conn.close()
    return {r["kind"]: r["count"] for r in rows}


# ============================================================
# SESSIONS (journal de bord)
# ============================================================

def log_session(project_path: Path, session: Session) -> int:
    """Enregistre une session dans le journal."""
    conn = init_db(project_path)
    cursor = conn.execute("""
        INSERT INTO sessions (started_at, ended_at, goal, mode, files_modified, commits, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session.started_at, session.ended_at, session.goal, session.mode,
        json.dumps(session.files_modified), json.dumps(session.commits), session.summary,
    ))
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def get_recent_sessions(project_path: Path, limit: int = 20) -> list[dict]:
    """Retourne les N dernieres sessions."""
    db_path = memory_path(project_path)
    if not db_path.exists():
        return []

    conn = init_db(project_path)
    rows = conn.execute("""
        SELECT * FROM sessions
        ORDER BY started_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    out = []
    for r in rows:
        d = dict(r)
        d["files_modified"] = json.loads(d["files_modified"]) if d["files_modified"] else []
        d["commits"] = json.loads(d["commits"]) if d["commits"] else []
        out.append(d)
    return out


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(f"Indexation de {path}...")
    stats = index_project(path)
    print(f"Fichiers: {stats['files_scanned']}")
    print(f"Symboles: {stats['symbols']}")
    print(f"Features: {stats['features']}")
    print(f"Integrations: {stats['integrations']}")
