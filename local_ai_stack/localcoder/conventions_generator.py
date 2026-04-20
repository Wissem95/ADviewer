"""Generateur de conventions adaptatives.

Lit la stack reelle du projet et genere une section CONVENTIONS.md
specifique avec les regles, commandes CLI, et pieges de chaque techno.
"""

from pathlib import Path
import json


# Base de connaissances : chaque techno avec ses regles, CLI, et pieges
TECH_KNOWLEDGE = {
    "Next.js": {
        "cli": "npx next",
        "rules": [
            "Utiliser le App Router (app/) sauf si pages/ existe deja",
            "Server Components par defaut — ajouter 'use client' uniquement si interactivite",
            "Ne pas fetch dans les composants client — utiliser server actions ou route handlers",
            "next/image pour toutes les images — jamais de <img> brut",
            "next/font pour les polices — pas de Google Fonts en <link>",
        ],
        "dangers": [
            "Le build Vercel echoue souvent sur des warnings ESLint — verifier next.config.js",
            "'use client' sur un composant parent rend TOUS les enfants client",
            "Les server actions ne doivent jamais exposer de logique sensible",
            "getServerSideProps n'existe plus dans App Router — utiliser les server components",
        ],
        "commands": {
            "dev": "npm run dev",
            "build": "npm run build",
            "lint": "npx next lint",
        },
    },
    "React": {
        "rules": [
            "Hooks en haut du composant — jamais dans des conditions",
            "useCallback/useMemo uniquement si probleme de performance mesure",
            "Props drilling > 2 niveaux → utiliser Context ou Zustand",
            "Composants < 200 lignes — decouper si plus gros",
        ],
        "dangers": [
            "useEffect sans deps = boucle infinie potentielle",
            "setState dans un useEffect qui depend du state = boucle",
            "Ne pas muter directement les objets/arrays dans le state",
        ],
    },
    "TypeScript": {
        "rules": [
            "strict: true dans tsconfig.json — pas de any sauf cas justifie",
            "Interfaces pour les objets, types pour les unions/intersections",
            "Generics plutot que any pour les fonctions reutilisables",
            "Zod ou io-ts pour valider les donnees externes (API, formulaires)",
        ],
        "dangers": [
            "as unknown as X = contournement de types, signe de probleme",
            "@ts-ignore cache les bugs — corriger plutot",
            "Les types ne sont pas verifies au runtime — valider les entrees API",
        ],
    },
    "FastAPI": {
        "cli": "uvicorn",
        "rules": [
            "Pydantic BaseModel pour TOUS les schemas request/response",
            "Depends() pour l'injection de dependances (auth, DB, etc.)",
            "HTTPException avec status_code precis, pas de raise generique",
            "async def pour les routes qui font du I/O (BDD, HTTP, fichiers)",
            "BackgroundTasks pour le travail non-bloquant",
        ],
        "dangers": [
            "sync def dans une route bloque le thread — toujours async pour I/O",
            "Ne pas oublier les status codes : 201 pour create, 204 pour delete",
            "Les dependances sont re-executees a chaque requete sauf si cachees",
            "CORS : verifier que les origins sont correctement configurees",
        ],
        "commands": {
            "dev": "uvicorn src.main:app --reload --port 8000",
            "test": "pytest -x -q",
            "lint": "ruff check .",
        },
    },
    "Python": {
        "rules": [
            "Type hints sur toutes les fonctions publiques",
            "f-strings plutot que .format() ou %",
            "pathlib.Path plutot que os.path",
            "logging plutot que print()",
            "dataclasses ou pydantic pour les structures de donnees",
        ],
        "dangers": [
            "Mutable default arguments (def f(x=[])): BUG classique",
            "except Exception: catch-all trop large — specifier le type",
            "import circulaire : restructurer les modules",
        ],
    },
    "Supabase": {
        "cli": "supabase",
        "rules": [
            "RLS (Row Level Security) sur TOUTES les tables — pas d'acces sans politique",
            "Les migrations sont immutables — ne JAMAIS modifier une migration appliquee",
            "Utiliser supabase.auth pour l'authentification, pas de JWT custom",
            "Service role key = acces admin — ne JAMAIS l'exposer cote client",
            "Stocker les fichiers dans Supabase Storage, pas dans la BDD",
        ],
        "dangers": [
            "supabase db reset DETRUIT toutes les donnees — JAMAIS en prod",
            "Oublier les RLS policies = donnees accessibles a tous",
            "Les fonctions SQL avec SECURITY DEFINER contournent les RLS — auditer",
            "Les migrations doivent etre retrocompatibles pour zero-downtime",
        ],
        "commands": {
            "status": "supabase status",
            "migrations": "supabase migration list",
            "diff": "supabase db diff --use-migra",
            "reset_local": "supabase db reset (LOCAL UNIQUEMENT)",
            "push": "supabase db push",
        },
    },
    "Stripe": {
        "cli": "stripe",
        "rules": [
            "Webhooks : toujours verifier la signature avec stripe.webhooks.constructEvent",
            "Idempotence : un webhook peut arriver plusieurs fois — gerer les doublons",
            "Toujours utiliser les modes test (sk_test_) pour le dev",
            "Prix en centimes — 10.00E = 1000 dans l'API Stripe",
            "Checkout Session pour les paiements, pas de charge direct sauf cas specifique",
        ],
        "dangers": [
            "Ne JAMAIS logger les cles API ou les payload complets",
            "Les webhooks en mode test et prod utilisent des endpoints differents",
            "Un client peut annuler un paiement entre l'intent et la confirmation",
            "Les subscriptions ont des etats complexes — tester tous les cas",
        ],
        "commands": {
            "listen": "stripe listen --forward-to localhost:8000/api/webhooks/stripe",
            "trigger": "stripe trigger payment_intent.succeeded",
            "logs": "stripe logs tail",
        },
    },
    "Railway": {
        "cli": "railway",
        "rules": [
            "Variables d'environnement via railway variables, pas dans le code",
            "Verifier les logs apres chaque deploy : railway logs",
            "Utiliser les health checks pour verifier que le service repond",
            "Les replicas partagent la meme BDD — attention aux migrations concurrentes",
        ],
        "dangers": [
            "railway up deploy depuis le code local — preferer le deploy depuis Git",
            "Les variables d'env ne sont pas versionnees — documenter les changements",
            "Le timeout par defaut peut couper les requetes longues",
        ],
        "commands": {
            "status": "railway status",
            "logs": "railway logs",
            "variables": "railway variables",
            "deploy": "railway up (depuis Git de preference)",
        },
    },
    "Vercel": {
        "cli": "vercel",
        "rules": [
            "Preview deployments pour chaque PR — verifier avant merge",
            "Environment variables via vercel env, pas dans le code",
            "Serverless functions : attention au cold start et timeout",
            "ISR pour les pages semi-statiques, SSR pour le dynamique pur",
        ],
        "dangers": [
            "Le build peut reussir en local et echouer sur Vercel (node version, deps)",
            "Les env vars de preview et production sont differentes",
            "Les edge functions ont des limitations (pas de node:fs, etc.)",
        ],
        "commands": {
            "dev": "vercel dev",
            "env_pull": "vercel env pull",
            "deploy_preview": "vercel",
            "deploy_prod": "vercel --prod",
            "logs": "vercel logs",
        },
    },
    "Docker": {
        "cli": "docker",
        "rules": [
            "Multi-stage builds pour reduire la taille de l'image",
            ".dockerignore pour exclure node_modules, .git, .env",
            "Ne pas lancer en root dans le container — USER non-root",
            "COPY requirements/package.json AVANT le code — cache des layers",
        ],
        "dangers": [
            "docker system prune supprime TOUT — attention aux volumes",
            "Les volumes persistent meme apres docker compose down",
            "Les images non taguees s'accumulent — nettoyer regulierement",
        ],
        "commands": {
            "up": "docker compose up -d",
            "logs": "docker compose logs -f",
            "down": "docker compose down",
            "build": "docker compose build --no-cache",
        },
    },
    "Redis": {
        "rules": [
            "Toujours definir un TTL sur les cles — pas de cles eternelles",
            "Utiliser des prefixes de namespace (cache:, queue:, session:)",
            "Les connexions doivent etre poolees, pas creees par requete",
        ],
        "dangers": [
            "FLUSHALL supprime TOUTES les donnees — JAMAIS en prod",
            "Redis est single-threaded — les commandes longues bloquent tout",
            "Les donnees Redis ne sont pas persistees par defaut",
        ],
    },
    "LangChain": {
        "rules": [
            "Structurer les prompts avec des templates, pas des f-strings",
            "Utiliser les callbacks pour le logging et le monitoring",
            "Limiter les tokens max pour eviter les couts inattendus",
            "Implementer un fallback si le LLM ne repond pas",
        ],
        "dangers": [
            "Les prompts longs consomment beaucoup de tokens = cout eleve",
            "Les reponses du LLM ne sont jamais garanties — valider le format",
            "Le streaming peut masquer des erreurs si mal gere",
        ],
    },
    "Tailwind CSS": {
        "rules": [
            "Utiliser les classes utilitaires, pas de CSS custom sauf necessite",
            "Composants React pour les patterns repetes (Button, Card, etc.)",
            "Dark mode avec la classe dark: — configurer dans tailwind.config",
            "Responsive : mobile-first (sm: md: lg:)",
        ],
        "dangers": [
            "Les classes longues reduisent la lisibilite — extraire dans des composants",
            "purge/content mal configure = styles manquants en production",
        ],
    },
    "Sentry": {
        "rules": [
            "Capturer les erreurs avec Sentry.captureException, pas juste console.error",
            "Ajouter du contexte utilisateur avec Sentry.setUser",
            "Configurer les transactions pour le performance monitoring",
            "Filtrer le bruit (erreurs reseau, extensions navigateur)",
        ],
        "dangers": [
            "Ne pas envoyer de PII (donnees personnelles) dans les breadcrumbs",
            "Le DSN n'est pas un secret mais ne devrait pas etre dans le code source",
        ],
    },
    "Zustand": {
        "rules": [
            "Un store par domaine (authStore, jobsStore, uiStore)",
            "Selectors pour eviter les re-renders inutiles",
            "Actions dans le store, pas dans les composants",
        ],
        "dangers": [
            "Un store trop gros = re-renders partout — decouper",
            "Ne pas stocker de donnees serveur dans Zustand — utiliser React Query",
        ],
    },
    "Node.js": {
        "rules": [
            "Toujours gerer les rejections de Promise (try/catch ou .catch)",
            "Utiliser les variables d'env via process.env, jamais en dur",
        ],
        "commands": {
            "dev": "npm run dev",
            "build": "npm run build",
            "test": "npm test",
        },
    },
}


