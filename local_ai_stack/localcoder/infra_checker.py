"""Infra Checker — comprend et valide l'etat de toute l'infra.

Lit les CLI (railway, supabase, stripe, vercel, etc.),
verifie les connexions, et donne un etat reel du systeme.
"""

from pathlib import Path
import subprocess
import json
import os
from dataclasses import dataclass, field


@dataclass
class ServiceStatus:
    name: str
    available: bool
    version: str = ""
    details: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class InfraReport:
    services: list[ServiceStatus] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)  # var → "set" ou "missing"
    warnings: list[str] = field(default_factory=list)

    def format(self) -> str:
        lines = ["# Rapport Infrastructure"]

        lines.append("\n## Services CLI")
        for s in self.services:
            icon = "OK" if s.available else "!!"
            lines.append(f"  {icon} {s.name}: {s.details}")
            for e in s.errors:
                lines.append(f"      Erreur: {e}")

        if self.env_vars:
            missing = {k: v for k, v in self.env_vars.items() if v == "missing"}
            present = {k: v for k, v in self.env_vars.items() if v != "missing"}
            lines.append(f"\n## Variables d'environnement ({len(present)} ok, {len(missing)} manquantes)")
            if missing:
                for k in sorted(missing):
                    lines.append(f"  !! MANQUANTE: {k}")

        if self.warnings:
            lines.append(f"\n## Warnings ({len(self.warnings)})")
            for w in self.warnings:
                lines.append(f"  ! {w}")

        return "\n".join(lines)


def _run_cmd(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    """Execute une commande et retourne (success, output)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip() or result.stderr.strip()
    except FileNotFoundError:
        return False, "non installe"
    except subprocess.TimeoutExpired:
        return False, "timeout"


def check_railway() -> ServiceStatus:
    """Verifie Railway CLI."""
    ok, output = _run_cmd(["railway", "version"])
    if not ok:
        return ServiceStatus("Railway", False, details="CLI non installe — npm i -g @railway/cli")

    status = ServiceStatus("Railway", True, version=output, details=f"v{output}")

    # Verifier si connecte
    ok_status, status_output = _run_cmd(["railway", "status"])
    if ok_status:
        status.details += f" | Projet connecte"
    else:
        status.errors.append("Non connecte — railway login puis railway link")

    return status


def check_supabase() -> ServiceStatus:
    """Verifie Supabase CLI."""
    ok, output = _run_cmd(["supabase", "--version"])
    if not ok:
        return ServiceStatus("Supabase", False, details="CLI non installe — brew install supabase/tap/supabase")

    return ServiceStatus("Supabase", True, version=output, details=output)


def check_stripe() -> ServiceStatus:
    """Verifie Stripe CLI."""
    ok, output = _run_cmd(["stripe", "version"])
    if not ok:
        return ServiceStatus("Stripe", False, details="CLI non installe — brew install stripe/stripe-cli/stripe")

    status = ServiceStatus("Stripe", True, version=output, details=output)

    # Verifier si authentifie
    ok_auth, auth_output = _run_cmd(["stripe", "config", "--list"])
    if not ok_auth or "test_" not in auth_output:
        status.errors.append("Non authentifie — stripe login")

    return status


def check_vercel() -> ServiceStatus:
    """Verifie Vercel CLI."""
    ok, output = _run_cmd(["vercel", "--version"])
    if not ok:
        return ServiceStatus("Vercel", False, details="CLI non installe — npm i -g vercel")

    return ServiceStatus("Vercel", True, version=output, details=f"v{output.splitlines()[-1] if output else ''}")


def check_docker() -> ServiceStatus:
    """Verifie Docker."""
    ok, output = _run_cmd(["docker", "--version"])
    if not ok:
        return ServiceStatus("Docker", False, details="Non installe")

    # Verifier si Docker tourne
    ok_ps, _ = _run_cmd(["docker", "ps"])
    if ok_ps:
        return ServiceStatus("Docker", True, version=output, details=f"{output} | daemon actif")
    else:
        return ServiceStatus("Docker", True, version=output, details=f"{output} | daemon ARRETE")


def check_ollama() -> ServiceStatus:
    """Verifie Ollama."""
    ok, output = _run_cmd(["ollama", "--version"])
    if not ok:
        return ServiceStatus("Ollama", False, details="Non installe — https://ollama.com")

    # Verifier les modeles
    ok_list, models = _run_cmd(["ollama", "list"])
    model_count = len(models.splitlines()) - 1 if ok_list else 0

    return ServiceStatus("Ollama", True, version=output, details=f"{output} | {model_count} modeles")


def check_node() -> ServiceStatus:
    """Verifie Node.js."""
    ok, output = _run_cmd(["node", "--version"])
    if not ok:
        return ServiceStatus("Node.js", False, details="Non installe")
    return ServiceStatus("Node.js", True, version=output, details=output)


def check_python() -> ServiceStatus:
    """Verifie Python."""
    ok, output = _run_cmd(["python3", "--version"])
    if not ok:
        return ServiceStatus("Python", False, details="Non installe")
    return ServiceStatus("Python", True, version=output, details=output)


def check_git() -> ServiceStatus:
    """Verifie Git."""
    ok, output = _run_cmd(["git", "--version"])
    if not ok:
        return ServiceStatus("Git", False, details="Non installe")
    return ServiceStatus("Git", True, version=output, details=output)


def check_env_vars(project_path: Path) -> dict[str, str]:
    """Verifie les variables d'environnement requises par le projet."""
    env_example = project_path / ".env.example"
    if not env_example.exists():
        return {}

    required_vars = {}
    for line in env_example.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            var_name = line.split("=")[0].strip()
            if os.environ.get(var_name):
                required_vars[var_name] = "set"
            else:
                required_vars[var_name] = "missing"

    return required_vars


def check_project_services(project_path: Path) -> list[str]:
    """Detecte les services utilises par le projet."""
    warnings = []

    # Verifier les fichiers de config
    if (project_path / "railway.toml").exists():
        ok, _ = _run_cmd(["railway", "version"])
        if not ok:
            warnings.append("railway.toml present mais CLI Railway non installe")

    if (project_path / "supabase").exists():
        ok, _ = _run_cmd(["supabase", "--version"])
        if not ok:
            warnings.append("Dossier supabase/ present mais CLI Supabase non installe")

    if (project_path / ".vercel").exists() or (project_path / "vercel.json").exists():
        ok, _ = _run_cmd(["vercel", "--version"])
        if not ok:
            warnings.append("Config Vercel presente mais CLI Vercel non installe")

    # Verifier les dependances
    req_file = project_path / "backend" / "requirements.txt"
    if req_file.exists():
        content = req_file.read_text().lower()
        if "stripe" in content:
            ok, _ = _run_cmd(["stripe", "version"])
            if not ok:
                warnings.append("Stripe dans requirements.txt mais CLI Stripe non installe")

    return warnings


def full_infra_check(project_path: Path) -> InfraReport:
    """Check complet de l'infrastructure."""
    project_path = Path(project_path).resolve()

    report = InfraReport()

    # Services
    report.services = [
        check_git(),
        check_python(),
        check_node(),
        check_ollama(),
        check_docker(),
        check_railway(),
        check_supabase(),
        check_stripe(),
        check_vercel(),
    ]

    # Env vars
    report.env_vars = check_env_vars(project_path)

    # Warnings specifiques au projet
    report.warnings = check_project_services(project_path)

    return report


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    report = full_infra_check(path)
    print(report.format())
