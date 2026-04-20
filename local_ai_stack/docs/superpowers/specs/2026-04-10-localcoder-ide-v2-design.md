# LocalCoder IDE v2.0 — Design Spec

**Date :** 2026-04-10  
**Statut :** Validé  
**Auteur :** Wissem × Claude  

---

## Vision

Un IDE intelligent local qui remplace Claude Code, Cursor, Devin et Jira simultanément. Un seul chat universel. Le système détecte ce que l'utilisateur veut et orchestre les bons LLMs automatiquement. Circuit fermé de l'idée au code validé sur GitHub — pour $30-60/mois.

---

## 1. Architecture technique

### Stack

```
[TAURI — shell natif macOS]
    ↕ WebSocket ws://localhost:8765
[FASTAPI PYTHON — port 8765]
    Orchestrateur | Router | Agent Loop | GitHub MCP | Memory
    ↕ LiteLLM (interface unifiée)
[MiniMax M2.5] [Gemini 2.5 Pro/Flash] [DeepSeek R1] [Codestral 2]
    ↕
[GitHub API via MCP] [Ollama local optionnel]
```

### Démarrage et cycle de vie des processus

Une seule commande : `localcoder ide`
1. FastAPI démarre comme **processus enfant** de Tauri (subprocess Python)
2. Tauri attend le health check sur `localhost:8765/health` (max 5s, retry 500ms)
3. Tauri s'ouvre avec l'UI React une fois FastAPI prêt
4. WebSocket établi automatiquement (`ws://localhost:8765/ws`)

**Arrêt propre :**
- Fermeture de la fenêtre Tauri → signal SIGTERM envoyé au processus FastAPI enfant
- FastAPI reçoit SIGTERM → finalise les tâches en cours (max 10s) → shutdown
- Si FastAPI crash → Tauri affiche une bannière d'erreur + bouton "Relancer le backend"
- FastAPI ne peut pas tourner sans Tauri (processus enfant, pas daemon)

### Modules backend

```
backend/
├── main.py              # FastAPI app + routes WebSocket
├── orchestrator.py      # Chef d'orchestre — point d'entrée de toute tâche
├── router_engine.py     # Routage par complexité + feedback loop
├── agent_loop.py        # 5 étapes universelles + retry intelligent
├── llm_manager.py       # LiteLLM + fallback chain + rate limiting
├── roadmap.py           # ProjectRoadmap — lecture/écriture SQLite
├── memory.py            # Mémoire courte (RAM) + longue (SQLite)
├── github_service.py    # Intégration GitHub via MCP
├── git_service.py       # Git local (diff, commit, branch)
├── file_lock.py         # Verrouillage fichiers par LLM
├── task_queue.py        # File d'attente par LLM (1 tâche à la fois)
├── ws_streamer.py       # Événements WebSocket temps réel
├── context_builder.py   # Construction contexte ciblé ~2-3K tokens
└── prompts/
    ├── system_minimax.md
    ├── system_deepseek_r1.md
    ├── system_codestral.md
    ├── system_gemini_pro.md
    └── system_gemini_flash.md
```

---

## 2. Stack LLM

### Modèles et rôles

| LLM | Rôle précis | SWE-bench | Input /1M | Output /1M |
|-----|-------------|-----------|-----------|------------|
| MiniMax M2.5 | Coding principal | 80.2% | $0.118 | $0.99 |
| Gemini 2.5 Pro | Analyse longue + CdC review | ~74% | $1.25 | $10.00 |
| Gemini 2.5 Flash | Routage + tâches rapides | ~65% | $0.075 | $0.30 |
| DeepSeek R1 | Architecture + raisonnement | 70% | $0.55 | $2.19 |
| Codestral 2 | Tests unitaires | — (92% HumanEval) | $0.30 | $0.90 |

### Routage par complexité

Le `router_engine.py` étend `complexity.py` existant en alignant ses seuils :

