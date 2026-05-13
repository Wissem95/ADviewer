# LocalCoder — IDE IA Local

> Systeme d'agents IA pour le developpement avec memoire persistante par projet.
> Conçu pour remplacer ~90% de Claude Code Opus en local + fallback API gratuit/pas cher.

**Hardware** : M3 Pro 18 Go | **Python** : 3.12.13 | **Moteur** : Aider 0.86 + wrapper intelligent

---

## Sommaire

1. [Installation](#installation)
2. [Les 20 commandes](#les-20-commandes)
3. [Les 3 modes de coding](#les-3-modes-de-coding)
4. [Le workspace IDE (tmux)](#le-workspace-ide-tmux)
5. [Memoire projet persistante](#memoire-projet-persistante)
6. [Workflow recommande](#workflow-recommande)
7. [Couts et limites honnetes](#couts-et-limites-honnetes)
8. [Depannage](#depannage)

---

## Installation

### Prerequis
- macOS (M3 Pro 18 Go)
- `brew install python@3.12 tmux`
- Ollama avec `qwen2.5-coder:14b` et `qwen2.5-coder:7b`
- Git

### Installation en 1 commande

```bash
cd ~/local_ai_stack
/opt/homebrew/bin/python3.12 -m venv venv
source venv/bin/activate
pip install -e .
```

### Activation automatique dans ton shell

```bash
echo 'source ~/local_ai_stack/venv/bin/activate' >> ~/.zshrc
source ~/.zshrc
```

### Cles API (optionnel)

```bash
# Gemini 2.5 Pro — GRATUIT, 1M contexte
# https://aistudio.google.com/apikey
export GEMINI_API_KEY="..."

# DeepSeek-R1 — ~0.005$/req, quasi-Opus
# https://platform.deepseek.com/
export DEEPSEEK_API_KEY="..."
```

---

## Les 20 commandes

### Categorie 1 — Analyse et memoire (9 commandes)

#### `localcoder scan [--strict]`
Scan complet du projet : doublons (0 faux positif), fichiers trop gros, TODOs, stack.
- Mode normal : filtre intelligent
- Mode `--strict` : montre aussi les borderline

```bash
localcoder scan                    # Dossier courant
localcoder scan --strict           # Inclut les borderline
localcoder scan ~/mon-projet       # Projet specifique
```

**Exemple** (huntzenjobs) : 676 fichiers, 147K lignes, 12 doublons, 135 gros fichiers, 102 TODOs.

#### `localcoder index`
Indexe tout le projet dans `.localcoder/memory.sqlite` :
- Tous les symboles (fonctions, classes, methodes)
- Toutes les features (routes, pages, composants, hooks, services, tables)
- Les integrations (backend ↔ frontend)

```bash
localcoder index
```

**Exemple** : 2108 symboles, 335 features, 230 integrations.

#### `localcoder find "terme"`
Recherche semantique dans la memoire : est-ce que cette feature/fonction existe deja ?

```bash
localcoder find "avatar upload"
localcoder find "stripe webhook"
localcoder find "send email"
```

**Cas d'usage** : AVANT de creer quelque chose, chercher ce qui existe deja pour le reutiliser.

#### `localcoder features`
Liste toutes les features par type (component, page, api_route, hook, service, agent, db_table).

```bash
localcoder features
```

**Exemple huntzenjobs** : 147 components, 47 pages, 42 db_tables, 38 api_routes, 31 hooks, 23 services, 7 agents.

#### `localcoder partial`
Detecte les features commencees mais pas finies :
- TODOs/FIXMEs/BUGs dans les routes
- console.log/print() de debug oublies
- Fonctions stub (pass, NotImplementedError)
- Migrations SQL recentes (< 7 jours)
- Composants sans fichier de test

```bash
localcoder partial
```

**Exemple** : 166 signaux detectes, dont 6 BUGs critiques dans auth.py.

#### `localcoder orphans`
Routes backend qui n'ont pas d'appel frontend detecte (matching approximatif).

```bash
localcoder orphans
```

**Note** : Certains "orphelins" sont intentionnels (routes internes, webhooks, test endpoints).

#### `localcoder dead`
Detection statique de code mort : fonctions/classes definies mais jamais referencees.

```bash
localcoder dead
```

**Exclusions automatiques** : entry points, tests, hooks React, route handlers FastAPI, `__init__`.

#### `localcoder graph [focus]`
Genere un call graph Mermaid dans `.localcoder/call_graph.md`.

```bash
localcoder graph                    # Top 40 fonctions les plus connectees
localcoder graph stripe_webhook     # Centre sur une fonction
```

Ouvrable dans VS Code (extension Mermaid), GitHub, tout editeur Markdown.

#### `localcoder journal`
Historique des sessions de travail sur le projet (loggees automatiquement par `localcoder code` et `localcoder ide`).

```bash
localcoder journal
```

---

### Categorie 2 — Git et review (4 commandes)

#### `localcoder git`
Rapport Git complet : branche, fichiers non commites, 20 derniers commits, hotspots (fichiers modifies frequemment = instables).

```bash
localcoder git
```

#### `localcoder review`
Review statique des changements Git non commites avec score /10.
Detecte : secrets en dur, `except: pass`, fonctions > 50 lignes, `console.log`, imports inutilises.

```bash
localcoder review
```

#### `localcoder pr [base]`
Review complete d'une PR avec verdict go/no-go :
- Tests (pytest, npm test)
- Lint (ruff, eslint)
- Doublons introduits
- Problemes de review statique
- Recommandations

```bash
localcoder pr             # vs main
localcoder pr . dev       # vs dev
```

#### `localcoder precommit`
Bloque le commit si probleme critique :
- Secret detecte dans le diff staged
- Fichier interdit (`.env`, `*.key`)
- Erreur de syntaxe Python
- Fichier > 500 Ko

```bash
localcoder precommit
```

---

### Categorie 3 — Infrastructure (4 commandes)

#### `localcoder infra`
Check complet de l'infra : CLI installes (Git, Node, Ollama, Docker, Railway, Supabase, Stripe, Vercel) et variables d'environnement du projet.

```bash
localcoder infra
```

#### `localcoder advise`
Upgrade advisor **intelligent** : analyse l'environnement, propose des ameliorations **sans rien modifier**.
Pour chaque probleme : plusieurs options avec pros/cons, et une recommandation.

```bash
localcoder advise
```

**C'est l'inverse de "change tout automatiquement"** — tu decides toujours.

#### `localcoder adapt`
Detecte la stack du projet et genere une section CONVENTIONS.md specifique avec regles, dangers, et commandes CLI pour chaque techno.

```bash
localcoder adapt
```

**Base de connaissances** : Next.js, React, TypeScript, FastAPI, Python, Supabase, Stripe, Railway, Vercel, Docker, Redis, LangChain, Tailwind, Sentry, Zustand.

#### `localcoder hooks [install|uninstall|status]`
Installe un hook Git `post-commit` qui re-indexe le projet automatiquement apres chaque commit (non-bloquant, en arriere-plan).

```bash
localcoder hooks install     # Installer
localcoder hooks status      # Verifier
localcoder hooks uninstall   # Desinstaller
```

---

### Categorie 4 — Coder (3 commandes)

#### `localcoder check "tache"`
Analyse la complexite d'une tache et recommande le bon modele :
- Simple (1-3/10) → local (14b, 0E)
- Medium (4-6/10) → Gemini (0E, 1M contexte)
- Complex (7-10/10) → DeepSeek-R1 (raisonnement profond)

```bash
localcoder check "corrige le typo dans le bouton login"
localcoder check "refactore admin.py qui fait 4000 lignes"
```

#### `localcoder code`
Lance Aider dans le terminal avec :
- Mode architect active (planifie avant de coder)
- CONVENTIONS adaptees au projet injectees
- Choix du modele (local/gemini/deepseek)
- **Session auto-loggee** dans le journal (goal, files_modified, commits)

```bash
localcoder code
```

**Modes Aider disponibles en session** :
- `/architect` : plan sans coder
- `/ask` : question sans modifier
- `/code` : edition directe
- `/run cmd` : executer une commande shell
- `/undo` : annuler
- `/diff` : voir les changements

#### `localcoder ide`
**Workspace IDE complet** via tmux — le mode ultime.

Layout multi-panneaux :
```
+----------------------------+---------------+
|                            |  Git status   |
|                            |   (auto       |
|         Aider              |   refresh)    |
|       (chat IA)            +---------------+
|                            |               |
|                            |   Terminal    |
|                            |   libre       |
+----------------------------+---------------+
```

- **Gauche** : Aider en chat (plan/code/execution)
- **Droite haut** : `git status` + 5 derniers commits, rafraichi toutes les 5s
- **Droite bas** : Terminal libre pour lancer des commandes (tests, build, localcoder...)

```bash
localcoder ide
```

**Raccourcis tmux** :
- `Ctrl+b` puis **flèche** : naviguer entre panneaux
- `Ctrl+b` puis **z** : zoomer/dezoomer
- `Ctrl+b` puis **d** : detacher (session continue en arriere-plan)
- `tmux attach -t localcoder-<projet>` : reattacher

---

## Les 3 modes de coding

| Mode | Modele | Contexte | Cout | Usage |
|---|---|---|---|---|
| **Local** | qwen2.5-coder:14b | 16K | 0E | Avion, petites taches, fix rapides |
| **Gemini** | gemini-2.5-pro | **1M** | **0E** | Multi-fichier, refacto, gros projets |
| **DeepSeek** | deepseek-reasoner | 128K | ~0.005$/req | Architecture, raisonnement profond |

**Sans internet** → local uniquement.
**Avec internet + free tier Gemini** → 95% des taches gratuitement.
**Pour les 5% restants** (raisonnement complexe) → DeepSeek a quelques centimes.

---

## Le workspace IDE (tmux)

Le vrai mode "IDE complet" est `localcoder ide`. C'est un environnement tmux avec 3 panneaux qui se parlent entre eux :

1. **Aider** au centre pour tcher avec l'IA
2. **Git watcher** qui montre en temps reel ce qui change
3. **Terminal libre** ou tu peux lancer n'importe quelle commande (tests, `localcoder find`, scripts, etc.)

Le tout est **persistent** : tu peux detacher la session (Ctrl+b d), fermer le terminal, revenir plus tard avec `tmux attach -t localcoder-<projet>` et tout est encore la.

---

## Memoire projet persistante

Chaque projet a sa propre base SQLite **locale** dans `.localcoder/memory.sqlite`.

**Aucune donnee n'est envoyee en ligne.** Tout reste sur ton Mac.

### Contenu de la memoire

```sql
symbols       -- Tous les fonctions/classes/methodes
features      -- Routes API, pages, composants, hooks, services, tables BDD
integrations  -- Qui appelle quoi (back <-> front <-> BDD)
sessions      -- Journal des sessions avec goal, commits, files_modified
```

### Isolation par projet

- `huntzenjobs` → `/Users/wissem/HuntzenIA/huntzen_jobsearch/.localcoder/memory.sqlite`
- `local_ai_stack` → `/Users/wissem/local_ai_stack/.localcoder/memory.sqlite`
- Aucune confusion possible entre projets

### Mise a jour automatique

Avec `localcoder hooks install`, la memoire est re-indexee **apres chaque commit Git** automatiquement.

---

## Workflow recommande

### Sur un nouveau projet

```bash
cd ~/nouveau-projet

# 1. Snapshot initial
localcoder scan             # Doublons, fichiers gros
localcoder index            # Memoire persistante
localcoder infra            # Check CLI et env
localcoder adapt            # CONVENTIONS specifique au projet
localcoder hooks install    # Re-index auto apres chaque commit

# 2. Comprendre l'etat
localcoder features         # Qu'est-ce qui existe ?
localcoder partial          # Qu'est-ce qui est incomplet ?
localcoder dead             # Qu'est-ce qui est mort ?
localcoder graph            # Comment tout est connecte ?
```

### Pour coder une feature

```bash
# 1. Verifier si ca existe deja
localcoder find "ma feature"

# 2. Lancer l'IDE complet
localcoder ide
# Dans Aider: /architect → plan → validation → /code

# 3. Apres la session
localcoder review           # Check des changements
localcoder precommit        # Bloque si probleme
git commit                  # Hook re-indexe auto
localcoder journal          # Historique
```

### Avant un merge

```bash
git checkout feature-branch
localcoder pr . main        # Verdict go/no-go complet
```

---

## Couts et limites honnetes

### Couts mensuels estimes

| Usage | Local | Gemini | DeepSeek | Total/mois |
|---|---|---|---|---|
| Hobby (2h/jour) | 100% | 0% | 0% | **0E** |
| Pro (6h/jour) | 40% | 55% | 5% | **~3-5E** |
| Intensif (8h+/jour) | 30% | 55% | 15% | **~15-25E** |
| **Claude Code Opus pur** | — | — | — | **200-500$** |

**Economie : 90-95%** vs Claude Code Opus.

### Limites honnetes

| Ce qui marche bien | Ce qui est limite |
|---|---|
| Scan, index, find, features, dead | Matching front/back : 63% (regex, pas AST) |
| Memoire SQLite persistante | Le 14b local hallucine sur taches complexes |
| Mode Gemini 1M contexte gratuit | Rate limit Gemini : 25 req/min |
| Auto-indexation post-commit | Detection semantique limitee (pas d'embeddings) |
| Workspace IDE tmux | tmux requis (install via brew) |

**Le systeme n'est pas parfait. Il est pragmatique.**

---

## Depannage

### `localcoder: command not found`
```bash
source ~/local_ai_stack/venv/bin/activate
```

### `aider: command not found`
```bash
cd ~/local_ai_stack && source venv/bin/activate && pip install -e .
```

### Python version incompatible
```bash
localcoder advise
# → Propose les options sans modifier
```

### Ollama ne repond pas
```bash
ollama serve &
ollama list
```

### `tmux: command not found`
```bash
brew install tmux
```

### Modele local trop lent (18 Go RAM saturee)
- Fermer les autres apps
- Utiliser le 7b : modifier `.aider.conf.yml`
- Utiliser Gemini (0 RAM local, tout distant)

### GEMINI_API_KEY non definie
```bash
# Cle gratuite : https://aistudio.google.com/apikey
echo 'export GEMINI_API_KEY="ta-cle"' >> ~/.zshrc
source ~/.zshrc
```

---

## Structure du projet

```
local_ai_stack/
├── venv/                           # Python 3.12.13
├── localcoder/                     # 16 modules
│   ├── cli.py                      # Point d'entree, 20 commandes
│   ├── scanner.py                  # Doublons, gros fichiers, TODOs
│   ├── reviewer.py                 # Review statique
│   ├── git_analyzer.py             # Git intelligence
│   ├── pr_reviewer.py              # Review de PR
│   ├── pre_commit_check.py         # Pre-commit hook
│   ├── infra_checker.py            # Check CLI + env
│   ├── complexity.py               # Routage tache → modele
│   ├── conventions_generator.py    # CONVENTIONS adaptatives
│   ├── upgrade_advisor.py          # Propose upgrades
│   ├── project_memory.py           # Memoire SQLite persistante
│   ├── partial_detector.py         # Features partielles
│   ├── call_graph.py               # Call graph Mermaid
│   ├── hooks_installer.py          # Hooks Git
│   ├── dead_code.py                # Dead code
│   └── workspace.py                # Workspace tmux IDE
├── CONVENTIONS.md                  # 9 sections de regles strictes
├── pyproject.toml
├── .aider.conf.yml                 # Mode local
├── .aider.conf.gemini.yml          # Mode Gemini (gratuit)
├── .aider.conf.api.yml             # Mode DeepSeek
├── .aider.model.settings.yml       # Calibrage 18 Go
├── .aider.model.metadata.json
├── .aiderignore
├── start.sh
└── README.md                       # Ce fichier
```

---

## Pipeline rigoureux (v2.1 en cours — Plan 5A)

LocalCoder v2.1 introduit un pipeline 11 étapes pour passer de "génération
texte" à "modifications fichiers vérifiées" avec re-vérifications croisées
et rollback automatique. Cible : 99 % succès simple / 95 % complexe.

**Spec complète** : `docs/superpowers/specs/2026-04-20-pipeline-rigoureux.md`.

### 11 étapes du pipeline

`ESTIMATE → INTAKE → CHALLENGE → GROUND → PLAN → PLAN_REVIEW → EXECUTE → SELF_CHECK → VERIFY → REVIEW → COMMIT`

Chaque étape utilise le LLM le mieux adapté à son rôle (Gemini Flash pour
classification, Pro pour analyse/review, R1 pour architecture, MiniMax M2.5
pour coding) via dispatch multi-LLM.

### État actuel — fin Plan 5C (2026-05)

**Modes SIMPLE / MEDIUM / COMPLEX tous activés** (8/11 étapes
implémentées en vrai, 3 stubs Plan 5D) :

- `Stage0Estimate` (Gemini Flash) — classification + cost preview.
- `Stage1Intake` (Gemini Flash) — validation non-ambiguïté.
- `Stage2Challenge` (Gemini Pro) — avocat du diable, risks/edge_cases/alternatives.
- `Stage3Ground` (MiniMax M2.5) — tool-calling read-only ancrage factuel.
- `Stage4Consensus` (R1 + Pro) — consensus 2 rounds max sur le PLAN.
- `Stage5Execute` (MiniMax M2.5) — tool-calling write + git stash rollback.
- `Stage7Verify` (mécanique) — ruff + eslint + cargo + pytest + vitest en parallèle, retry max 3.

**Plan 5C livré** : Stage2Challenge, Stage4aPlan (R1), Stage4bPlanReview (Pro),
mécanisme consensus 2/2 avec deadlock UI (DeadlockModal), modes MEDIUM et
COMPLEX activés dans le Pipeline orchestrator, ConsensusRoundsLog côté UI.

342 tests pytest + 158 tests vitest verts. UI : modal ESTIMATE +
TraceViewer + StreamingBubble + BudgetIndicator + ChallengePanel +
PlanDiffView + ConsensusRoundsLog + DeadlockModal.

### Plans à venir

- **Plan 5B** — VERIFY étendu (pytest/vitest + retry max 3 + rollback robuste) + streaming.
- **Plan 5C** — CHALLENGE multi-LLM + PLAN consensus 2/2.
- **Plan 5D** — SELF-CHECK + REVIEW consensus 2/2.
- **Plan 5E** — UX raffinée + Settings + suivi coûts.
- **Plan 5F** — Packaging + intégration Ollama + release v2.

---

## Version

**LocalCoder v0.3** — 2026-04-05
- 16 modules Python
- 20 commandes CLI
- 3 modes coding (local / gemini / deepseek)
- Workspace IDE tmux
- Memoire SQLite persistante par projet
- Hook Git auto-index
- Python 3.12.13 | Aider 0.86.2 | Rich 14.0
