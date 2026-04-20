# LocalCoder IDE v2 — Plan 5 : MVP utilisable + packaging

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Combler le gap entre "fondations solides" (Plans 1-4) et "produit réellement utilisable et distribuable". Brancher les vrais LLMs, donner à l'AgentLoop les outils pour modifier des fichiers, couvrir l'UX, packager l'app et l'outiller pour l'usage quotidien.

**Architecture :** 4 phases A/B/C/D, 16 tâches, progression MVP → production :

- **Phase A (critique)** — app qui MARCHE : vrais LLMs, outils fichiers, tokenizer, tests E2E, UX erreurs.
- **Phase B (important)** — app qu'on VEUT utiliser : settings UI, syntax highlight, shortcuts, cost tracking, cleanup DB.
- **Phase C (packaging)** — app DISTRIBUABLE : bundle Tauri, icône+menu, observabilité.
- **Phase D (features avancées)** — app COMPLÈTE : Ollama local, multi-project, templates.

**Tech Stack additionnel :**
- Backend : `tiktoken`, `structlog`, `apscheduler` (DB cleanup), `prometheus-client` (optionnel).
- UI : `sonner` (toasts), `shiki` (syntax highlight WASM), `cmdk` (palette commandes), `@tauri-apps/plugin-updater`, `@tauri-apps/plugin-store`.
- Rust : `tauri-plugin-updater`, `tauri-plugin-store`.

**Prérequis :** Plans 1-4 + Phase 2 complets. Tests 157/157 pytest, 105/105 vitest. API keys réelles pour DeepSeek, MiniMax, Google AI, Mistral (un compte de chaque pour les tests live).

**Corrections critiques de référence :** `docs/superpowers/plans/2026-04-10-corrections-critiques.md` reste applicable.

---

## Fichiers créés ou modifiés

```
backend/
├── tools/
│   ├── __init__.py                # CRÉÉ — init package
│   ├── file_ops.py                # CRÉÉ — edit/create/delete/read/list_files
│   ├── run_tests.py               # CRÉÉ — pytest/vitest/cargo invokers
│   └── registry.py                # CRÉÉ — JSON schema tools + dispatcher
├── agent_loop.py                  # MODIFIÉ — boucle exécute les tool_calls
├── llm_manager.py                 # MODIFIÉ — health_check par LLM
├── context_builder.py             # MODIFIÉ — tiktoken
├── memory.py                      # MODIFIÉ — cleanup_old_messages
├── cost_tracker.py                # CRÉÉ — prix par modèle + cumul
├── workspace_registry.py          # CRÉÉ — multi-projet
├── logging_config.py              # CRÉÉ — structlog JSON
├── main.py                        # MODIFIÉ — scheduler, logs, /llms/health, /settings/*
└── prompts/
    ├── agent_tools.md             # CRÉÉ — system prompt tools
    └── cdc_templates/             # CRÉÉ — SaaS, API, mobile, CLI
        ├── SaaS.md
        ├── API.md
        ├── mobile-app.md
        └── CLI.md

tests/backend/
├── test_tools_file_ops.py         # CRÉÉ
├── test_tools_run_tests.py        # CRÉÉ
├── test_cost_tracker.py           # CRÉÉ
├── test_workspace_registry.py     # CRÉÉ
├── test_context_builder.py        # MODIFIÉ (tiktoken)
├── test_memory.py                 # MODIFIÉ (cleanup)
├── test_llm_manager.py            # MODIFIÉ (health + live)
└── test_e2e_chat_to_commit.py     # CRÉÉ (bout-en-bout)

ui/src/
├── components/
│   ├── Settings/
│   │   ├── SettingsTab.tsx
│   │   ├── ApiKeysForm.tsx
│   │   └── LLMTogglesForm.tsx
│   ├── CommandPalette/
│   │   └── CommandPalette.tsx
│   ├── Toasts/
│   │   └── Toaster.tsx
│   ├── NewProjectModal.tsx
│   ├── WorkspaceSwitcher.tsx
│   └── tabs/ChatTab/
│       ├── CodeBlock.tsx
│       └── MessageBubble.tsx      # MODIFIÉ — rend les blocs ``` via CodeBlock
├── stores/
│   ├── settingsStore.ts
│   └── costStore.ts
├── hooks/
│   └── useKeyboardShortcuts.ts
└── App.tsx                        # MODIFIÉ — Toaster, CommandPalette, Settings tab

