"""Scanner de projet — analyse AVANT de coder.

Detecte les doublons, fichiers trop gros, code mort, patterns,
et produit un rapport que l'agent utilise comme contexte.
"""

from pathlib import Path
from collections import defaultdict
import hashlib
import re
import json


IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".next", "venv", ".venv",
    "dist", "build", ".cache", ".ruff_cache", "htmlcov", ".pytest_cache",
    "test-results", ".aider.tags.cache.v3", ".vercel", "archive", "backups",
}

CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte",
    ".go", ".rs", ".java", ".rb", ".php", ".sql",
}


def should_ignore(path: Path) -> bool:
    """Verifie si un chemin doit etre ignore."""
    return any(part in IGNORE_DIRS for part in path.parts)


def hash_content(content: str) -> str:
    """Hash normalise (sans espaces/commentaires) pour detecter les vrais doublons."""
    # Supprime les lignes vides et les espaces en debut/fin
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    normalized = "\n".join(lines)
    return hashlib.md5(normalized.encode()).hexdigest()


def _is_false_positive(block: str, file_a: str, file_b: str) -> bool:
    """Filtre les faux positifs — blocs qui ne sont PAS de vrais doublons."""
    lines = [l.strip() for l in block.splitlines() if l.strip()]

    if len(lines) < 3:
        return True

    # 1. Bloc compose principalement d'imports → pas un doublon
    import_lines = sum(1 for l in lines if l.startswith(("import ", "from ", "export ", "require(", '"use '))
                       or l.startswith(("} from", "const {", "import {")))
    if import_lines >= len(lines) * 0.6:
        return True

    # 2. Migrations SQL : fonctions recreees dans des migrations differentes → normal
    if ".sql" in file_a and ".sql" in file_b:
        if "migration" in file_a or "migration" in file_b:
            return True

    # 3. Bloc de fermeture/ouverture (accolades, parentheses) → bruit
    structural_lines = sum(1 for l in lines if l in ("{", "}", "});", ");", "]", "});", "}", "),", "})"))
    if structural_lines >= len(lines) * 0.5:
        return True

    # 4. Tests avec meme setup vitest/jest/pytest → pattern normal
    if ("test" in file_a or "spec" in file_a) and ("test" in file_b or "spec" in file_b):
        test_boilerplate = sum(1 for l in lines if any(kw in l for kw in [
            "describe(", "it(", "expect(", "beforeEach", "afterEach",
            "vi.", "jest.", "pytest", "assert", "mock",
        ]))
        if test_boilerplate >= len(lines) * 0.5:
            return True

    # 5. Sentry/config boilerplate → pas refactorable
    if "sentry" in file_a.lower() and "sentry" in file_b.lower():
        return True

    # 6. Bloc vide ou quasi-vide (espaces, lignes vides, commentaires)
    meaningful = sum(1 for l in lines if l and not l.startswith(("#", "//", "/*", "*", "---")))
    if meaningful < 4:
        return True

    # 7. Bloc "export const dynamic" ou single-line patterns / boilerplate court
    if all(len(l) < 40 for l in lines):
        boilerplate = sum(1 for l in lines if any(kw in l for kw in [
            "export const", "export default", "'use client'", '"use client"',
            "export {", "module.exports",
        ]))
        if boilerplate >= len(lines) * 0.5:
            return True

    # 8. Cron routes / API routes avec meme boilerplate → pattern normal si peu de lignes
    if "/api/cron/" in file_a and "/api/cron/" in file_b:
        return True

    # 9. Donnees i18n (traductions) dans des fichiers de data differents → normal
    if "data." in file_a and "data." in file_b:
        data_ext_a = file_a.rsplit("data.", 1)[-1] if "data." in file_a else ""
        data_ext_b = file_b.rsplit("data.", 1)[-1] if "data." in file_b else ""
        if data_ext_a != data_ext_b:
            return True

    # 10. Meme pattern d'UI dans navbar/menus (imports de DropdownMenu, etc.) → trop generique
    ui_imports = sum(1 for l in lines if any(kw in l for kw in [
        "DropdownMenu", "DialogContent", "DialogHeader", "DialogTitle",
        "SheetContent", "SheetHeader", "Badge", "Button",
    ]))
    if ui_imports >= len(lines) * 0.4:
        return True

    # 11. Docstrings / commentaires identiques (pas du code)
    doc_lines = sum(1 for l in lines if l.startswith(('"""', "'''", "/*", "*", "*/"))
                    or l.endswith(('"""', "'''", "*/"))
                    or l.startswith("Returns:") or l.startswith("Args:")
                    or l.startswith("Parameters:") or l.startswith("Dictionary"))
    if doc_lines >= len(lines) * 0.5:
        return True

    # 12. CSS identique entre pages (prose, styles) → pas refactorable dans les composants
    css_lines = sum(1 for l in lines if any(kw in l for kw in [
        "margin-bottom", "font-size", "font-weight", "line-height",
        "padding", "color:", ".prose", "text-align",
    ]))
    if css_lines >= len(lines) * 0.4:
        return True

    # 13. Tags fermants JSX/HTML (</div>, </Link>, etc.) → bruit structurel
    closing_tags = sum(1 for l in lines if l.startswith("</") or l in (")", ");", "},", "/>", "})", "});"))
    if closing_tags >= len(lines) * 0.5:
        return True

    # 14. E2E test login fixtures → pattern normal
    if "e2e/" in file_a and "e2e/" in file_b:
        login_pattern = sum(1 for l in lines if any(kw in l for kw in [
            "page.fill", "page.click", "page.goto", "page.waitFor", "email", "password",
        ]))
        if login_pattern >= len(lines) * 0.3:
            return True

    return False