```python
# complexity.py existant : seuils 3 et 6 → alignés sur 4 et 7
# La fonction analyze_task_complexity() est réutilisée telle quelle
# Seuls les seuils de décision changent dans router_engine.py

score = analyze_task_complexity(prompt, file_count).score

if score <= 4:    # Simple → 1 LLM direct
    # Déclencheurs : fix, typo, rename, ajout champ, commentaire
    MiniMax seul, agent loop direct

elif score <= 7:  # Medium → 1 LLM + validation légère
    # Déclencheurs : optimisation, extraction, test unitaire, petite feature
    MiniMax implémente + Gemini Flash review rapide (1 round)

else:             # Complexe ≥ 8 → Multi-agent complet
    # Déclencheurs : architecture, migration, refacto globale, nouveau module
    R1 planifie → MiniMax code → Codestral teste → Gemini review
```

**Algorithme de scoring (hérité de complexity.py, seuils ajustés) :**
- Patterns complexes (regex sur prompt) : +4 à +8 points
- Patterns simples : réduction au score+1
- Nombre de fichiers impliqués > 5 : score minimum 6
- Nombre de fichiers > 10 : score minimum 8
- Mots-clés projet ("crée une app", "nouveau projet") : score forcé à 9

**Note :** `multi_ask.py` existant est conservé tel quel et accessible via `@all` dans le chat pour interroger tous les LLMs en parallèle (usage manuel uniquement, hors routing automatique).

### Fallback chain

```python
CODING_FALLBACK   = ["minimax/minimax-m2.5", "deepseek/deepseek-v3", "gemini/gemini-2.5-pro"]
ANALYSIS_FALLBACK = ["gemini/gemini-2.5-pro", "minimax/minimax-m2.5"]
ARCH_FALLBACK     = ["deepseek/deepseek-r1", "gemini/gemini-2.5-pro"]
```

### Override manuel

L'utilisateur peut forcer un LLM en préfixant son message :
`@minimax`, `@gemini`, `@deepseek`, `@codestral`

### Feedback loop routing

Si l'utilisateur corrige un mauvais routage, la correction est stockée en SQLite et utilisée aux prochains appels similaires.

---

## 3. Interface utilisateur

### Layout principal

```
┌──┬──────────────────────────────────────────────────────────┐
│  │  [Chat]  [Terminaux]  [Routing]  [Monitoring]            │
│A │──────────────────────────────────────────────────────────│
│c │                                                          │
│t │                Zone principale                           │
│i │             (contenu du tab actif)                       │
│v │                                                          │
│i ├──────────────────────────────────────────────────────────┤
│t │ MiniMax● Gemini● DeepSeek● Codestral● | branch | tokens │
│y └──────────────────────────────────────────────────────────┘
```

### Activity Bar (colonne gauche, toujours visible)

- **Fichiers** → FileTree (explorateur projet, fichiers modifiés en jaune)
- **LLMs** → Statut temps réel : actif / occupé / désactivé
- **Git** → Diff, stage, commit, PR sans quitter l'app
- **Sprints** → Kanban board des tickets en cours

### Tab Chat

Interface universelle. Un seul endroit. Le système détecte et route.

```
┌─────────────────────────────────────────────────────────┐
│  [Historique conversation avec badges LLM par message]  │
│                                                         │
│  💡 DeepSeek R1 (Architecture)                          │
│  "Je recommande de splitter auth.py en 3..."            │
│                                                         │
│  💻 MiniMax M2.5 (Coding)                               │
│  "auth_core.py créé avec login(), logout()..."          │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ [@minimax] [@gemini] [@deepseek] [@codestral]  [📎]     │
│ ┌─────────────────────────────────────────────┐  [↵]   │
│ │ Écris ici...                                │        │
│ └─────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘
```

Chaque message affiche : quel LLM a répondu, durée, tokens consommés.

### Tab Terminaux