ui/src-tauri/
├── Cargo.toml                     # MODIFIÉ — tauri-plugin-updater, -store
├── tauri.conf.json                # MODIFIÉ — updater endpoint, icon custom
├── icons/                         # REMPLACÉ — logo LocalCoder
└── src/
    ├── lib.rs                     # MODIFIÉ — plugins + menu register
    └── menu.rs                    # CRÉÉ — menu bar macOS natif

.github/workflows/
└── release.yml                    # CRÉÉ — build cross-platform sur tag

docs/
├── USER_GUIDE.md                  # CRÉÉ
├── API_KEYS_SETUP.md              # CRÉÉ
└── TROUBLESHOOTING.md             # CRÉÉ
```

---

# PHASE A — MVP Critique (app qui MARCHE)

## Task 1 : LLM calls réels end-to-end

**Files:** `backend/llm_manager.py`, `backend/main.py`, `tests/backend/test_llm_manager.py`, `scripts/smoke_llms.sh`.

- [ ] **Step 1.1 — `LLMManager.health_check(llm_id)` method**

  Ping minimal (1 token) sur un LLM. Retourne `{ok: bool, latency_ms: int, error: str | None}`. Utilise `perf_counter` pour mesurer.

- [ ] **Step 1.2 — Endpoint `GET /llms/health`**

  Dans `main.py`, lance `health_check` sur les 5 LLMs via `asyncio.gather`. Retourne `{llm_id: health_result}`.

- [ ] **Step 1.3 — Tests live (skippés sans API key)**

  Marker `@pytest.mark.llm_live` + `@pytest.mark.skipif(not os.environ.get("DEEPSEEK_API_KEY"), ...)` sur chacun des 5 tests. Lance avec `pytest -m llm_live`.

- [ ] **Step 1.4 — Script `scripts/smoke_llms.sh`**

  Lance un petit script Python qui appelle `health_check` sur les 5 LLMs et affiche les résultats. Usage : après avoir exporté les API keys.

- [ ] **Step 1.5 — Ajuster FALLBACK_CHAINS selon les résultats**

  Observer latency et reliability réels, réordonner les fallbacks. Ex: si Codestral est lent, fallback direct vers Gemini Flash.

- [ ] **Step 1.6 — Commit via /commit skill**

---

## Task 2 : Outils fichier pour l'AgentLoop

**Files:** `backend/tools/` (package complet), `backend/agent_loop.py`, `backend/prompts/agent_tools.md`, `tests/backend/test_tools_*.py`.

- [ ] **Step 2.1 — `backend/tools/file_ops.py`**

  Fonctions async :
  - `edit_file(path, content, file_lock, repo_root)` — écrit via FileLock. Rejette les paths hors repo (guard `repo_root in abs_path.parents`).
  - `create_file(path, content, ...)` — échoue si existe déjà.
  - `delete_file(path, ...)` — supprime.
  - `read_file(path, ..., max_bytes=100_000)` — tronque si trop gros, décode utf-8 avec errors="replace".
  - `list_files(path, ...)` — listing non-récursif, ignore `.git`, `node_modules`, `venv`, `__pycache__`, `dist`, `build`.
  - Classe `ToolError` pour les erreurs remontées au LLM.

- [ ] **Step 2.2 — `backend/tools/run_tests.py`**

  Wrappers async autour de `asyncio.subprocess` pour lancer `pytest`, `vitest`, `cargo check`. Retournent `{exit_code, passed, failed, stdout}` (stdout tronqué à 3000 chars pour ne pas saturer le contexte LLM).

- [ ] **Step 2.3 — `backend/tools/registry.py`**

  `TOOLS_SCHEMA` au format OpenAI/Anthropic function calling : `edit_file`, `create_file`, `delete_file`, `read_file`, `list_files`, `run_pytest`, `run_vitest`, `run_cargo_check`. Fonction `execute_tool(name, arguments, file_lock, repo_root)` dispatche vers l'implémentation.

- [ ] **Step 2.4 — `backend/prompts/agent_tools.md`**

  System prompt décrivant quand utiliser quel outil. Insiste sur : lire avant d'éditer, tester après modification, ne jamais supposer l'état d'un fichier.

- [ ] **Step 2.5 — Modifier `AgentLoop.execute_step`**

  Passe `tools=TOOLS_SCHEMA` au LLM. Si `response.tool_calls` non vide : exécute chaque tool via `registry.execute_tool`, ajoute les résultats au contexte sous `{"role": "tool", "tool_call_id": ..., "content": ...}`, relance `execute_step` récursivement avec le nouveau contexte. Limite la profondeur à 10 itérations pour éviter les boucles.

- [ ] **Step 2.6 — Tests**

  - `test_tools_file_ops.py` : write, rejet path hors repo, create fails if exists, delete, read truncation.
  - `test_tools_run_tests.py` : fixture avec un mini projet Python + tests, vérifie que `run_pytest` renvoie passed/failed corrects.

- [ ] **Step 2.7 — Commit via /commit**

---

## Task 3 : Tokenizer réel dans ContextBuilder

**Files:** `backend/context_builder.py`, `tests/backend/test_context_builder.py`, `pyproject.toml`.

- [ ] **Step 3.1 — Ajouter `tiktoken>=0.7` dans pyproject**

- [ ] **Step 3.2 — `count_tokens(text, model="gpt-4o")` via tiktoken avec cache**

  `_ENC_CACHE: dict[str, Encoding]`. Fallback `len(text) // 4` si modèle inconnu (KeyError).