def find_duplicate_blocks(files: dict[str, str], min_lines: int = 10, strict: bool = False) -> list[dict]:
    """Detecte les blocs de code dupliques entre fichiers.

    Args:
        strict: Si True, ne filtre que les SQL migrations (minimum de faux positifs).
                Si False (defaut), filtre agressif pour 0 faux positif.
    """
    block_index: dict[str, list[dict]] = defaultdict(list)
    duplicates = []

    for filepath, content in files.items():
        lines = content.splitlines()
        if len(lines) < min_lines:
            continue

        for start in range(0, len(lines) - min_lines + 1, min_lines // 2):
            block = "\n".join(lines[start:start + min_lines])
            block_hash = hash_content(block)

            for existing in block_index[block_hash]:
                if existing["file"] != filepath:
                    # Filtrer les faux positifs
                    if not strict and _is_false_positive(block, existing["file"], filepath):
                        continue
                    # En mode strict, filtrer seulement les SQL migrations
                    if strict and ".sql" in existing["file"] and ".sql" in filepath:
                        continue

                    duplicates.append({
                        "file_a": existing["file"],
                        "line_a": existing["line"],
                        "file_b": filepath,
                        "line_b": start + 1,
                        "lines": min_lines,
                        "preview": lines[start][:80],
                        "confidence": "eleve",
                    })

            block_index[block_hash].append({
                "file": filepath,
                "line": start + 1,
            })

    # Deduplique les paires
    seen = set()
    unique = []
    for d in duplicates:
        key = tuple(sorted([d["file_a"], d["file_b"]]))
        if key not in seen:
            seen.add(key)
            unique.append(d)

    # Clusteriser : si le meme bloc est duplique dans N fichiers,
    # regrouper en 1 seul probleme au lieu de N*(N-1)/2 paires
    clusters = _clusterize_duplicates(unique)

    return clusters


def _clusterize_duplicates(duplicates: list[dict]) -> list[dict]:
    """Regroupe les doublons en clusters.

    Si adminFetch est dans fichiers A, B, C, D → 1 cluster au lieu de 6 paires.
    """
    # Construire un graphe de fichiers connectes par le meme bloc
    from collections import defaultdict

    # Grouper par preview (approximation du bloc duplique)
    preview_groups: dict[str, set[str]] = defaultdict(set)
    preview_to_dups: dict[str, list[dict]] = defaultdict(list)

    for d in duplicates:
        # Utiliser la preview comme cle de regroupement
        key = d["preview"].strip()[:50]
        preview_groups[key].add(d["file_a"])
        preview_groups[key].add(d["file_b"])
        preview_to_dups[key].append(d)

    result = []
    seen_files = set()

    for preview_key, files in sorted(preview_groups.items(), key=lambda x: -len(x[1])):
        # Si ce groupe a plus de 2 fichiers → c'est un cluster
        if len(files) > 2:
            # Emettre 1 seul doublon representatif avec la liste des fichiers
            representative = preview_to_dups[preview_key][0]
            result.append({
                "file_a": representative["file_a"],
                "line_a": representative["line_a"],
                "file_b": f"(+{len(files)-1} fichiers)",
                "line_b": 0,
                "lines": representative["lines"],
                "preview": representative["preview"],
                "confidence": "eleve",
                "cluster_size": len(files),
                "cluster_files": sorted(files),
            })
            # Marquer ces fichiers comme traites
            for f in files:
                seen_files.add(f)
        else:
            # Paire simple — emettre si pas deja dans un cluster
            for d in preview_to_dups[preview_key]:
                if d["file_a"] not in seen_files or d["file_b"] not in seen_files:
                    result.append(d)
                    seen_files.add(d["file_a"])
                    seen_files.add(d["file_b"])

    return result


def find_large_files(project_path: Path, threshold: int = 300) -> list[dict]:
    """Trouve les fichiers trop gros qui devraient etre decoupes."""
    large = []
    for f in project_path.rglob("*"):
        if f.is_file() and f.suffix in CODE_EXTENSIONS and not should_ignore(f):
            try:
                line_count = len(f.read_text(errors="ignore").splitlines())
                if line_count > threshold:
                    large.append({
                        "file": str(f.relative_to(project_path)),
                        "lines": line_count,
                        "severity": "critique" if line_count > 1000 else "attention",
                    })
            except (PermissionError, OSError):
                pass

    return sorted(large, key=lambda x: x["lines"], reverse=True)


def find_todos(project_path: Path) -> list[dict]:
    """Trouve les TODO/FIXME/HACK/XXX dans le code."""
    pattern = re.compile(r"(TODO|FIXME|HACK|XXX|BUG)[\s:]+(.+)", re.IGNORECASE)
    todos = []

    for f in project_path.rglob("*"):
        if f.is_file() and f.suffix in CODE_EXTENSIONS and not should_ignore(f):
            try:
                for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
                    match = pattern.search(line)
                    if match:
                        todos.append({
                            "file": str(f.relative_to(project_path)),
                            "line": i,
                            "type": match.group(1).upper(),
                            "content": match.group(2).strip()[:100],
                        })
            except (PermissionError, OSError):
                pass

    return todos


def detect_stack(project_path: Path) -> dict:
    """Detecte la stack technique du projet."""
    indicators = {
        "package.json": "Node.js",
        "requirements.txt": "Python",
        "pyproject.toml": "Python",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
        "Gemfile": "Ruby",
        "docker-compose.yml": "Docker",
        "Dockerfile": "Docker",
        "next.config.js": "Next.js",
        "next.config.mjs": "Next.js",
        "next.config.ts": "Next.js",
        "tailwind.config.js": "Tailwind CSS",
        "tailwind.config.ts": "Tailwind CSS",
        "tsconfig.json": "TypeScript",
        "supabase": "Supabase",
        ".env": "Environment vars",
        "railway.toml": "Railway",
        "vercel.json": "Vercel",
    }

    stack = set()
    for indicator, tech in indicators.items():
        if (project_path / indicator).exists():
            stack.add(tech)

    # Detecter les frameworks Python
    req_file = project_path / "requirements.txt"
    if req_file.exists():
        content = req_file.read_text(errors="ignore").lower()
        if "fastapi" in content:
            stack.add("FastAPI")
        if "django" in content:
            stack.add("Django")
        if "flask" in content:
            stack.add("Flask")
        if "langchain" in content:
            stack.add("LangChain")
        if "stripe" in content:
            stack.add("Stripe")

    return {"technologies": sorted(stack)}


def count_lines_by_language(project_path: Path) -> dict[str, int]:
    """Compte les lignes de code par langage."""
    lang_map = {
        ".py": "Python",
        ".ts": "TypeScript",
        ".tsx": "TypeScript (React)",
        ".js": "JavaScript",
        ".jsx": "JavaScript (React)",
        ".sql": "SQL",
        ".css": "CSS",
        ".html": "HTML",
    }
    counts: dict[str, int] = defaultdict(int)

    for f in project_path.rglob("*"):
        if f.is_file() and f.suffix in lang_map and not should_ignore(f):
            try:
                line_count = len(f.read_text(errors="ignore").splitlines())
                counts[lang_map[f.suffix]] += line_count
            except (PermissionError, OSError):
                pass

    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def scan_project(project_path: Path, strict: bool = False) -> dict:
    """Scan complet du projet — produit un rapport structure.

    Args:
        strict: Si True, mode strict — montre tous les doublons sauf SQL.
                Si False (defaut), filtre intelligent — 0 faux positif.
    """
    project_path = Path(project_path).resolve()

    if not project_path.exists():
        raise FileNotFoundError(f"Projet introuvable: {project_path}")

    # Charger tous les fichiers code
    code_files = {}
    for f in project_path.rglob("*"):
        if f.is_file() and f.suffix in CODE_EXTENSIONS and not should_ignore(f):
            try:
                code_files[str(f.relative_to(project_path))] = f.read_text(errors="ignore")
            except (PermissionError, OSError):
                pass

    report = {
        "project": project_path.name,
        "total_files": len(code_files),
        "lines_by_language": count_lines_by_language(project_path),
        "stack": detect_stack(project_path),
        "large_files": find_large_files(project_path),
        "todos": find_todos(project_path),
        "duplicates": find_duplicate_blocks(code_files, strict=strict),
    }

    total_lines = sum(report["lines_by_language"].values())
    report["total_lines"] = total_lines

    return report


def format_report(report: dict) -> str:
    """Formate le rapport en texte lisible."""
    lines = []
    lines.append(f"# Rapport d'analyse — {report['project']}")
    lines.append(f"\nFichiers code: {report['total_files']}")
    lines.append(f"Lignes totales: {report['total_lines']:,}")

    lines.append("\n## Stack detectee")
    for tech in report["stack"]["technologies"]:
        lines.append(f"  - {tech}")

    lines.append("\n## Lignes par langage")
    for lang, count in report["lines_by_language"].items():
        lines.append(f"  {lang}: {count:,}")

    if report["large_files"]:
        lines.append(f"\n## Fichiers trop gros ({len(report['large_files'])})")
        for f in report["large_files"][:20]:
            icon = "!!" if f["severity"] == "critique" else "!"
            lines.append(f"  {icon} {f['file']} ({f['lines']} lignes)")

    if report["duplicates"]:
        lines.append(f"\n## Doublons detectes ({len(report['duplicates'])})")
        for d in report["duplicates"][:15]:
            lines.append(f"  {d['file_a']}:{d['line_a']} <-> {d['file_b']}:{d['line_b']} ({d['lines']} lignes)")
            lines.append(f"    Preview: {d['preview']}")

    if report["todos"]:
        lines.append(f"\n## TODOs/FIXMEs ({len(report['todos'])})")
        for t in report["todos"][:20]:
            lines.append(f"  [{t['type']}] {t['file']}:{t['line']} — {t['content']}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    report = scan_project(path)
    print(format_report(report))