def detect_project_stack(project_path: Path) -> list[str]:
    """Detecte toutes les technos utilisees dans le projet."""
    stack = set()

    indicators = {
        "next.config.js": "Next.js",
        "next.config.mjs": "Next.js",
        "next.config.ts": "Next.js",
        "tailwind.config.js": "Tailwind CSS",
        "tailwind.config.ts": "Tailwind CSS",
        "tsconfig.json": "TypeScript",
        "docker-compose.yml": "Docker",
        "Dockerfile": "Docker",
        "railway.toml": "Railway",
        "vercel.json": "Vercel",
        ".vercel": "Vercel",
    }

    for indicator, tech in indicators.items():
        if (project_path / indicator).exists():
            stack.add(tech)

    # package.json
    pkg_paths = [project_path / "package.json", project_path / "frontend-next" / "package.json"]
    for pkg_path in pkg_paths:
        if pkg_path.exists():
            try:
                pkg = json.loads(pkg_path.read_text())
                all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "react" in all_deps:
                    stack.add("React")
                if "next" in all_deps:
                    stack.add("Next.js")
                if "zustand" in all_deps:
                    stack.add("Zustand")
                if "@sentry/nextjs" in all_deps or "@sentry/react" in all_deps:
                    stack.add("Sentry")
                if "tailwindcss" in all_deps:
                    stack.add("Tailwind CSS")
                stack.add("Node.js")
            except (json.JSONDecodeError, OSError):
                pass

    # requirements.txt / pyproject.toml
    req_paths = [project_path / "requirements.txt", project_path / "backend" / "requirements.txt"]
    for req_path in req_paths:
        if req_path.exists():
            content = req_path.read_text(errors="ignore").lower()
            stack.add("Python")
            if "fastapi" in content:
                stack.add("FastAPI")
            if "supabase" in content:
                stack.add("Supabase")
            if "stripe" in content:
                stack.add("Stripe")
            if "redis" in content or "arq" in content:
                stack.add("Redis")
            if "langchain" in content or "langgraph" in content:
                stack.add("LangChain")
            if "sentry" in content:
                stack.add("Sentry")

    # Supabase directory
    if (project_path / "supabase").exists():
        stack.add("Supabase")

    return sorted(stack)


