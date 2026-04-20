"""Upgrade Advisor — analyse intelligente avant de modifier l'environnement.

Avant de toucher a Python, aux dependances, ou a l'infra, ce module :
1. Analyse la situation actuelle
2. Detecte les conflits et incompatibilites
3. Propose les options possibles avec pros/cons
4. Laisse l'utilisateur DECIDER

Jamais de modification silencieuse. Toujours transparent.
"""

from pathlib import Path
import subprocess
import sys
import re
from dataclasses import dataclass, field


@dataclass
class UpgradeOption:
    """Une option d'upgrade possible."""
    name: str
    action: str          # Ce que ca va faire
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    recommended: bool = False
    reason: str = ""


@dataclass
class UpgradeProposal:
    """Proposition d'upgrade avec plusieurs options."""
    title: str
    context: str         # Situation actuelle
    problem: str         # Pourquoi un changement est envisage
    options: list[UpgradeOption] = field(default_factory=list)

    def recommended_option(self) -> UpgradeOption | None:
        for opt in self.options:
            if opt.recommended:
                return opt
        return None

    def format(self) -> str:
        lines = [f"# {self.title}", "", f"## Contexte", self.context, "", f"## Situation", self.problem, ""]
        lines.append("## Options")
        for i, opt in enumerate(self.options, 1):
            star = " [RECOMMANDE]" if opt.recommended else ""
            lines.append(f"\n### Option {i}: {opt.name}{star}")
            lines.append(f"{opt.action}")
            if opt.pros:
                lines.append("\nAvantages:")
                for p in opt.pros:
                    lines.append(f"  + {p}")
            if opt.cons:
                lines.append("\nInconvenients:")
                for c in opt.cons:
                    lines.append(f"  - {c}")
            if opt.commands:
                lines.append("\nCommandes:")
                for cmd in opt.commands:
                    lines.append(f"  $ {cmd}")
            if opt.reason:
                lines.append(f"\nRaison: {opt.reason}")
        return "\n".join(lines)


def _run(cmd: list[str]) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.returncode == 0, r.stdout.strip() or r.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""


def detect_python_versions() -> dict[str, str]:
    """Detecte toutes les versions de Python installees."""
    versions = {}

    # Candidats courants
    candidates = [
        "/usr/bin/python3",
        "/opt/homebrew/bin/python3",
        "/opt/homebrew/bin/python3.10",
        "/opt/homebrew/bin/python3.11",
        "/opt/homebrew/bin/python3.12",
        "/opt/homebrew/bin/python3.13",
        "/opt/homebrew/bin/python3.14",
        "/usr/local/bin/python3",
    ]

    for path in candidates:
        if Path(path).exists():
            ok, version = _run([path, "--version"])
            if ok:
                match = re.search(r"(\d+\.\d+\.\d+)", version)
                if match:
                    versions[path] = match.group(1)

    return versions


def check_package_compat(python_path: str, package: str) -> tuple[bool, str]:
    """Verifie si un package est compatible avec un Python."""
    ok, output = _run([python_path, "-m", "pip", "index", "versions", package])
    return ok, output


