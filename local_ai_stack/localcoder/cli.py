"""CLI principal — le cerveau qui orchestre tout.

Usage:
    localcoder                     → Menu interactif
    localcoder scan [path]         → Analyse du projet (doublons, gros fichiers, stack)
    localcoder review [path]       → Review des derniers changements Git
    localcoder git [path]          → Rapport Git complet (commits, branches, hotspots)
    localcoder pr [path] [base]    → Review de PR avant merge
    localcoder check "tache"       → Analyse la complexite et recommande le mode
    localcoder precommit [path]    → Verification pre-commit
    localcoder code [path]         → Lance Aider avec le bon mode
    localcoder infra [path]        → Check infra (Railway, Supabase, Stripe, Vercel, env vars)
"""

from datetime import datetime
from pathlib import Path
import subprocess
import sys
import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt

from localcoder.scanner import scan_project
from localcoder.reviewer import review_git_changes
from localcoder.complexity import analyze_task_complexity
from localcoder.git_analyzer import full_git_report, format_git_report
from localcoder.conventions_generator import update_conventions_file, detect_project_stack
from localcoder.upgrade_advisor import analyze_environment, format_all_proposals
from localcoder.project_memory import (
    index_project, search_symbols, search_features,
    find_orphans, get_index_stats, get_features_by_kind,
    get_recent_sessions, log_session, Session,
)
from localcoder.partial_detector import detect_partial_features
from localcoder.call_graph import build_call_graph, save_mermaid_to_file
from localcoder.hooks_installer import install_hooks, uninstall_hooks, hooks_status
from localcoder.dead_code import find_dead_code
from localcoder.workspace import launch_workspace, launch_ultra_workspace, is_tmux_available, is_in_tmux
from localcoder.multi_ask import ask_all_models
from localcoder.pr_reviewer import review_pr
from localcoder.pre_commit_check import run_all_checks
from localcoder.infra_checker import full_infra_check

console = Console()

SCRIPT_DIR = Path(__file__).parent.parent
CONFIGS = {
    "local": SCRIPT_DIR / ".aider.conf.yml",
    "gemini": SCRIPT_DIR / ".aider.conf.gemini.yml",
    "deepseek": SCRIPT_DIR / ".aider.conf.api.yml",
    "ultra": SCRIPT_DIR / ".aider.conf.ultra.yml",
}


def check_connectivity() -> bool:
    try:
        subprocess.run(
            ["curl", "-s", "--max-time", "3", "https://google.com"],
            capture_output=True, timeout=5,
        )
        return True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_api_key(mode: str) -> bool:
    if mode == "local":
        return True
    if mode == "gemini":
        return bool(os.environ.get("GEMINI_API_KEY"))
    if mode == "deepseek":
        return bool(os.environ.get("DEEPSEEK_API_KEY"))
    return False


def resolve_project_path(arg: str | None = None) -> Path:
    if arg:
        return Path(arg).resolve()
    return Path.cwd()


# ===== COMMANDES =====

def cmd_scan(project_path: Path, strict: bool = False) -> None:
    """Analyse complete du projet."""
    mode_label = "strict" if strict else "intelligent"
    with console.status(f"[bold cyan]Analyse du projet (mode {mode_label})..."):
        report = scan_project(project_path, strict=strict)

    console.print(Panel(
        f"[bold]{report['project']}[/bold]\n"
        f"Fichiers: {report['total_files']} | Lignes: {report['total_lines']:,}",
        title="Scan projet", border_style="cyan",
    ))

    # Stack
    if report["stack"]["technologies"]:
        console.print("\n[bold]Stack:[/bold]")
        for tech in report["stack"]["technologies"]:
            console.print(f"  [green]>[/green] {tech}")

    # Langages
    table = Table(title="Lignes par langage")
    table.add_column("Langage", style="cyan")
    table.add_column("Lignes", justify="right", style="green")
    for lang, count in report["lines_by_language"].items():
        table.add_row(lang, f"{count:,}")
    console.print(table)

    # Gros fichiers
    if report["large_files"]:
        console.print(f"\n[bold red]Fichiers trop gros ({len(report['large_files'])}):[/bold red]")
        for f in report["large_files"][:15]:
            style = "red bold" if f["severity"] == "critique" else "yellow"
            console.print(f"  [{style}]{f['lines']:>5} lignes[/{style}] {f['file']}")

    # Doublons
    if report["duplicates"]:
        console.print(f"\n[bold red]Doublons ({len(report['duplicates'])}):[/bold red]")
        for d in report["duplicates"][:10]:
            console.print(f"  [red]>[/red] {d['file_a']}:{d['line_a']} <-> {d['file_b']}:{d['line_b']}")
    else:
        console.print("\n[green]Aucun doublon detecte[/green]")

    # TODOs
    if report["todos"]:
        console.print(f"\n[bold yellow]TODOs/BUGs ({len(report['todos'])}):[/bold yellow]")
        for t in report["todos"][:15]:
            console.print(f"  [{t['type']}] {t['file']}:{t['line']} — {t['content']}")


def cmd_review(project_path: Path) -> None:
    """Review des derniers changements Git."""
    with console.status("[bold cyan]Review en cours..."):
        report = review_git_changes(project_path)

    if not report.files_changed:
        console.print("[yellow]Aucun changement Git detecte[/yellow]")
        return

    score = report.score
    color = "green" if score >= 7 else "yellow" if score >= 4 else "red"
    console.print(Panel(
        f"Score: [{color}]{score}/10[/{color}] | Fichiers: {len(report.files_changed)}",
        title="Review", border_style=color,
    ))

    for f in report.files_changed:
        console.print(f"  [cyan]>[/cyan] {f}")

    if report.issues:
        console.print(f"\n[bold red]Problemes ({len(report.issues)}):[/bold red]")
        for issue in report.issues:
            icon = {"error": "[red]!![/red]", "warning": "[yellow]![/yellow]", "info": "[blue]~[/blue]"}
            console.print(f"  {icon[issue.severity]} [{issue.rule}] {issue.file}:{issue.line} — {issue.message}")


