# LocalCoder IDE v2.1 — Plan 5A : Fondations pipeline + Grounding + ESTIMATE

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. TDD strict obligatoire.

**Goal :** Poser les fondations du pipeline rigoureux — package `backend/pipeline/`, tool-calling (`backend/tools/`), cost estimator, étape 0 ESTIMATE avec modal UI, étape 1 INTAKE minimale, étape 3 GROUND avec tools read-only, étape 5 EXECUTE avec tools write. À la fin de Plan 5A, un prompt simple produit un fichier réellement modifié via le pipeline.

**Architecture :** Pipeline remplace `AgentLoop`. Orchestrator dispatche vers Pipeline. Mode simple uniquement à ce stade (5 étapes : 0, 1, 3, 5, 7). Mode medium/complex arrivent en Plans 5C/5D.

**Tech stack ajouté :** `tiktoken>=0.7`, `litellm>=1.81` (déjà en place avec tool-calling).

**Prérequis :**
- Plans 1-4 + Phase 2 complets (pushed sur main distant).
- Spec de référence : `docs/superpowers/specs/2026-04-20-pipeline-rigoureux.md`.
- Venv Python activé (`source venv/bin/activate`).
- API keys exportées manuellement par user pour tests live (voir Task 1).

**Durée estimée :** 1.5 semaine (10-12 jours full-time).

**Résultat attendu :**
- 200+ tests pytest verts (157 actuels + ~50 nouveaux).
- 120+ tests vitest verts (105 actuels + ~15 nouveaux).
- Un prompt simple comme "Crée un fichier hello.py qui print 'hi'" déclenche le pipeline complet mode simple et produit le fichier sur disque.

---

## Fichiers créés ou modifiés

```
backend/
├── pipeline/                          # CRÉÉ — package complet
│   ├── __init__.py
│   ├── base.py                        # Stage base class + StageResult types
│   ├── orchestrator.py                # Pipeline orchestrateur (dispatch stages)
│   ├── stage_0_estimate.py
│   ├── stage_1_intake.py
│   ├── stage_3_ground.py
│   ├── stage_5_execute.py
│   ├── stage_7_verify.py              # (minimal, étendu Plan 5B)
│   └── types.py                       # TypedDicts communes
│
├── tools/                             # CRÉÉ — package complet
│   ├── __init__.py
│   ├── registry.py                    # TOOLS_SCHEMA + dispatcher
│   ├── file_ops.py                    # read/edit/patch/create/delete/list
│   ├── search.py                      # grep_codebase
│   └── exceptions.py                  # ToolError, PathOutsideWorkspace
│
├── cost_estimator.py                  # CRÉÉ — PRICING dict + estimate()
├── orchestrator.py                    # MODIFIÉ — dispatch vers Pipeline
├── llm_manager.py                     # MODIFIÉ — health_check + tool_calling support
├── memory.py                          # MODIFIÉ — table pipeline_runs
├── main.py                            # MODIFIÉ — endpoint /llms/health, WS events
│
└── prompts/
    ├── stage_0_estimate.md
    ├── stage_1_intake.md
    ├── stage_3_ground.md
    └── stage_5_execute.md

tests/backend/
├── test_llm_manager.py                # MODIFIÉ — live tests + health_check
├── test_cost_estimator.py             # CRÉÉ
├── test_tools_file_ops.py             # CRÉÉ
├── test_tools_search.py               # CRÉÉ
├── test_tools_registry.py             # CRÉÉ
├── test_pipeline_orchestrator.py      # CRÉÉ
├── test_stage_0_estimate.py           # CRÉÉ
├── test_stage_1_intake.py             # CRÉÉ
├── test_stage_3_ground.py             # CRÉÉ
├── test_stage_5_execute.py            # CRÉÉ
├── test_stage_7_verify.py             # CRÉÉ (minimal)
└── test_pipeline_e2e_simple.py        # CRÉÉ — prompt simple → fichier créé

tests/fixtures/
├── scripted_llm.py                    # CRÉÉ — LLM scripté pour tests
└── mock_tool_calls.py                 # CRÉÉ — réponses tool_calls scriptées

ui/src/
├── components/
│   ├── Pipeline/
│   │   ├── EstimateModal.tsx          # CRÉÉ — modal coût avant lancement
│   │   ├── TraceViewer.tsx            # CRÉÉ — affichage pipeline temps réel
│   │   └── StageRow.tsx               # CRÉÉ — une ligne d'étape
│   └── tabs/RoutingTab/
│       └── RoutingTab.tsx             # MODIFIÉ — intègre TraceViewer
│
├── stores/
│   └── pipelineStore.ts               # CRÉÉ — state pipeline actif
│
└── types/
    └── pipeline.ts                    # CRÉÉ — types TypeScript alignés backend

scripts/
└── smoke_llms.sh                      # CRÉÉ — sanity check LLMs live

pyproject.toml                         # MODIFIÉ — tiktoken dependency
```

