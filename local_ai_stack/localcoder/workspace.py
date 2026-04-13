"""Workspace IDE — environnement multi-panneaux via tmux.

Cree une session tmux avec :
- Panneau principal (60%) : Aider (chat IA, plan/code/execution)
- Panneau droite haut (20%) : Git status live + file watcher
- Panneau droite bas (20%) : Terminal libre pour commandes shell

Raccourcis tmux :
- Ctrl+b puis flèche : naviguer entre panneaux
- Ctrl+b puis z : zoomer/dezoomer un panneau
- Ctrl+b puis d : detacher (garde la session en arriere-plan)
- tmux attach : reattacher une session detachee
- Ctrl+b puis & : fermer le panneau
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import requests


def is_tmux_available() -> bool:
    """Verifie si tmux est installe."""
    try:
        subprocess.run(["tmux", "-V"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_in_tmux() -> bool:
    """Verifie si on est deja dans une session tmux."""
    import os
    return bool(os.environ.get("TMUX"))


def session_exists(session_name: str) -> bool:
    """Verifie si une session tmux existe deja."""
    r = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True,
    )
    return r.returncode == 0


def kill_session(session_name: str) -> None:
    """Tue une session tmux existante."""
    subprocess.run(
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True,
    )


def create_workspace(
    project_path: Path,
    aider_config: Path,
    mode: str = "local",
) -> str:
    """Cree un workspace tmux avec Aider + Git + Terminal.

    Layout :
    +----------------------------+---------------+
    |                            |  Git / Watch  |
    |                            |    (top)      |
    |         Aider              |               |
    |        (principal)         +---------------+
    |                            |               |
    |                            |   Terminal    |
    |                            |    (bottom)   |
    +----------------------------+---------------+

    Returns:
        Le nom de la session tmux creee.
    """
    project_path = Path(project_path).resolve()
    session_name = f"localcoder-{project_path.name}"

    # Nettoyer une eventuelle session existante
    if session_exists(session_name):
        kill_session(session_name)

    aider_cmd = f"aider --config {aider_config}"

    # 1. Creer la session avec le panneau principal (Aider)
    subprocess.run([
        "tmux", "new-session", "-d",
        "-s", session_name,
        "-c", str(project_path),
        "-x", "200", "-y", "50",  # Taille minimum
    ], check=True)

    # Configurer la session
    subprocess.run([
        "tmux", "set-option", "-t", session_name,
        "status-left", f"[LocalCoder {mode}] ",
    ])
    subprocess.run([
        "tmux", "set-option", "-t", session_name,
        "status-right", " %H:%M ",
    ])

    # 2. Split vertical : droite pour git + terminal (40% largeur)
    subprocess.run([
        "tmux", "split-window", "-h",
        "-t", f"{session_name}:0.0",
        "-c", str(project_path),
        "-p", "35",
    ], check=True)

    # 3. Split horizontal dans la partie droite : haut (git) + bas (terminal)
    subprocess.run([
        "tmux", "split-window", "-v",
        "-t", f"{session_name}:0.1",
        "-c", str(project_path),
        "-p", "60",
    ], check=True)

    # Maintenant on a 3 panneaux : 0 (gauche/aider), 1 (droite-haut/git), 2 (droite-bas/terminal)

    # 4. Lancer le git watcher dans le panneau 1
    git_watch_cmd = (
        'clear && echo "=== GIT STATUS (auto-refresh 5s) ===" && '
        'while true; do '
        'clear; '
        'echo "=== GIT STATUS ($(date +%H:%M:%S)) ==="; '
        'echo ""; '
        'git status --short 2>/dev/null || echo "Pas un repo Git"; '
        'echo ""; '
        'echo "=== RECENT COMMITS ==="; '
        'git log --oneline -5 2>/dev/null; '
        'sleep 5; '
        'done'
    )
    subprocess.run([
        "tmux", "send-keys",
        "-t", f"{session_name}:0.1",
        git_watch_cmd,
        "Enter",
    ], check=True)

    # 5. Lancer un message de bienvenue dans le terminal (panneau 2)
    welcome_cmd = (
        'clear && '
        'echo "=== TERMINAL LIBRE ===" && '
        'echo "" && '
        'echo "Commandes utiles :" && '
        'echo "  localcoder scan      - analyse projet" && '
        'echo "  localcoder find X    - chercher X" && '
        'echo "  localcoder partial   - features partielles" && '
        'echo "  localcoder dead      - code mort" && '
        'echo "  localcoder graph X   - call graph" && '
        'echo "" && '
        'echo "Ctrl+b puis fleche : naviguer entre panneaux" && '
        'echo "Ctrl+b puis z : zoom/dezoom" && '
        'echo "Ctrl+b puis d : detacher (session continue)" && '
        'echo ""'
    )
    subprocess.run([
        "tmux", "send-keys",
        "-t", f"{session_name}:0.2",
        welcome_cmd,
        "Enter",
    ], check=True)

    # 6. Lancer Aider dans le panneau principal (panneau 0)
    subprocess.run([
        "tmux", "send-keys",
        "-t", f"{session_name}:0.0",
        aider_cmd,
        "Enter",
    ], check=True)

    # 7. Focus sur le panneau Aider
    subprocess.run([
        "tmux", "select-pane",
        "-t", f"{session_name}:0.0",
    ], check=True)

    return session_name


def create_ultra_workspace(
    project_path: Path,
    aider_ultra_config: Path,
) -> str:
    """Cree un workspace tmux ULTRA avec les 3 modeles accessibles simultanement.

    Layout :
    +--------------------------+-------------------+
    |                          |  Git status       |
    |  Aider TEAM              +-------------------+
    |  (Gemini+DeepSeek+Local) |  Multi-ask        |
    |  coding principal        |  (comparer 3      |
    |                          |   modeles)        |
    |                          +-------------------+
    |                          |  Terminal libre   |
    +--------------------------+-------------------+
    """
    project_path = Path(project_path).resolve()
    session_name = f"localcoder-ultra-{project_path.name}"

    if session_exists(session_name):
        kill_session(session_name)

    # Creer la session
    subprocess.run([
        "tmux", "new-session", "-d",
        "-s", session_name,
        "-c", str(project_path),
        "-x", "220", "-y", "55",
    ], check=True)

    subprocess.run([
        "tmux", "set-option", "-t", session_name,
        "status-left", "[LocalCoder ULTRA — Gemini+DeepSeek+Local] ",
    ])

    # Split vertical (40% droite)
    subprocess.run([
        "tmux", "split-window", "-h",
        "-t", f"{session_name}:0.0",
        "-c", str(project_path),
        "-p", "38",
    ], check=True)

    # Split horizontal dans la droite : git (top)
    subprocess.run([
        "tmux", "split-window", "-v",
        "-t", f"{session_name}:0.1",
        "-c", str(project_path),
        "-p", "70",
    ], check=True)

    # Re-split la partie basse droite : ask (milieu) + terminal (bas)
    subprocess.run([
        "tmux", "split-window", "-v",
        "-t", f"{session_name}:0.2",
        "-c", str(project_path),
        "-p", "55",
    ], check=True)

    # Maintenant : 0 (main aider), 1 (git), 2 (ask helper), 3 (terminal)

    # Git watcher dans panneau 1
    git_cmd = (
        'clear && while true; do '
        'clear; '
        'echo "=== GIT STATUS ($(date +%H:%M)) ==="; '
        'git status --short 2>/dev/null || echo "Pas git"; '
        'echo ""; echo "=== COMMITS ==="; '
        'git log --oneline -5 2>/dev/null; '
        'sleep 5; done'
    )
    subprocess.run([
        "tmux", "send-keys",
        "-t", f"{session_name}:0.1",
        git_cmd, "Enter",
    ], check=True)

    # Multi-ask helper dans panneau 2
    ask_welcome = (
        'clear && '
        'echo "=== MULTI-ASK (3 modeles en parallele) ===" && '
        'echo "" && '
        'echo "Pour poser une question aux 3 modeles :" && '
        'echo "" && '
        'echo "  lc ask \\"ta question\\"" && '
        'echo "" && '
        'echo "Les 3 reponses (Local + Gemini + DeepSeek) s\'afficheront ici." && '
        'echo "Utile pour les decisions importantes." && '
        'echo "" && '
        'echo "=== COMMANDES UTILES ===" && '
        'echo "  lc find X      - chercher" && '
        'echo "  lc partial     - features incompletes" && '
        'echo "  lc dead        - code mort" && '
        'echo ""'
    )
    subprocess.run([
        "tmux", "send-keys",
        "-t", f"{session_name}:0.2",
        ask_welcome, "Enter",
    ], check=True)

    # Terminal libre dans panneau 3
    term_welcome = (
        'clear && '
        'echo "=== TERMINAL LIBRE ===" && '
        'echo "Commandes shell, tests, build, scripts..." && '
        'echo ""'
    )
    subprocess.run([
        "tmux", "send-keys",
        "-t", f"{session_name}:0.3",
        term_welcome, "Enter",
    ], check=True)

    # Lancer Aider ULTRA dans panneau 0 (principal)
    aider_cmd = f"aider --config {aider_ultra_config}"
    subprocess.run([
        "tmux", "send-keys",
        "-t", f"{session_name}:0.0",
        aider_cmd, "Enter",
    ], check=True)

    # Focus sur Aider
    subprocess.run([
        "tmux", "select-pane",
        "-t", f"{session_name}:0.0",
    ], check=True)

    return session_name


def attach_workspace(session_name: str) -> None:
    """Attache le terminal a la session tmux (remplace le processus courant)."""
    import os
    os.execvp("tmux", ["tmux", "attach-session", "-t", session_name])


def launch_workspace(project_path: Path, aider_config: Path, mode: str = "local") -> None:
    """Lance le workspace complet et s'attache automatiquement."""
    if not is_tmux_available():
        raise RuntimeError(
            "tmux n'est pas installe. Installe avec: brew install tmux"
        )

    if is_in_tmux():
        raise RuntimeError(
            "Tu es deja dans une session tmux. "
            "Detache avec Ctrl+b puis d, puis relance."
        )

    session_name = create_workspace(project_path, aider_config, mode)
    attach_workspace(session_name)


