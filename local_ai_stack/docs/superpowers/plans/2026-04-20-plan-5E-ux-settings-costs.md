# LocalCoder IDE v2.1 — Plan 5E : UX raffinée + Settings + Cost tracking

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`. TDD strict obligatoire.

**Goal :** Polir l'UX au quotidien : toasts d'erreur/succès, syntax highlighting dans le chat, keyboard shortcuts + command palette, Settings UI avec persistance, cost tracking temps réel avec calibration delta estimé/réel.

**Architecture :** Sonner pour toasts, shiki pour syntax highlight, cmdk pour command palette, tauri-plugin-store pour persistence settings + API keys. Backend charge les API keys depuis `~/Library/Application Support/LocalCoder/settings.json` au boot. CostTracker alimente MonitoringTab avec breakdown par LLM + par étape + calibration correction_factor.

**Tech stack ajouté :** `sonner`, `shiki`, `cmdk`, `@tauri-apps/plugin-store`, `tauri-plugin-store`, `platformdirs` (Python).

**Prérequis :** Plans 5A + 5B + 5C + 5D complets. Pipeline 11 étapes fonctionnel.

**Durée estimée :** 1 semaine (5-7 jours full-time).

**Résultat attendu :**
- 340+ tests pytest verts.
- 180+ tests vitest verts.
- Toasts d'erreur / succès WS.
- Syntax highlight dans MessageBubble.
- Cmd+K ouvre command palette.
- Settings UI avec API keys persistées + LLM toggles.
- MonitoringTab : coût temps réel, breakdown par LLM/étape, delta estimé/réel, calibration correction_factor.

---

## Fichiers créés ou modifiés

```
backend/
├── cost_tracker.py                     # CRÉÉ — accumulateur + calibration
├── settings_loader.py                  # CRÉÉ — load settings.json cross-platform
├── main.py                             # MODIFIÉ — settings/api-key endpoint + boot load
├── memory.py                           # MODIFIÉ — table pipeline_runs avec actual_cost
└── pipeline/orchestrator.py            # MODIFIÉ — CostTracker intégré

tests/backend/
├── test_cost_tracker.py                # CRÉÉ
├── test_settings_loader.py             # CRÉÉ
└── test_main_settings.py               # CRÉÉ