def propose_python_upgrade(current_version: str, required_package: str = "aider-chat") -> UpgradeProposal:
    """Propose les options si la version Python n'est pas optimale."""
    proposal = UpgradeProposal(
        title=f"Version Python — analyse",
        context=f"Version actuelle: Python {current_version}",
        problem="",
    )

    versions = detect_python_versions()

    # Situation 1: Python 3.9 (fin de vie)
    if current_version.startswith("3.9"):
        proposal.problem = (
            "Python 3.9 est en fin de vie (EOL octobre 2025). Pas de mise a jour securite. "
            "Les type hints modernes (int | None) ne fonctionnent pas sans hack."
        )

        # Option 1: rester en 3.9
        proposal.options.append(UpgradeOption(
            name="Rester en Python 3.9",
            action="Aucun changement. Continuer avec Python 3.9.",
            pros=["Zero changement", "Tout fonctionne deja"],
            cons=["Plus de mises a jour securite", "Syntaxe limitee", "Packages recents incompatibles"],
        ))

        # Option 2: passer en 3.12 (si dispo)
        has_312 = any(v.startswith("3.12") for v in versions.values())
        if has_312:
            proposal.options.append(UpgradeOption(
                name="Migrer vers Python 3.12",
                action="Recreer le venv avec Python 3.12 deja installe.",
                pros=["LTS stable", "Compatible avec tous les packages", "Syntaxe moderne"],
                cons=["Recreer le venv (quelques secondes)"],
                commands=[
                    "rm -rf venv",
                    "/opt/homebrew/bin/python3.12 -m venv venv",
                    "source venv/bin/activate",
                    "pip install -e .",
                ],
                recommended=True,
                reason="3.12 est la version recommandee : stable, recente, compatible",
            ))
        else:
            proposal.options.append(UpgradeOption(
                name="Installer Python 3.12",
                action="Installer via Homebrew et recreer le venv.",
                pros=["LTS stable", "Compatible avec tous les packages"],
                cons=["Install Homebrew (quelques minutes)"],
                commands=[
                    "brew install python@3.12",
                    "rm -rf venv",
                    "/opt/homebrew/bin/python3.12 -m venv venv",
                    "source venv/bin/activate && pip install -e .",
                ],
                recommended=True,
            ))

    # Situation 2: Python 3.13 (trop recent pour aider)
    elif current_version.startswith("3.13") and required_package == "aider-chat":
        proposal.problem = (
            f"Python 3.13 est TROP RECENT pour {required_package}. "
            f"Aider requiert Python >=3.10,<3.13. "
            f"aider-chat ne pourra PAS s'installer en 3.13."
        )

        has_312 = any(v.startswith("3.12") for v in versions.values())
        if has_312:
            proposal.options.append(UpgradeOption(
                name="Migrer vers Python 3.12 (recommande)",
                action="Recreer le venv avec Python 3.12.",
                pros=[
                    "Compatible avec aider-chat",
                    "Version LTS stable",
                    "Tous les packages fonctionnent",
                ],
                cons=["Recreer le venv (quelques secondes)"],
                commands=[
                    "rm -rf venv",
                    "/opt/homebrew/bin/python3.12 -m venv venv",
                    "source venv/bin/activate && pip install -e .",
                ],
                recommended=True,
                reason="La seule option ou aider fonctionne tout en gardant un Python recent",
            ))

        proposal.options.append(UpgradeOption(
            name="Attendre que aider supporte 3.13",
            action="Garder Python 3.13 mais ne pas utiliser aider pour l'instant.",
            pros=["Python le plus recent"],
            cons=[
                "Aider inutilisable",
                "Localcoder code ne fonctionnera pas",
                "Attendre la prochaine version d'aider (date inconnue)",
            ],
        ))

        proposal.options.append(UpgradeOption(
            name="Downgrader vers Python 3.12",
            action="Supprimer Python 3.13 et installer 3.12 via Homebrew.",
            pros=["Un seul Python sur le systeme"],
            cons=["Plus lourd que juste changer le venv", "Impact d'autres projets potentiellement"],
            commands=[
                "brew uninstall python@3.13",
                "brew install python@3.12",
            ],
        ))

    # Situation 3: Python OK, rien a faire
    else:
        proposal.problem = "Version Python compatible. Aucune action requise."
        proposal.options.append(UpgradeOption(
            name="Aucun changement",
            action="Continuer avec la version actuelle.",
            recommended=True,
            reason=f"Python {current_version} est compatible avec tous les packages",
        ))

    return proposal


def analyze_environment() -> list[UpgradeProposal]:
    """Analyse globale de l'environnement et propose des upgrades."""
    proposals = []

    # 1. Version Python du venv actuel
    current_python = sys.version.split()[0]
    python_proposal = propose_python_upgrade(current_python)
    if python_proposal.problem and "Aucune action" not in python_proposal.problem:
        proposals.append(python_proposal)

    # 2. Version d'aider
    ok, aider_version = _run(["aider", "--version"])
    if ok:
        # Extraire le numero
        match = re.search(r"(\d+\.\d+\.\d+)", aider_version)
        if match:
            ver = match.group(1)
            major, minor, _ = ver.split(".")
            if int(minor) < 85:
                proposal = UpgradeProposal(
                    title="Aider — version obsolete",
                    context=f"Aider version {ver}",
                    problem=f"Aider {ver} est ancienne. Version recommandee : 0.86+",
                )
                proposal.options.append(UpgradeOption(
                    name="Mettre a jour aider",
                    action="Upgrade vers la derniere version.",
                    pros=["Nouvelles features", "Bugs corriges", "Meilleurs modeles supportes"],
                    cons=["Potentiels breaking changes mineurs"],
                    commands=["pip install --upgrade aider-chat"],
                    recommended=True,
                ))
                proposals.append(proposal)

    # 3. Modeles Ollama obsoletes
    ok, ollama_list = _run(["ollama", "list"])
    if ok and "qwen2.5-coder" in ollama_list:
        # Verifier si qwen3-coder existe (version plus recente hypothetique)
        # Pour l'instant, juste signaler si des modeles sont vieux
        pass

    return proposals


def format_all_proposals(proposals: list[UpgradeProposal]) -> str:
    """Formate toutes les propositions."""
    if not proposals:
        return "Aucune amelioration proposee. Environnement OK."

    lines = ["=" * 60, f"UPGRADE ADVISOR — {len(proposals)} proposition(s)", "=" * 60, ""]
    for i, p in enumerate(proposals, 1):
        lines.append(f"\n{'=' * 60}")
        lines.append(f"Proposition {i}/{len(proposals)}")
        lines.append("=" * 60)
        lines.append(p.format())

    lines.append("\n" + "=" * 60)
    lines.append("IMPORTANT: Aucune modification n'a ete faite.")
    lines.append("A toi de choisir et d'executer les commandes si tu veux.")
    lines.append("=" * 60)

    return "\n".join(lines)


if __name__ == "__main__":
    proposals = analyze_environment()
    print(format_all_proposals(proposals))