def cmd_git(project_path: Path) -> None:
    """Rapport Git complet."""
    with console.status("[bold cyan]Analyse Git..."):
        report = full_git_report(project_path)

    console.print(Panel(
        f"Branche: [bold]{report.current_branch}[/bold]\n"
        f"Etat: {'[green]propre[/green]' if report.is_clean else '[red]modifications non commitees[/red]'}",
        title="Git", border_style="cyan",
    ))

    if report.uncommitted_files:
        console.print(f"\n[yellow]Non commites ({len(report.uncommitted_files)}):[/yellow]")
        for f in report.uncommitted_files[:15]:
            console.print(f"  [yellow]![/yellow] {f}")

    console.print(f"\n[bold]Derniers commits ({len(report.recent_commits)}):[/bold]")
    for c in report.recent_commits[:15]:
        console.print(f"  [dim]{c.hash}[/dim] {c.date} — {c.message} [dim]+{c.insertions}/-{c.deletions}[/dim]")

    if report.files_at_risk:
        console.print(f"\n[bold red]Hotspots (fichiers instables):[/bold red]")
        for h in report.files_at_risk[:10]:
            color = "red" if h["risk"] == "eleve" else "yellow"
            console.print(f"  [{color}]{h['modifications']}x[/{color}] {h['file']}")


def cmd_pr(project_path: Path, base_branch: str = "main") -> None:
    """Review de PR avant merge."""
    console.print(Panel(
        f"Review de la branche courante vs [bold]{base_branch}[/bold]",
        title="PR Review", border_style="cyan",
    ))

    with console.status("[bold cyan]Analyse de la PR..."):
        report = review_pr(project_path, base_branch, run_ci=True)

    # Verdict
    if report.can_merge:
        console.print(Panel(
            f"[bold green]APPROUVE[/bold green] — La PR peut etre mergee\n"
            f"Commits: {report.commits_count} | Fichiers: {report.files_changed}",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold red]BLOQUE[/bold red] — La PR ne peut PAS etre mergee\n"
            f"Bloquants: {len(report.blockers)}",
            border_style="red",
        ))
        for b in report.blockers:
            console.print(f"  [red]!![/red] {b}")

    if report.issues:
        console.print(f"\n[bold]Problemes de code ({len(report.issues)}):[/bold]")
        for issue in report.issues:
            console.print(f"  [{issue.severity}] {issue.file}:{issue.line} — {issue.message}")

    if report.duplicates_introduced:
        console.print(f"\n[bold yellow]Doublons dans la PR ({len(report.duplicates_introduced)}):[/bold yellow]")
        for d in report.duplicates_introduced:
            console.print(f"  {d['file_a']} <-> {d['file_b']}")

    if report.warnings:
        console.print(f"\n[yellow]Warnings ({len(report.warnings)}):[/yellow]")
        for w in report.warnings:
            console.print(f"  [yellow]![/yellow] {w}")

    if report.recommendations:
        console.print(f"\n[cyan]Recommendations:[/cyan]")
        for r in report.recommendations:
            console.print(f"  [cyan]>[/cyan] {r}")

    console.print(f"\nTests: {report.tests_status}")
    console.print(f"Lint: {report.lint_status}")


def cmd_check(task: str) -> None:
    """Analyse de complexite."""
    result = analyze_task_complexity(task)
    colors = {"simple": "green", "medium": "yellow", "complex": "red"}
    color = colors[result.level]

    console.print(Panel(
        f"[bold]Tache:[/bold] {task}\n\n"
        f"Complexite: [{color}]{result.level.upper()} ({result.score}/10)[/{color}]\n"
        f"Raison: {result.reason}\n"
        f"Mode: [{color}]{result.mode}[/{color}]\n"
        f"Modele: {result.model}",
        title="Analyse", border_style=color,
    ))


def cmd_precommit(project_path: Path) -> None:
    """Verification pre-commit."""
    errors, warnings = run_all_checks(project_path)

    if warnings:
        console.print(f"\n[yellow]Warnings ({len(warnings)}):[/yellow]")
        for w in warnings:
            console.print(f"  [yellow]![/yellow] {w}")

    if errors:
        console.print(f"\n[bold red]BLOQUE ({len(errors)} erreurs):[/bold red]")
        for e in errors:
            console.print(f"  [red]!![/red] {e}")
    else:
        console.print("\n[green]Toutes les verifications passent.[/green]")