---

# PHASE A1 — Prérequis (Tasks 1-3)

## Task 1 : LLMs réels + health_check + smoke script

**Files:** `backend/llm_manager.py`, `backend/main.py`, `tests/backend/test_llm_manager.py`, `scripts/smoke_llms.sh`.

**Durée :** 1 jour.

- [ ] **Step 1.1 — Tests rouges health_check**

  Dans `tests/backend/test_llm_manager.py`, ajouter 2 tests :
  - `test_health_check_returns_ok_latency_error` : mock `acompletion` renvoyant un message succès → `{ok: True, latency_ms: int, error: None}`.
  - `test_health_check_returns_error_on_failure` : mock lève RuntimeError → `{ok: False, error: "down"}`.

  Vérifier : tests FAIL (méthode n'existe pas).

- [ ] **Step 1.2 — Implémenter `LLMManager.health_check(llm_id)`**

  Ajouter méthode async qui ping le LLM avec `max_tokens=1, timeout=10` et mesure la latence via `perf_counter`. Retourne dict avec `ok`, `latency_ms`, `error`.

  Vérifier : tests verts.

- [ ] **Step 1.3 — Endpoint `GET /llms/health`**

  Dans `backend/main.py`, nouvelle route qui lance `health_check` sur les 5 LLMs via `asyncio.gather` et retourne un dict `{llm_id: result}`.

  Ajouter test dans `tests/backend/test_main.py`.

- [ ] **Step 1.4 — Tests live (skippés sans API key)**

  Ajouter marker `@pytest.mark.llm_live` dans tests + skip conditionnel sur présence env var. Un test par provider (DeepSeek, MiniMax, Gemini, Mistral).

  Enregistrer le marker dans `pyproject.toml` section `[tool.pytest.ini_options.markers]`.

- [ ] **Step 1.5 — Script `scripts/smoke_llms.sh`**

  Script bash qui active le venv et lance `pytest tests/backend/test_llm_manager.py -m llm_live -v`.

  Documenté dans README : utilisateur doit exporter les 4 API keys avant de lancer.

- [ ] **Step 1.6 — Commit via skill `commit-commands:commit`**

  Message type : "feat(backend): LLM health_check endpoint + live smoke tests".

---

## Task 2 : Tokenizer tiktoken

**Files:** `backend/context_builder.py`, `tests/backend/test_context_builder.py`, `pyproject.toml`.

**Durée :** 0.5 jour.

- [ ] **Step 2.1 — Ajouter `tiktoken>=0.7` dans pyproject.toml**, puis `pip install -e .`.

- [ ] **Step 2.2 — Tests rouges `count_tokens`**

  Trois tests :
  - `count_tokens("hello world")` retourne entre 1 et 5.
  - Texte long (400 répétitions) retourne entre 400 et 800.
  - Modèle inconnu → fallback `len(text) // 4`.

- [ ] **Step 2.3 — Implémenter `count_tokens(text, model="gpt-4o")`**

  Utilise `tiktoken.encoding_for_model` avec cache `_ENC_CACHE`. Fallback `len // 4` si KeyError.

- [ ] **Step 2.4 — Commit**

---

## Task 3 : Cost Estimator

**Files:** `backend/cost_estimator.py`, `tests/backend/test_cost_estimator.py`.

**Durée :** 1 jour.

- [ ] **Step 3.1 — Tests rouges cost_estimator**

  Trois tests :
  - `PRICING` contient les 5 LLMs avec clés `input_per_million` et `output_per_million`.
  - `estimate_cost("gemini/gemini-2.5-flash", 1_000_000, 1_000_000)` = 0.375 ± 0.01.
  - `estimate_pipeline_cost(prompt, mode="simple")` retourne dict avec `classification`, `estimated_cost_usd` < $0.01, et stage_estimates contenant `intake`, `ground`, `execute`.

- [ ] **Step 3.2 — Implémenter `cost_estimator.py`**

  Contenu :
  - `PRICING: dict[str, dict[str, float]]` avec prix sept 2025 pour les 5 LLMs.
  - `STAGE_LLM_MAP` : mapping nom étape → LLM dédié (voir spec §2.2).
  - `STAGE_TOKEN_ESTIMATES` : estimations tokens in/out par étape par mode (simple/medium/complex).
  - `estimate_cost(llm, in_tokens, out_tokens) -> float`.
  - `estimate_pipeline_cost(prompt, mode, files_hint) -> dict` retourne `{classification, estimated_cost_usd, estimated_tokens_in, estimated_tokens_out, stage_estimates, estimated_duration_seconds, estimated_files_touched}`.

- [ ] **Step 3.3 — Commit**

---

# PHASE A2 — Tools (Tasks 4-5)

## Task 4 : Tools file_ops

**Files:** `backend/tools/exceptions.py`, `backend/tools/file_ops.py`, `tests/backend/test_tools_file_ops.py`.

**Durée :** 1.5 jour.

- [ ] **Step 4.1 — Créer package `backend/tools/`** avec `__init__.py` vide + `exceptions.py`.

  Exceptions : `ToolError(Exception)` avec kwarg `stage`, `PathOutsideWorkspace(ToolError)`.

- [ ] **Step 4.2 — Tests rouges file_ops**

  6 tests :
  - `read_file` lit un fichier existant, tronque si > max_bytes, échec si absent.
  - `edit_file` écrit un fichier, acquiert le file lock, refuse path hors workspace.
  - `patch_file` remplace une chaîne unique, échec si chaîne non-unique ou absente.
  - `create_file` crée un fichier, échoue si existe.
  - `delete_file` supprime un fichier.
  - `list_files` liste non-récursive, ignore dossiers exclus.

  Liste exclusion : `.git`, `node_modules`, `venv`, `__pycache__`, `dist`, `build`.

- [ ] **Step 4.3 — Implémenter `file_ops.py`**

  Helper `_resolve(path, workspace_root)` qui `Path.resolve()` et vérifie que `workspace_root.resolve()` est ancêtre. Sinon lève `PathOutsideWorkspace`.

  6 fonctions async publiques :
  - `read_file(path, workspace_root, max_bytes=100_000) -> dict` retourne `{success, content, truncated}`.
  - `edit_file(path, content, file_lock, workspace_root, llm_id) -> dict` retourne `{success, bytes_written}`.
  - `patch_file(path, old_str, new_str, file_lock, workspace_root, llm_id) -> dict`. Vérifie unicité de `old_str` avant remplacement.
  - `create_file(path, content, file_lock, workspace_root, llm_id) -> dict`. Échec si fichier existe.
  - `delete_file(path, file_lock, workspace_root, llm_id) -> dict`.
  - `list_files(path, workspace_root, recursive=False) -> dict` retourne `{success, files: [...]}`.

  Chaque fonction acquiert/libère le `file_lock` proprement.

- [ ] **Step 4.4 — Commit**

---

## Task 5 : Tools search + registry

**Files:** `backend/tools/search.py`, `backend/tools/registry.py`, `tests/backend/test_tools_search.py`, `tests/backend/test_tools_registry.py`.

**Durée :** 1 jour.

- [ ] **Step 5.1 — Tests rouges search**

  Test `grep_codebase` : 2 fichiers Python avec `foo` → retourne 2 matches avec `file`, `line`, `excerpt`.
  Test exclusion : fichier dans `node_modules/` non scanné.

- [ ] **Step 5.2 — Implémenter `search.py`**

  Fonction async `grep_codebase(pattern, path_glob="**/*", workspace_root, max_results=50) -> list[dict]`.

  Implémentation Python pure avec `pathlib.glob` + `re.compile`. Saut des dossiers exclus (mêmes que file_ops). Lecture avec `errors="ignore"` pour skip les binaires.

- [ ] **Step 5.3 — Tests rouges registry**

  Trois tests :
  - `TOOLS_SCHEMA_READ` contient au moins `read_file`, `grep_codebase`, `list_files`.
  - `TOOLS_SCHEMA_WRITE` inclut TOOLS_SCHEMA_READ + `edit_file`, `create_file`, `patch_file`, `delete_file`.
  - `execute_tool("read_file", {"path": "a.txt"}, ...)` retourne `{success: True, content: ...}`.

- [ ] **Step 5.4 — Implémenter `registry.py`**

  Deux listes `TOOLS_SCHEMA_READ` et `TOOLS_SCHEMA_WRITE` au format JSON Schema compatible OpenAI/Anthropic function-calling (voir spec §5.1).

  Fonction `execute_tool(name, args, file_lock, workspace_root) -> dict` : dispatcher qui route vers `backend.tools.file_ops.*` ou `backend.tools.search.*`.

  Si nom de tool inconnu → retourne `{success: False, error: "unknown tool"}`.

- [ ] **Step 5.5 — Commit**

---

# PHASE A3 — Pipeline Core (Tasks 6-11)

## Task 6 : Pipeline base + types

**Files:** `backend/pipeline/types.py`, `backend/pipeline/base.py`, `backend/pipeline/__init__.py`, `tests/backend/test_pipeline_base.py`.

**Durée :** 1 jour.

- [ ] **Step 6.1 — Définir les types dans `types.py`**

  Dataclasses :
  - `PipelineMode(str, Enum)` : SIMPLE / MEDIUM / COMPLEX.
  - `PipelineContext` : `prompt, workspace_root, session_id, mode, mention, stage_results, total_cost_usd, total_tokens`.
  - `StageResult` : `stage_name, llm_used, duration_ms, tokens_in, tokens_out, cost_usd, output, success, error`.
  - `PipelineResult` : `success, files_modified, stages, total_cost_usd, total_duration_ms, rollback_performed, error`.

- [ ] **Step 6.2 — Stage base class dans `base.py`**

  Classe abstraite `Stage(ABC)` :
  - Attribut `name: str`.
  - `__init__(llm_manager, ws_streamer)`.
  - Méthode `run(ctx) -> StageResult` (template method) qui :
    1. émet event `stage_start`,
    2. appelle `_execute(ctx)` (abstract),
    3. mesure durée via `perf_counter`,
    4. construit StageResult,
    5. émet event `stage_complete`,
    6. capture exceptions → retourne StageResult avec `success=False`.
  - Méthode virtuelle `_llm_for_stage() -> Optional[str]` pour override par les sous-classes.

- [ ] **Step 6.3 — Tests base**

  Créer une `DummyStage(Stage)` dont `_execute` retourne un dict. Vérifier :
  - `run` appelle `ws.broadcast_event("stage_start", ...)` puis `stage_complete`.
  - Retour = `StageResult` avec `duration_ms > 0`.
  - Exception dans `_execute` → `StageResult(success=False, error=...)`.

- [ ] **Step 6.4 — Commit**

---

## Task 7 : Stage 0 ESTIMATE

**Files:** `backend/pipeline/stage_0_estimate.py`, `backend/prompts/stage_0_estimate.md`, `tests/backend/test_stage_0_estimate.py`.

**Durée :** 1 jour.

- [ ] **Step 7.1 — System prompt `stage_0_estimate.md`**

  Markdown strict décrivant :
  - Rôle : classifier un prompt utilisateur.
  - Sortie JSON stricte : `{classification, reason, files_hint, confidence, ambiguities}`.
  - Règles : simple = 1 fichier <20 lignes ; medium = 2-3 fichiers locaux ; complex = 4+ fichiers ou archi.
  - Mots-clés projet forcent complex.
  - Interdiction de texte hors JSON.

- [ ] **Step 7.2 — Tests rouges ESTIMATE**

  Deux tests :
  - Mock LLMManager retourne JSON simple → stage retourne `classification="simple"` et `estimated_cost_usd < 0.01`.
  - Mock retourne texte avec JSON enveloppé → parser extrait correctement.

- [ ] **Step 7.3 — Implémenter `Stage0Estimate`**

  Hérite de `Stage`, `name = "estimate"`, `_llm_for_stage()` retourne `"gemini/gemini-2.5-flash"`.

  `_execute(ctx)` :
  1. Charge system prompt depuis MD file.
  2. Appelle `llm.call_with_fallback(role=ROUTING, messages=[system, user], temperature=0.1, timeout=10)`.
  3. Parse JSON avec regex fallback (match `{.*}`).
  4. Enrichit avec `estimate_pipeline_cost(ctx.prompt, mode, files_hint)`.
  5. Retourne dict merged.

- [ ] **Step 7.4 — Commit**

---

## Task 8 : Stage 1 INTAKE (minimal)

**Files:** `backend/pipeline/stage_1_intake.py`, `backend/prompts/stage_1_intake.md`, `tests/backend/test_stage_1_intake.py`.

**Durée :** 0.5 jour.

- [ ] **Step 8.1 — System prompt `stage_1_intake.md`** : rôle validation non-ambiguïté.

- [ ] **Step 8.2 — Tests rouges**

  Deux tests :
  - Mock retourne `needs_clarification: false` → stage OK.
  - Mock retourne `needs_clarification: true` avec questions → stage lève `ClarificationNeeded(questions)`.

- [ ] **Step 8.3 — Implémenter `Stage1Intake`**

  Similaire à Stage0 mais output : `{prompt_cleaned, target_files_hint, action_verbs, needs_clarification, clarification_questions}`.

  Si `needs_clarification=True` → lève exception custom `ClarificationNeeded` qui sera remontée par `Pipeline.run()` en `PipelineResult(success=False, error="clarification needed", ...)`.

- [ ] **Step 8.4 — Commit**

---

## Task 9 : Stage 3 GROUND (tool-calling read-only)

**Files:** `backend/pipeline/stage_3_ground.py`, `backend/prompts/stage_3_ground.md`, `tests/backend/test_stage_3_ground.py`, `tests/fixtures/scripted_llm.py`.

**Durée :** 1.5 jour.

- [ ] **Step 9.1 — System prompt `stage_3_ground.md`** : règles strictes grounding, citations obligatoires, pas d'hypothèse.

- [ ] **Step 9.2 — Fixture `ScriptedLLMWithTools`**

  Dans `tests/fixtures/scripted_llm.py`, fixture qui simule un LLM produisant une séquence de `tool_calls` puis un message final. Format compatible litellm response structure.

- [ ] **Step 9.3 — Tests rouges GROUND**

  Scénarios :
  - Mock LLM appelle `read_file("main.py")` puis message final → stage retourne `GroundedContext(files_read={"main.py": ...})`.
  - Mock LLM boucle 21 fois sur tool_calls → stage lève RuntimeError "budget dépassé".

- [ ] **Step 9.4 — Implémenter `Stage3Ground`**

  Utilise `litellm.acompletion(model, messages, tools=TOOLS_SCHEMA_READ)` en boucle max 20 itérations.

  À chaque itération :
  - Si `response.tool_calls` vide → break et parse le message final pour construire `GroundedContext`.
  - Sinon pour chaque tool_call → `execute_tool` → append result à `messages` sous role `"tool"`.
  - Enregistrer les `read_file` dans `files_read`, les `grep_codebase` dans `greps`.

  Accès au `file_lock` partagé injecté via `self.file_lock` (setté par Pipeline orchestrator).

- [ ] **Step 9.5 — Commit**

---

## Task 10 : Stage 5 EXECUTE (tool-calling write)

**Files:** `backend/pipeline/stage_5_execute.py`, `backend/prompts/stage_5_execute.md`, `tests/backend/test_stage_5_execute.py`.

**Durée :** 1.5 jour.

- [ ] **Step 10.1 — System prompt `stage_5_execute.md`** : usage des tools write, un fichier à la fois, message final de résumé.

- [ ] **Step 10.2 — Helper git_stash**

  Dans `stage_5_execute.py`, fonctions async `git_stash_save(workspace_root, label)` et `git_stash_pop(workspace_root, stash_ref)` qui wrappent `asyncio.create_subprocess_*` pour lancer git stash.

  Retournent respectivement le stash ref (string vide si rien à stash) et un bool success.

- [ ] **Step 10.3 — Tests rouges EXECUTE**

  Setup : tmp git repo avec commit initial.

  Test 1 : mock LLM retourne `tool_call create_file("hello.py", "print('hi')")` puis message final → fichier existe sur disque après.

  Test 2 : mock LLM retourne un `edit_file` vers path hors workspace → stage lève ToolError + rollback stash pop appelé.

- [ ] **Step 10.4 — Implémenter `Stage5Execute`**

  Préambule : `stash_ref = await git_stash_save(workspace_root, f"pipeline_pre_{session_id}")`.

  Try block : boucle tool-calling similaire à Stage3Ground mais avec `TOOLS_SCHEMA_WRITE` et tracking `files_modified`. Max 20 itérations.

  Sur exception : `await git_stash_pop(workspace_root, stash_ref)` puis re-raise.

  Retourne `ExecuteResult(files_modified, stash_ref, tool_calls_log)`.

- [ ] **Step 10.5 — Commit**

---

## Task 11 : Stage 7 VERIFY (minimal) + Pipeline orchestrator

**Files:** `backend/pipeline/stage_7_verify.py`, `backend/pipeline/orchestrator.py`, `backend/orchestrator.py` (MAJ), `tests/backend/test_pipeline_orchestrator.py`.

**Durée :** 1.5 jour.

- [ ] **Step 11.1 — Stage7Verify minimal**

  Pour Plan 5A, uniquement :
  - ruff check sur chaque .py modifié (via `asyncio.create_subprocess_*`).
  - cargo check sur ui/src-tauri/ si au moins un .rs touché.

  Retourne `VerifyResult(lint_errors, all_green, attempts_used=1)`. Pas de retry interne à ce stade (viendra en Plan 5B avec pytest/vitest complet).

- [ ] **Step 11.2 — Pipeline orchestrator**

  Dans `backend/pipeline/orchestrator.py`, classe `Pipeline` :
  - `__init__(llm_manager, ws_streamer, file_lock)`.
  - Attribut `stages_by_mode: dict[PipelineMode, list[type[Stage]]]`. En Plan 5A, seul `SIMPLE` est rempli : `[Stage0Estimate, Stage1Intake, Stage3Ground, Stage5Execute, Stage7Verify]`.
  - Méthode `run(ctx: PipelineContext) -> PipelineResult` :
    1. Itère sur les stages du mode.
    2. Instancie stage avec `llm_manager, ws_streamer`.
    3. Injecte `file_lock` si attribut présent sur la stage.
    4. Appelle `stage.run(ctx)`.
    5. Si échec → rollback via stash_ref trouvé dans ctx.stage_results["execute"].output.stash_ref.
    6. Accumule duration/cost/tokens dans PipelineResult.

- [ ] **Step 11.3 — Modifier `backend/orchestrator.py`**

  `Orchestrator.handle()` : ne crée plus un `AgentLoop`. Crée un `PipelineContext` + appelle `self.pipeline.run(ctx)`. Retourne `OrchestratorResponse` construit depuis `PipelineResult`.

  Garder compatibilité avec mode projet (roadmap active) : pour l'instant, mode projet n'utilise pas Pipeline, utilise toujours l'ancien code. Migration en Plan 5D.

- [ ] **Step 11.4 — Tests pipeline orchestrator**

  Deux tests :
  - Mock tous les stages avec retours OK → pipeline retourne `PipelineResult(success=True)` avec `files_modified` correct.
  - Stage5 échoue → pipeline appelle `git_stash_pop` et retourne `success=False, rollback_performed=True`.

- [ ] **Step 11.5 — Commit**

---

# PHASE A4 — UI (Tasks 12-13)

## Task 12 : Modal ESTIMATE (UI)

**Files:** `ui/src/types/pipeline.ts`, `ui/src/stores/pipelineStore.ts`, `ui/src/components/Pipeline/EstimateModal.tsx`.

**Durée :** 1 jour.

- [ ] **Step 12.1 — Types pipeline TypeScript**

  `ui/src/types/pipeline.ts` : interfaces `EstimateResult`, `StageEstimate`, `PipelineMode`, `StageProgress`, `PipelineResult`. Alignés sur les types backend.

- [ ] **Step 12.2 — Store `pipelineStore.ts`**

  Zustand store :
  - State : `estimate: EstimateResult | null`, `isAwaitingConfirmation: boolean`, `currentStageName: string | null`, `stages: StageProgress[]`, `totalCostUSD: number`.
  - Actions : `onEstimateReceived`, `confirm()`, `cancel()`, `onStageStart`, `onStageComplete`, `onPipelineComplete`.

  Installer listeners WS : `pipeline_estimate`, `stage_start`, `stage_complete`, `pipeline_complete`, `pipeline_rollback`.

- [ ] **Step 12.3 — `EstimateModal.tsx`**

  Composant React :
  - Overlay `fixed inset-0 bg-black/50 z-50`.
  - Card centrée : header (classification + raison), tableau étapes, totaux coût/durée, boutons.
  - Trois boutons : `Annuler` (cancel), `Forcer simple`, `Lancer ($X.XX)`.
  - Click lancer → `ws.send("pipeline_confirmed", {estimate_id, mode})`.

- [ ] **Step 12.4 — Tests vitest**

  Render modal avec mock store, simuler click "Lancer" → vérifier `ws.send` appelé avec payload correct.

- [ ] **Step 12.5 — Commit**

---

## Task 13 : Trace Viewer (UI)

**Files:** `ui/src/components/Pipeline/StageRow.tsx`, `TraceViewer.tsx`, `ui/src/components/tabs/RoutingTab/RoutingTab.tsx`.

**Durée :** 1 jour.

- [ ] **Step 13.1 — `StageRow.tsx`**

  Affiche une ligne : index + nom + LLM badge + statut (pending/running/done/failed) + durée + coût + détails collapsibles.

  Statut avec icônes : sablier, spinner, check, croix.

- [ ] **Step 13.2 — `TraceViewer.tsx`**

  Container qui lit `pipelineStore.stages`. Affiche header (prompt + mode + progress global X/5 étapes pour mode simple) + liste de StageRow + footer (Stop button).

- [ ] **Step 13.3 — Intégrer dans `RoutingTab.tsx`**

  Remplace le contenu actuel par TraceViewer + historique (RoutingHistory existant).

- [ ] **Step 13.4 — Tests snapshot**

  Vitest snapshot test avec mock stages à différents états.

- [ ] **Step 13.5 — Commit**

---

# PHASE A5 — Tests E2E + Release (Tasks 14-15)

## Task 14 : Test E2E pipeline simple

**Files:** `tests/backend/test_pipeline_e2e_simple.py`, `tests/fixtures/scripted_llm.py` (MAJ).

**Durée :** 1 jour.

- [ ] **Step 14.1 — Fixture ScriptedLLM**

  Classe qui mappe `stage_name → list[response]`. Chaque appel consomme la prochaine réponse. Détecte le stage depuis `messages[0]["content"]` (le system prompt contient "Étape N").

- [ ] **Step 14.2 — Test E2E "prompt simple → fichier créé"**

  Setup : tmp_path avec git init + commit vide.

  Scripted responses :
  - estimate : `{classification: "simple", files_hint: ["hello.py"], confidence: "high"}`.
  - intake : `{prompt_cleaned: "...", needs_clarification: false, ...}`.
  - ground : message final sans tool_calls (rien à ground pour un create from scratch).
  - execute : tool_call `create_file("hello.py", "print('hi')\n")` puis message final.

  Assertions :
  - `result.success == True`.
  - `hello.py` existe dans tmp_path avec contenu correct.
  - `result.files_modified == ["hello.py"]`.
  - `result.total_cost_usd` non-nul.

- [ ] **Step 14.3 — Test E2E avec rollback**

  Scripted execute retourne un `create_file` vers path hors workspace → stage échoue → rollback → fichier absent après.

- [ ] **Step 14.4 — Commit**

---

## Task 15 : Récap tests + push distant + tag alpha

**Files:** README (MAJ), tag git.

**Durée :** 0.5 jour.

- [ ] **Step 15.1 — Suite tests complète**

  Lancer :
  - `python -m pytest tests/backend/ -v --tb=short` → cible **200+ verts**.
  - `cd ui && npx vitest run` → cible **115+ verts**.
  - `cd ui/src-tauri && cargo check` → **Finished OK**.

  Tous verts avant de continuer.

- [ ] **Step 15.2 — Mise à jour README**

  Ajouter section "Pipeline rigoureux (v2.1 en cours)" :
  - Description des 11 étapes (lien vers spec).
  - État actuel : mode simple fonctionnel (5/11 étapes implémentées).
  - Plans 5B-5F à venir.

- [ ] **Step 15.3 — Push distant**

  Via subtree split sur branche export + push vers `https://github.com/Wissem95/localcoder-ide.git` sur `main`.

- [ ] **Step 15.4 — Tag alpha**

  `git tag v2.1.0-alpha.1 -m "Plan 5A complete : pipeline foundations + mode simple fonctionnel"` + push tag.

- [ ] **Step 15.5 — Checkpoint fin Plan 5A**

  Créer `docs/superpowers/checkpoints/2026-04-XX-plan-5A-done.md` avec :
  - Nombre de tests passants (pytest, vitest).
  - Fonctionnalités livrées.
  - Ce qui reste pour Plan 5B (VERIFY complet, rollback robuste, streaming, stop button).

- [ ] **Step 15.6 — Commit final via skill `commit-commands:commit`**

---

## Vérification finale Plan 5A

- [ ] `source venv/bin/activate && python -m pytest tests/backend/ -v` → **200+ verts**.
- [ ] `cd ui && npx vitest run` → **115+ verts**.
- [ ] `cd ui/src-tauri && cargo check` → **Finished OK**.
- [ ] Backend tourne, un prompt simple envoyé via curl déclenche :
  - Event WS `pipeline_estimate` émis.
  - Events WS `stage_start`/`stage_complete` par étape.
  - Fichier réellement créé sur disque.
  - Rollback automatique si erreur simulée.
- [ ] UI Tauri tourne, prompt tapé dans chat déclenche :
  - Modal ESTIMATE s'ouvre avec breakdown coût.
  - Click Lancer → TraceViewer affiche progression temps réel.
  - Résultat final visible dans ChatTab.

---

## Récap Plan 5A

**15 tasks, 5 phases** :

| Phase | Tasks | Impact | Durée |
|-------|-------|--------|-------|
| A1 Prérequis | 1-3 | Infrastructure nécessaire | 2.5 jours |
| A2 Tools | 4-5 | Read/write tools + schema | 2.5 jours |
| A3 Pipeline Core | 6-11 | Stages 0/1/3/5/7 + orchestrator | 7 jours |
| A4 UI | 12-13 | Modal + trace viewer | 2 jours |
| A5 E2E + Release | 14-15 | Tests bout-en-bout + push | 1.5 jour |

**Total : ~15 jours (3 semaines part-time, 10-12 jours full-time).**

**Livrables :**
- Backend : pipeline mode simple complet + tools + cost estimator.
- UI : modal ESTIMATE + trace viewer.
- Tests : 200+ pytest, 115+ vitest.
- Release : tag v2.1.0-alpha.1 pushé sur github.

**Post-Plan 5A :**
- Plan 5B : VERIFY complet (pytest/vitest/cargo) + rollback robuste + streaming + stop button.
- Plan 5C : CHALLENGE + PLAN consensus (modes medium/complex).
- Plan 5D : SELF-CHECK + REVIEW + SECOND-REVIEW (consensus 2/2).
- Plan 5E : UX raffinée + settings + cost tracking live.
- Plan 5F : packaging + Ollama + release v2.0.0.

---

*Plan 5A validation-ready. Démarrage Phase A1 Task 1 dès validation utilisateur.*