- [ ] **Step 3.3 — Tests**

  Vérifier comptage précis sur petit texte (< 10 tokens pour "hello world") et texte long (400-700 tokens pour la phrase *The quick brown fox…* × 50).

- [ ] **Step 3.4 — Commit via /commit**

---

## Task 4 : Tests E2E chat → commit

**Files:** `tests/backend/test_e2e_chat_to_commit.py`, `tests/fixtures/mock_llm.py`.

- [ ] **Step 4.1 — `ScriptedLLM` fixture**

  Classe dont `chat_with_tools` renvoie des réponses scénarisées itération par itération (via `iter()`).

- [ ] **Step 4.2 — Test "prompt → fichier créé → commit"**

  - Fixture `git_workspace` avec `git init` + commit initial.
  - Orchestrator configuré avec `ScriptedLLM` qui renvoie : (1) tool_call `edit_file("main.py", "def ping()...")`, (2) message final.
  - `orch.handle(prompt="ajoute /ping")` → vérifier fichier créé + (en mode projet) commit apparaît dans `git log`.

- [ ] **Step 4.3 — Test "CI rouge → retry branche reset"**

  Scénario avec `_wait_for_ci` retournant False la 1re fois, True la 2e. Vérifier `create_or_reset_branch` appelé 2 fois sans crash.

- [ ] **Step 4.4 — Commit via /commit**

---

## Task 5 : Gestion erreurs UI (toasts, retry, feedback)

**Files:** `ui/src/components/Toasts/Toaster.tsx`, `ui/src/main.tsx`, `ui/src/stores/sessionStore.ts`.

- [ ] **Step 5.1 — `npm install sonner`**

- [ ] **Step 5.2 — `Toaster.tsx`**

  Wrapper de `<Toaster />` de Sonner, thème dark, position bottom-right, style aligné sur la palette LocalCoder (bg-panel, border-border, text-text).

- [ ] **Step 5.3 — Connecter toasts aux events WS**

  Dans `main.tsx` : `ws.on("disconnect", ...)` → `toast.warning("Connexion perdue")`, `ws.on("error", ...)` → `toast.error(data.message)`, `ws.on("health", ...)` → `toast.success("Connecté")` (seulement si transition connecting → ready).

- [ ] **Step 5.4 — Spinner dans StatusBar pendant `backendStatus === "connecting"`**