ui/src/
├── components/
│   ├── Toasts/
│   │   └── Toaster.tsx                 # CRÉÉ — wrapper Sonner
│   ├── Settings/
│   │   ├── SettingsTab.tsx             # CRÉÉ
│   │   ├── ApiKeysForm.tsx             # CRÉÉ
│   │   ├── LLMTogglesForm.tsx          # CRÉÉ
│   │   └── PipelineSettingsForm.tsx    # CRÉÉ — seuils cost, cap budget
│   ├── CommandPalette/
│   │   └── CommandPalette.tsx          # CRÉÉ
│   ├── tabs/
│   │   ├── ChatTab/
│   │   │   ├── CodeBlock.tsx           # CRÉÉ — shiki
│   │   │   └── MessageBubble.tsx       # MODIFIÉ — render code blocks
│   │   └── MonitoringTab/
│   │       ├── CostBreakdown.tsx       # CRÉÉ — par LLM + par étape
│   │       ├── CalibrationTable.tsx    # CRÉÉ — delta estimé/réel
│   │       └── MonitoringTab.tsx       # MODIFIÉ — intègre CostBreakdown
├── stores/
│   ├── settingsStore.ts                # CRÉÉ
│   └── costStore.ts                    # CRÉÉ — en temps réel via WS
├── hooks/
│   └── useKeyboardShortcuts.ts         # CRÉÉ
└── App.tsx                             # MODIFIÉ — Toaster, palette, settings tab
```

---

# PHASE E1 — Cost tracking (Tasks 1-2)

## Task 1 : Backend CostTracker + calibration

**Files:** `backend/cost_tracker.py`, `backend/memory.py` (MODIFIÉ), `tests/backend/test_cost_tracker.py`.

**Durée :** 1 jour.

- [ ] **Step 1.1 — Tests rouges CostTracker**

  - `CostTracker()` vide initialement.
  - `track(llm, stage, tokens_in, tokens_out)` accumule.
  - `total_cost()` retourne dict {total_usd, per_llm, per_stage}.
  - `by_llm("minimax/...")` retourne dict {tokens_in, tokens_out, cost_usd}.
  - Persist en LongTermMemory via méthode `persist_to_db(session_id)`.

- [ ] **Step 1.2 — Implémenter `cost_tracker.py`**

  Dataclass avec dicts accumulateurs par LLM et par étape. Utilise `estimate_cost` de cost_estimator pour calculer.

  Méthode `get_correction_factor(mode)` : lit les 50 derniers rows `pipeline_runs` du mode donné, calcule `mean(actual_cost / estimated_cost)`. Retourne 1.0 si < 5 runs dispo.

- [ ] **Step 1.3 — Table pipeline_runs**

  Migration SQL dans `_CREATE_TABLES_SQL` de memory.py avec colonnes : id, session_id, prompt, mode, estimated_cost, actual_cost, estimated_tokens, actual_tokens, estimated_duration_s, actual_duration_s, success (INTEGER 0/1), rollback_reason, stages_json, created_at.

  Méthodes `LongTermMemory.save_pipeline_run(...)`, `get_recent_runs(mode, limit)`.

- [ ] **Step 1.4 — Intégrer CostTracker dans Pipeline orchestrator**

  Pipeline crée un `CostTracker` par run. Chaque stage → `tracker.track(...)`. À la fin → persist via `save_pipeline_run`.

  Appliquer `correction_factor` dans `Stage0Estimate._execute` : multiplie l'estimation par le facteur appris.

- [ ] **Step 1.5 — Tests calibration**

  Insérer 10 rows fake dans pipeline_runs avec ratio actual/estimated=1.2, vérifier que `get_correction_factor("simple") == 1.2`.

- [ ] **Step 1.6 — Commit**

---

## Task 2 : UI CostBreakdown + CalibrationTable

**Files:** `ui/src/stores/costStore.ts`, `ui/src/components/tabs/MonitoringTab/CostBreakdown.tsx`, `CalibrationTable.tsx`, `MonitoringTab.tsx` (MODIFIÉ).

**Durée :** 1 jour.

- [ ] **Step 2.1 — costStore.ts**

  Zustand store :
  - State : `currentPipelineCost, totalSessionCost, costByLLM, costByStage, recentRuns`.
  - Handlers WS : `token_usage`, `stage_complete` (ajoute le cost_usd), `pipeline_complete` (ajoute à recentRuns).

- [ ] **Step 2.2 — CostBreakdown.tsx**

  Deux barres :
  - Par LLM : barre horizontale par LLM avec coût + pourcentage.
  - Par étape : pareil par étape.

  Total en bas.

- [ ] **Step 2.3 — CalibrationTable.tsx**

  Tableau des 20 derniers runs : prompt (tronqué), mode, estimé, réel, delta%, durée, statut (✅/❌).

  Ligne de résumé en bas : "Correction factor actuel : simple=1.05 / medium=0.95 / complex=1.12".

- [ ] **Step 2.4 — Intégrer dans MonitoringTab**

  Layout : sys stats + CostBreakdown en haut, CalibrationTable dessous pleine largeur.

- [ ] **Step 2.5 — Tests vitest**

- [ ] **Step 2.6 — Commit**

---

# PHASE E2 — Toasts + Syntax highlight (Tasks 3-4)

## Task 3 : Toasts (Sonner)

**Files:** `ui/src/components/Toasts/Toaster.tsx`, `ui/src/App.tsx` (MODIFIÉ), `ui/src/ws.ts` (MODIFIÉ), tests.

**Durée :** 0.5 jour.

- [ ] **Step 3.1 — `npm install sonner`**

- [ ] **Step 3.2 — Toaster.tsx**

  Wrapper du `<Toaster>` de Sonner. Thème dark aligné sur palette LocalCoder. Position bottom-right.

- [ ] **Step 3.3 — Connecter events WS aux toasts**

  Dans `main.tsx` ou `App.tsx` :
  - `ws.on("disconnect")` → `toast.warning("Connexion backend perdue")`.
  - `ws.on("error")` → `toast.error(data.message)`.
  - Transition connecting→ready → `toast.success("Backend connecté")`.
  - `pipeline_rollback` → `toast.info("Rollback effectué, état restauré")`.
  - `pipeline_complete` avec success → `toast.success("Pipeline terminé ($X.XX)")`.
  - `pipeline_complete` avec échec → `toast.error("Pipeline échoué : " + reason)`.

- [ ] **Step 3.4 — Tests vitest**

  Mock sonner, simuler events, vérifier appels toast correspondants.

- [ ] **Step 3.5 — Commit**

---

## Task 4 : Syntax highlighting (shiki)

**Files:** `ui/src/components/tabs/ChatTab/CodeBlock.tsx`, `MessageBubble.tsx` (MODIFIÉ), tests.

**Durée :** 1 jour.

- [ ] **Step 4.1 — `npm install shiki`**

- [ ] **Step 4.2 — CodeBlock.tsx**

  Async component : appelle `codeToHtml(code, {lang, theme: "github-dark"})` de shiki.

  Fallback `<pre>` pendant le load async. Gestion erreur si lang inconnu → fallback "text".

  Le HTML produit par shiki est passé par DOMPurify avant l'injection HTML React pour défense en profondeur (le HTML shiki est normalement safe car pré-généré à partir de tokens, mais le wrap DOMPurify protège contre toute régression).

- [ ] **Step 4.3 — MessageBubble parser**

  Split content via regex triple-backtick multiline : `/```(\w+)?\n([\s\S]*?)```/g`.

  Alterner `<p>` pour texte et `<CodeBlock>` pour blocs.

- [ ] **Step 4.4 — Tests snapshot**

  Message avec bloc ```python / ```ts → snapshot HTML.

- [ ] **Step 4.5 — Commit**

---

# PHASE E3 — Shortcuts + Command Palette (Tasks 5-6)

## Task 5 : useKeyboardShortcuts hook

**Files:** `ui/src/hooks/useKeyboardShortcuts.ts`, `ui/src/App.tsx` (MODIFIÉ).

**Durée :** 0.5 jour.

- [ ] **Step 5.1 — Hook**

  `useKeyboardShortcuts(shortcuts: Array<{key, cmdOrCtrl, shift, handler}>)`.

  useEffect attache un listener global sur `keydown`. Gère `metaKey || ctrlKey` selon flag.

- [ ] **Step 5.2 — Enregistrer shortcuts dans App.tsx**

  - `Cmd+K` → ouvre command palette.
  - `Cmd+1..4` → switch tab.
  - `Cmd+,` → open Settings.
  - `Cmd+.` → stop pipeline (déjà partiellement en 5B).
  - `Cmd+Enter` dans ChatInput → send prompt.

- [ ] **Step 5.3 — Tests vitest**

  Simuler keydown via React Testing Library, vérifier handler appelé.

- [ ] **Step 5.4 — Commit**

---

## Task 6 : Command Palette (cmdk)

**Files:** `ui/src/components/CommandPalette/CommandPalette.tsx`, `ui/src/App.tsx` (MODIFIÉ).

**Durée :** 1 jour.

- [ ] **Step 6.1 — `npm install cmdk`**

- [ ] **Step 6.2 — CommandPalette.tsx**

  Modal cmdk avec input search + liste d'actions :
  - "Switch to Chat" / "Switch to Routing" / "Switch to Monitoring" / "Switch to Terminals".
  - "Open Settings".
  - "Toggle LLM: MiniMax" / "Toggle LLM: Gemini Pro" etc.
  - "Start new project".
  - "Stop current pipeline" (si pipeline actif).
  - "Clear chat history".
  - "Show last cost breakdown".

  Fermeture sur Escape ou click extérieur.

- [ ] **Step 6.3 — Tests vitest**

  Render, simuler keyboard navigation, vérifier actions.

- [ ] **Step 6.4 — Commit**

---

# PHASE E4 — Settings UI (Tasks 7-8)

## Task 7 : Backend settings loader + endpoints

**Files:** `backend/settings_loader.py`, `backend/main.py` (MODIFIÉ), `tests/backend/test_settings_loader.py`, `test_main_settings.py`.

**Durée :** 1 jour.

- [ ] **Step 7.1 — pyproject ajouter `platformdirs`**

- [ ] **Step 7.2 — Tests rouges settings_loader**

  - `get_settings_path()` retourne path cross-platform (~/Library/Application Support/LocalCoder/settings.json sur mac).
  - `load_settings()` retourne dict vide si absent, parse JSON sinon.
  - `save_settings(data)` crée dir + écrit.
  - `load_api_keys_into_env()` pose `os.environ["DEEPSEEK_API_KEY"]` etc. selon le JSON.

- [ ] **Step 7.3 — Implémenter `settings_loader.py`**

  Utilise `platformdirs.user_config_dir("LocalCoder")`.

- [ ] **Step 7.4 — Endpoint POST /settings/api-key**

  Body `{provider, value}`. Mappe provider → env var. Pose dans `os.environ` + merge dans settings.json + save.

- [ ] **Step 7.5 — Boot : load settings au démarrage**

  Dans `lifespan()` de main.py : appeler `load_api_keys_into_env()` AVANT création LLMManager (pour que les clés soient dispo).

- [ ] **Step 7.6 — Endpoint GET /settings**

  Retourne le dict settings (masque les API keys avec `***` sauf les 4 derniers chars).

- [ ] **Step 7.7 — Commit**

---

## Task 8 : UI Settings Tab

**Files:** `ui/src-tauri/Cargo.toml` (MODIFIÉ), `ui/src/stores/settingsStore.ts`, `ui/src/components/Settings/*.tsx`, `App.tsx` (MODIFIÉ).

**Durée :** 1.5 jour.

- [ ] **Step 8.1 — Installer plugin store**

  Ajouter `tauri-plugin-store = "2"` dans Cargo.toml + `@tauri-apps/plugin-store` npm.

- [ ] **Step 8.2 — settingsStore.ts**

  Zustand + persistence via plugin store.

  State :
  - `apiKeys: {deepseek, minimax, gemini, mistral}`.
  - `llmsEnabled: {llm_id: boolean}`.
  - `pipelineSettings: {autoApproveUsd, capBudgetUsd, alwaysConfirmComplex}`.

  Actions :
  - `setApiKey(provider, value)` → persist + POST /settings/api-key.
  - `toggleLLM(id)` → persist + POST /llms/{id}/(dis|en)able.

- [ ] **Step 8.3 — ApiKeysForm.tsx**

  4 inputs type password. Bouton "Tester" par provider qui appelle `/llms/health?provider=X` → indicateur vert/rouge.

- [ ] **Step 8.4 — LLMTogglesForm.tsx**

  Liste 5 LLMs avec checkbox et rôle affiché.

- [ ] **Step 8.5 — PipelineSettingsForm.tsx**

  Sliders/inputs pour :
  - Seuil auto-approve : défaut $0.05, range $0-$1.
  - Cap budget par pipeline : défaut $1.00, range $0.10-$10.
  - Toggle "Toujours confirmer mode complex".
  - Toggle "Activer mode économie par défaut" (→ skip CHALLENGE/REVIEW).

- [ ] **Step 8.6 — SettingsTab.tsx**

  Container avec 3 sections : API Keys, LLMs actifs, Pipeline.

- [ ] **Step 8.7 — Ajouter dans TAB_ORDER**

  App.tsx : `settings` tab + lazy import.

- [ ] **Step 8.8 — Tests vitest**

  Form saisit une clé → store set → POST émis.

- [ ] **Step 8.9 — Commit**

---

# PHASE E5 — Tests E2E + Release (Task 9)

## Task 9 : Tests E2E + push + tag alpha.5

**Files:** `tests/backend/test_e2e_full_ux.py`, README MAJ, tag.

**Durée :** 1 jour.

- [ ] **Step 9.1 — Test E2E boot load settings**

  Insérer settings.json avec DEEPSEEK_API_KEY. Start backend. Vérifier `os.environ["DEEPSEEK_API_KEY"]` correctement posé.

- [ ] **Step 9.2 — Test E2E calibration après N runs**

  Insérer 10 rows pipeline_runs avec ratio actual/estimated=1.15. Vérifier que Stage0Estimate sur nouveau prompt retourne un coût multiplié par 1.15.

- [ ] **Step 9.3 — Test UI E2E**

  (Playwright en manuel uniquement ou vitest avec mocks) :
  - Ouvrir Settings → saisir API key → toast success.
  - Cmd+K → palette ouvre.
  - Send prompt → ChatTab affiche avec syntax highlight des blocs code.

- [ ] **Step 9.4 — Suite tests complète**

  - pytest → 340+ verts.
  - vitest → 180+ verts.

- [ ] **Step 9.5 — Push distant + tag v2.1.0-alpha.5**

- [ ] **Step 9.6 — Checkpoint Plan 5E**

- [ ] **Step 9.7 — Commit final**

---

## Vérification finale Plan 5E

- [ ] 340+ tests pytest, 180+ tests vitest.
- [ ] Settings UI : API keys saisies, testées, persistées, rechargées au boot.
- [ ] Toasts sur events WS critiques.
- [ ] Syntax highlight dans MessageBubble.
- [ ] Cmd+K ouvre palette fonctionnelle.
- [ ] MonitoringTab : CostBreakdown temps réel + CalibrationTable.
- [ ] Correction factor appliqué après 5+ runs.

---

## Récap Plan 5E

**9 tasks, 5 phases** :

| Phase | Tasks | Impact | Durée |
|-------|-------|--------|-------|
| E1 Cost tracking | 1-2 | Visibilité coûts + calibration | 2 jours |
| E2 Toasts + syntax | 3-4 | Feedback UX + lisibilité code | 1.5 jour |
| E3 Shortcuts + palette | 5-6 | Productivité user | 1.5 jour |
| E4 Settings UI | 7-8 | Configuration user + persistence | 2.5 jours |
| E5 E2E + Release | 9 | Validation bout-en-bout | 1 jour |

**Total : ~8.5 jours (1.5 semaine full-time).**

**Post-Plan 5E :** Plan 5F packaging + Ollama + release v2.0.0 publique.

---

*Plan 5E validation-ready après Plan 5D livré.*