def cmd_infra(project_path: Path) -> None:
    """Check complet de l'infrastructure."""
    with console.status("[bold cyan]Verification infrastructure..."):
        report = full_infra_check(project_path)

    # Services
    table = Table(title="Services CLI")
    table.add_column("Service", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Details")

    for s in report.services:
        status = "[green]OK[/green]" if s.available else "[red]MANQUANT[/red]"
        table.add_row(s.name, status, s.details)
    console.print(table)

    # Erreurs de services
    for s in report.services:
        for e in s.errors:
            console.print(f"  [red]!![/red] {s.name}: {e}")

    # Env vars
    if report.env_vars:
        missing = {k: v for k, v in report.env_vars.items() if v == "missing"}
        present = {k: v for k, v in report.env_vars.items() if v != "missing"}
        console.print(f"\n[bold]Variables d'environnement:[/bold] {len(present)} ok, {len(missing)} manquantes")
        if missing:
            for k in sorted(missing):
                console.print(f"  [red]!![/red] {k}")

    # Warnings
    if report.warnings:
        console.print(f"\n[yellow]Warnings ({len(report.warnings)}):[/yellow]")
        for w in report.warnings:
            console.print(f"  [yellow]![/yellow] {w}")


def cmd_code(project_path: Path) -> None:
    """Lance Aider avec le bon mode."""
    online = check_connectivity()

    console.print(Panel(
        "[bold]Choisis ton mode:[/bold]\n\n"
        "  [green]1)[/green] Local — qwen2.5-coder:14b (0E, avion OK)\n"
        + ("  [green]2)[/green] Gemini 2.5 Pro (0E, 1M contexte)\n"
           "  [green]3)[/green] DeepSeek-R1 (~0.005$/req, raisonnement)\n"
           if online else
           "  [red]2)[/red] Gemini [HORS LIGNE]\n"
           "  [red]3)[/red] DeepSeek [HORS LIGNE]\n"),
        title="LocalCoder", border_style="cyan",
    ))

    choice = IntPrompt.ask("Mode", choices=["1", "2", "3"], default=2 if online else 1)
    modes = {1: "local", 2: "gemini", 3: "deepseek"}
    mode = modes[choice]

    if not online and mode != "local":
        console.print("[red]Pas de connexion. Mode local force.[/red]")
        mode = "local"

    if not check_api_key(mode):
        key_name = "GEMINI_API_KEY" if mode == "gemini" else "DEEPSEEK_API_KEY"
        url = "https://aistudio.google.com/apikey" if mode == "gemini" else "https://platform.deepseek.com/"
        console.print(f"[red]{key_name} non definie.[/red]")
        console.print(f"[yellow]{url}[/yellow]")
        return

    config_file = CONFIGS[mode]

    # Copier CONVENTIONS.md de base si absent
    conventions_src = SCRIPT_DIR / "CONVENTIONS.md"
    conventions_dst = project_path / "CONVENTIONS.md"
    if not conventions_dst.exists() and conventions_src.exists():
        import shutil
        shutil.copy2(conventions_src, conventions_dst)
        console.print("[green]CONVENTIONS.md copie[/green]")

    # Generer la section stack adaptee au projet
    stack = detect_project_stack(project_path)
    if stack:
        result = update_conventions_file(project_path)
        console.print(f"[green]{result}[/green]")

    # Objectif de la session (optionnel mais enregistre dans le journal)
    goal = Prompt.ask(
        "[cyan]Objectif de la session[/cyan] [dim](optionnel, Entree pour ignorer)[/dim]",
        default="",
    )

    # Capturer l'etat Git AVANT la session
    started_at = datetime.now().isoformat(timespec="seconds")
    commits_before = _get_head_commit(project_path)
    files_before = _get_uncommitted_files(project_path)

    console.print(f"\n[bold green]Lancement Aider — mode {mode}[/bold green]\n")

    # Lancer Aider avec subprocess (pas execvp) pour pouvoir logger apres
    try:
        subprocess.run(
            ["aider", "--config", str(config_file)],
            cwd=project_path,
        )
    except KeyboardInterrupt:
        pass

    # Apres la session : logger
    ended_at = datetime.now().isoformat(timespec="seconds")
    commits_after = _get_commits_since(project_path, commits_before)
    files_after = _get_uncommitted_files(project_path)

    # Fichiers modifies = nouveaux dans le dirty set + fichiers dans les nouveaux commits
    files_modified = list(set(files_after) - set(files_before))
    for c in commits_after:
        files_modified.extend(_get_files_in_commit(project_path, c))
    files_modified = sorted(set(files_modified))

    session = Session(
        started_at=started_at,
        ended_at=ended_at,
        goal=goal or "(non specifie)",
        mode=mode,
        files_modified=files_modified,
        commits=commits_after,
        summary=f"{len(commits_after)} commits, {len(files_modified)} fichiers modifies",
    )
    log_session(project_path, session)

    console.print(
        f"\n[bold green]Session enregistree[/bold green] — "
        f"{len(commits_after)} commits, {len(files_modified)} fichiers"
    )
    console.print(f"[dim]localcoder journal pour voir l'historique[/dim]")


def _get_head_commit(project_path: Path) -> str:
    """Retourne le SHA du HEAD actuel."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=project_path, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _get_commits_since(project_path: Path, old_head: str) -> list[str]:
    """Retourne les SHAs des commits crees apres old_head."""
    if not old_head:
        return []
    try:
        r = subprocess.run(
            ["git", "log", "--format=%H", f"{old_head}..HEAD"],
            capture_output=True, text=True, cwd=project_path, timeout=5,
        )
        return [c.strip() for c in r.stdout.splitlines() if c.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _get_files_in_commit(project_path: Path, commit_sha: str) -> list[str]:
    """Retourne les fichiers modifies par un commit."""
    try:
        r = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha],
            capture_output=True, text=True, cwd=project_path, timeout=5,
        )
        return [f.strip() for f in r.stdout.splitlines() if f.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _get_uncommitted_files(project_path: Path) -> list[str]:
    """Retourne les fichiers non commites actuels."""
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=project_path, timeout=5,
        )
        return [line[3:].strip() for line in r.stdout.splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def show_main_menu(project_path: Path) -> None:
    """Menu principal."""
    console.print(Panel(
        "[bold cyan]LOCALCODER[/bold cyan] — Systeme d'agents IA\n"
        f"[dim]{project_path}[/dim]",
        border_style="cyan",
    ))

    console.print(
        "\n[bold cyan]Analyse & Memoire[/bold cyan]\n"
        "  [green]1)[/green] [bold]scan[/bold]       Analyser le projet (doublons, gros fichiers)\n"
        "  [green]2)[/green] [bold]index[/bold]      Indexer le projet en memoire SQLite\n"
        "  [green]3)[/green] [bold]find[/bold]       Chercher une feature/fonction existante\n"
        "  [green]4)[/green] [bold]features[/bold]   Liste des features par type\n"
        "  [green]5)[/green] [bold]orphans[/bold]    Routes API orphelines\n"
        "  [green]6)[/green] [bold]journal[/bold]    Historique des sessions\n"
        "\n[bold cyan]Git & Review[/bold cyan]\n"
        "  [green]7)[/green] [bold]git[/bold]        Rapport Git (commits, hotspots)\n"
        "  [green]8)[/green] [bold]review[/bold]     Review des derniers changements\n"
        "  [green]9)[/green] [bold]pr[/bold]         Review de PR avant merge\n"
        "  [green]10)[/green] [bold]precommit[/bold]  Verification pre-commit\n"
        "\n[bold cyan]Infra & Setup[/bold cyan]\n"
        "  [green]11)[/green] [bold]infra[/bold]      Check Railway/Supabase/Stripe/env\n"
        "  [green]12)[/green] [bold]advise[/bold]     Propose des upgrades intelligents\n"
        "  [green]13)[/green] [bold]adapt[/bold]      Genere CONVENTIONS adaptees au projet\n"
        "\n[bold cyan]Coder[/bold cyan]\n"
        "  [green]14)[/green] [bold]check[/bold]      Evaluer la complexite d'une tache\n"
        "  [green]15)[/green] [bold]code[/bold]       Lancer Aider (choisir le mode)\n"
        "\n  [green]0)[/green] [bold]quit[/bold]       Quitter\n"
    )

    choice = IntPrompt.ask("Choix", choices=[str(i) for i in range(16)])

    actions = {
        1: lambda: cmd_scan(project_path),
        2: lambda: cmd_index(project_path),
        3: lambda: cmd_find(project_path, Prompt.ask("Terme a chercher")),
        4: lambda: cmd_features(project_path),
        5: lambda: cmd_orphans(project_path),
        6: lambda: cmd_journal(project_path),
        7: lambda: cmd_git(project_path),
        8: lambda: cmd_review(project_path),
        9: lambda: cmd_pr(project_path, Prompt.ask("Branche de base", default="main")),
        10: lambda: cmd_precommit(project_path),
        11: lambda: cmd_infra(project_path),
        12: lambda: cmd_advise(),
        13: lambda: _cmd_adapt(project_path),
        14: lambda: cmd_check(Prompt.ask("Decris la tache")),
        15: lambda: cmd_code(project_path),
        0: lambda: sys.exit(0),
    }

    actions[choice]()


def cmd_index(project_path: Path) -> None:
    """Indexe le projet dans la base de memoire."""
    console.print(Panel(
        f"[bold cyan]INDEXATION[/bold cyan]\n[dim]{project_path}[/dim]",
        border_style="cyan",
    ))

    with console.status("[bold cyan]Analyse en cours..."):
        stats = index_project(project_path)

    table = Table(title="Memoire projet creee")
    table.add_column("Element", style="cyan")
    table.add_column("Nombre", justify="right", style="green")
    table.add_row("Fichiers scannes", str(stats["files_scanned"]))
    table.add_row("Symboles extraits", str(stats["symbols"]))
    table.add_row("Features detectees", str(stats["features"]))
    table.add_row("Integrations", str(stats["integrations"]))
    console.print(table)

    # Features par type
    by_kind = get_features_by_kind(project_path)
    if by_kind:
        console.print("\n[bold]Features par type:[/bold]")
        for kind, count in sorted(by_kind.items(), key=lambda x: -x[1]):
            console.print(f"  [cyan]{kind:15s}[/cyan] {count}")

    console.print(f"\n[dim]Base SQLite: {project_path}/.localcoder/memory.sqlite[/dim]")


def cmd_find(project_path: Path, query: str) -> None:
    """Cherche dans la memoire : symboles + features."""
    if not query:
        console.print("[red]Usage: localcoder find \"terme\"[/red]")
        return

    # S'assurer que l'index existe
    stats = get_index_stats(project_path)
    if not stats.get("indexed"):
        console.print("[yellow]Projet pas encore indexe. Lancement de l'indexation...[/yellow]")
        index_project(project_path)

    console.print(Panel(
        f"Recherche: [bold]{query}[/bold]",
        border_style="cyan",
    ))

    # Features
    features = search_features(project_path, query)
    if features:
        console.print(f"\n[bold green]Features trouvees ({len(features)}):[/bold green]")
        for f in features[:15]:
            files_str = f["files"][0] if f["files"] else ""
            console.print(f"  [cyan][{f['kind']:12s}][/cyan] [bold]{f['name']}[/bold]")
            console.print(f"    [dim]{files_str}[/dim]")

    # Symboles
    symbols = search_symbols(project_path, query, limit=20)
    if symbols:
        console.print(f"\n[bold green]Symboles trouves ({len(symbols)}):[/bold green]")
        for s in symbols[:15]:
            parent = f" (in {s['parent']})" if s['parent'] else ""
            console.print(f"  [cyan][{s['kind']:8s}][/cyan] [bold]{s['name']}[/bold]{parent}")
            console.print(f"    [dim]{s['file']}:{s['line_start']}[/dim]")
            if s['signature']:
                console.print(f"    [italic]{s['signature'][:80]}[/italic]")

    if not features and not symbols:
        console.print(f"\n[yellow]Aucun resultat pour '{query}'[/yellow]")
        console.print("[dim]Cette feature/fonction n'existe probablement pas — tu peux la creer.[/dim]")
    else:
        console.print(f"\n[bold yellow]CONSEIL:[/bold yellow] Reutilise ces elements existants plutot que de recreer.")


def cmd_orphans(project_path: Path) -> None:
    """Trouve les routes API sans appel frontend."""
    stats = get_index_stats(project_path)
    if not stats.get("indexed"):
        console.print("[yellow]Indexation requise...[/yellow]")
        index_project(project_path)

    orphans = find_orphans(project_path)

    console.print(Panel(
        f"[bold]Routes API orphelines[/bold]\n"
        f"[dim]Routes backend jamais appelees par le frontend (matching approximatif)[/dim]",
        border_style="yellow",
    ))

    if not orphans:
        console.print("[green]Aucune route orpheline detectee.[/green]")
        return

    # Grouper par fichier
    by_file: dict[str, list[str]] = {}
    for o in orphans:
        by_file.setdefault(o["source_file"], []).append(o["source_name"])

    console.print(f"\n[bold yellow]{len(orphans)} routes dans {len(by_file)} fichiers[/bold yellow]\n")
    for filepath in sorted(by_file.keys())[:15]:
        console.print(f"[bold cyan]{filepath}[/bold cyan]")
        for route in by_file[filepath][:5]:
            console.print(f"  [yellow]>[/yellow] {route}")
        if len(by_file[filepath]) > 5:
            console.print(f"  [dim]... +{len(by_file[filepath]) - 5} autres[/dim]")
    console.print("\n[dim]Note: le matching est approximatif. Verifier manuellement avant de supprimer.[/dim]")


def cmd_features(project_path: Path, kind: str | None = None) -> None:
    """Liste les features du projet."""
    stats = get_index_stats(project_path)
    if not stats.get("indexed"):
        console.print("[yellow]Indexation requise...[/yellow]")
        index_project(project_path)

    by_kind = get_features_by_kind(project_path)

    console.print(Panel(
        f"[bold]Features du projet[/bold]",
        border_style="cyan",
    ))

    table = Table()
    table.add_column("Type", style="cyan")
    table.add_column("Nombre", justify="right", style="green")
    total = 0
    for k, count in sorted(by_kind.items(), key=lambda x: -x[1]):
        table.add_row(k, str(count))
        total += count
    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total}[/bold]")
    console.print(table)


def cmd_ask(query: str, project_path: Path, files: list[str] | None = None, include_repo_map: bool = True) -> None:
    """Pose une question aux 3 modeles en parallele.

    Args:
        query: La question a poser.
        project_path: Racine du projet courant.
        files: Liste de fichiers a inclure comme contexte (--file flag).
        include_repo_map: Si True et que le projet est indexe, injecte automatiquement
                          un extrait du repo-map depuis la memoire SQLite.
    """
    if not query:
        console.print("[red]Usage: localcoder ask \"ta question\" [--file path1 --file path2][/red]")
        return

    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    has_deepseek = bool(os.environ.get("DEEPSEEK_API_KEY"))

    active = ["Local (qwen 14b)"]
    if has_gemini:
        active.append("Gemini 2.5 Flash")
    if has_deepseek:
        active.append("DeepSeek-R1")

    # Construire la liste des fichiers contextes (paths absolus)
    context_files: list[Path] = []
    if files:
        for f in files:
            p = Path(f)
            if not p.is_absolute():
                p = project_path / p
            if p.exists() and p.is_file():
                context_files.append(p)
            else:
                console.print(f"[yellow]Fichier introuvable : {f}[/yellow]")

    # Auto-inclure un extrait du repo-map depuis la memoire SQLite
    # (liste des features + gros fichiers concernes pour donner du contexte projet)
    auto_context = ""
    if include_repo_map:
        stats = get_index_stats(project_path)
        if stats.get("indexed"):
            try:
                kinds = get_features_by_kind(project_path)
                auto_context = (
                    f"\n### Contexte projet (depuis .localcoder/memory.sqlite)\n"
                    f"Projet: {project_path.name}\n"
                    f"Fichiers indexes: {stats.get('files_scanned', '?')}\n"
                    f"Symboles: {stats.get('symbols', '?')}\n"
                    f"Features: {', '.join(f'{k}={v}' for k, v in kinds.items())}\n"
                )
            except Exception:
                pass

    # Panel d'affichage
    file_info = f"\n[dim]Fichiers en contexte:[/dim] {len(context_files)}" if context_files else ""
    repo_info = f"\n[dim]Repo-map:[/dim] inclus" if auto_context else ""
    console.print(Panel(
        f"[bold]Question:[/bold] {query}\n\n"
        f"[dim]Modeles actifs:[/dim] {', '.join(active)}"
        f"{file_info}{repo_info}",
        title="MULTI-ASK",
        border_style="cyan",
    ))

    # Construire le prompt enrichi (repo-map inline + fichiers via parametre)
    enriched_query = auto_context + "\n\n" + query if auto_context else query

    with console.status("[bold cyan]Appel en parallele des 3 modeles..."):
        responses = ask_all_models(enriched_query, context_files=context_files or None)

    # Afficher chaque reponse dans un panel
    colors = {"local": "green", "gemini": "blue", "deepseek": "magenta"}
    icons = {"local": "LOCAL 14b", "gemini": "GEMINI 2.5 Flash", "deepseek": "DEEPSEEK-R1"}

    for r in responses:
        color = colors.get(r.mode, "white")
        icon = icons.get(r.mode, r.mode.upper())

        if r.error:
            content = f"[red]ERREUR: {r.error}[/red]"
        else:
            content = r.content

        console.print(Panel(
            content,
            title=f"{icon} — {r.duration:.1f}s",
            border_style=color,
        ))


def cmd_ultra(project_path: Path) -> None:
    """Lance le workspace ULTRA avec les 3 modeles en equipe."""
    if not is_tmux_available():
        console.print("[red]tmux non installe. brew install tmux[/red]")
        return
    if is_in_tmux():
        console.print("[red]Deja dans tmux. Detache avec Ctrl+b puis d.[/red]")
        return

    online = check_connectivity()
    if not online:
        console.print("[red]Mode ULTRA necessite une connexion internet (Gemini + DeepSeek)[/red]")
        console.print("[yellow]Utilise 'localcoder ide' en mode local pour l'offline.[/yellow]")
        return

    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    has_deepseek = bool(os.environ.get("DEEPSEEK_API_KEY"))

    if not has_gemini or not has_deepseek:
        console.print("[red]Mode ULTRA necessite GEMINI_API_KEY ET DEEPSEEK_API_KEY[/red]")
        if not has_gemini:
            console.print("  [yellow]GEMINI_API_KEY manquante: https://aistudio.google.com/apikey (gratuit)[/yellow]")
        if not has_deepseek:
            console.print("  [yellow]DEEPSEEK_API_KEY manquante: https://platform.deepseek.com/[/yellow]")
        return

    console.print(Panel(
        "[bold cyan]ULTRA MODE — 3 MODELES EN EQUIPE[/bold cyan]\n\n"
        "[green]Gemini 2.5 Pro[/green]   → Architecte (planifie, 1M contexte)\n"
        "[magenta]DeepSeek-R1[/magenta]      → Editeur (applique le plan, raisonnement)\n"
        "[yellow]Qwen local 7b[/yellow]    → Commits & resumes (gratuit)\n\n"
        "[bold]Layout tmux :[/bold]\n"
        "  Gauche       : Aider team (chat principal)\n"
        "  Droite haut  : Git status live\n"
        "  Droite mid   : Multi-ask helper (comparer 3 avis)\n"
        "  Droite bas   : Terminal libre\n\n"
        "[dim]Cout estime : ~0.005-0.01$/message (grace au free tier Gemini)[/dim]",
        border_style="cyan",
    ))

    # Adapter CONVENTIONS
    stack = detect_project_stack(project_path)
    conventions_dst = project_path / "CONVENTIONS.md"
    if not conventions_dst.exists():
        conventions_src = SCRIPT_DIR / "CONVENTIONS.md"
        if conventions_src.exists():
            import shutil
            shutil.copy2(conventions_src, conventions_dst)
    if stack:
        update_conventions_file(project_path)

    console.print(f"\n[bold green]Lancement du workspace ULTRA...[/bold green]")
    console.print("[dim]Ctrl+b puis fleche : naviguer | Ctrl+b z : zoom | Ctrl+b d : detacher[/dim]\n")

    try:
        launch_ultra_workspace(project_path, CONFIGS["ultra"])
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")


def cmd_ide(project_path: Path) -> None:
    """Lance le workspace IDE multi-panneaux (Aider + Git + Terminal)."""
    if not is_tmux_available():
        console.print("[red]tmux n'est pas installe.[/red]")
        console.print("[yellow]Installe avec : brew install tmux[/yellow]")
        return

    if is_in_tmux():
        console.print("[red]Tu es deja dans une session tmux.[/red]")
        console.print("[yellow]Detache avec Ctrl+b puis d, puis relance.[/yellow]")
        return

    online = check_connectivity()
    console.print(Panel(
        "[bold cyan]WORKSPACE IDE[/bold cyan]\n"
        "Layout multi-panneaux :\n"
        "  [green]Gauche[/green]       : Aider (chat, plan, code, execution)\n"
        "  [green]Droite haut[/green]  : Git status live\n"
        "  [green]Droite bas[/green]   : Terminal libre",
        border_style="cyan",
    ))

    # Choix du mode Aider
    console.print(
        "\n[bold]Mode Aider:[/bold]\n"
        "  [green]1)[/green] Local — qwen2.5-coder:14b\n"
        + ("  [green]2)[/green] Gemini 2.5 Pro (gratuit, 1M contexte)\n"
           "  [green]3)[/green] DeepSeek-R1 (payant, raisonnement profond)\n"
           if online else
           "  [red]2)[/red] Gemini [HORS LIGNE]\n"
           "  [red]3)[/red] DeepSeek [HORS LIGNE]\n")
    )

    choice = IntPrompt.ask("Mode", choices=["1", "2", "3"], default=2 if online else 1)
    modes = {1: "local", 2: "gemini", 3: "deepseek"}
    mode = modes[choice]

    if not online and mode != "local":
        console.print("[red]Pas de connexion. Mode local force.[/red]")
        mode = "local"

    if not check_api_key(mode):
        key_name = "GEMINI_API_KEY" if mode == "gemini" else "DEEPSEEK_API_KEY"
        console.print(f"[red]{key_name} non definie[/red]")
        return

    # Adapter CONVENTIONS
    stack = detect_project_stack(project_path)
    conventions_dst = project_path / "CONVENTIONS.md"
    if not conventions_dst.exists():
        conventions_src = SCRIPT_DIR / "CONVENTIONS.md"
        if conventions_src.exists():
            import shutil
            shutil.copy2(conventions_src, conventions_dst)
    if stack:
        update_conventions_file(project_path)

    console.print(f"\n[bold green]Lancement du workspace IDE (mode {mode})...[/bold green]")
    console.print("[dim]Raccourcis tmux: Ctrl+b puis fleche (navigation), z (zoom), d (detacher)[/dim]\n")

    try:
        launch_workspace(project_path, CONFIGS[mode], mode=mode)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")


def cmd_dead(project_path: Path, confidence: str = "high") -> None:
    """Detecte le code mort."""
    stats = get_index_stats(project_path)
    if not stats.get("indexed"):
        console.print("[yellow]Indexation requise...[/yellow]")
        index_project(project_path)

    with console.status("[bold cyan]Analyse du code mort..."):
        dead = find_dead_code(project_path, confidence_min=confidence)

    if not dead:
        console.print("[green]Aucun code mort detecte.[/green]")
        return

    # Grouper par fichier
    by_file: dict[str, list] = {}
    for d in dead:
        by_file.setdefault(d.file, []).append(d)

    console.print(Panel(
        f"[bold]{len(dead)} symboles probablement morts[/bold]\n"
        f"[dim]Niveau de confiance: {confidence}+[/dim]",
        title="Dead Code", border_style="yellow",
    ))

    # Stats par kind
    by_kind: dict[str, int] = {}
    for d in dead:
        by_kind[d.kind] = by_kind.get(d.kind, 0) + 1
    table = Table()
    table.add_column("Type", style="cyan")
    table.add_column("Nombre", justify="right", style="yellow")
    for kind, count in sorted(by_kind.items(), key=lambda x: -x[1]):
        table.add_row(kind, str(count))
    console.print(table)

    # Top fichiers avec le plus de code mort
    console.print(f"\n[bold]Top 10 fichiers avec code mort:[/bold]")
    top = sorted(by_file.items(), key=lambda x: -len(x[1]))[:10]
    for filepath, items in top:
        console.print(f"  [cyan]{filepath}[/cyan] — {len(items)} symboles morts")
        for d in items[:3]:
            sev = "red" if d.confidence == "high" else "yellow"
            console.print(f"    [{sev}]{d.kind}[/{sev}] [bold]{d.name}[/bold] (ligne {d.line})")

    console.print(
        f"\n[dim]Ceci est une detection statique. Verifier manuellement avant suppression.[/dim]\n"
        f"[dim]Certains symboles peuvent etre utilises dynamiquement (getattr, reflection).[/dim]"
    )


def cmd_hooks(project_path: Path, action: str = "install") -> None:
    """Installe ou retire les hooks Git pour auto-indexation."""
    if action == "install":
        result = install_hooks(project_path)
        console.print(Panel(
            "[bold]Installation des hooks Git[/bold]",
            border_style="cyan",
        ))
        if result["installed"]:
            for h in result["installed"]:
                console.print(f"  [green]OK[/green] {h} installe")
        if result["skipped"]:
            for h in result["skipped"]:
                console.print(f"  [yellow]~[/yellow] {h}")
        if result["errors"]:
            for e in result["errors"]:
                console.print(f"  [red]!![/red] {e}")
        console.print("\n[dim]Apres chaque commit, le projet sera re-indexe automatiquement.[/dim]")
    elif action == "uninstall":
        result = uninstall_hooks(project_path)
        for h in result["removed"]:
            console.print(f"  [green]OK[/green] {h} retire")
    elif action == "status":
        status = hooks_status(project_path)
        if not status["is_git_repo"]:
            console.print("[red]Pas un repo Git[/red]")
            return
        for name, state in status["hooks"].items():
            color = {"localcoder": "green", "other": "yellow", "not_installed": "red"}[state]
            console.print(f"  [{color}]{name}[/{color}]: {state}")
    else:
        console.print(f"[red]Action inconnue: {action}. Utilise install/uninstall/status[/red]")


def cmd_graph(project_path: Path, focus: str | None = None) -> None:
    """Genere un call graph du projet au format Mermaid."""
    stats = get_index_stats(project_path)
    if not stats.get("indexed"):
        console.print("[yellow]Indexation requise...[/yellow]")
        index_project(project_path)

    output_file = project_path / ".localcoder" / "call_graph.md"
    output_file.parent.mkdir(exist_ok=True)

    with console.status("[bold cyan]Construction du graphe..."):
        save_mermaid_to_file(project_path, output_file, focus=focus)

    graph = build_call_graph(project_path)
    ranked = sorted(
        graph.items(),
        key=lambda x: len(x[1].calls) + len(x[1].called_by),
        reverse=True,
    )

    console.print(Panel(
        f"[bold]Call Graph genere[/bold]\n"
        f"Fichier: [green]{output_file.relative_to(project_path)}[/green]\n"
        f"Noeuds: {len(graph)}\n" +
        (f"Focus: [cyan]{focus}[/cyan]" if focus else "Top 40 fonctions les plus connectees"),
        border_style="cyan",
    ))

    console.print("\n[bold]Top 10 symboles les plus connectes:[/bold]")
    for name, node in ranked[:10]:
        total = len(node.calls) + len(node.called_by)
        console.print(f"  [cyan]{name[:30]:30s}[/cyan] {total:>3} connexions [dim]({node.file})[/dim]")

    console.print(f"\n[dim]Ouvrir dans VS Code ou GitHub pour voir le diagramme rendu.[/dim]")


def cmd_partial(project_path: Path) -> None:
    """Detecte les features partielles / code incomplet."""
    with console.status("[bold cyan]Detection des features partielles..."):
        signals = detect_partial_features(project_path)

    if not signals:
        console.print("[green]Aucun signal de feature partielle detecte.[/green]")
        return

    # Stats par type
    by_kind: dict[str, list] = {}
    for s in signals:
        by_kind.setdefault(s.kind, []).append(s)

    console.print(Panel(
        f"[bold]{len(signals)} signaux detectes[/bold]",
        title="Features partielles", border_style="yellow",
    ))

    table = Table()
    table.add_column("Type", style="cyan")
    table.add_column("Nombre", justify="right")
    table.add_column("Severite max")
    for kind, sigs in sorted(by_kind.items(), key=lambda x: -len(x[1])):
        max_sev = "low"
        for s in sigs:
            if s.severity == "high":
                max_sev = "high"
                break
            if s.severity == "medium":
                max_sev = "medium"
        color = {"high": "red", "medium": "yellow", "low": "green"}[max_sev]
        table.add_row(kind, str(len(sigs)), f"[{color}]{max_sev}[/{color}]")
    console.print(table)

    # Top 15 signaux critiques
    critical = [s for s in signals if s.severity == "high"]
    if critical:
        console.print(f"\n[bold red]Critiques ({len(critical)}):[/bold red]")
        for s in critical[:10]:
            console.print(f"  [red]![/red] [{s.kind}] {s.file}:{s.line}")
            console.print(f"    [dim]{s.message}[/dim]")


def cmd_journal(project_path: Path) -> None:
    """Affiche le journal de bord des sessions."""
    sessions = get_recent_sessions(project_path, limit=20)

    console.print(Panel(
        f"[bold]Journal de bord[/bold] — {project_path.name}",
        border_style="cyan",
    ))

    if not sessions:
        console.print("[yellow]Aucune session enregistree pour ce projet.[/yellow]")
        console.print("[dim]Les sessions sont loggees automatiquement lors de 'localcoder code'.[/dim]")
        return

    for s in sessions:
        console.print(f"\n[bold cyan]{s['started_at']}[/bold cyan] [dim]({s['mode']})[/dim]")
        if s['goal']:
            console.print(f"  Objectif: {s['goal']}")
        if s['files_modified']:
            console.print(f"  Fichiers: {len(s['files_modified'])}")
        if s['summary']:
            console.print(f"  [italic]{s['summary']}[/italic]")


def cmd_advise() -> None:
    """Propose des upgrades intelligents sans rien modifier."""
    console.print(Panel(
        "[bold cyan]UPGRADE ADVISOR[/bold cyan]\n"
        "[dim]Analyse l'environnement et propose des ameliorations.[/dim]\n"
        "[dim]Aucune modification automatique — tu decides.[/dim]",
        border_style="cyan",
    ))

    with console.status("[bold cyan]Analyse..."):
        proposals = analyze_environment()

    if not proposals:
        console.print("\n[green]Environnement optimal. Aucune amelioration proposee.[/green]")
        return

    console.print(f"\n[bold yellow]{len(proposals)} proposition(s) detectee(s)[/bold yellow]\n")

    for i, p in enumerate(proposals, 1):
        console.print(Panel(
            f"[bold]{p.title}[/bold]\n\n"
            f"[dim]Contexte:[/dim] {p.context}\n"
            f"[dim]Probleme:[/dim] {p.problem}",
            title=f"Proposition {i}/{len(proposals)}",
            border_style="yellow",
        ))

        for j, opt in enumerate(p.options, 1):
            border = "green" if opt.recommended else "dim"
            tag = " [RECOMMANDE]" if opt.recommended else ""
            content = f"[bold]{opt.action}[/bold]\n"
            if opt.pros:
                content += "\n[green]Avantages:[/green]\n"
                for pro in opt.pros:
                    content += f"  + {pro}\n"
            if opt.cons:
                content += "\n[red]Inconvenients:[/red]\n"
                for con in opt.cons:
                    content += f"  - {con}\n"
            if opt.commands:
                content += "\n[cyan]Commandes:[/cyan]\n"
                for cmd in opt.commands:
                    content += f"  [dim]$[/dim] {cmd}\n"
            if opt.reason:
                content += f"\n[italic]Raison: {opt.reason}[/italic]"

            console.print(Panel(
                content.rstrip(),
                title=f"Option {j}: {opt.name}{tag}",
                border_style=border,
            ))

    console.print(
        "\n[bold]IMPORTANT:[/bold] Aucune modification n'a ete faite.\n"
        "A toi de choisir et d'executer les commandes si tu veux.\n"
    )


def _cmd_adapt(project_path: Path) -> None:
    """Genere les conventions adaptees au projet."""
    stack = detect_project_stack(project_path)
    if not stack:
        console.print("[yellow]Aucune stack detectee[/yellow]")
        return

    console.print(f"[bold]Stack detectee ({len(stack)} technos):[/bold]")
    for tech in stack:
        console.print(f"  [green]>[/green] {tech}")

    conventions_dst = project_path / "CONVENTIONS.md"
    if not conventions_dst.exists():
        # Copier la base d'abord
        import shutil
        base = SCRIPT_DIR / "CONVENTIONS.md"
        if base.exists():
            shutil.copy2(base, conventions_dst)

    if conventions_dst.exists():
        result = update_conventions_file(project_path)
        console.print(f"\n[green]{result}[/green]")
    else:
        console.print("[red]Pas de CONVENTIONS.md a mettre a jour[/red]")


def main():
    """Point d'entree CLI."""
    if len(sys.argv) > 1:
        command = sys.argv[1]

        # Commandes qui prennent une query/focus, pas un path en 2eme arg
        QUERY_COMMANDS = {"check", "find", "graph", "hooks", "ask"}

        if command in QUERY_COMMANDS:
            path = Path.cwd()
        else:
            path = resolve_project_path(sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None)

        strict = "--strict" in sys.argv
        no_repo_map = "--no-repo-map" in sys.argv

        # Extraire les --file path (peut etre repete)
        ask_files: list[str] = []
        i = 0
        while i < len(sys.argv):
            if sys.argv[i] == "--file" and i + 1 < len(sys.argv):
                ask_files.append(sys.argv[i + 1])
                i += 2
            else:
                i += 1

        # argv_clean : retirer tous les flags (--strict, --file X, --no-repo-map)
        argv_clean = []
        i = 0
        while i < len(sys.argv):
            a = sys.argv[i]
            if a == "--file":
                i += 2  # skip --file et sa valeur
                continue
            if a.startswith("--"):
                i += 1
                continue
            argv_clean.append(a)
            i += 1

        # Recuperer la query/kind pour find/features (tout ce qui suit la commande et le path)
        find_query = " ".join(argv_clean[2:]) if len(argv_clean) > 2 else ""
        check_query = " ".join(argv_clean[2:]) if len(argv_clean) > 2 else ""

        commands = {
            "scan": lambda: cmd_scan(path, strict=strict),
            "review": lambda: cmd_review(path),
            "git": lambda: cmd_git(path),
            "pr": lambda: cmd_pr(path, argv_clean[3] if len(argv_clean) > 3 else "main"),
            "check": lambda: cmd_check(check_query),
            "precommit": lambda: cmd_precommit(path),
            "infra": lambda: cmd_infra(path),
            "adapt": lambda: _cmd_adapt(path),
            "advise": lambda: cmd_advise(),
            "index": lambda: cmd_index(path),
            "find": lambda: cmd_find(path, find_query),
            "orphans": lambda: cmd_orphans(path),
            "features": lambda: cmd_features(path),
            "partial": lambda: cmd_partial(path),
            "graph": lambda: cmd_graph(path, argv_clean[2] if len(argv_clean) > 2 else None),
            "hooks": lambda: cmd_hooks(path, argv_clean[2] if len(argv_clean) > 2 else "install"),
            "dead": lambda: cmd_dead(path),
            "ide": lambda: cmd_ide(path),
            "ultra": lambda: cmd_ultra(path),
            "ask": lambda: cmd_ask(" ".join(argv_clean[2:]), path, files=ask_files, include_repo_map=not no_repo_map),
            "journal": lambda: cmd_journal(path),
            "code": lambda: cmd_code(path),
        }

        if command in commands:
            commands[command]()
        else:
            console.print(f"[red]Commande inconnue: {command}[/red]")
            console.print(
                "Commandes disponibles:\n"
                "  Memoire    : scan [--strict], index, find, features, partial, orphans, dead, graph, journal\n"
                "  Git/Review : git, review, pr, precommit\n"
                "  Infra      : infra, advise, adapt, hooks [install|uninstall|status]\n"
                "  Coder      : check, code, ide, ultra, ask"
            )
    else:
        show_main_menu(Path.cwd())


if __name__ == "__main__":
    main()