- [ ] **Step 5.5 — Tests**

  Mock sonner, vérifier que `dispatch("error")` appelle `toast.error` avec le bon message.

- [ ] **Step 5.6 — Commit via /commit**

---

# PHASE B — Important (app qu'on VEUT utiliser)

## Task 6 : Settings panel UI (API keys, LLM toggles)

**Files:** `ui/src-tauri/Cargo.toml`, `ui/src-tauri/src/lib.rs`, `ui/src/stores/settingsStore.ts`, `ui/src/components/Settings/*.tsx`, `backend/main.py`, `ui/src/App.tsx`.

- [ ] **Step 6.1 — Installer `tauri-plugin-store` côté Rust + `@tauri-apps/plugin-store` côté TS**

- [ ] **Step 6.2 — `settingsStore.ts`**

  State Zustand : `apiKeys` (4 champs : deepseek/minimax/google_ai/mistral), `llmsEnabled` (dict par id). Persiste via `Store.load("settings.json")`. `setApiKey` persiste + appelle `POST /settings/api-key` pour updater `os.environ` côté backend.

- [ ] **Step 6.3 — `ApiKeysForm.tsx`**

  4 inputs type password, bouton "Tester" par provider qui appelle `/llms/health` filtré sur ce provider, indicateur vert/rouge.

- [ ] **Step 6.4 — `LLMTogglesForm.tsx`**

  Liste des 5 LLMs avec `<input type="checkbox">`, connecté à `llmsEnabled`.

- [ ] **Step 6.5 — `SettingsTab.tsx`** : container avec 2 sections (API Keys, LLMs actifs).

- [ ] **Step 6.6 — Ajouter `settings` dans `TAB_ORDER` + label + lazy import dans App.tsx**

- [ ] **Step 6.7 — Backend `POST /settings/api-key`**

  Body `{provider, value}`. Mappe provider → env var name (DEEPSEEK_API_KEY, MINIMAX_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY), pose dans `os.environ`.

- [ ] **Step 6.8 — Tests**

  UI : form saisit une clé → store set → POST émis.
  Backend : POST ajoute bien l'env var.

- [ ] **Step 6.9 — Commit via /commit**

---

## Task 7 : Syntax highlighting dans ChatTab

**Files:** `ui/src/components/tabs/ChatTab/CodeBlock.tsx`, `MessageBubble.tsx`.

- [ ] **Step 7.1 — `npm install shiki`**

- [ ] **Step 7.2 — `CodeBlock.tsx`**

  Component async qui appelle `codeToHtml(code, {lang, theme: "github-dark"})` de shiki et affiche le résultat via le mécanisme d'injection HTML React standard. Fallback `<pre>` pendant le loading.

- [ ] **Step 7.3 — Parser dans `MessageBubble.tsx`**

  Split le content sur la regex de blocs code triple-backtick (multiline). Rend alternativement `<p>` pour le texte et `<CodeBlock>` pour les blocs. Gérer lang par défaut `text`.

- [ ] **Step 7.4 — Sécurité XSS**

  Le HTML produit par shiki est safe (pré-généré à partir de tokens), mais on passe le code par DOMPurify (déjà dispo via deps transitive) pour défense en profondeur avant l'injection.

- [ ] **Step 7.5 — Tests**

  Snapshot d'un message contenant un bloc code → vérifier présence classe shiki.

- [ ] **Step 7.6 — Commit via /commit**

---

## Task 8 : Keyboard shortcuts + command palette

**Files:** `ui/src/hooks/useKeyboardShortcuts.ts`, `ui/src/components/CommandPalette/CommandPalette.tsx`, `ui/src/App.tsx`.

- [ ] **Step 8.1 — `npm install cmdk`**

- [ ] **Step 8.2 — `useKeyboardShortcuts(shortcuts)` hook**

  Liste de `{key, cmdOrCtrl, shift, handler}`. `useEffect` attache un listener global sur `keydown`, gère `metaKey || ctrlKey` selon flag.

- [ ] **Step 8.3 — `CommandPalette.tsx`**

  Modal cmdk : input de recherche + liste d'actions (switch tab, toggle LLM, open settings, new project, etc.). Fermeture sur click extérieur ou Escape.

