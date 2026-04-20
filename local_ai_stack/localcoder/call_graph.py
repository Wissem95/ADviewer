"""Call Graph — construction et export du graphe d'appels du projet.

Lit la base .localcoder/memory.sqlite et construit un graphe :
  noeud = fonction/classe
  arete = A appelle B

Exports :
- Mermaid (diagramme dans un .md)
- DOT/Graphviz (pour generation PNG)
- JSON (pour autres visus)
"""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class CallGraphNode:
    name: str
    kind: str      # function, class, method
    file: str
    calls: list[str] = field(default_factory=list)
    called_by: list[str] = field(default_factory=list)


def build_call_graph(project_path: Path) -> dict[str, CallGraphNode]:
    """Construit le graphe d'appels depuis la base SQLite."""
    from localcoder.project_memory import memory_path, init_db

    db = memory_path(project_path)
    if not db.exists():
        return {}

    conn = init_db(project_path)
    rows = conn.execute("""
        SELECT name, kind, file, calls FROM symbols
    """).fetchall()
    conn.close()

    # Construire l'index de tous les symboles
    nodes: dict[str, CallGraphNode] = {}
    all_names: set[str] = set()

    for r in rows:
        name = r["name"]
        if name not in nodes:
            nodes[name] = CallGraphNode(
                name=name, kind=r["kind"], file=r["file"],
            )
        all_names.add(name)

    # Populer les appels — ne garder que les appels qui pointent vers un symbole connu
    for r in rows:
        name = r["name"]
        calls_json = r["calls"]
        if not calls_json:
            continue
        try:
            calls = json.loads(calls_json)
        except (json.JSONDecodeError, TypeError):
            continue

        for callee in calls:
            if callee in all_names and callee != name:
                if callee not in nodes[name].calls:
                    nodes[name].calls.append(callee)
                if callee in nodes and name not in nodes[callee].called_by:
                    nodes[callee].called_by.append(name)

    return nodes


def export_mermaid(
    project_path: Path,
    focus: str | None = None,
    max_nodes: int = 40,
) -> str:
    """Exporte le graphe au format Mermaid.

    Args:
        focus: Si fourni, centre le graphe sur cette fonction (et son voisinage).
        max_nodes: Limite du nombre de noeuds affiches.
    """
    nodes = build_call_graph(project_path)
    if not nodes:
        return "graph LR\n  empty[Base SQLite vide. Lance localcoder index.]"

    # Si focus defini, limiter aux voisins (2 niveaux)
    if focus:
        if focus not in nodes:
            return f"graph LR\n  notfound[Symbole '{focus}' non trouve]"

        selected: set[str] = {focus}
        # Niveau 1 : ce qui appelle focus + ce que focus appelle
        for c in nodes[focus].calls:
            selected.add(c)
        for c in nodes[focus].called_by:
            selected.add(c)
        # Niveau 2 : les voisins des voisins (limite)
        level1 = set(selected)
        for name in level1:
            if name == focus:
                continue
            for c in nodes[name].calls[:3]:
                selected.add(c)
            if len(selected) >= max_nodes:
                break

        filtered = {n: nodes[n] for n in selected if n in nodes}
    else:
        # Top des noeuds les plus connectes
        ranked = sorted(
            nodes.items(),
            key=lambda x: len(x[1].calls) + len(x[1].called_by),
            reverse=True,
        )
        filtered = dict(ranked[:max_nodes])

    lines = ["graph LR"]

    # Sanitize : mermaid n'aime pas certains caracteres dans les noms
    def sid(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "_", name)[:40]

    import re

    # Declarer les noeuds avec labels
    for name, node in filtered.items():
        short_file = node.file.split("/")[-1]
        label = f"{name}<br/><small>{short_file}</small>"
        style = ""
        if focus and name == focus:
            style = ":::focus"
        lines.append(f'  {sid(name)}["{label}"]{style}')

    # Arêtes
    edges = set()
    for name, node in filtered.items():
        for callee in node.calls:
            if callee in filtered:
                edge = (sid(name), sid(callee))
                if edge not in edges:
                    edges.add(edge)
                    lines.append(f"  {edge[0]} --> {edge[1]}")

    if focus:
        lines.append("  classDef focus fill:#f9a,stroke:#333,stroke-width:3px")

    return "\n".join(lines)


def export_json(project_path: Path) -> str:
    """Exporte le graphe au format JSON (pour autres visus)."""
    nodes = build_call_graph(project_path)
    return json.dumps({
        name: {
            "kind": n.kind,
            "file": n.file,
            "calls": n.calls,
            "called_by": n.called_by,
        }
        for name, n in nodes.items()
    }, indent=2)


def save_mermaid_to_file(project_path: Path, output_file: Path, focus: str | None = None) -> Path:
    """Sauvegarde le graphe Mermaid dans un fichier Markdown."""
    mermaid = export_mermaid(project_path, focus=focus)

    content = f"""# Call Graph — {project_path.name}

{'Centre sur : `' + focus + '`' if focus else 'Top des fonctions les plus connectees'}

```mermaid
{mermaid}
```

Genere par LocalCoder.
Visualisable dans : VS Code (extension Mermaid), GitHub, tout editeur Markdown moderne.
"""
    output_file.write_text(content)
    return output_file


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    focus = sys.argv[2] if len(sys.argv) > 2 else None
    print(export_mermaid(path, focus=focus))