def generate_conventions_section(project_path: Path) -> str:
    """Genere la section CONVENTIONS adaptee au projet."""
    stack = detect_project_stack(project_path)

    if not stack:
        return "\n## 9. STACK PROJET\n\nStack non detectee. Ajouter manuellement.\n"

    lines = []
    lines.append("\n---\n")
    lines.append(f"## 9. STACK PROJET (genere automatiquement)")
    lines.append(f"\nStack detectee : {', '.join(stack)}")
    lines.append("")

    for tech in stack:
        knowledge = TECH_KNOWLEDGE.get(tech)
        if not knowledge:
            continue

        lines.append(f"### {tech}")

        if "rules" in knowledge:
            lines.append(f"\nRegles :")
            for rule in knowledge["rules"]:
                lines.append(f"- {rule}")

        if "dangers" in knowledge:
            lines.append(f"\nDangers :")
            for danger in knowledge["dangers"]:
                lines.append(f"- !! {danger}")

        if "commands" in knowledge:
            lines.append(f"\nCommandes CLI :")
            for name, cmd in knowledge["commands"].items():
                lines.append(f"- `{cmd}` — {name}")

        lines.append("")

    return "\n".join(lines)


def update_conventions_file(project_path: Path) -> str:
    """Met a jour le CONVENTIONS.md du projet avec la section stack adaptee.

    Preserve les sections 1-8 existantes, remplace/ajoute la section 9.
    """
    conventions_path = project_path / "CONVENTIONS.md"
    if not conventions_path.exists():
        return "CONVENTIONS.md non trouve dans le projet"

    content = conventions_path.read_text()

    # Generer la nouvelle section
    new_section = generate_conventions_section(project_path)

    # Trouver et remplacer la section 9 existante
    marker = "## 9."
    if marker in content:
        # Couper avant la section 9
        before = content[:content.index(marker)].rstrip()
        result = before + "\n" + new_section
    else:
        # Ajouter a la fin
        result = content.rstrip() + "\n" + new_section

    conventions_path.write_text(result)

    stack = detect_project_stack(project_path)
    return f"CONVENTIONS.md mis a jour avec {len(stack)} technos : {', '.join(stack)}"


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(generate_conventions_section(path))