- [ ] **Step 8.4 — Enregistrer shortcuts dans App.tsx**

  - `Cmd+K` → ouvre palette
  - `Cmd+1..4` → switch tab
  - `Cmd+,` → Settings
  - `Cmd+Enter` dans ChatInput → send

- [ ] **Step 8.5 — Tests**

  keydown Cmd+K → palette visible. Test navigation clavier dans la liste cmdk.

- [ ] **Step 8.6 — Commit via /commit**

---

## Task 9 : Cost tracking précis

**Files:** `backend/cost_tracker.py`, `tests/backend/test_cost_tracker.py`, `backend/llm_manager.py`, `ui/src/stores/costStore.ts`, `ui/src/components/tabs/MonitoringTab/MonitoringTab.tsx`.

- [ ] **Step 9.1 — `cost_tracker.py`**

  `PRICING` dict `{llm_id: (input_dollar_per_M, output_dollar_per_M)}` mis à jour sept 2025 (DeepSeek R1 : 0.55/2.19, MiniMax : 0.20/1.10, Gemini Pro : 1.25/10, Gemini Flash : 0.075/0.30, Codestral : 0.20/0.60).
  `CostTracker` dataclass : dicts `input_tokens`/`output_tokens` par llm_id, méthodes `record(llm, in, out)`, `cost_for(llm)`, `total_cost()`.

- [ ] **Step 9.2 — Intégrer dans LLMManager**

  Après chaque call réussi, lire les tokens de la réponse LiteLLM et appeler `cost_tracker.record`. Broadcast `token_usage` event WebSocket avec `{tokens, costUSD}` delta.

- [ ] **Step 9.3 — `costStore.ts`** : accumulé par LLM, alimenté par `ws.on("token_usage")`.

- [ ] **Step 9.4 — MonitoringTab : section "Coût par LLM"**

  Liste des LLMs avec coût cumulé en dollars, total en bas. Barre de progression relative.

- [ ] **Step 9.5 — Tests**

  `test_cost_tracker_accumulates` : 1M input + 1M output Gemini Flash → cost = 0.075 + 0.30 = 0.375.

- [ ] **Step 9.6 — Commit via /commit**

---

## Task 10 : DB cleanup (retention policy)

**Files:** `pyproject.toml`, `backend/memory.py`, `backend/main.py`, `tests/backend/test_memory.py`.

- [ ] **Step 10.1 — Ajouter `apscheduler>=3.10` dans pyproject**

- [ ] **Step 10.2 — `LongTermMemory.cleanup_old_messages(days=30)`**

  SQL `DELETE FROM messages WHERE created_at < datetime('now', '-30 days')` + idem pour `decisions`. Retourne le nombre de lignes supprimées.

- [ ] **Step 10.3 — Scheduler dans `lifespan` de main.py**

  `AsyncIOScheduler` avec job quotidien (`interval`, `days=1`) qui lance `cleanup_old_messages(30)`. Log `{"removed": N}` via structlog.

- [ ] **Step 10.4 — Tests**

  Insérer 2 rows dans `messages` avec `created_at` mocké à -40j et aujourd'hui. Call cleanup(30) → doit supprimer la première, garder la seconde.

- [ ] **Step 10.5 — Commit via /commit**

---

# PHASE C — Packaging (app DISTRIBUABLE)

## Task 11 : Packaging Tauri + auto-update

**Files:** `ui/src-tauri/Cargo.toml`, `ui/src-tauri/tauri.conf.json`, `ui/src-tauri/icons/`, `.github/workflows/release.yml`.

- [ ] **Step 11.1 — Ajouter `tauri-plugin-updater = "2"` dans Cargo.toml**

- [ ] **Step 11.2 — Générer les icônes depuis un logo 1024×1024**

  `npx @tauri-apps/cli icon /path/to/logo.png` génère 32×32, 128×128, 128×128@2x, icon.icns, icon.ico dans `ui/src-tauri/icons/`.