Grille xterm.js — un terminal par LLM actif. Chaque terminal affiche les logs en temps réel du processus LLM correspondant (stdout de l'agent loop, sorties bash, résultats lint).

### Tab Routing Flow

**Live :** animation du prompt en cours → LLM cible → statut traitement
**Historique :** tableau de tous les routages avec LLM, raison, durée, tokens

### Tab Monitoring

- Utilisation CPU/RAM par processus LLM
- Tokens/minute par modèle
- Latence moyenne par modèle
- Statut CI GitHub par ticket en cours
- Coût estimé de la session

### Status Bar (toujours visible)

- Pastille couleur par LLM (vert / orange / gris)
- Branche git + nb fichiers modifiés
- Tokens today + coût estimé

---

## 4. Agent Engineering Layer

### MD Files par LLM

Chaque modèle reçoit un system prompt optimisé pour ses forces et faiblesses.

**Structure commune à tous :**
```markdown
# Règles absolues — [NOM LLM]

## AVANT TOUTE MODIFICATION
1. Lis ENTIÈREMENT le fichier cible
2. Grep tous les appelants de la fonction modifiée
3. Vérifie que la dépendance n'existe pas déjà (roadmap + codebase)
4. Liste les fichiers qui seront touchés

## FORMAT RÉPONSE OBLIGATOIRE
[spécifique à chaque LLM]

## INTERDICTIONS ABSOLUES
- Créer un fichier si le code peut aller dans un existant
- Supposer qu'une fonction existe sans vérifier
- Modifier plus d'un fichier à la fois sans confirmation
- Ignorer les entrées du champ do_not_touch de la roadmap
```

**Spécificités par LLM :**
- `system_minimax.md` : focus diff propre, imports cohérents, un fichier à la fois
- `system_deepseek_r1.md` : format plan → trade-offs → décision → rationale
- `system_codestral.md` : coverage minimum 80%, nommage test_ strict, pas de mocks inutiles
- `system_gemini_pro.md` : structure rapport, points critiques d'abord, liste exhaustive
- `system_gemini_flash.md` : classification rapide, réponse JSON uniquement, pas de code

### Agent Loop universel

```
Étape 1 — PLAN
  LLM liste exactement ce qu'il va faire
  Pas de code encore
  Orchestrateur valide le plan vs roadmap

Étape 2 — VERIFY
  Orchestrateur vérifie :
  - Fichiers concernés existent ?
  - Fichiers verrouillés par un autre LLM ?
  - Duplication détectée dans la roadmap ?
  - Champ do_not_touch respecté ?

Étape 3 — EXECUTE
  Un fichier à la fois
  Orchestrateur écrit via write_file (pas le LLM directement)

Étape 4 — CHECK
  Lint (ruff pour Python, eslint pour JS/TS)
  Syntaxe valide
  Imports cohérents
  Orchestrateur exécute — pas le LLM

Étape 5 — CONFIRM
  Diff présenté dans l'UI
  Roadmap mise à jour par l'orchestrateur
  GitHub Issue sous-tâche cochée
```

**Retry intelligent (agent loop interne — 3 tentatives max) :**
```
Erreur détectée à l'étape 4 :
  Tentative 1 → injection erreur exacte dans le prompt
  Tentative 2 → changement de stratégie de prompt
  Tentative 3 → dernier essai avec contexte maximal
  Échec total  → lève AgentLoopError avec rapport complet
```

**Note sur les deux niveaux de retry :**
- **Niveau 1 — Agent Loop** (étape 4) : 3 tentatives sur un fichier donné (lint/syntaxe)
- **Niveau 2 — Mode Projet** (section 6) : si CI GitHub échoue, 3 nouvelles exécutions complètes du ticket
- Ces niveaux ne s'imbriquent pas : 3 retries internes OU 3 relances CI, jamais les deux en cascade (max 3 tentatives total par niveau)

### Tool Use (identique pour tous les LLMs)

```python
TOOLS = [
    # Filesystem
    {"name": "read_file",       "desc": "Lit un fichier avant modification"},
    {"name": "write_file",      "desc": "LLM propose le contenu → orchestrateur valide et écrit physiquement"},
    {"name": "bash",            "desc": "Commande shell (grep, lint, test)"},
    {"name": "git_diff",        "desc": "Diff avant commit"},
    {"name": "search_codebase", "desc": "Grep projet pour éviter doublons"},
    # Roadmap (lecture seule pour les LLMs)
    {"name": "roadmap_read",    "desc": "Lit l'état actuel du projet"},
    # GitHub (via MCP)
    {"name": "github_create_issue",  "desc": "Crée un ticket GitHub"},
    {"name": "github_create_pr",     "desc": "Crée une PR liée à l'issue"},
    {"name": "github_update_issue",  "desc": "Coche sous-tâches, labels"},
    {"name": "github_close_issue",   "desc": "Ferme si CI vert"},
]
```

---

## 5. Système Multi-Agent avec Mémoire

### Règle fondamentale

```
Les LLMs ne s'appellent JAMAIS directement.
Ils déposent des demandes à l'orchestrateur.
L'orchestrateur exécute et retourne les résultats.
Maximum 5 rounds de consultation par tâche.
```

### Types de messages inter-LLMs

```python
class MessageType(Enum):
    DECISION = "decision"  # J'ai décidé quelque chose d'important
    QUESTION = "question"  # J'ai besoin de l'avis d'un autre LLM
    RESULT   = "result"    # J'ai terminé, voici ce que j'ai fait
    WARNING  = "warning"   # J'ai détecté un problème
    CONTEXT  = "context"   # Je partage du contexte utile
```

### Mémoire courte (RAM, session)

```python
@dataclass
class ShortTermMemory:
    session_id: str
    active_task: str
    actions: list[Action]           # Journal temps réel
    file_locks: dict[str, str]      # filepath → llm_name
    messages: list[Message]         # Inter-LLMs
    consultation_rounds: int        # Max 5
    
    # Contexte injecté à chaque LLM : ~2-3K tokens ciblés
    # Pas le contexte brut complet
```

### Mémoire longue (SQLite persistant)

```sql
CREATE TABLE decisions (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT,
    llm         TEXT,
    type        TEXT,         -- 'architecture', 'pattern', 'warning'
    content     TEXT,
    rationale   TEXT,
    files       TEXT,         -- JSON
    valid       BOOLEAN DEFAULT true,
    valid_until DATE,         -- TTL optionnel
    created_at  TIMESTAMP
);

CREATE TABLE llm_messages (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT,
    from_llm    TEXT,
    to_llm      TEXT,         -- LLM cible ou 'all'
    type        TEXT,
    content     TEXT,
    replied     BOOLEAN DEFAULT false,
    created_at  TIMESTAMP
);

CREATE TABLE roadmap_history (
    id          INTEGER PRIMARY KEY,
    project     TEXT,
    ticket_id   TEXT,
    action      TEXT,         -- 'created', 'started', 'done', 'failed', 'modified'
    by          TEXT,         -- LLM ou 'orchestrator' ou 'user'
    detail      TEXT,
    created_at  TIMESTAMP
);

CREATE TABLE routing_feedback (
    id           INTEGER PRIMARY KEY,
    prompt_hash  TEXT,
    routed_to    TEXT,        -- LLM initial
    corrected_to TEXT,        -- LLM correct selon user
    pattern      TEXT,        -- Pattern extrait du prompt
    created_at   TIMESTAMP
);
```

### Project Roadmap

```json
{
  "project": "nom-projet",
  "session_id": "2026-04-10-09h15",
  "tasks": [
    {
      "id": "T-003",
      "title": "Endpoint login JWT",
      "status": "in_progress",
      "assigned_to": "minimax_m2",
      "subtasks": [
        {"id": "T-003-1", "text": "User model", "done": true},
        {"id": "T-003-2", "text": "POST /auth/login", "done": false}
      ],
      "blocked_by": [],
      "github_issue": 42
    }
  ],
  "files_state": {
    "auth.py": {"status": "modified", "by": "minimax_m2", "locked": true}
  },
  "decisions": [
    {
      "by": "deepseek_r1",
      "content": "auth.py splitté en 3 fichiers",
      "valid": true
    }
  ],
  "do_not_touch": ["_validate_scope()", "Redis config dans settings.py"],
  "done_this_session": ["auth_core.py créé avec login(), logout(), verify_token()"]
}
```

**Règle absolue :** La roadmap est écrite uniquement par l'orchestrateur FastAPI après vérification réelle. Les LLMs lisent, jamais n'écrivent.

### Context Builder

```python
def build_context_for(llm: str, task: str, roadmap: Roadmap | None) -> str:
    """
    ~2-3K tokens ciblés. Jamais le contexte brut complet.
    Si roadmap est None (session simple sans mode projet) :
    → contexte minimal : CONVENTIONS.md + AGENT_RULES.md du projet courant
    Si roadmap active :
    → contexte complet avec état des tâches, décisions, fichiers verrouillés
    """
    if roadmap is None:
        # Mode conversation simple — pas de roadmap projet
        return load_project_conventions()   # CONVENTIONS.md + AGENT_RULES.md
    
    return "\n\n".join([
        roadmap.get_done_summary(),          # ~300 tokens — ce qui est fait
        roadmap.get_do_not_touch(),          # ~200 tokens — ce qu'on ne touche pas
        roadmap.get_locked_files(),          # ~100 tokens — fichiers occupés
        roadmap.get_relevant_decisions(task),# ~500 tokens — décisions pertinentes
        roadmap.get_known_patterns(),        # ~300 tokens — patterns du projet
    ])
```

### Protections concurrence

```python
import asyncio

class FileLock:
    """Thread-safe via asyncio.Lock — opération acquire atomique."""
    _locks: dict[str, str] = {}
    _mutex: asyncio.Lock = asyncio.Lock()
    
    async def acquire(self, filepath: str, llm: str) -> bool:
        async with self._mutex:          # Atomique — pas de race condition
            if filepath in self._locks:
                return False             # Refusé
            self._locks[filepath] = llm
            return True
    
    async def release(self, filepath: str, llm: str):
        async with self._mutex:
            if self._locks.get(filepath) == llm:
                del self._locks[filepath]

class LLMTaskQueue:
    # Une tâche à la fois par LLM
    # Nouvelle tâche → attend la fin de la précédente
    # UI affiche : "MiniMax occupé — 1 tâche en attente"
    
    rate_limits = {
        "minimax/minimax-m2.5":       {"rpm": 200},
        "gemini/gemini-2.5-pro":      {"rpm": 60},
        "gemini/gemini-2.5-flash":    {"rpm": 1000},
        "deepseek/deepseek-r1":       {"rpm": 50},
        "mistral/codestral-2":        {"rpm": 100},
    }
```

---

## 6. Mode Projet — Circuit fermé

### Déclenchement automatique

Complexité score ≥ 8 + détection mots-clés projet :
"crée une app", "je veux construire", "nouveau projet", "génère le CdC"

### Étape 1 — Génération CdC

```
[DeepSeek R1] reçoit la description utilisateur
  → Génère CdC structuré :
    - Contexte et objectifs
    - Fonctionnalités (MoSCoW)
    - Stack technique recommandée
    - Contraintes et non-fonctionnels
    - Critères de succès

[Gemini Pro] review le CdC (1M contexte si existant)
  → Complète les trous
  → Signale les incohérences

[User] valide le CdC (~5 min)
```

### Étape 2 — Découpage en Sprints et Tickets

```
[DeepSeek R1] génère :
  Sprint 1 → Milestone GitHub (date de fin estimée)
  Sprint 2 → Milestone GitHub
  ...

[R1 + MiniMax] par ticket :
{
  "id": "T-003",
  "sprint": "Sprint 1",
  "title": "Endpoint login avec JWT",
  "description": "...",
  "acceptance_criteria": ["...", "..."],
  "subtasks": [{"id": "T-003-1", "text": "...", "done": false}],
  "tests_required": ["test_login_success()", "test_login_invalid()"],
  "blocked_by": ["T-001", "T-002"],
  "estimated_complexity": 5
}
```

### Étape 3 — Création GitHub automatique

Via GitHub MCP, l'orchestrateur crée :
- GitHub Issues avec checkboxes (acceptance criteria + subtasks)
- Labels : `sprint-1`, `pending`, `backend`, etc.
- Milestones par sprint
- Project Board Kanban
- Workflow GitHub Actions

### GitHub Issue générée

```markdown
## T-003 — Endpoint login avec JWT

**Sprint :** Sprint 1 | **Complexité :** 5/10

### Description
POST /auth/login → retourne access_token + refresh_token

### Critères d'acceptation
- [ ] Login valide retourne 200 + JWT
- [ ] Mauvais mot de passe retourne 401
- [ ] Token expiré retourne 403
- [ ] Refresh token fonctionne

### Sous-tâches
- [ ] T-003-1 — Créer User model SQLAlchemy
- [ ] T-003-2 — Créer POST /auth/login
- [ ] T-003-3 — Générer JWT avec python-jose
- [ ] T-003-4 — Implémenter refresh token

### Tests requis
- test_login_success()
- test_login_wrong_password()
- test_login_expired_token()
- test_refresh_token()

**Branch :** `feature/T-003-login-jwt`
**Bloqué par :** T-001, T-002
```

### GitHub Actions générées

```yaml
# .github/workflows/ticket-validation.yml
name: Ticket Validation
on:
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup environment
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/ -v --tb=short
      - name: Extract GitHub Issue number from PR title
        # PR title générée par le système : "[T-003] Endpoint login JWT (#42)"
        # Le numéro GitHub Issue est le dernier segment entre parenthèses
        run: |
          ISSUE_NUMBER=$(echo "${{ github.event.pull_request.title }}" \
            | grep -oP '(?<=#)\d+(?=\))')
          echo "ISSUE_NUMBER=$ISSUE_NUMBER" >> $GITHUB_ENV
      - name: Close Issue on success
        if: success()
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh issue close $ISSUE_NUMBER \
            --comment "✅ CI vert. Tous les tests passent. PR mergée."
          gh issue edit $ISSUE_NUMBER --add-label "validated" --remove-label "in-progress"
      - name: Flag Issue on failure
        if: failure()
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh issue comment $ISSUE_NUMBER \
            --body "❌ CI échoue. Agent loop retry en cours."
          gh issue edit $ISSUE_NUMBER --add-label "blocked"
```

### Étape 4 — Exécution autonome par ticket

```
Pour chaque ticket (ordre : dépendances respectées) :

1. Roadmap check → pas bloqué ?
2. Branch créée : feature/T-XXX-nom
3. [MiniMax] implémente via agent loop 5 étapes
4. [Codestral] génère les tests requis
5. Commit + push automatique
6. PR créée → liée à l'Issue
7. GitHub Actions CI lance (environnement propre)
8a. CI vert → auto-merge → Issue fermée → roadmap updated → ticket suivant
8b. CI rouge → retry max 3 → si échec total → flag user
```

### Checkpoint humain

```
"Sprint 1 terminé — 8/8 tickets validés par CI ✅
 Review avant Sprint 2 ?
 [Démarrer Sprint 2 automatiquement] [Je review d'abord]"
```

### Modifications roadmap autorisées par le système

```python
# Le système PEUT faire seul :
ALLOWED = [
    "Réordonner tickets dans un sprint si dépendances OK",
    "Splitter un ticket trop complexe (score > 8) en 2",
    "Ajouter un ticket si gap découvert pendant implémentation",
    "Marquer un ticket bloqué avec raison explicite",
]

# Le système DOIT demander confirmation :
REQUIRES_APPROVAL = [
    "Supprimer un ticket",
    "Modifier le scope du CdC original",
    "Réordonner des sprints entiers",
    "Modifier un ticket déjà validé par CI",
]
```

---

## 7. Sécurité et robustesse

| Risque | Solution |
|--------|---------|
| Clés API en clair | Keychain natif macOS via Tauri secure store |
| Conflit fichiers | File locking — 1 fichier = 1 LLM à la fois |
| Tâches simultanées | Task queue par LLM — 1 tâche à la fois |
| Boucle infinie agents | Max 5 rounds consultation, max 3 retries |
| Annulation mi-tâche | CancellationToken → rollback fichiers modifiés |
| Rate limits API | LiteLLM throttle automatique par provider |
| Décisions obsolètes | TTL sur decisions + invalidation manuelle |
| Roadmap corrompue | Orchestrateur seul écrit — LLMs lisent uniquement |
| Routing erroné | Feedback loop → correction stockée en SQLite |
| Provider down | Fallback chain automatique par rôle |
| Deadlock agents | Timeout 120s par tâche → escalade user |

---

## 8. Structure complète du projet

```
local_ai_stack/
├── localcoder/                    # 16 modules existants — INCHANGÉS
│   ├── cli.py
│   ├── scanner.py
│   ├── reviewer.py
│   ├── git_analyzer.py
│   ├── pr_reviewer.py
│   ├── pre_commit_check.py
│   ├── infra_checker.py
│   ├── complexity.py              # ÉTENDU — intégré au router_engine
│   ├── conventions_generator.py
│   ├── upgrade_advisor.py
│   ├── project_memory.py          # ÉTENDU — intégré à memory.py
│   ├── partial_detector.py
│   ├── call_graph.py
│   ├── hooks_installer.py
│   ├── dead_code.py
│   └── workspace.py               # REMPLACÉ par Tauri
│
├── backend/                       # NOUVEAU
│   ├── main.py
│   ├── orchestrator.py
│   ├── router_engine.py
│   ├── agent_loop.py
│   ├── llm_manager.py
│   ├── roadmap.py
│   ├── memory.py
│   ├── github_service.py
│   ├── git_service.py
│   ├── file_lock.py
│   ├── task_queue.py
│   ├── ws_streamer.py
│   ├── context_builder.py
│   └── prompts/
│       ├── system_minimax.md
│       ├── system_deepseek_r1.md
│       ├── system_codestral.md
│       ├── system_gemini_pro.md
│       └── system_gemini_flash.md
│
├── ui/                            # NOUVEAU
│   ├── src-tauri/
│   │   ├── src/
│   │   │   └── main.rs            # Shell Rust minimal
│   │   └── tauri.conf.json
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── ActivityBar/
│       │   │   ├── FileTree.tsx
│       │   │   ├── LLMStatus.tsx
│       │   │   ├── GitPanel.tsx
│       │   │   └── SprintBoard.tsx
│       │   ├── StatusBar/
│       │   │   └── StatusBar.tsx
│       │   └── tabs/
│       │       ├── ChatTab/
│       │       │   ├── ChatTab.tsx
│       │       │   ├── MessageBubble.tsx
│       │       │   └── ChatInput.tsx
│       │       ├── TerminalsTab/
│       │       │   └── TerminalsTab.tsx
│       │       ├── RoutingTab/
│       │       │   ├── RoutingLive.tsx
│       │       │   └── RoutingHistory.tsx
│       │       └── MonitoringTab/
│       │           └── MonitoringTab.tsx
│       └── stores/
│           ├── llmStore.ts         # Zustand — statut LLMs
│           ├── routingStore.ts     # Zustand — historique routing
│           ├── roadmapStore.ts     # Zustand — roadmap courante
│           └── sessionStore.ts     # Zustand — session active
│
├── .github/
│   └── workflows/
│       └── ticket-validation.yml  # Généré automatiquement par mode projet
│
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-04-10-localcoder-ide-v2-design.md
│
├── config.yml                     # ÉTENDU — ajout LLMs + rôles + GitHub
├── pyproject.toml                 # ÉTENDU — FastAPI, litellm, anthropic, etc.
├── CONVENTIONS.md                 # Existant
└── README.md                      # À mettre à jour
```

---

## 9. Comparaison finale

| Capacité | Claude Code | Cursor | Devin | Jira | LocalCoder IDE v2 |
|----------|------------|--------|-------|------|-------------------|
| Multi-LLM spécialisés | ❌ | ❌ | ❌ | ❌ | ✅ |
| LLMs qui se consultent | ❌ | ❌ | ❌ | ❌ | ✅ |
| Mémoire inter-sessions | ❌ | ❌ | ❌ | ✅ | ✅ |
| CdC → Sprints → Tickets auto | ❌ | ❌ | ⚠️ | ❌ | ✅ |
| Tests par ticket (CI) | ❌ | ❌ | ❌ | ❌ | ✅ |
| GitHub circuit fermé | ❌ | ❌ | ❌ | ✅ | ✅ |
| Anti-duplication roadmap | ❌ | ❌ | ❌ | ❌ | ✅ |
| Routing intelligent | ❌ | ❌ | ❌ | ❌ | ✅ |
| Visible temps réel | ❌ | ❌ | ❌ | ❌ | ✅ |
| Coût mensuel | ~$200 | ~$20 | ~$500 | ~$10 | **~$30-60** |

---

## 10. Ce qui est en v2 (post-lancement)

- Patterns auto-appris via embeddings (vector store)
- Support équipe multi-utilisateurs
- Plugin marketplace pour nouveaux LLMs
- Intégration Linear / Notion en alternative à GitHub Issues

---

*Spec validée le 2026-04-10 — Prête pour implémentation*