def launch_ultra_workspace(project_path: Path, aider_ultra_config: Path) -> None:
    """Lance le workspace ULTRA (3 modeles en equipe)."""
    if not is_tmux_available():
        raise RuntimeError("tmux n'est pas installe. brew install tmux")
    if is_in_tmux():
        raise RuntimeError("Deja dans tmux. Detache avec Ctrl+b puis d.")

    session_name = create_ultra_workspace(project_path, aider_ultra_config)
    attach_workspace(session_name)


def start_backend(
    host: str = "127.0.0.1",
    port: int = 8765,
    max_retries: int = 10,
    retry_delay: float = 0.5,
) -> subprocess.Popen:
    """Demarre le backend FastAPI comme subprocess et attend le health check.

    Args:
        host: Hote de bind (defaut : 127.0.0.1 pour securite locale).
        port: Port d'ecoute.
        max_retries: Nombre de tentatives health check (10 x 0.5s = 5s max).
        retry_delay: Delai entre tentatives (secondes).

    Returns:
        Le subprocess Popen du backend.

    Raises:
        TimeoutError: Si le backend n'est pas pret apres max_retries x retry_delay.
        RuntimeError: Si le processus backend meurt pendant le demarrage.
    """
    # Trouver le Python du venv ou fallback sur sys.executable
    venv_python = os.path.join(os.path.dirname(os.path.dirname(__file__)), "venv", "bin", "python")
    python = venv_python if os.path.exists(venv_python) else sys.executable

    process = subprocess.Popen(
        [python, "-m", "uvicorn", "backend.main:app",
         "--host", host, "--port", str(port)],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    url = f"http://{host}:{port}/health"
    for attempt in range(max_retries):
        # Verifier que le processus est toujours vivant
        if process.poll() is not None:
            stderr_output = process.stderr.read().decode(errors="ignore")[:500]
            raise RuntimeError(
                f"Backend a crache au demarrage (exit code {process.poll()}). "
                f"Stderr: {stderr_output}"
            )
        try:
            resp = requests.get(url, timeout=1)
            if resp.status_code == 200:
                return process
        except (requests.ConnectionError, requests.Timeout, Exception):
            pass
        time.sleep(retry_delay)

    # Timeout — kill le processus avant de lever l'exception
    process.kill()
    raise TimeoutError(
        f"Backend n'a pas repondu a {url} apres {max_retries * retry_delay:.0f}s"
    )