- [ ] **Step 11.3 — Generate updater keypair**

  `npx @tauri-apps/cli signer generate -w ~/.tauri/localcoder-private.key`. Copier la pubkey dans `tauri.conf.json` sous `plugins.updater.pubkey`. **Garder la private key hors du repo** (stockée uniquement en GitHub Actions secret).

- [ ] **Step 11.4 — Configurer `tauri.conf.json` updater endpoints**

  `endpoints: ["https://github.com/Wissem95/localcoder-ide/releases/latest/download/latest.json"]`.

- [ ] **Step 11.5 — `.github/workflows/release.yml`**

  Workflow déclenché sur tag `v*`. Matrix os: macos-latest / ubuntu-latest / windows-latest. Installe Node 20 + Rust stable + deps système (linux only : libwebkit2gtk-4.1-dev, libappindicator3-dev, librsvg2-dev, patchelf). Lance `npm run tauri build`. Upload artefacts DMG/DEB/MSI via `softprops/action-gh-release`. Signer avec `TAURI_SIGNING_PRIVATE_KEY` et `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` (secrets repo).

- [ ] **Step 11.6 — Test build local**

  `cd ui && npm run tauri build`. Vérifier la présence de `ui/src-tauri/target/release/bundle/dmg/*.dmg`.

- [ ] **Step 11.7 — Commit via /commit**

---

## Task 12 : Menu bar macOS natif

**Files:** `ui/src-tauri/src/menu.rs`, `ui/src-tauri/src/lib.rs`.

- [ ] **Step 12.1 — `menu.rs` — fonction `build_menu(app) -> Menu<Wry>`**

  3 submenus :
  - **LocalCoder** : About, separator, Preferences (Cmd+,), separator, Quit.
  - **Édition** : undo, redo, separator, cut, copy, paste (PredefinedMenuItem).
  - **Affichage** : Palette de commandes (Cmd+K), separator, fullscreen.

- [ ] **Step 12.2 — Register + `on_menu_event` dans lib.rs**

  Match `event.id()` :
  - `"settings"` → `app.emit("open-settings", ())`
  - `"cmd_palette"` → `app.emit("open-command-palette", ())`

  Côté UI, `listen` via `@tauri-apps/api/event` et déclencher l'action correspondante.

- [ ] **Step 12.3 — Commit via /commit**

---

## Task 13 : Observabilité (structlog + métriques)

**Files:** `pyproject.toml`, `backend/logging_config.py`, `backend/main.py` + tous les modules.

- [ ] **Step 13.1 — Ajouter `structlog>=24` et `prometheus-client>=0.20` (optionnel)**

- [ ] **Step 13.2 — `logging_config.py` — `setup_logging(level)`**

  Config JSON renderer avec TimeStamper ISO, add_log_level, format_exc_info. Niveau par défaut INFO.

- [ ] **Step 13.3 — Remplacer `logging.getLogger` par `structlog.get_logger` dans tous les modules**

  Appels avec kwargs : `log.info("ticket_created", task_id=..., issue=...)`.

- [ ] **Step 13.4 — Endpoint `GET /metrics` (optionnel)**

  Compteurs Prometheus : `llm_calls_total{llm_id}`, `llm_duration_seconds{llm_id}` (Histogram). `generate_latest()` en text/plain.

- [ ] **Step 13.5 — Tests**

  `log.info("x", y=1)` produit un JSON parsable avec keys `timestamp`, `level`, `event`, `y`.

- [ ] **Step 13.6 — Commit via /commit**

---

# PHASE D — Features avancées (app COMPLÈTE)

## Task 14 : Mode Ollama (100% local, offline)

**Files:** `backend/llm_manager.py`, `backend/models.py`, `ui/src/components/Settings/SettingsTab.tsx`.

- [ ] **Step 14.1 — `detect_ollama()` — GET localhost:11434/api/tags via aiohttp, timeout 2s**

  Retourne la liste des modèles installés, ou `[]` si absent.

- [ ] **Step 14.2 — Étendre `LLMConfig` avec `is_local: bool`**

