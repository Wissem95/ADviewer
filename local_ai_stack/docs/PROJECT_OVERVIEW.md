# LocalCoder IDE v2.1 — Vue d'ensemble ultra-détaillée

> **Document généré le 2026-05-04** • Couvre Plans 1, 2, 3, 4, 5 (5A complet, 5B en cours, 5C-5F prévus).
> Branche `main`, tag `v2.1.0-alpha.1` poussé sur `https://github.com/Wissem95/localcoder-ide`.

---

## Sommaire

- [1. Vision et objectif du projet](#1-vision-et-objectif-du-projet)
- [2. Public cible et cas d'usage](#2-public-cible-et-cas-dusage)
- [3. État actuel — qu'est-ce qui marche aujourd'hui](#3-état-actuel--quest-ce-qui-marche-aujourdhui)
- [4. Stack technique complète](#4-stack-technique-complète)
- [5. Architecture globale](#5-architecture-globale)
- [6. Les 5 LLMs orchestrés](#6-les-5-llms-orchestrés)
- [7. Le pipeline rigoureux 11 étapes](#7-le-pipeline-rigoureux-11-étapes)
- [8. Les 3 modes de pipeline (simple / medium / complex)](#8-les-3-modes-de-pipeline)
- [9. Fonctionnalités côté backend, fichier par fichier](#9-fonctionnalités-côté-backend)
- [10. Tools — les actions que les LLMs peuvent appeler](#10-tools--les-actions-que-les-llms-peuvent-appeler)
- [11. UI — composants, stores, flows](#11-ui--composants-stores-flows)
- [12. Persistance — SQLite, fichiers, git stash](#12-persistance--sqlite-fichiers-git-stash)
- [13. Mode Projet — du CdC à la PR fusionnée](#13-mode-projet--du-cdc-à-la-pr-fusionnée)
- [14. Tests — 285 pytest + 121 vitest verts](#14-tests--285-pytest--121-vitest-verts)
- [15. Coûts réels et estimés](#15-coûts-réels-et-estimés)
- [16. Comment lancer le projet en dev](#16-comment-lancer-le-projet-en-dev)
- [17. Plans 1-4 — historique complet](#17-plans-1-4--historique-complet)
- [18. Plan 5A — fondations pipeline (livré)](#18-plan-5a--fondations-pipeline-livré)
- [19. Plan 5B — VERIFY + retry + streaming (en cours)](#19-plan-5b--verify--retry--streaming-en-cours)
- [20. Plans 5C, 5D, 5E, 5F — à venir](#20-plans-5c-5d-5e-5f--à-venir)
- [21. Tous les events WebSocket](#21-tous-les-events-websocket)
- [22. Tous les endpoints HTTP](#22-tous-les-endpoints-http)
- [23. Garanties de sécurité](#23-garanties-de-sécurité)
- [24. Limitations connues](#24-limitations-connues)
- [25. Glossaire](#25-glossaire)
- [26. FAQ technique](#26-faq-technique)

---

## 1. Vision et objectif du projet

**LocalCoder IDE v2.1** est un IDE agentique multi-LLM pensé comme un **remplaçant ~90 % de Claude Code Opus**, lancé localement sur Mac (M3 Pro 18 Go visé), à coût compris entre **$30 et $300 par mois** selon l'intensité.

**Ce que le produit promet** :

- **Zéro hallucination LLM grâce au "grounding"** : aucun stage critique ne suppose le contenu d'un fichier — il le lit via tool-calling avant de décider.
- **Modifications fichiers vraiment vérifiées** : avant qu'un commit ne parte, ruff/eslint/cargo/pytest/vitest sont lancés ; rouge → retry automatique avec feedback ; après 3 retries rouges → rollback git automatique.
- **Re-vérifications croisées** : sur les tâches complexes, deux LLMs différents doivent se mettre d'accord (consensus 2/2) avant que le PLAN soit validé, et avant que la REVIEW finale soit acceptée.
- **Cost preview avant action** : un modal affiche le coût estimé en USD avant que la moindre étape coûteuse ne tourne — l'utilisateur valide, force un mode moins cher, ou annule.
- **Cible quantifiée** : 99 % succès sur tâches simples, 95 %+ sur complexes (cible tenue par la chaîne re-vérifications + retry + rollback).

**Ce que ça remplace** :

- Claude Code Opus (~$15-30 par session lourde) en gardant la qualité de coding (MiniMax M2.5 = SWE-bench 80 %).
- Cursor avec un focus fort sur "modifications vérifiées" plutôt que "complétion de texte".
- Aider en mode pipeline structuré au lieu de chat libre.

**Slogan implicite (extrait du `README.md`)** :

> Système d'agents IA pour le développement avec mémoire persistante par projet. Conçu pour remplacer ~90 % de Claude Code Opus en local + fallback API gratuit/pas cher.

---

## 2. Public cible et cas d'usage

**Profil utilisateur** :

- Développeur full-stack solo ou équipe ≤ 3 personnes.
- Codes principalement en Python/TypeScript/Rust (les linters supportés out-of-the-box : `ruff`, `eslint`, `cargo check`, `pytest`, `vitest`).
- Mac M-series (le Tauri shell est testé sur macOS, Linux/Windows viennent plus tard).
- Veut une IA qui **modifie réellement les fichiers** et **vérifie son travail**, pas juste qui suggère du texte.

**Cas d'usage concrets supportés ou prévus** :

| Cas | Mode pipeline | LLMs sollicités | Coût type |
|-----|--------------|-----------------|-----------|
| "Crée hello.py qui print 'hi'" | SIMPLE | Flash + MiniMax | $0.002 |
| "Refactor login() pour utiliser le nouveau JWT helper" | MEDIUM | Flash + MiniMax + Pro | $0.02 |
| "Implémente le multi-tenant complet sur ce backend" | COMPLEX | Flash + Pro + R1 + MiniMax | $0.08-0.15 |
| Mode Projet : "Fais-moi un MVP CRM" → CdC + sprints + 14 tickets GitHub | COMPLEX × N tickets | Tous | $1-3 par sprint |

**Hors scope explicite** :

- Pas un éditeur texte complet (pas de remplacement direct de VS Code en termes d'extensions).
- Pas un cloud SaaS — local-only (clés API stockées dans `~/.localcoder/keys.toml` à terme).
- Pas un agent "open-ended" qui tourne toute la nuit sur un repo — chaque pipeline est borné en coût + temps + nb d'itérations.

---

## 3. État actuel — qu'est-ce qui marche aujourd'hui

| Capacité | État | Plan source |
|---------|------|-------------|
| Backend FastAPI + 5 LLMs configurables | ✅ Plan 1 | Foundation |
| Routing complexité → LLM (RouterEngine) | ✅ Plan 1 | Foundation |
| Mémoire courte (RAM session) + longue (SQLite) | ✅ Plan 2 | Intelligence Layer |
| AgentLoop legacy 5 étapes (PLAN→VERIFY→EXECUTE→CHECK→CONFIRM) | ✅ Plan 2 | (sera remplacé par Pipeline en Plan 5D) |
| UI Tauri + React 19 + 4 tabs | ✅ Plan 3 | UI Tauri+React |
| Mode Projet : CdC → Sprints → 14 tickets GitHub | ✅ Plan 4 | GitHub Integration |
| Webhook GitHub `/ci-webhook` (check_run/check_suite) | ✅ Plan 4 | GitHub Integration |
| Pipeline 11 étapes — squelette + 5 stages opérationnels (0/1/3/5/7) | ✅ Plan 5A | Foundations |
| Mode SIMPLE end-to-end : prompt → fichier réellement créé | ✅ Plan 5A | Foundations |
| Tool-calling read (TOOLS_SCHEMA_READ) + write (TOOLS_SCHEMA_WRITE) | ✅ Plan 5A | Foundations |
| Cost estimator avec PRICING par LLM | ✅ Plan 5A | Foundations |
| Workspace guard (PathOutsideWorkspace) | ✅ Plan 5A | Foundations |
| Modal ESTIMATE (cost preview) | ✅ Plan 5A | Foundations |
| TraceViewer temps réel (StageRow par étape) | ✅ Plan 5A | Foundations |
| Git stash automatique avant EXECUTE + rollback sur exception | ✅ Plan 5A | Foundations |
| `Stage7Verify` étendu : pytest + vitest + cargo + lint en parallèle | ✅ Plan 5B Task 2 | VERIFY+streaming |
| Retry loop Stage5↔Stage7 (max 3 tentatives) avec feedback erreurs | ✅ Plan 5B Task 3 | VERIFY+streaming |
| `tools/run_tests.py` : wrappers pytest/vitest/cargo/lint | ✅ Plan 5B Task 1 | VERIFY+streaming |
| Streaming token-par-token (litellm `stream=True`) | ⏳ Plan 5B Task 4 | VERIFY+streaming |
| Bouton Stop fonctionnel (CancelledError propagation) | ⏳ Plan 5B Task 6 | VERIFY+streaming |
| Budget cap par pipeline ($1.00 par défaut, configurable) | ⏳ Plan 5B Task 7 | VERIFY+streaming |
| Stage 2 CHALLENGE (multi-LLM, avocat du diable) | ⏳ Plan 5C | CHALLENGE+consensus |
| Stage 4a PLAN + 4b PLAN-REVIEW (consensus 2/2) | ⏳ Plan 5C | CHALLENGE+consensus |
| Stage 6 SELF-CHECK + Stage 8 REVIEW + Stage 9 SECOND-REVIEW | ⏳ Plan 5D | self-check+review |
| Toasts (Sonner) + syntax highlight (Shiki) + command palette | ⏳ Plan 5E | UX raffinée |
| Settings UI (clés API, toggles LLMs, budget mensuel) | ⏳ Plan 5E | UX raffinée |
| CostTracker persistant + calibration estimé/réel | ⏳ Plan 5E | UX raffinée |
| Bundle Tauri (DMG/DEB/MSI) + menu bar macOS | ⏳ Plan 5F | packaging+ollama |
| Mode Ollama (privacy-first, détection localhost:11434) | ⏳ Plan 5F | packaging+ollama |
| Tag release v2.0.0 + workflow GitHub Actions | ⏳ Plan 5F | packaging+ollama |

**Compteurs tests à l'instant T** :

- Backend : **285 tests pytest verts** (tag `v2.1.0-alpha.1` à 264, +21 sur Plan 5B Tasks 1-3).
- UI : **121 tests vitest verts**, `tsc --noEmit` clean.
- 5 tests `llm_live` désactivés par défaut (lancés à la main via `scripts/smoke_llms.sh`).

---

## 4. Stack technique complète

### Backend (Python 3.12.13)

| Dépendance | Version min | Rôle |
|-----------|-------------|------|
| `fastapi` | 0.128 | Serveur HTTP/WS |
| `uvicorn[standard]` | 0.30 | ASGI runtime |
| `litellm` | 1.81 | Wrapper unifié multi-LLM (OpenAI + Gemini + DeepSeek + Mistral + MiniMax) |
| `pydantic` | 2.0 | Modèles I/O |
| `aiosqlite` | 0.20 | Mémoire longue persistante |
| `httpx` | 0.27 | Client HTTP async |
| `PyGithub` | 2.3 | Wrapper GitHub API |
| `GitPython` | 3.1 | Wrapper git local |
| `psutil` | 6.0 | Monitoring CPU/RAM |
| `tiktoken` | 0.7 | Comptage tokens (fallback `len(text)//4`) |
| `aider-chat` | 0.82 | Référence sur l'édition de code (utilisé via wrapper interne) |
| `rich` | 13.0 | CLI logs colorés |
| `pytest` + `pytest-asyncio` | 8.0 / 0.23 | Tests |

**Marker pytest custom** (`pyproject.toml`) :

- `llm_live` : tests qui appellent les vrais LLMs (clés API requises). **Désactivés par défaut** via `addopts = "-m 'not llm_live'"`. Pour les lancer : `pytest -m llm_live`.

### UI (TypeScript / React 19)

| Dépendance | Version | Rôle |
|-----------|---------|------|
| `react` / `react-dom` | 19.1 | UI |
| `vite` | 7.0 | Bundler dev |
| `vitest` | 4.1 | Tests unitaires |
| `@testing-library/react` | 16.3 | Render utils |
| `jsdom` | 29 | DOM headless pour tests |
| `zustand` | 5.0 | State management |
| `@tauri-apps/api` | 2 | Bridge Rust/JS |
| `@xterm/xterm` + addons | 5.5 | Émulation terminal |
| `tailwindcss` + `tailwindcss-animate` | 3.4 | Styling |
| `lucide-react` | 1.8 | Icônes |
| `clsx` / `class-variance-authority` / `tailwind-merge` | — | Helpers de classes |

### Shell natif (Rust + Tauri 2)

- `ui/src-tauri/Cargo.toml` : crate Tauri 2.
- `ui/src-tauri/src/main.rs` : démarre le subprocess FastAPI, attend la santé `localhost:8765/health`, puis monte le webview.

### Outils CLI requis sur la machine

- `python3.12`, `tmux` (workspace IDE optionnel), `git`, `gh` (GitHub CLI optionnel pour Mode Projet local).
- `ollama` avec `qwen2.5-coder:14b` et `qwen2.5-coder:7b` (utilisé en backup local — 100 % offline).
- `node` + `npm`/`npx` (pour `vitest` et `eslint` lancés depuis `Stage7Verify`).
- `cargo` + `rustc` (pour `cargo check` sur `ui/src-tauri/`).
- `ruff` (linter Python).

---

## 5. Architecture globale

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Tauri shell (macOS native window) — Rust crate ui/src-tauri/             │
│   ├─ Démarre le subprocess FastAPI (port 8765, localhost-only)           │
│   ├─ Health-check loop (5s timeout)                                      │
│   └─ Webview React (Vite dev :5173 / build prod inline)                  │
└──────────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ WebSocket bidirectional ws://127.0.0.1:8765/ws
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ React 19 UI (ui/src/)                                                    │
│   ├─ App.tsx : layout 4 tabs (Chat / Terminals / Routing / Monitoring)   │
│   ├─ ActivityBar : FileTree, LLMStatus, GitPanel, SprintBoard            │
│   ├─ StatusBar : session id, branch, $ accumulé, latence WS              │
│   ├─ Stores Zustand :                                                    │
│   │   • llmStore (statut + tokens + latence par LLM)                     │
│   │   • routingStore (historique 100 dernières décisions)                │
│   │   • roadmapStore (sprints/tickets actifs)                            │
│   │   • sessionStore (session courante : tokens, $, branch)              │
│   │   • pipelineStore (état pipeline en cours, stages, retry, rollback)  │
│   ├─ Pipeline UI : EstimateModal + TraceViewer + StageRow                │
│   └─ ws.ts : singleton WebSocket avec reconnect 2s + buffer 100 msg      │
└──────────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTP REST + WS push
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Backend FastAPI (backend/, port 8765, listen 127.0.0.1)                  │
│                                                                          │
│   ┌── HTTP routes (backend/main.py) ────────────────────────────────┐    │
│   │ GET  /health           : ping LLMs configurés                    │    │
│   │ POST /route            : analyse complexité prompt               │    │
│   │ POST /chat             : exécute Orchestrator.handle()           │    │
│   │ POST /ci-webhook       : reçoit GitHub check_run/check_suite     │    │
│   │ POST /project/start    : lance Mode Projet (CdC→Sprints→GH)      │    │
│   │ GET  /project/status   : roadmap + ticket actif                  │    │
│   │ POST /project/feedback : feedback routing → SQLite               │    │
│   │ GET  /llms             : liste config LLMs                       │    │
│   │ GET  /llms/health      : health-check par LLM (live, timeout 5s) │    │
│   │ POST /llms/{id}/disable: désactive un LLM dynamiquement          │    │
│   │ POST /llms/{id}/enable : réactive                                │    │
│   │ WS   /ws               : events temps réel (auth session_id)     │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│   ┌── Orchestrator (backend/orchestrator.py) ──────────────────────┐    │
│   │ • Seul point d'entrée côté backend ; les LLMs ne se parlent     │    │
│   │   JAMAIS directement (règle architecturale fondatrice).         │    │
│   │ • Délègue à RouterEngine pour le choix du LLM (legacy mode)     │    │
│   │ • Délègue à Pipeline pour le mode pipeline 11-stages            │    │
│   │ • Persiste les décisions en LongTermMemory                      │    │
│   │ • Émet les events WS via WSStreamer                             │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│   ┌── Pipeline orchestrator (backend/pipeline/orchestrator.py) ────┐    │
│   │ stages_by_mode = {                                              │    │
│   │   SIMPLE  : [Stage0, Stage1, Stage3, Stage5, Stage7],          │    │
│   │   MEDIUM  : (Plan 5C remplira),                                │    │
│   │   COMPLEX : (Plan 5C+5D rempliront),                           │    │
│   │ }                                                              │    │
│   │ run(ctx) :                                                     │    │
│   │   1. Boucle stages → Stage.run() → ctx.stage_results[name]     │    │
│   │   2. Si Stage5+ échoue : git_stash_pop + success=False         │    │
│   │   3. Si Stage7Verify all_green=False : retry Stage5→Stage7      │    │
│   │      jusqu'à 3 tentatives, sinon rollback git stash             │    │
│   │   4. Accumulation cost/tokens/duration                         │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│   ┌── Tools dispatcher (backend/tools/registry.py) ────────────────┐    │
│   │ TOOLS_SCHEMA_READ  : read_file, list_files, grep_codebase       │    │
│   │ TOOLS_SCHEMA_WRITE : edit_file, patch_file, create_file,        │    │
│   │                      delete_file (+ tous READ aussi)            │    │
│   │ execute_tool(name, args, file_lock, workspace_root)             │    │
│   │   → invoque la fonction concrète, capte ToolError + retourne   │    │
│   │     {success: bool, ...} pour réinjection LLM                   │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│   ┌── LLM dispatch (backend/llm_manager.py) ───────────────────────┐    │
│   │ LLMManager.call_with_fallback(role, messages, ...) :            │    │
│   │   1. Pick LLM principal pour ce rôle (FALLBACK_CHAINS[role][0]) │    │
│   │   2. Inject system prompt MD selon le LLM (system_minimax.md…)  │    │
│   │   3. Rate-limit par LLM (RPM dans LLMConfig)                    │    │
│   │   4. Si échec (rate-limit, timeout, 5xx) → fallback suivant     │    │
│   │   5. Retourne string content, tokens, durée                     │    │
│   │ health_check(llm_id) : ping minimal, retourne latence ms        │    │
│   └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│   ┌── Mémoire (backend/memory.py) ──────────────────────────────────┐    │
│   │ ShortTermMemory  : RAM, par session_id, actions récentes        │    │
│   │ LongTermMemory   : SQLite, 4 tables :                           │    │
│   │   • decisions          (session_id, llm, type, content, ts)     │    │
│   │   • llm_messages       (from_llm, to_llm, type, content)        │    │
│   │   • roadmap_history    (sprint, ticket, status, ts)             │    │
│   │   • routing_feedback   (prompt, llm_chosen, success, score)     │    │
│   └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ subprocess argv-list (asyncio)
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Outils système locaux                                                    │
│   • git stash push -u / pop  (rollback automatique du working dir)       │
│   • ruff check / eslint / npx vitest run / cargo check / pytest          │
│   • ollama (mode local optionnel, port 11434)                            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Les 5 LLMs orchestrés

Configurés par défaut dans `backend/main.py` (`DEFAULT_LLMS`) et tarifés dans `backend/cost_estimator.py` (`PRICING`). Chacun a un rôle principal mais peut être appelé en fallback.

### 6.1 MiniMax M2.5 — `minimax/minimax-m2.5`
- **Rôle principal** : `CODING` (LLMRole).
- **RPM** : 200.
- **Tarif** : $0.118 / 1M input, $0.99 / 1M output.
- **Pourquoi lui** : SWE-bench Verified ~80 %, prix imbattable pour la qualité de code, contexte 245 K tokens.
- **Stages** : 3 GROUND, 5 EXECUTE, 6 SELF-CHECK (à venir).
- **Fallback chain** : MiniMax → DeepSeek-Chat → Gemini Pro.
- **System prompt** : `backend/prompts/system_minimax.md`.

### 6.2 Gemini 2.5 Pro — `gemini/gemini-2.5-pro`
- **Rôle principal** : `ANALYSIS`.
- **RPM** : 60.
- **Tarif** : $1.25 / 1M input, $10.00 / 1M output.
- **Pourquoi lui** : 1 M tokens de contexte, excellent en analyse critique et review.
- **Stages** : 2 CHALLENGE (à venir), 4b PLAN-REVIEW (à venir), 8 REVIEW (à venir).
- **Fallback chain** : Gemini Pro → MiniMax.
- **System prompt** : `backend/prompts/system_gemini_pro.md`.

### 6.3 Gemini 2.5 Flash — `gemini/gemini-2.5-flash`
- **Rôle principal** : `ROUTING`.
- **RPM** : 1000.
- **Tarif** : $0.075 / 1M input, $0.30 / 1M output.
- **Pourquoi lui** : ultra-rapide (<1s), idéal pour classification JSON.
- **Stages** : 0 ESTIMATE, 1 INTAKE.
- **Fallback chain** : Gemini Flash → MiniMax.
- **System prompt** : `backend/prompts/system_gemini_flash.md`.

### 6.4 DeepSeek R1 — `deepseek/deepseek-r1`
- **Rôle principal** : `ARCHITECTURE`.
- **RPM** : 50.
- **Tarif** : $0.55 / 1M input, $2.19 / 1M output.
- **Pourquoi lui** : reasoning chain-of-thought puissant, idéal pour le PLAN structurel.
- **Stages** : 4a PLAN (à venir), 9 SECOND-REVIEW (à venir), CdC en Mode Projet.
- **Fallback chain** : DeepSeek R1 → Gemini Pro.
- **System prompt** : `backend/prompts/system_deepseek_r1.md`.

### 6.5 Codestral 2 — `mistral/codestral-2`
- **Rôle principal** : `TESTING`.
- **RPM** : 100.
- **Tarif** : $0.30 / 1M input, $0.90 / 1M output.
- **Pourquoi lui** : spécialisé code completion + génération de tests.
- **Stages** : utilisé pour générer/réparer des tests dans Mode Projet (Plan 4) et en Plan 5D potentiel.
- **Fallback chain** : Codestral → MiniMax.
- **System prompt** : `backend/prompts/system_codestral.md`.

### 6.6 (Bonus) DeepSeek Chat — `deepseek/deepseek-chat`
Modèle de fallback non-reasoning. Tarif : $0.27 / 1M input, $1.10 / 1M output. Utilisé comme fallback du rôle CODING.

### 6.7 Health-check unifié

`GET /llms/health` retourne pour chaque LLM `{ llm, healthy, latency_ms, error }`. Implémentation : `LLMManager.health_check(llm_id)` lance un `acompletion(messages=[{"role":"user","content":"ping"}], max_tokens=1, timeout=5)` et chronomètre via `perf_counter`. Tests : `tests/backend/test_llm_manager.py` (mock) + `scripts/smoke_llms.sh` (live).

---

## 7. Le pipeline rigoureux 11 étapes

Spec complète : `docs/superpowers/specs/2026-04-20-pipeline-rigoureux.md`. Schéma chronologique :

```
┌─────────────────────────────────────────────────────────────────┐
│ USER PROMPT                                                     │
│      │                                                          │
│      ▼                                                          │
│ 0  ESTIMATE      Flash       classification + cost preview      │
│      │           (~$0.0002)                                     │
│      ▼                                                          │
│ ┌────────────────┐                                              │
│ │ Modal UI       │ user voit "$0.05, 4 stages, 2 min" → confirme│
│ └────────────────┘                                              │
│      │                                                          │
│      ▼                                                          │
│ 1  INTAKE        Flash       valide non-ambiguïté + extrait     │
│      │           (~$0.0002) target_files_hint, action_verbs     │
│      │           ↓ raise ClarificationNeeded si ambigu          │
│      ▼                                                          │
│ 2  CHALLENGE     Pro         [complex] avocat du diable :       │
│      │           (~$0.005)   "as-tu pensé à X ? as-tu vérifié Y?"│
│      ▼                                                          │
│ 3  GROUND        MiniMax     tool-calling read-only :           │
│      │           (~$0.001)   read_file, grep_codebase, list…    │
│      │                       → GroundedContext.summary           │
│      ▼                                                          │
│ 4a PLAN          R1          [medium/complex] decompose         │
│      │           (~$0.005)   en sous-tâches + tests à lancer    │
│      ▼                                                          │
│ 4b PLAN-REVIEW   Pro         [complex] consensus 2/2 :          │
│      │           (~$0.005)   Pro doit accepter le plan de R1    │
│      ▼                                                          │
│ ┌────────────────┐                                              │
│ │ git stash push │ état working dir capturé pour rollback       │
│ └────────────────┘                                              │
│      │                                                          │
│      ▼                                                          │
│ 5  EXECUTE       MiniMax     tool-calling write :               │
│      │           (~$0.005)   create_file / edit_file /          │
│      │                       patch_file / delete_file           │
│      │                       → ExecuteResult.files_modified      │
│      ▼                                                          │
│ 6  SELF-CHECK    MiniMax     [medium/complex] re-lit son diff   │
│      │           (~$0.003)   et signale les erreurs internes    │
│      ▼                                                          │
│ 7  VERIFY        ∅           pytest + vitest + cargo + lint     │
│      │           ($0)        en parallèle (asyncio.gather)      │
│      │                                                          │
│      ↓                                                          │
│ ┌────────────────────────────┐                                  │
│ │ all_green ?                │                                  │
│ │                            │                                  │
│ │ NON → retry Stage5 avec    │ jusqu'à 3 tentatives             │
│ │  retry_context (errors)    │ sinon git stash pop + abort      │
│ │                            │                                  │
│ │ OUI → continue             │                                  │
│ └────────────────────────────┘                                  │
│      │                                                          │
│      ▼                                                          │
│ 8  REVIEW        Pro         [medium/complex] review du diff :  │
│      │           (~$0.01)    feedback critique sur la qualité   │
│      ▼                                                          │
│ 9  SECOND-REVIEW R1          [complex si Pro hesite] avis indé   │
│      │           (~$0.005)                                      │
│      ▼                                                          │
│ ┌────────────────┐                                              │
│ │ Consensus 2/2 ?│ Pro + R1 d'accord pour merge ?               │
│ │  NON → modal   │ user décide                                  │
│ │  OUI → continue│                                              │
│ └────────────────┘                                              │
│      │                                                          │
│      ▼                                                          │
│ 10 COMMIT + CI   git         commit, push, attend webhook CI     │
│                  (+ ws ping) /ci-webhook → merge ou rollback     │
└─────────────────────────────────────────────────────────────────┘
```

### 7.1 Détail par étape

| # | Nom | LLM | Output principal | Garanties formelles |
|---|-----|-----|------------------|---------------------|
| 0 | ESTIMATE | Flash | `EstimateResult` (classification, files_hint, cost_breakdown) | Aucun side-effect, retourne JSON strict, fallback `len//4` si tiktoken indispo |
| 1 | INTAKE | Flash | `IntakeResult` ou `ClarificationNeeded` | `needs_clarification=true` → exception → pipeline stop avant coût supplémentaire |
| 2 | CHALLENGE | Pro | `ChallengeResult.questions[]` | (Plan 5C) Si ≥1 question critique non répondue → retour à user |
| 3 | GROUND | MiniMax | `GroundedContext(files_read, greps_performed, summary)` | Read-only — aucune modification possible (TOOLS_SCHEMA_READ uniquement) |
| 4a | PLAN | R1 | `Plan(steps[], tests_to_run[], files_to_touch[])` | (Plan 5C) JSON strict, validé par schéma |
| 4b | PLAN-REVIEW | Pro | `PlanReview(approved: bool, concerns[])` | (Plan 5C) Consensus 2/2 obligatoire en mode COMPLEX |
| 5 | EXECUTE | MiniMax | `ExecuteResult(files_modified[], stash_ref, summary)` | Git stash systématique avant action ; sur exception, `git_stash_pop` automatique |
| 6 | SELF-CHECK | MiniMax | `SelfCheckResult(internal_issues[])` | (Plan 5D) Si issues critiques → retour à Stage5 avec feedback |
| 7 | VERIFY | ∅ | `VerifyResult(lint_errors[], test_errors[], all_green, attempts_used, runners_summary)` | Mécanique (pas de LLM) ; 3 retries max ; après 3 → rollback |
| 8 | REVIEW | Pro | `ReviewResult(approved: bool, blockers[])` | (Plan 5D) Pro lit le diff complet (1M ctx) |
| 9 | SECOND-REVIEW | R1 | `SecondReview(approved: bool, reasons)` | (Plan 5D) Avis indépendant ; si désaccord avec Pro → modal user |
| 10 | COMMIT | ∅ | `CommitResult(sha, branch, ci_status)` | Mode Projet : push branch, attend webhook `check_run` ; si CI rouge → rollback |

### 7.2 Implémentation actuelle (mode SIMPLE)

Le `Pipeline` (backend/pipeline/orchestrator.py) instancie et orchestre uniquement les 5 stages opérationnels :

```python
stages_by_mode = {
    PipelineMode.SIMPLE: [
        Stage0Estimate,    # backend/pipeline/stage_0_estimate.py
        Stage1Intake,      # backend/pipeline/stage_1_intake.py
        Stage3Ground,      # backend/pipeline/stage_3_ground.py
        Stage5Execute,     # backend/pipeline/stage_5_execute.py
        Stage7Verify,      # backend/pipeline/stage_7_verify.py
    ],
    PipelineMode.MEDIUM: [],   # Plan 5C remplira
    PipelineMode.COMPLEX: [],  # Plan 5C+5D rempliront
}
```

Chaque stage hérite de `Stage` (`backend/pipeline/base.py`), implémente `_execute(ctx)`. La méthode publique `run(ctx)` :
1. Émet l'event WS `stage_start` (UI affiche spinner).
2. Mesure la durée via `perf_counter`.
3. Appelle `_execute` sous try/except.
4. Construit un `StageResult` (success/error, tokens_in/out, cost_usd).
5. **Persiste dans `ctx.stage_results[self.name]`** (corrigé en Plan 5A Task 14, sans ça les stages avals ne voyaient rien).
6. Accumule `ctx.total_cost_usd` / `tokens_in/out`.
7. Émet `stage_complete`.

---

## 8. Les 3 modes de pipeline

Définis dans `backend/pipeline/types.py` (`PipelineMode` enum) et dans `backend/cost_estimator.py` (`STAGE_TOKEN_ESTIMATES`).

| Mode | Score complexité | Stages actifs | LLM calls | Coût type | Latence type |
|------|------------------|--------------|-----------|-----------|--------------|
| **SIMPLE** | ≤ 4 | 0, 1, 3, 5, 7 | 3-4 | $0.001 - $0.005 | 5-15 s |
| **MEDIUM** | 5-7 | 0, 1, 3, 5, 6, 7, 8 | 5-6 | $0.01 - $0.03 | 30-60 s |
| **COMPLEX** | ≥ 8 | 0, 1, 2, 3, 4a, 4b, 5, 6, 7, 8, (9) | 9-10 | $0.05 - $0.15 | 2-8 min |

**Comment le mode est déterminé** :

1. Stage0 ESTIMATE classifie via Flash : retourne `classification: "simple" | "medium" | "complex"` + `reason`.
2. UI affiche le modal ESTIMATE avec coût + durée.
3. User confirme (`Lancer`), ou force un mode moins cher (`Forcer simple`), ou annule.
4. Pipeline.run dispatche selon `ctx.mode`.

**Calcul du coût** :

`backend/cost_estimator.py:estimate_pipeline_cost(prompt_text, mode, files_hint)` :

```python
total = 0
for stage in STAGE_TOKEN_ESTIMATES[mode]:
    llm_id = STAGE_LLM_MAP[stage]
    pricing = PRICING[llm_id]
    tokens_in = STAGE_TOKEN_ESTIMATES[mode][stage]["in"]
    tokens_out = STAGE_TOKEN_ESTIMATES[mode][stage]["out"]
    total += (tokens_in * pricing["in"] + tokens_out * pricing["out"]) / 1_000_000
return {"stages": [...], "total_cost_usd": total, "total_duration_sec": ...}
```

Les heuristiques de tokens proviennent de tests live et seront affinées en Plan 5E (calibration via CostTracker).

---

## 9. Fonctionnalités côté backend

Tour complet de `backend/`, fichier par fichier, par ordre d'importance.

### 9.1 `main.py` — point d'entrée FastAPI

- Crée l'app, configure CORS (`localhost:5173` autorisé pour dev), monte les routes, configure le lifespan (boot Orchestrator + Pipeline).
- Définit `DEFAULT_LLMS` : 5 `LLMConfig` Pydantic.
- Endpoint clé `GET /llms/health` : `asyncio.gather` des `health_check` par LLM.
- Endpoint `POST /chat` : reçoit `OrchestratorRequest`, appelle `Orchestrator.handle()`, retourne `OrchestratorResponse`.
- WebSocket `/ws` : authentification par `session_id` au connect, dispatch des events via `WSStreamer`.

### 9.2 `models.py` — Pydantic communs

- Enums : `LLMRole` (CODING, ARCHITECTURE, ANALYSIS, TESTING, ROUTING), `MessageType`, `TaskStatus`.
- Models : `LLMConfig`, `LLMMessage`, `RoutingDecision`, `AgentAction`, `WSEvent`, `PipelineMode` (importé de pipeline.types).

### 9.3 `llm_manager.py` — orchestrateur LLMs

- `LLMManager` :
  - `__init__(self, configs: list[LLMConfig])` : stocke les configs, instancie un `RateLimiter` par LLM.
  - `call_with_fallback(role, messages, **kwargs) -> str` : tente le LLM principal ; si rate-limit, timeout, ou 5xx → suivant dans `FALLBACK_CHAINS[role]`.
  - `health_check(llm_id) -> dict` : ping minimal, retourne `{healthy, latency_ms, error}`.
  - `disable(llm_id)` / `enable(llm_id)` : flip un flag dans la config.
- `FALLBACK_CHAINS` (dict role → list[llm_id]).
- Injection système : `_load_system_prompt(llm_id)` lit `backend/prompts/system_<llm>.md` et l'injecte comme premier message user.

### 9.4 `router_engine.py` — routing legacy (avant pipeline)

- `RouterEngine.route(prompt, file_count, mention) -> RoutingDecision` :
  - Calcule un score de complexité (1-10) : longueur, mots-clés (`refactor`, `architecture`, `multi-tenant`…), nombre de fichiers attendus.
  - Détecte une mention explicite (`@minimax`, `@gemini`, `@deepseek`) via `MENTION_MAP`.
  - Détecte le mode projet via `PROJECT_KEYWORDS` (`MVP`, `sprint`, `roadmap`).
  - Retourne `RoutingDecision(prompt, score, llm, role, mode, reason)`.
- Persiste les décisions dans `routing_feedback` (SQLite) pour calibration.

### 9.5 `orchestrator.py` — chef d'orchestre

- `Orchestrator.handle(request: OrchestratorRequest) -> OrchestratorResponse` :
  1. Routing : `await router.route(prompt)`.
  2. Émet event WS `routing_decision`.
  3. Construit le contexte : `build_context_for(llm, task, roadmap)`.
  4. Soumet à `LLMTaskQueue` (1 tâche à la fois par LLM).
  5. Persiste en `LongTermMemory`.
  6. Met à jour `ShortTermMemory` (session).
  7. Retourne réponse à l'UI.
- Mode Projet : `run_project_mode(description, github_token, repo_name)` lance `ProjectMode.generate_cdc()` + `generate_sprints()` + `create_github_structure()`.
- **Note importante** : pour l'instant `Orchestrator.handle()` utilise encore `AgentLoop` (legacy). Le branchement vers `Pipeline` se fera au Plan 5D Step 11.3.

### 9.6 `agent_loop.py` — boucle 5 étapes legacy

- `AgentLoop(llm, file_lock, ws, decision, context).run(prompt) -> AgentResult` :
  - Étape 1 PLAN : LLM produit un plan textuel.
  - Étape 2 VERIFY : LLM relit son plan.
  - Étape 3 EXECUTE : LLM produit du texte (PAS de modif fichier — bug à corriger en Plan 5D).
  - Étape 4 CHECK : LLM auto-vérifie.
  - Étape 5 CONFIRM : LLM signe la réponse.
- Retry 3x max sur erreurs (timeout, rate-limit).
- **Limitation** : ne modifie PAS les fichiers. C'est précisément ce que le pipeline 5A+ corrige.

### 9.7 `memory.py` — mémoire courte + longue

- `ShortTermMemory` : RAM, stocke par `user_id` les actions récentes (max ~100), un `session_id` régénéré à chaque démarrage.
- `LongTermMemory(db_path)` : SQLite avec 4 tables :
  - `decisions(id, session_id, llm, dtype, content, rationale, ts)`.
  - `llm_messages(id, session_id, from_llm, to_llm, type, content, replied, ts)`.
  - `roadmap_history(id, sprint_id, ticket_id, status, ts)`.
  - `routing_feedback(id, prompt, llm_chosen, success, score, notes, ts)`.
- Méthodes : `save_decision`, `save_message`, `record_routing_feedback`, `get_recent_decisions(session_id, limit=10)`.

### 9.8 `roadmap.py` — modèle Mode Projet

- `ProjectRoadmap(project_name, cdc, sprints[])`.
- `Sprint(id, name, tickets[], start_date, end_date)`.
- `Task(id, title, description, status, sub_tasks[], decisions[])`.
- `SubTask(id, title, status)`.
- Persistance JSON dans `~/.localcoder/projects/<slug>/roadmap.json`.

### 9.9 `context_builder.py` — contextes ciblés

- `build_context_for(llm, task, roadmap=None) -> str` :
  - Pour CODING : derniers 10 fichiers édités + 1 fichier proche du sujet.
  - Pour ARCHITECTURE : roadmap résumée + sprint actif.
  - Pour ANALYSIS : diff récent (`git diff HEAD~5..HEAD`) + commits.
  - Cible : ~2-3K tokens (compté via `count_tokens(text, model)` qui utilise `tiktoken` ou fallback).
- `count_tokens(text, model="gpt-4")` : cache `_ENC_CACHE` pour éviter de recharger l'encoder.

### 9.10 `cost_estimator.py` — calculs de coût

- `PRICING : dict[llm_id, {"in": float, "out": float}]` — tarifs par 1M tokens.
- `STAGE_LLM_MAP : dict[stage_name, llm_id]` — quel LLM pour quelle étape.
- `STAGE_TOKEN_ESTIMATES : dict[mode, dict[stage_name, {"in": int, "out": int}]]` — heuristiques calibrées.
- `estimate_cost(llm_id, tokens_in, tokens_out) -> float` : conversion simple.
- `estimate_pipeline_cost(prompt_text, mode, files_hint) -> dict` : itère sur `STAGE_TOKEN_ESTIMATES[mode]`, retourne `{stages: list[StageEstimate], total_cost_usd, total_duration_sec, classification}`.

### 9.11 `file_lock.py` — verrous fichiers asyncio

- `FileLock` : un dict `path -> asyncio.Lock` partagé.
- `acquire(path, llm_id)` / `release(path, llm_id)`.
- Évite les écritures simultanées par 2 LLMs sur le même fichier (en mode multi-agent).

### 9.12 `task_queue.py` — file d'attente par LLM

- `LLMTaskQueue` : un dict `llm_id -> asyncio.Queue` + worker async qui pop et traite.
- `submit(llm, coro)` : enqueue, retourne le résultat quand traité.
- Évite que 2 calls simultanés vers le même LLM ne dépassent le rate-limit.

### 9.13 `ws_streamer.py` — broadcast events WebSocket

- `WSStreamer` : maintient un dict `session_id -> WebSocket`.
- `broadcast(event: WSEvent)` : envoie à toutes les connexions de la session.
- `unicast(session_id, event)` : envoie à une seule.
- Helpers spécialisés : `emit_routing(decision)`, `emit_step(step, llm)`, `emit_chat_token(token)` (Plan 5B Task 5 à venir).

### 9.14 `git_service.py` — wrapper GitPython

- `GitService(repo_path)` :
  - `create_branch(name)`, `checkout(branch)`, `commit(message, files)`, `push(branch)`.
  - `diff(branch_a, branch_b) -> str`.
  - `stash_save(label)` / `stash_pop(ref)`.
  - `get_recent_commits(n=10)`.

### 9.15 `github_service.py` — wrapper PyGithub

- `GitHubService(token, repo_name)` :
  - `create_issue(title, body, milestone)`.
  - `create_pull_request(branch, title, body)`.
  - `get_check_runs(sha)` / `get_check_suite_status(sha)`.
  - `add_to_project_board(item, column)`.
  - `merge_pr(pr_number, method="squash")`.

### 9.16 `project_mode.py` — Mode Projet orchestration

- `ProjectMode(llm_manager, ws, github_service, git_service)` :
  - `generate_cdc(description) -> CdC` : appelle DeepSeek R1 avec `prompts/cdc_generation.md`, parse JSON.
  - `generate_sprints(cdc) -> list[Sprint]` : appelle Pro pour découper en 3-5 sprints.
  - `create_github_structure(cdc, sprints) -> ProjectRoadmap` : crée milestones, issues, project board.
  - `execute_ticket(task)` : route vers le bon LLM, génère le code, ouvre PR.

### 9.17 `pipeline/` — package complet

- `base.py:Stage` : ABC, template method `run(ctx)`.
- `types.py` : `PipelineMode` (SIMPLE/MEDIUM/COMPLEX), `PipelineContext` (prompt, workspace_root, session_id, mode, mention, stage_results, total_cost_usd, retry_context), `StageResult`, `PipelineResult`.
- `orchestrator.py:Pipeline` : dispatch + retry loop (Plan 5B Task 3).
- `stage_0_estimate.py` : Flash classification → JSON strict.
- `stage_1_intake.py` : Flash validation → `IntakeResult` ou `ClarificationNeeded`.
- `stage_3_ground.py` : MiniMax tool-calling read-only, max 20 itérations, retourne `GroundedContext`.
- `stage_5_execute.py` : MiniMax tool-calling write, git stash + rollback, max 20 itérations.
- `stage_7_verify.py` : pytest+vitest+cargo+lint en parallèle via `asyncio.gather`, `VerifyResult`.

---

## 10. Tools — les actions que les LLMs peuvent appeler

Définis dans `backend/tools/`. Chaque tool retourne un `dict` standardisé `{success: bool, ...}`. En cas d'erreur (path hors workspace, fichier absent, lock détenu), `success=False` et le LLM voit l'erreur dans le tool_call_result, ce qui lui permet de corriger sans crash.

### 10.1 Tools READ-ONLY (TOOLS_SCHEMA_READ)

Disponibles à Stage3 (GROUND) et tous les stages avals.

| Tool | Args | Retour | Usage |
|------|------|--------|-------|
| `read_file(path, max_bytes?)` | `path: str, max_bytes: int = 100000` | `{success, content, bytes_read, truncated}` | Lit un fichier UTF-8, refuse si > max_bytes |
| `list_files(path, recursive?)` | `path: str, recursive: bool = False` | `{success, files: list[str]}` | Liste un dossier (gitignore non pris en compte) |
| `grep_codebase(pattern, path?, ignore_case?, max_matches?)` | `pattern: str (regex), path: str = ".", ignore_case: bool = False, max_matches: int = 50` | `{success, matches: list[{file, line, text}]}` | Cherche dans tout le workspace ; exclut `node_modules`, `.git`, `__pycache__`, `dist`, `target`, `venv` |

### 10.2 Tools WRITE (TOOLS_SCHEMA_WRITE)

Disponibles à Stage5 (EXECUTE) uniquement. **Tous protégés par `FileLock`** pour éviter writes concurrents.

| Tool | Args | Retour | Comportement |
|------|------|--------|--------------|
| `edit_file(path, content)` | `path: str, content: str (full file)` | `{success, bytes_written}` | Réécrit intégralement le fichier ; échoue si lock détenu |
| `patch_file(path, old_str, new_str)` | `path, old_str, new_str` | `{success, replacements: int}` | Remplace UNE occurrence unique de `old_str` par `new_str` ; échoue si `old_str` non unique |
| `create_file(path, content)` | `path, content` | `{success, bytes_written}` | Crée le fichier ; échoue si existe déjà ; crée parents |
| `delete_file(path)` | `path` | `{success}` | Supprime ; échoue si lock détenu ou inexistant |

### 10.3 Garantie sécurité workspace

`backend/tools/exceptions.py:PathOutsideWorkspace` est levée par `_resolve(path, workspace_root)` si :
- Le path résolu n'est pas un descendant de `workspace_root`.
- Le path contient `..` qui dépasse la racine.
- Le path commence par `/` (absolu) en dehors du workspace.

L'exception est capturée par `execute_tool()` et retournée comme `{success: False, error: "path outside workspace: ..."}`. Le LLM corrige son tool_call.

### 10.4 Tools tests / lint (Plan 5B Task 1)

`backend/tools/run_tests.py` (utilisé par Stage7Verify, pas exposé au LLM) :

| Helper | Signature | Retour |
|--------|-----------|--------|
| `run_pytest(target, workspace_root, timeout=60)` | str/Path/int | `{exit_code, passed, failed, stdout_tail (≤3000 chars), duration_s, error?}` |
| `run_vitest(target, workspace_root, timeout=60)` | idem | idem |
| `run_cargo_check(workspace_root, timeout=120)` | Path/int | idem |
| `run_lint(path, workspace_root, timeout=30)` | Dispatch ruff/eslint selon extension | idem |

### 10.5 Registry (`backend/tools/registry.py`)

- `TOOLS_SCHEMA_READ` : list[dict] au format OpenAI/Anthropic tools.
- `TOOLS_SCHEMA_WRITE` : superset (READ + WRITE).
- `execute_tool(name, args, file_lock, workspace_root) -> dict` : dispatcher async.
- Tests : `tests/backend/test_tools_registry.py` (10 tests).

---

## 11. UI — composants, stores, flows

### 11.1 Layout général (`ui/src/App.tsx`)

```
┌─────────────────────────────────────────────────────────────┐
│ ActivityBar (gauche, 240 px)            │ Tab content       │
│  • FileTree                             │  ┌──────────────┐ │
│  • LLMStatus (statut + tokens/min/lat)  │  │ Tabs header  │ │
│  • GitPanel (branch, dirty files)       │  │ Chat / Term  │ │
│  • SprintBoard (Mode Projet)            │  │ Routing/Mon  │ │
│                                         │  └──────────────┘ │
│                                         │  Tab body         │
├─────────────────────────────────────────────────────────────┤
│ StatusBar (bas) : session_id, $ accumulé, ws status, …      │
└─────────────────────────────────────────────────────────────┘
```

### 11.2 Tabs

#### `ChatTab`
- Input multi-line (`ChatInput.tsx`), Enter pour envoyer.
- Liste de bulles (`MessageBubble.tsx`) : user à droite, assistant à gauche avec badge LLM coloré + tokens + durée.
- Plan 5B Task 5 ajoutera le streaming token-par-token.

#### `TerminalsTab`
- Émulateur xterm.js (`@xterm/xterm`) avec onglets multiples.
- Chaque terminal connecté à un PTY backend (Tauri command).

#### `RoutingTab`
- `TraceViewer` (Plan 5A Task 13) en haut : pipeline en cours, StageRow par étape, footer Stop ou résumé final.
- `RoutingLive` : décision de routing actuelle.
- `RoutingHistory` : 100 dernières décisions, filtrables par LLM.

#### `MonitoringTab`
- CPU/RAM (lecture `/proc/cpuinfo` via `psutil`).
- Tokens/min global, latence WS, fallback chains visuelles.

### 11.3 Stores Zustand

| Store | Fichier | Keys principales |
|-------|---------|------------------|
| `llmStore` | `ui/src/stores/llmStore.ts` | `llms[] (id, name, role, healthy, tokens_per_min, latency_ms, enabled)`, actions : `setStatus`, `updateTokens`, `updateLatency` |
| `routingStore` | `routingStore.ts` | `history: RoutingEntry[]` (cap 100), `live: LiveRouting` |
| `roadmapStore` | `roadmapStore.ts` | `roadmap: ProjectRoadmap | null`, `activeSprint`, `activeTicket` |
| `sessionStore` | `sessionStore.ts` | `sessionId`, `tokensConsumed`, `costAccumulated`, `branch` |
| `pipelineStore` | `pipelineStore.ts` | `estimate: EstimateResult | null`, `isAwaitingConfirmation: bool`, `currentStageName: string | null`, `stages: StageProgress[]`, `totalCostUSD: number`, `finalResult: PipelineResultPayload | null` ; actions : `onEstimateReceived`, `confirm(mode?)`, `cancel()`, `onStageStart`, `onStageComplete`, `onPipelineComplete`, `onPipelineRollback`, `reset()` ; helper `connectPipelineStore()` qui pose les listeners WS |

### 11.4 Composants Pipeline (Plan 5A Tasks 12-13)

#### `EstimateModal` (`ui/src/components/Pipeline/EstimateModal.tsx`)

- Overlay `fixed inset-0 bg-black/50 z-50`, `role="dialog"`, `aria-modal`.
- Header : classification (`SIMPLE` en uppercase) + `reason`.
- Tableau : nom étape, LLM, tokens in/out, coût USD, durée sec.
- Footer 3 boutons :
  - **Annuler** : `cancel()` → `ws.send("pipeline_cancelled", {estimate_id})` + reset store.
  - **Forcer simple** : `confirm("simple")` → `ws.send("pipeline_confirmed", {estimate_id, mode: "simple"})`.
  - **Lancer ($X.XXXX)** : `confirm()` → `ws.send("pipeline_confirmed", {estimate_id, mode: classification})`.
- Tests : `ui/src/__tests__/EstimateModal.test.tsx` (5 tests).

#### `StageRow` (`ui/src/components/Pipeline/StageRow.tsx`)

- Une ligne par étape : index + icône statut (sablier/spinner/check/croix) + nom + badge LLM + durée + coût.
- Si `status="failed"` et `error` présent : bouton **Plus/Moins** déploie l'erreur en `<pre>`.
- Couleurs : pending=zinc-400, running=blue-500, done=green-600, failed=red-600.
- Tests : `StageRow.test.tsx` (4 tests).

#### `TraceViewer` (`ui/src/components/Pipeline/TraceViewer.tsx`)

- Lit le store `pipelineStore`. Caché tant que `isAwaitingConfirmation=true` (le modal s'occupe).
- Header : "Pipeline {classification}" + `reason` + compteur "X/Y étapes" + coût total cumulé.
- Body : liste de `StageRow`.
- Footer dynamique :
  - Pendant l'exécution : bouton **Stop** (Plan 5B Task 6 le câblera côté backend).
  - À la fin : message succès vert avec liste fichiers ou message échec rouge avec `rollback_performed` + erreur.
- Tests : `TraceViewer.test.tsx` (7 tests).

### 11.5 WebSocket client (`ui/src/ws.ts`)

- Singleton `WSClient` exporté `ws`.
- URL : `ws://127.0.0.1:8765/ws` (localhost only).
- Reconnexion auto 2 s sur close.
- Buffer borné `pendingMessages` (max 100, drop-head).
- API : `ws.on(type, handler) -> cleanup`, `ws.send(type, data)`.
- Émet en local les events `health`, `disconnect`, `error` pour intégration UI.

### 11.6 Theming (`ui/src/lib/llmTheme.ts`)

- Map `llm_id -> {color, icon}` :
  - MiniMax : violet, ⚡
  - Gemini Pro : bleu, 🌌
  - Gemini Flash : jaune, ⚡
  - DeepSeek R1 : vert, 🧠
  - Codestral : orange, 🔧

---

## 12. Persistance — SQLite, fichiers, git stash

### 12.1 Base SQLite (`localcoder.db` à la racine)

4 tables (cf. §9.7) gérées par `aiosqlite`. Schéma initialisé au boot (`LongTermMemory.__init__` lance `CREATE TABLE IF NOT EXISTS`).

### 12.2 Fichiers locaux

- `~/.localcoder/projects/<slug>/roadmap.json` : roadmap Mode Projet sérialisée.
- `~/.localcoder/keys.toml` (Plan 5E) : clés API stockées (chiffrées par OS keychain idéalement).
- `~/.localcoder/cache/` : cache LLM responses pour replays (Plan 5E).

### 12.3 Git stash automatique (Plan 5A Task 10)

- Avant Stage5 EXECUTE : `git stash push -u -m "pipeline_pre_execute_<session_id>"`.
- Stash ref retourné dans `ExecuteResult.stash_ref` (vide si rien à stash).
- Sur exception dans Stage5 : `git_stash_pop(stash_ref)` automatique avant re-raise.
- Sur Stage7Verify rouge après 3 retries : `git_stash_pop(stash_ref)` + `PipelineResult(success=False, rollback_performed=True)`.
- Sécurité : sous-processus en mode argv-list (pas de shell), pas d'interpolation utilisateur dans la commande.

---

## 13. Mode Projet — du CdC à la PR fusionnée

Implémenté en Plan 4. Flow :

1. **User** : `POST /project/start` avec `{description, github_token, repo_name}`.
2. **DeepSeek R1** génère le **Cahier des Charges (CdC)** structuré JSON :
   - `project_name`, `description`, `tech_stack`, `features[]`, `non_functional[]`, `deliverables[]`.
3. **Gemini Pro** découpe en **Sprints** (3-5 sprints, ~10-15 tickets/sprint) :
   - Chaque sprint a un thème (`auth`, `payments`, `frontend MVP`…).
   - Chaque ticket a `title`, `description`, `acceptance_criteria[]`, `estimated_effort`.
4. **GitHub Service** crée la structure :
   - 1 milestone par sprint.
   - 1 issue par ticket, taggée `sprint-N`.
   - 1 project board avec colonnes `Backlog / In Progress / Review / Done`.
5. **Per-ticket execution** :
   - `ProjectMode.execute_ticket(task)` route vers le LLM adéquat.
   - Branche dédiée `feature/<ticket-slug>`.
   - Code généré via Pipeline (à terme — pour l'instant via AgentLoop legacy).
   - PR ouverte vers `main`, label `auto-merge` si CI verte.
6. **CI webhook** :
   - GitHub envoie `check_suite.completed` à `POST /ci-webhook`.
   - Backend vérifie statut, log dans `routing_feedback`.
   - Si ✅ : `merge_pr()` automatique.
   - Si ❌ : retry du ticket avec feedback CI dans le prompt.

**État aujourd'hui** : Mode Projet utilise toujours l'AgentLoop legacy (qui ne modifie PAS les fichiers — bug à corriger). Plan 5D Step 11.3 le branchera sur Pipeline.

---

## 14. Tests — 285 pytest + 121 vitest verts

### 14.1 Backend (`tests/backend/`)

37 fichiers `test_*.py`. Markers :

- Sans marker : tests rapides, mocks intégraux. **Lancés par défaut**.
- `@pytest.mark.llm_live` : tests qui appellent les vrais LLMs. **Skipped par défaut** (`addopts = "-m 'not llm_live'"` dans `pyproject.toml`). Lancés via `pytest -m llm_live` ou `scripts/smoke_llms.sh`.

Catégories :
- **Foundation** (Plan 1) : `test_llm_manager.py`, `test_models.py`, `test_router_engine.py`, `test_main.py`, `test_file_lock.py`, `test_task_queue.py`, `test_ws_streamer.py`.
- **Intelligence** (Plan 2) : `test_memory.py`, `test_roadmap.py`, `test_context_builder.py`, `test_agent_loop.py`, `test_orchestrator.py`.
- **GitHub Mode Projet** (Plan 4) : `test_git_service.py`, `test_github_service.py`, `test_project_mode.py`, `test_project_slug.py`, `test_workspace.py`.
- **Pipeline foundations** (Plan 5A) : `test_cost_estimator.py`, `test_tools_file_ops.py`, `test_tools_search.py`, `test_tools_registry.py`, `test_pipeline_base.py`, `test_pipeline_orchestrator.py`, `test_pipeline_e2e_simple.py`, `test_stage_0_estimate.py`, `test_stage_1_intake.py`, `test_stage_3_ground.py`, `test_stage_5_execute.py`, `test_stage_7_verify.py`.
- **Pipeline VERIFY+retry** (Plan 5B) : `test_tools_run_tests.py`, `test_stage_7_verify_full.py`, `test_stage_5_retry.py`.

### 14.2 UI (`ui/src/__tests__/`)

21 fichiers `*.test.tsx` ou `*.test.ts`. Catégories :
- Composants : `App.test.tsx`, `ActivityBar.test.tsx`, `StatusBar.test.tsx`, `ChatInput.test.tsx`, `ChatTab.test.tsx`, `MessageBubble.test.tsx`, `LLMStatus.test.tsx`, `GitPanel.test.tsx`, `SprintBoard.test.tsx`, `TerminalsTab.test.tsx`, `RoutingHistory.test.tsx`, `RoutingLive.test.tsx`, `MonitoringTab.test.tsx`.
- Pipeline UI : `EstimateModal.test.tsx`, `StageRow.test.tsx`, `TraceViewer.test.tsx`.
- Stores : `llmStore.test.ts`, `routingStore.test.ts`, `roadmapStore.test.ts`, `sessionStore.test.ts`.
- WS : `ws.test.ts`.

### 14.3 Fixtures (`tests/fixtures/`)

- `scripted_llm.py` : `ScriptedLLM(stage_responses)` — drop-in pour `litellm.acompletion`. Détecte le stage via regex `"# Étape N — XXX"` dans le system prompt et retourne la prochaine réponse scriptée. Helpers : `ScriptedLLM.text(content)`, `ScriptedLLM.tool_call(id, name, args_json)`. Trace `calls_made`. Permet de tester E2E un pipeline sans toucher au réseau.

### 14.4 Lancer les tests

```bash
# Backend (rapide, ~6s)
source venv/bin/activate
python -m pytest tests/backend/ --tb=short

# Backend live (lent, requiert clés API)
python -m pytest -m llm_live -v
# ou
./scripts/smoke_llms.sh

# UI (~3s)
cd ui && npx vitest run

# UI typecheck
cd ui && npx tsc --noEmit
```

---

## 15. Coûts réels et estimés

### 15.1 Tarifs LLM (par 1M tokens)

| LLM | Input USD | Output USD | Source |
|-----|-----------|-----------|--------|
| MiniMax M2.5 | 0.118 | 0.99 | minimax.io pricing 2025 |
| Gemini 2.5 Pro | 1.25 | 10.00 | ai.google.dev pricing |
| Gemini 2.5 Flash | 0.075 | 0.30 | ai.google.dev pricing |
| DeepSeek R1 | 0.55 | 2.19 | deepseek.com |
| DeepSeek Chat | 0.27 | 1.10 | deepseek.com |
| Codestral 2 | 0.30 | 0.90 | mistral.ai |

### 15.2 Coût type par mode (estimé)

| Mode | Coût bas | Coût médian | Coût haut |
|------|----------|------------|-----------|
| SIMPLE | $0.001 | $0.003 | $0.01 |
| MEDIUM | $0.01 | $0.02 | $0.04 |
| COMPLEX | $0.05 | $0.10 | $0.30 |

### 15.3 Budget mensuel par profil

- **Étudiant / hobby** (~10 simples + 5 medium / jour) : $5-10/mois.
- **Dev solo full-time** (~30 simples + 10 medium + 5 complex / jour) : $30-80/mois.
- **Équipe 3-5 devs power user** : $200-500/mois.

### 15.4 Cap budget (Plan 5B Task 7 à venir)

- Default : $1.00 par pipeline.
- Configurable dans Settings (Plan 5E).
- Si dépassé en cours de pipeline : abort + WS event `pipeline_budget_exceeded`.

---

## 16. Comment lancer le projet en dev

### 16.1 Setup initial

```bash
# Pré-requis
brew install python@3.12 tmux node ollama
ollama pull qwen2.5-coder:14b qwen2.5-coder:7b

# Backend
cd local_ai_stack
python3.12 -m venv venv
source venv/bin/activate
pip install -e .

# UI
cd ui
npm install

# Variables d'env (clés API)
export GEMINI_API_KEY="..."
export DEEPSEEK_API_KEY="..."
export MISTRAL_API_KEY="..."
export MINIMAX_API_KEY="..."
```

### 16.2 Lancer en dev

```bash
# Terminal 1 — Backend
source venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload

# Terminal 2 — UI
cd ui && npm run dev   # vite dev server :5173

# Terminal 3 — Tauri (optionnel pour shell natif)
cd ui && npm run tauri dev
```

### 16.3 Lancer un pipeline mode SIMPLE (manuel)

```python
# Via Python REPL ou script
from pathlib import Path
from backend.file_lock import FileLock
from backend.llm_manager import LLMManager
from backend.ws_streamer import WSStreamer
from backend.pipeline.orchestrator import Pipeline
from backend.pipeline.types import PipelineContext, PipelineMode
from backend.main import DEFAULT_LLMS

llm_manager = LLMManager(DEFAULT_LLMS)
pipeline = Pipeline(llm_manager, WSStreamer(), FileLock())

import asyncio
ctx = PipelineContext(
    prompt="Crée hello.py qui print 'hi'",
    workspace_root=Path("/tmp/myproj"),
    session_id="manual",
    mode=PipelineMode.SIMPLE,
)
result = asyncio.run(pipeline.run(ctx))
print(result.success, result.files_modified, result.total_cost_usd)
```

---

## 17. Plans 1-4 — historique complet

### 17.1 Plan 1 — Backend Foundation (livré)

Créé `backend/` avec :
- FastAPI app + 8 endpoints REST + WebSocket.
- 5 LLMs configurables via `DEFAULT_LLMS`.
- LLMManager avec fallback chains + system prompt injection.
- RouterEngine (complexity score 1-10).
- WSStreamer (broadcast).
- FileLock (asyncio).
- LLMTaskQueue (1 tâche/LLM à la fois).
- Tests : ~50 pytest verts.

### 17.2 Plan 2 — Intelligence Layer (livré)

- `memory.py` : ShortTermMemory + LongTermMemory (4 tables SQLite).
- `roadmap.py` : ProjectRoadmap + Task + SubTask.
- `context_builder.py` : `build_context_for(llm, task, roadmap)` (~2-3K tokens).
- `agent_loop.py` : 5 étapes PLAN→VERIFY→EXECUTE→CHECK→CONFIRM, retry 3x.
- `orchestrator.py` : Orchestrator central.
- 5 system prompts MD.
- Tests : ~80 pytest verts.

### 17.3 Plan 3 — UI Tauri+React (livré)

- Tauri 2 shell (Rust) avec subprocess FastAPI démarré au boot.
- React 19 + Vite 7 + Tailwind 3.
- 4 tabs (Chat, Terminals, Routing, Monitoring).
- ActivityBar (FileTree, LLMStatus, GitPanel, SprintBoard).
- StatusBar.
- 4 stores Zustand (llm/routing/roadmap/session).
- Singleton WS client avec reconnect 2s + buffer 100 msg.
- Tests : ~80 vitest verts.

### 17.4 Plan 4 — GitHub Mode Projet (livré)

- `git_service.py` : GitPython wrapper.
- `github_service.py` : PyGithub wrapper.
- `project_mode.py` : ProjectMode orchestration.
- `prompts/cdc_generation.md` : prompt DeepSeek R1 pour CdC structuré.
- Routes étendues : `/project/start`, `/project/status`, `/project/feedback`.
- `/ci-webhook` : reçoit GitHub `check_run` / `check_suite`.
- Mode Projet : CdC → Sprints → Tickets GitHub → execution → PR → CI → merge.
- Tests : ~100 pytest verts.

---

## 18. Plan 5A — fondations pipeline (livré)

15 tasks, 5 phases (A1 prereqs / A2 tools / A3 pipeline core / A4 UI / A5 E2E+release). Tag `v2.1.0-alpha.1` poussé.

### Tasks livrées

| # | Sujet | Commit |
|---|-------|--------|
| 1 | LLM `health_check` + `/llms/health` + smoke tests | `0e537bd` |
| 2 | Tokenizer tiktoken `count_tokens` | `004bd29` |
| 3 | `cost_estimator` PRICING + `estimate_pipeline_cost` | `ae7011a` |
| 4 | `tools/file_ops` + `PathOutsideWorkspace` guard | `c9a7e0d` |
| 5 | `tools/search.grep_codebase` + registry dispatcher | `bf45328` |
| 6 | `pipeline/` package base + types + Stage abstract | `78259e6` |
| 7 | `Stage0Estimate` (Gemini Flash classification) | `eee7b45` |
| 8 | `Stage1Intake` (validation non-ambiguïté + ClarificationNeeded) | `d779185` |
| 9 | `Stage3Ground` (tool-calling read-only ancrage factuel) | `736667f` |
| 10 | `Stage5Execute` (tool-calling write + git stash rollback) | `0b7d9f5` |
| 11 | `Stage7Verify` minimal + Pipeline orchestrator | `565e0f8` |
| 12 | UI Modal ESTIMATE (types + store + composant) | `b56d136` |
| 13 | UI TraceViewer + StageRow + intégration RoutingTab | `be63f43` |
| 14 | Fixture ScriptedLLM + test E2E pipeline simple | `b622aa5` |
| 15 | Récap tests + README + checkpoint + tag alpha | `7db3eba` |

### Bug critique corrigé en Task 14

`Stage.run` n'enregistrait pas le `StageResult` dans `ctx.stage_results[name]`. Conséquence : Stage3 (qui lit `intake`), Stage5 (qui lit `plan` ou `ground`), Stage7 (qui lit `execute`) ne voyaient rien. `Pipeline.files_modified` restait vide. Corrigé en ajoutant 4 lignes dans `backend/pipeline/base.py` qui persistent + accumulent cost/tokens.

### Résultat fin Plan 5A

- 264 pytest + 121 vitest verts (cibles 200+ / 115+).
- Mode SIMPLE fonctionnel de bout en bout.
- Tag `v2.1.0-alpha.1` poussé sur `https://github.com/Wissem95/localcoder-ide`.

---

## 19. Plan 5B — VERIFY + retry + streaming (en cours)

8 tasks. **3/8 livrées** au moment de la rédaction.

### Tasks livrées

| # | Sujet | Commit | Statut |
|---|-------|--------|--------|
| 1 | `tools/run_tests.py` wrappers pytest/vitest/cargo/lint | `251a11e` | ✅ |
| 2 | `Stage7Verify` complet (lint + pytest + vitest + cargo en parallèle) | `1070a93` | ✅ |
| 3 | Retry loop Stage5↔Stage7 (max 3 tentatives + rollback) | `daf69df` | ✅ |
| 4 | Backend streaming LLM (litellm `stream=True` → events WS) | — | ⏳ |
| 5 | UI streaming `chat_token` + bulle progressive | — | ⏳ |
| 6 | Stop button + cancellation (CancelledError propagation) | — | ⏳ |
| 7 | Budget cap par pipeline + UI BudgetIndicator | — | ⏳ |
| 8 | Tests E2E + push + tag `v2.1.0-alpha.2` | — | ⏳ |

### Détails Task 1 — `tools/run_tests.py`

- 4 wrappers async : `run_pytest`, `run_vitest`, `run_cargo_check`, `run_lint`.
- Sortie standardisée : `{exit_code, passed, failed, stdout_tail, duration_s, error?}`.
- `stdout_tail` tronqué à 3000 chars avec préfixe `...[truncated]...`.
- Timeout via `asyncio.wait_for` ; si dépassé : `exit_code=-1, error="timeout"`, kill du proc.
- Si binaire absent : `exit_code=127, error="runner not found"` (pas de crash).
- 9 tests verts dans `test_tools_run_tests.py`.

### Détails Task 2 — `Stage7Verify` étendu

- Avant : ruff + cargo seulement.
- Après : lint (ruff/eslint) + pytest + vitest + cargo en parallèle via `asyncio.gather`.
- Dispatch automatique :
  - Files `.py` → `run_lint` ruff.
  - Files `.ts/.tsx/.js/.jsx` → `run_lint` eslint via npx.
  - Au moins un `.rs` modifié → `run_cargo_check` sur `ui/src-tauri/`.
  - `tests_to_run` du plan : si chemin commence par `ui/` ou se finit par `.test.ts(x)` → `run_vitest`, sinon `run_pytest`.
- `VerifyResult` enrichi : `lint_errors[]`, `test_errors[]`, `runners_summary` (compteurs).
- 9 nouveaux tests dans `test_stage_7_verify_full.py` + 8 legacy verts.

### Détails Task 3 — Retry loop

- Nouveau champ `PipelineContext.retry_context: Optional[dict]`.
- `Stage5Execute._retry_hint(ctx)` : si `retry_context` présent, ajoute un bloc dans le user message :
  ```
  RETRY (tentative #2/3) — VERIFY a échoué à la passe précédente avec les erreurs suivantes :
  - F401 'os' imported but unused
  - test_login: AssertionError
  
  Corrige le code pour que ces erreurs disparaissent.
  ```
- `Pipeline._retry_until_green_or_max(ctx, result)` :
  - Boucle Stage5 → Stage7 jusqu'à `all_green=True` ou 3 tentatives.
  - À chaque retry : remplit `ctx.retry_context = {previous_verify_errors, attempt}`.
  - Si toujours rouge après 3 : `git_stash_pop(stash_ref)` + `success=False, error="verify failed after 3 retries"`.
  - Si vert : patch `verify_output.attempts_used` avec le nb de tentatives.
- 3 nouveaux tests dans `test_stage_5_retry.py`.

### Tasks 4-8 (à venir)

- **Task 4** (Backend streaming) : `backend/streaming.py` helper qui wrappe `litellm.acompletion(stream=True)` → publie chaque token comme event WS `chat_token`. `LLMManager.call_with_fallback_stream(role, messages)` (1 jour).
- **Task 5** (UI streaming) : `MessageBubble` consomme les events `chat_token` et appende au texte progressivement. Cursor `▎` pendant streaming. (1 jour.)
- **Task 6** (Stop button) : event WS `pipeline_stop` côté UI → `Pipeline.cancel()` qui propage `asyncio.CancelledError` ; rollback garanti via finally. (1 jour.)
- **Task 7** (Budget cap) : `backend/budget_tracker.py` compte $ accumulé pendant le pipeline ; si > cap, abort. UI `BudgetIndicator` jauge en temps réel. (1 jour.)
- **Task 8** (E2E + release) : tests E2E retry/rollback/cancel/budget + suite complète + tag `v2.1.0-alpha.2` (0.5 jour).

---

## 20. Plans 5C, 5D, 5E, 5F — à venir

### 20.1 Plan 5C — CHALLENGE + PLAN consensus

**Goal** : implémenter Stage 2 (CHALLENGE) + Stage 4a (PLAN) + Stage 4b (PLAN-REVIEW), activer modes `MEDIUM` et `COMPLEX` dans Pipeline.

- Stage 2 CHALLENGE : Gemini Pro joue l'avocat du diable, identifie 3-5 questions critiques.
- Stage 4a PLAN : DeepSeek R1 décompose en sous-tâches + tests à lancer (output JSON validé par schéma).
- Stage 4b PLAN-REVIEW : Gemini Pro vérifie le plan ; consensus 2/2 (Pro doit accepter).
- En cas de désaccord → modal user `pipeline_user_decision_needed`.
- Pipeline.run dispatche `MEDIUM=[0,1,3,5,6,7,8]` et `COMPLEX=[0,1,2,3,4a,4b,5,6,7,8,(9)]`.
- Cible : 270+ pytest verts.

### 20.2 Plan 5D — SELF-CHECK + REVIEW

**Goal** : Stage 6 (SELF-CHECK), Stage 8 (REVIEW), Stage 9 (SECOND-REVIEW).

- Stage 6 SELF-CHECK : MiniMax relit son propre diff, signale erreurs internes (logique, edge cases).
- Stage 8 REVIEW : Gemini Pro review le diff complet (utilise 1M ctx).
- Stage 9 SECOND-REVIEW : DeepSeek R1, déclenché si Pro hésite (`approved=null`).
- Consensus 8+9 : si Pro et R1 désaccord → modal user.
- Brancher `Orchestrator.handle()` sur `Pipeline` (remplace `AgentLoop`).
- Cible : 310+ pytest.

### 20.3 Plan 5E — UX raffinée + Settings + Costs

**Goal** : raffinage UI + Settings persistants + CostTracker calibration.

- Toasts (Sonner) pour notifications non-bloquantes.
- Syntax highlight (Shiki) dans `MessageBubble` pour les blocs code.
- Command palette (Cmdk) — Cmd+K pour actions rapides.
- Settings UI :
  - Clés API (stockées dans `~/.localcoder/keys.toml`, masquées partiellement).
  - Toggles LLM (enable/disable).
  - Pipeline settings (budget cap mensuel, max retries, mode forcé).
  - Theme (dark/light/system).
- CostTracker persistant :
  - Compteur $ par jour, par session, par projet.
  - Comparaison estimé/réel — calibre `STAGE_TOKEN_ESTIMATES`.
  - Graphique 30 jours.
- Cible : 340+ pytest, 180+ vitest.

### 20.4 Plan 5F — Packaging + Ollama + Release

**Goal** : produire un binaire installable + mode privacy-first 100 % local.

- Bundle Tauri (DMG macOS, DEB Linux, MSI Windows).
- Menu bar macOS natif (Tauri tray icon, raccourcis Cmd+space pour ouvrir le chat global).
- Mode Ollama :
  - Détection auto `localhost:11434`.
  - Models locaux : `qwen2.5-coder:14b` (CODING), `qwen2.5-coder:7b` (ROUTING).
  - Toggle UI "Privacy mode" → tous les stages route vers Ollama.
- Workflow GitHub Actions release :
  - Tag → build cross-platform → upload artifacts.
- Docs utilisateur :
  - `USER_GUIDE.md` (~50 pages PDF).
  - `API_KEYS_SETUP.md` (comment obtenir les clés gratuites).
  - `TROUBLESHOOTING.md`.
- Tag `v2.0.0` final.

---

## 21. Tous les events WebSocket

Émis depuis `backend/ws_streamer.py:WSStreamer`. Format : `{type: string, data: any, session_id: string, ts: ISO8601}`.

### 21.1 Events backend → UI

| Event | Émetteur | Data | Quand |
|-------|----------|------|-------|
| `health` | local UI (sur ws.onopen) | `{}` | À la connexion |
| `disconnect` | local UI (sur ws.onclose) | `{}` | À la déconnexion |
| `error` | local UI (sur ws.onerror) | `{message: str}` | Erreur réseau |
| `routing_decision` | Orchestrator | `RoutingEntry(id, ts, prompt, llm, role, mode, reason, durationMs, tokens)` | Après RouterEngine.route() |
| `agent_step` | AgentLoop | `{step: "PLAN"\|"VERIFY"\|..., attempt: int}` | Pendant boucle legacy |
| `pipeline_estimate` | Stage0Estimate | `EstimateResult(estimateId, classification, reason, stages[], totalCostUSD, totalDurationSec)` | Fin Stage0 |
| `stage_start` | Stage.run | `{stage: str, llm: str\|null}` | Début de chaque stage |
| `stage_complete` | Stage.run | `{stage, success, duration_ms, tokens_in, tokens_out, cost_usd, error}` | Fin de chaque stage |
| `pipeline_complete` | Pipeline.run | `PipelineResultPayload(success, filesModified, totalCostUSD, totalDurationMs, rollbackPerformed, error)` | Fin globale |
| `pipeline_rollback` | Pipeline.run | `{reason: str}` | Rollback déclenché |
| `chat_token` (Plan 5B Task 5) | LLMManager.stream | `{token: str, llm: str}` | Pendant streaming |
| `pipeline_user_decision_needed` (Plan 5C) | Stage1/Stage4b/Stage8 | `{stage, questions: list[str]}` | Ambiguïté ou désaccord |
| `pipeline_budget_exceeded` (Plan 5B Task 7) | BudgetTracker | `{cap_usd, current_usd}` | Cap dépassé |

### 21.2 Events UI → backend

| Event | Émetteur | Data | Effet |
|-------|----------|------|-------|
| `pipeline_confirmed` | EstimateModal | `{estimate_id, mode}` | Lance le pipeline |
| `pipeline_cancelled` | EstimateModal | `{estimate_id}` | Annule (avant exécution) |
| `pipeline_stop` (Plan 5B Task 6) | TraceViewer Stop | `{session_id}` | Cancel en cours d'exécution |
| `clarification_response` (Plan 5C) | UI | `{questions, answers[]}` | Continue après pause INTAKE |

---

## 22. Tous les endpoints HTTP

Définis dans `backend/main.py`.

| Méthode | Path | Body | Réponse | Description |
|---------|------|------|---------|-------------|
| GET | `/health` | — | `{status, llms_count}` | Ping basique |
| POST | `/route` | `{prompt, file_count?, mention?}` | `RoutingDecision` | Analyse complexité d'un prompt sans le lancer |
| POST | `/chat` | `{user_id, prompt, file_count?, mention?}` | `OrchestratorResponse(content, llm_used, role, duration, tokens, routing_reason)` | Lance via Orchestrator |
| POST | `/ci-webhook` | GitHub `check_run` ou `check_suite` JSON | `{ack: true}` | Reçoit notif CI, met à jour `routing_feedback` |
| POST | `/project/start` | `{description, github_token, repo_name}` | `ProjectRoadmap` | Lance Mode Projet (CdC + sprints + GH structure) |
| GET | `/project/status` | — | `{roadmap, active_sprint, active_ticket}` | État Mode Projet |
| POST | `/project/feedback` | `{prompt, llm_chosen, success: bool, score: int, notes?}` | `{saved: true}` | Insère dans `routing_feedback` |
| GET | `/llms` | — | `list[LLMConfig]` | Liste LLMs configurés |
| GET | `/llms/health` | — | `list[{llm, healthy, latency_ms, error?}]` | Health-check par LLM (live, parallèle) |
| POST | `/llms/{llm_id}/disable` | — | `{disabled: true}` | Désactive un LLM |
| POST | `/llms/{llm_id}/enable` | — | `{enabled: true}` | Réactive |
| WebSocket | `/ws?session_id=...` | — | events temps réel | Auth par query param |

---

## 23. Garanties de sécurité

### 23.1 Sous-processus en mode argv-list

Toutes les invocations système (git, ruff, pytest, vitest, cargo) passent par `asyncio.create_subprocess_*` avec une **liste d'arguments**, jamais de string concaténée. Aucune interpolation utilisateur dans `argv`. Pas de risque d'injection de commande.

### 23.2 PathOutsideWorkspace guard

Implémenté dans `backend/tools/exceptions.py` + `_resolve(path, workspace_root)` dans tous les `file_ops`. Levée si :
- Le path résolu n'est pas un descendant de `workspace_root`.
- `..` traverse au-delà de la racine.
- Path absolu hors workspace.

L'exception est capturée par `execute_tool()` et retournée comme `{success: False, error: "path outside workspace"}` au LLM. Pas de crash, pas d'écriture hors zone.

### 23.3 FileLock asyncio

`backend/file_lock.py` empêche 2 LLMs (en mode multi-agent) d'écrire simultanément dans le même fichier. Lock acquis par `(path, llm_id)` ; release garantie via `try/finally`.

### 23.4 Backend localhost-only

FastAPI écoute sur `127.0.0.1:8765`, jamais `0.0.0.0`. Pas accessible depuis le réseau local.

### 23.5 CORS strict

Seul `http://localhost:5173` (Vite dev) est whitelisté. En prod (Tauri bundle), pas de CORS car webview en `tauri://localhost`.

### 23.6 Clés API

Stockées hors du repo (`~/.localcoder/keys.toml` à terme via Plan 5E ; pour l'instant variables d'env). Jamais loggées.

### 23.7 Git stash systématique avant EXECUTE

Capture l'état du working dir avant que le LLM ne touche aux fichiers. Sur exception ou échec VERIFY × 3 → `git stash pop` automatique → état restauré. L'utilisateur ne perd jamais son travail.

### 23.8 Budget cap (Plan 5B Task 7)

Empêche un pipeline runaway ($1.00 par défaut). Au-delà → abort + rollback.

---

## 24. Limitations connues

- **AgentLoop legacy ne modifie PAS les fichiers** : `Orchestrator.handle()` (mode chat classique) utilise encore `AgentLoop` qui ne fait que générer du texte. Le branchement vers `Pipeline` (qui modifie réellement) viendra en Plan 5D Step 11.3.
- **Mode MEDIUM et COMPLEX vides** : `Pipeline.stages_by_mode` ne remplit que `SIMPLE`. Plans 5C/5D rempliront.
- **Pas de retry sur les LLM calls Stage par Stage** : si Gemini Flash timeout pendant Stage0, on a juste le fallback chain. Plan 5E ajoutera un retry exponentiel par stage.
- **Streaming pas encore branché** : Plan 5B Task 4-5.
- **Bouton Stop UI non fonctionnel** : le bouton existe (TraceViewer) mais n'envoie qu'un `pipeline_cancelled` sans cancellation côté backend. Plan 5B Task 6.
- **Settings UI inexistant** : pour configurer les clés API, il faut éditer les variables d'env. Plan 5E.
- **Pas de syntax highlight dans les bulles chat** : code en monospace simple. Plan 5E (Shiki).
- **Pas de bundle distribuable** : pour utiliser, il faut cloner + setup dev. Plan 5F (Tauri bundle).
- **Mode Ollama pas configuré** : qwen2.5-coder est mentionné dans le README mais pas branché dans LLMManager. Plan 5F.
- **Pas de menu bar macOS natif** : pas de raccourci global. Plan 5F.
- **Pas de tests cross-platform** : tout est testé sur macOS. Linux/Windows à venir.
- **Pas de monitoring CPU/RAM en temps réel UI** : `MonitoringTab` affiche statique. Améliorations Plan 5E.

---

## 25. Glossaire

| Terme | Définition |
|-------|-----------|
| **CdC** | Cahier des Charges, document structuré JSON décrivant un projet (généré par DeepSeek R1 en Mode Projet) |
| **CHALLENGE** | Stage 2 du pipeline : LLM joue l'avocat du diable pour identifier les angles morts |
| **Consensus 2/2** | Mécanisme où 2 LLMs différents doivent être d'accord pour qu'une décision avance (ex: PLAN+PLAN-REVIEW, REVIEW+SECOND-REVIEW) |
| **EXECUTE** | Stage 5 du pipeline : seul stage qui modifie réellement les fichiers |
| **FALLBACK_CHAINS** | Dictionnaire `LLMRole → list[llm_id]` qui définit la cascade si le LLM principal est rate-limited ou down |
| **GROUND** | Stage 3 du pipeline : LLM lit le code réel (pas d'hypothèse) via tool-calling read-only |
| **INTAKE** | Stage 1 du pipeline : valide non-ambiguité avant les étapes coûteuses |
| **LiteLLM** | Wrapper unifié multi-LLM utilisé pour appeler tous les modèles avec une seule API |
| **Mode Projet** | Workflow Plan 4 : description user → CdC → Sprints → Tickets GitHub → execution |
| **PathOutsideWorkspace** | Exception levée par les tools si un LLM tente de toucher un fichier hors de `workspace_root` |
| **Pipeline rigoureux** | L'orchestration 11-stages introduite en Plan 5A, avec re-vérifications croisées |
| **PRICING** | Dict `llm_id → {in, out}` USD par 1M tokens dans `cost_estimator.py` |
| **retry_context** | Champ dans `PipelineContext` rempli quand Stage7Verify rouge → injecté dans le user message de Stage5 pour le retry |
| **ScriptedLLM** | Fixture de test qui mock `litellm.acompletion` avec des réponses pré-scriptées par stage |
| **SELF-CHECK** | Stage 6 : le même LLM qui a écrit relit son diff pour repérer ses propres erreurs |
| **stash_ref** | Référence git stash retournée par `git stash push` ; utilisée pour `git stash pop` rollback |
| **Stage** | Classe abstraite `backend/pipeline/base.py:Stage` ; chaque étape du pipeline en hérite |
| **STAGE_LLM_MAP** | Dict `stage_name → llm_id` : quel LLM pour quelle étape |
| **STAGE_TOKEN_ESTIMATES** | Dict `mode → stage → {in: int, out: int}` : heuristiques de tokens consommés par étape |
| **TOOLS_SCHEMA_READ / WRITE** | Listes JSON-Schema des tools exposés au LLM via litellm tool-calling |
| **Tool-calling** | Mécanisme où le LLM retourne un tool_call JSON ; le backend l'exécute, réinjecte le résultat, le LLM continue |
| **Workspace guard** | Ensemble des protections empêchant tout file_op hors de `workspace_root` |
| **WSStreamer** | Service backend qui broadcast/unicast des events WebSocket à l'UI |

---

## 26. FAQ technique

**Q1 : Pourquoi pas un seul LLM partout ?**
Parce que les LLMs ont des forces complémentaires : MiniMax bon en coding (SWE-bench 80 %), Gemini Pro bon en analyse (1M context), Flash rapide pour classification, R1 fort en reasoning d'architecture. Multi-LLM avec consensus 2/2 sur étapes critiques fait monter le taux de succès de ~85 % (mono-LLM) à ~95-99 % (cible).

**Q2 : Comment le pipeline garantit "zéro hallucination" ?**
Stage3 GROUND impose la lecture du code réel via tool-calling avant que les stages avals décident. Le LLM ne peut pas "supposer" qu'une fonction existe — il doit la lire. En plus, Stage7 VERIFY est mécanique (pas de LLM), donc si un LLM ment sur "j'ai testé", VERIFY révèle la vérité.

**Q3 : Que se passe-t-il si un LLM est down ?**
`FALLBACK_CHAINS[role]` cascade vers le suivant. Si tous les LLMs d'un rôle sont down → exception remontée à l'UI → modal user. Mode Ollama (Plan 5F) permettra de rester opérationnel offline.

**Q4 : Comment le rollback fonctionne ?**
Avant Stage5 EXECUTE, `git stash push -u` capture le working dir + untracked. Le `stash_ref` est conservé dans `ExecuteResult.stash_ref`. Sur exception ou Stage7 rouge × 3 → `git stash pop` automatique. L'utilisateur ne perd JAMAIS son travail non commité.

**Q5 : Pourquoi 3 retries max et pas plus ?**
Empirique : si après 3 tentatives le LLM n'a pas corrigé les erreurs VERIFY, c'est que le problème est plus complexe que ce qu'il peut résoudre. Mieux vaut faire un rollback propre et demander à l'utilisateur que de boucler indéfiniment en brûlant des $.

**Q6 : Les tests live sont skipped — comment vérifier que les LLMs marchent ?**
`scripts/smoke_llms.sh` fait un health-check live sur les 5 LLMs. Aussi `pytest -m llm_live` lance les tests qui appellent vraiment les APIs (3-5 tests, ~$0.02 par run).

**Q7 : Comment ajouter un nouveau LLM ?**
1. Ajouter une `LLMConfig` dans `DEFAULT_LLMS` (`backend/main.py`).
2. Ajouter le tarif dans `PRICING` (`cost_estimator.py`).
3. Ajouter dans `FALLBACK_CHAINS[role]` (`llm_manager.py`).
4. Ajouter (optionnel) un system prompt MD `backend/prompts/system_<llm>.md`.
5. Ajouter dans `STAGE_LLM_MAP` si on veut l'utiliser à un stage spécifique.

**Q8 : Pourquoi pas de RAG / vector store ?**
Pas nécessaire pour un IDE local. Le contexte est limité à un repo (`workspace_root`), et `grep_codebase` + `read_file` couvrent les besoins. Un RAG serait du overhead pour peu de gain. Si nécessaire à grande échelle, ajout possible en Plan 5E.

**Q9 : Quelle est la différence avec Aider ?**
Aider est mono-LLM en mode chat libre. LocalCoder est multi-LLM avec pipeline structuré + re-vérifications + rollback. Plus rigoureux mais aussi plus cher (3-10 calls par tâche au lieu de 1-2).

**Q10 : Quelle est la différence avec Cursor / Windsurf ?**
Cursor/Windsurf sont des éditeurs avec auto-complétion AI puissante. LocalCoder est un orchestrateur agentique : tu donnes une tâche, il décompose, lance, vérifie, commit. Plus proche de Claude Code que de Cursor.

**Q11 : Peut-on utiliser le pipeline sans l'UI ?**
Oui — voir §16.3 (Python script direct). Le `Pipeline.run(ctx)` est utilisable headless.

**Q12 : Combien coûte un mois d'utilisation typique ?**
Dev solo full-time : $30-80/mois (cf. §15.3). Étudiant : $5-10. Équipe 5 : $200-500.

**Q13 : Où sont stockées les données ?**
- Code : workspace local (jamais uploadé sauf push git).
- Mémoire : SQLite local (`localcoder.db`).
- Cache LLM (Plan 5E) : `~/.localcoder/cache/`.
- Clés API : variables d'env, plus tard `~/.localcoder/keys.toml`.
- **Aucune télémétrie**.

**Q14 : Comment contribuer ?**
Repo : `https://github.com/Wissem95/localcoder-ide`. Branche `main`, PR welcome. Tests obligatoires (`pytest tests/backend/` + `npx vitest run`). TDD strict suivi par les agents superpowers.

**Q15 : Quelle est la prochaine grosse étape ?**
Plan 5C : implémenter le consensus 2/2 (PLAN + PLAN-REVIEW), activer mode COMPLEX. Cible : ~3 semaines.

---

*Dernière mise à jour : 2026-05-04. Ce document est régénéré à chaque fin de plan majeur.*