- [ ] **Step 14.3 — Modifier FALLBACK_CHAINS**

  Si `detect_ollama()` retourne des modèles, ajouter `ollama/qwen2.5-coder:14b` (ou `deepseek-coder-v2:16b`) en fin de chaque chain comme fallback privacy-first.

- [ ] **Step 14.4 — Settings UI : toggle "Privacy-first mode (Ollama only)"**

  Si activé : bypass les APIs cloud, route tout vers Ollama. Si Ollama non détecté → toast erreur.

- [ ] **Step 14.5 — Tests**

  Mock aiohttp ClientSession pour simuler Ollama up (200 JSON) / down (timeout).

- [ ] **Step 14.6 — Commit via /commit**

---

## Task 15 : Multi-project switcher

**Files:** `backend/workspace_registry.py`, `backend/orchestrator.py`, `backend/memory.py`, `ui/src/components/WorkspaceSwitcher.tsx`, `ui/src/stores/settingsStore.ts`.

- [ ] **Step 15.1 — `workspace_registry.py`**

  Dataclass `Workspace(id, name, path, last_opened)`. `WorkspaceRegistry` avec `workspaces: list[Workspace]`, `current_id: str | None`, méthodes `add(path)`, `switch(ws_id)`, `remove(ws_id)`.

- [ ] **Step 15.2 — Endpoints REST**

  - `POST /workspace/open` body `{path}` → add + switch
  - `GET /workspace/list` → liste
  - `POST /workspace/switch` body `{id}` → switch
  - `DELETE /workspace/{id}`

- [ ] **Step 15.3 — Colonne `workspace_id` dans toutes les tables de LongTermMemory**

  Migration SQL : `ALTER TABLE messages ADD COLUMN workspace_id TEXT;` etc. Tous les SELECT/INSERT filtrent/set sur le workspace courant.

- [ ] **Step 15.4 — UI `WorkspaceSwitcher.tsx`**

  Dropdown dans l'ActivityBar (ou en haut). Liste des workspaces + "+ Ouvrir un dossier" (appelle dialog Tauri natif).

- [ ] **Step 15.5 — Tests**

  Registry ajoute/switch/remove. Messages insérés avec workspace A ne remontent pas quand workspace B actif.

- [ ] **Step 15.6 — Commit via /commit**

---

## Task 16 : Templates CdC

**Files:** `backend/prompts/cdc_templates/*.md`, `backend/project_mode.py`, `ui/src/components/NewProjectModal.tsx`, `ui/src/components/tabs/ChatTab/ChatTab.tsx`.

- [ ] **Step 16.1 — 4 templates .md**

  - `SaaS.md` : auth (email+OAuth), subscription billing (Stripe), multi-tenancy, admin dashboard, landing page. Stack : Next.js + Postgres + Stripe.
  - `API.md` : REST pur, rate limiting, OpenAPI docs, auth JWT, tests contract.
  - `mobile-app.md` : React Native ou Flutter, nav, state management, push notifications, stores iOS/Android.
  - `CLI.md` : Click/Typer, tests coverage, packaging pip, homebrew tap.

  Chaque template = contraintes + stack reco + fonctionnalités must-have imposées.

- [ ] **Step 16.2 — `ProjectMode.generate_cdc(description, template=None)`**

  Si `template` : prepend le contenu de `cdc_templates/{template}.md` au system prompt. Sinon comportement actuel.

- [ ] **Step 16.3 — UI `NewProjectModal.tsx`**

  Wizard avec :
  - Step 1 : choix template (radio : SaaS / API / Mobile / CLI / Custom).
  - Step 2 : description libre (textarea).
  - Step 3 : GitHub config (owner/repo, token si pas déjà dans settings).
  - Bouton "Créer le projet" → `POST /project/start` avec `template` dans body.

- [ ] **Step 16.4 — Bouton "Nouveau projet" dans ChatTab**

  En haut du chat. Ouvre le modal. Remplace le comportement actuel (taper "crée une app X" dans le chat).

- [ ] **Step 16.5 — Tests**

  `generate_cdc("une app", template="SaaS")` → le prompt envoyé au LLM contient "Stripe" et "multi-tenancy".

- [ ] **Step 16.6 — Commit via /commit**

---

# Vérification finale Plan 5

- [ ] **Step Final.1 — Suite tests complète**

  - `source venv/bin/activate && python -m pytest tests/backend/ -v --tb=short` → cible **220+ passed**.
  - `cd ui && npx vitest run` → cible **130+ passed**.
  - `cargo check` dans `ui/src-tauri/` → Finished OK.

- [ ] **Step Final.2 — Tests live LLMs**

  Exporter les 4 API keys, lancer `pytest -m llm_live tests/backend/test_llm_manager.py`. Les 5 tests health check passent.

- [ ] **Step Final.3 — Build packaging**

  `cd ui && npm run tauri build` → DMG présent dans `target/release/bundle/dmg/`.

- [ ] **Step Final.4 — Test E2E manuel complet**

  1. Installe le DMG (glisse-dépose dans Applications).
  2. Lance `LocalCoder IDE.app`.
  3. Ouvre Settings (Cmd+,), colle DeepSeek API key, bouton "Tester" → vert.
  4. Tab Chat, écrit "Crée un fichier hello.py qui affiche hello world".
  5. Observe : tool_call edit_file déclenché. Vérifier que `hello.py` existe dans le workspace actuel.
  6. Cmd+K ouvre la palette de commandes → chercher "settings" → bascule dessus.
  7. Switch "Privacy-first mode" → re-envoyer même prompt → cette fois Ollama répond.
  8. Tab Monitoring : cost tracking cumulé en dollars.
  9. Settings → disable MiniMax → prochain prompt route vers DeepSeek.
  10. Fermer l'app → backend se termine gracieusement (SIGTERM visible dans les logs).

- [ ] **Step Final.5 — Documentation utilisateur**

  - `docs/USER_GUIDE.md` : install, première config, tutoriel 10 min.
  - `docs/API_KEYS_SETUP.md` : liens d'inscription + étapes pour chaque provider.
  - `docs/TROUBLESHOOTING.md` : erreurs fréquentes (backend down, CI webhook, LLM 429, etc.).

- [ ] **Step Final.6 — Release v2.0.0**

  - `git tag v2.0.0 && git push origin v2.0.0`
  - GitHub Actions `release.yml` se déclenche : build 3 plateformes, upload sur Releases.
  - Mettre à jour README avec badge version + lien Releases.

---

## Récap Plan 5

**16 tasks, 4 phases** :

| Phase | Tasks | Impact | Durée estimée |
|-------|-------|--------|---------------|
| A — Critique | 1-5 | Sans elles, l'app ne marche pas vraiment | 1-2 semaines |
| B — Important | 6-10 | Usage quotidien fluide | 1 semaine |
| C — Packaging | 11-13 | Distribution publique | 3-4 jours |
| D — Features | 14-16 | Différenciation | 4-5 jours |

**Total** : ≈ 3-4 semaines à temps plein.

**Dépendances ajoutées** : `tiktoken`, `structlog`, `apscheduler`, `prometheus-client` (optionnel), `sonner`, `shiki`, `cmdk`, `@tauri-apps/plugin-store`, `@tauri-apps/plugin-updater`, `tauri-plugin-store`, `tauri-plugin-updater`.

**Artefacts finaux** :
- DMG / DEB / MSI publics sur GitHub Releases (signés Tauri updater)
- Tests 220+ pytest + 130+ vitest
- Documentation utilisateur complète (install, API keys, troubleshooting)
- Privacy-first mode (Ollama) activable
- Templates CdC (SaaS / API / Mobile / CLI)
- Multi-workspace natif
- Cost tracking réel (tokens × prix par modèle)
- Menu bar macOS natif + shortcuts complets

**Post-Plan 5** (v2.1+, non couvert) : marketplace de templates communautaires, plugins tierce partie, mode collaboratif temps réel (Yjs), intégration Slack/Discord, benchmarks LLM automatisés, mode agent autonome 24/7.

---

*Plan 5 conclut le cycle v2 : Plans 1+2+3+4+5 = LocalCoder IDE v2.0.0 distribuable. Versions futures = v2.1, v2.2, v3...*
