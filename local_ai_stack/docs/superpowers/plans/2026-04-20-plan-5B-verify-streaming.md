# LocalCoder IDE v2.1 — Plan 5B : VERIFY complet + rollback robuste + streaming + stop

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`. TDD strict obligatoire.

**Goal :** Compléter VERIFY avec pytest/vitest/eslint, rendre le rollback robuste (3 retries avec feedback), ajouter le streaming des réponses LLM token-par-token, implémenter le bouton Stop + cap budget par pipeline.

**Architecture :** Stage7Verify orchestré avec retry vers Stage5Execute sur échec. Streaming via litellm `stream=True` + events WS `chat_token`. Stop via `asyncio.CancelledError` propagée dans le pipeline + rollback garanti.

**Tech stack ajouté :** Aucun (utilise litellm streaming et asyncio existants).

**Prérequis :** Plan 5A complet (pipeline mode simple fonctionnel).

**Durée estimée :** 1 semaine (5-7 jours full-time).

**Résultat attendu :**
- 230+ tests pytest verts.
- 125+ tests vitest verts.
- Un prompt avec code buggé déclenche VERIFY rouge → Stage5 retry (3x) → si toujours rouge → rollback propre.
- Streaming token-par-token visible dans ChatTab.
- Cmd+. interrompt le pipeline + rollback.
- Cap budget $1.00/pipeline respecté (configurable).

---

## Fichiers créés ou modifiés

```
backend/
├── pipeline/
│   ├── stage_5_execute.py             # MODIFIÉ — retry loop avec feedback VERIFY
│   ├── stage_7_verify.py              # MODIFIÉ — pytest/vitest/eslint complets + retry
│   └── orchestrator.py                # MODIFIÉ — cancellation support + budget cap
├── tools/
│   └── run_tests.py                   # CRÉÉ — wrappers pytest/vitest/cargo
├── streaming.py                       # CRÉÉ — helper LLM streaming → WS tokens
└── budget_tracker.py                  # CRÉÉ — compteur $ par pipeline + cap

tests/backend/
├── test_tools_run_tests.py            # CRÉÉ
├── test_stage_7_verify_full.py        # CRÉÉ
├── test_stage_5_retry.py              # CRÉÉ
├── test_streaming.py                  # CRÉÉ
├── test_budget_tracker.py             # CRÉÉ
└── test_pipeline_cancellation.py      # CRÉÉ

ui/src/
├── components/
│   ├── Pipeline/
│   │   ├── TraceViewer.tsx            # MODIFIÉ — bouton Stop
│   │   └── BudgetIndicator.tsx        # CRÉÉ — jauge $ en temps réel
│   └── tabs/ChatTab/
│       └── MessageBubble.tsx          # MODIFIÉ — render streaming tokens
├── stores/
│   └── pipelineStore.ts               # MODIFIÉ — cancel(), streaming state
└── ws.ts                              # MODIFIÉ — handler chat_token
```

---

# PHASE B1 — VERIFY complet (Tasks 1-3)

## Task 1 : Tools run_tests

**Files:** `backend/tools/run_tests.py`, `tests/backend/test_tools_run_tests.py`.

**Durée :** 1 jour.

- [ ] **Step 1.1 — Tests rouges run_tests**

  Fixture : mini projet Python dans tmp_path avec 1 test passant et 1 test échouant.

  Tests :
  - `run_pytest(target, workspace_root)` retourne `{exit_code, passed, failed, stdout_tail, duration_s}` avec stdout tronqué à 3000 chars.
  - `run_vitest(target, workspace_root)` équivalent.
  - `run_cargo_check(workspace_root)` détecte erreurs compilation Rust.
  - `run_lint(path, workspace_root)` dispatch ruff/eslint selon extension.
  - Timeout dépassé → retour avec `exit_code=-1` et `error="timeout"`.

- [ ] **Step 1.2 — Implémenter `run_tests.py`**

  Utilise `asyncio.create_subprocess_exec` wrappé dans try/except + `asyncio.wait_for` pour timeout.

  Parse la sortie pytest via regex `r"(\d+) passed"` et `r"(\d+) failed"`.

  Retourne dict standardisé pour tous les runners.

- [ ] **Step 1.3 — Commit**

---

## Task 2 : Stage7Verify complet

**Files:** `backend/pipeline/stage_7_verify.py`, `tests/backend/test_stage_7_verify_full.py`.

**Durée :** 1 jour.

- [ ] **Step 2.1 — Tests rouges**

  Setup : tmp git repo avec fichier Python modifié + un test associé.

  Scénarios :
  - Test vert → VerifyResult(all_green=True).
  - Test rouge → VerifyResult(all_green=False, test_errors contient le traceback).
  - Lint rouge → VerifyResult(all_green=False, lint_errors).
  - Fichier .ts modifié → lance eslint.
  - Fichier .rs modifié → lance cargo check.
  - `tests_to_run` du plan respecté (pas de full suite).

- [ ] **Step 2.2 — Implémenter `Stage7Verify._execute`**

  Reçoit `ctx.stage_results["execute"].output` pour `files_modified` et `ctx.stage_results.get("plan").output.tests_to_run`.

  Lance en parallèle via `asyncio.gather` :
  1. `run_lint` pour chaque fichier modifié (ruff ou eslint selon extension).
  2. `run_cargo_check` si au moins un .rs modifié.
  3. `run_pytest` pour chaque test du plan en `tests/`.
  4. `run_vitest` pour chaque test du plan en `ui/`.

  Agrège les résultats. `all_green = True` si aucune erreur partout.

- [ ] **Step 2.3 — Commit**

---

## Task 3 : Retry loop Stage5 ← Stage7

**Files:** `backend/pipeline/stage_5_execute.py` (MODIFIÉ), `backend/pipeline/orchestrator.py` (MODIFIÉ), `tests/backend/test_stage_5_retry.py`.

**Durée :** 1.5 jour.

- [ ] **Step 3.1 — Tests rouges retry**

  Scripted LLM :
  - Passe 1 : tool_call crée un fichier avec syntaxe Python invalide.
  - Passe 2 (après feedback VERIFY) : tool_call corrige la syntaxe.

  Assertions :
  - Pipeline success final.
  - Stage5 appelé 2x.
  - VerifyResult final : all_green=True.
  - 1er appel execute reçoit messages normaux.
  - 2e appel execute reçoit dans ses messages les erreurs VERIFY en context.

- [ ] **Step 3.2 — Modifier Pipeline orchestrator**

  Nouveau comportement pour Stage7Verify :
  - Après Stage7 : si `all_green=False`, on boucle back à Stage5 avec une nouvelle entrée "previous_verify_errors" dans le context.
  - Max 3 tentatives Stage5→Stage7.
  - Si 3 fois rouge → rollback via stash_ref + return PipelineResult(success=False, error="verify failed after 3 retries").

  `Stage5Execute._execute` : si `ctx.retry_context` présent, injecte les erreurs VERIFY dans le user message au LLM.

- [ ] **Step 3.3 — Tests retry exhaustif**

  - 3 retries rouges → rollback + success=False.
  - 1 retry vert → success=True avec attempts_used=2.

- [ ] **Step 3.4 — Commit**

---

# PHASE B2 — Streaming (Tasks 4-5)

## Task 4 : Backend streaming LLM

**Files:** `backend/streaming.py`, `backend/llm_manager.py` (MODIFIÉ), `tests/backend/test_streaming.py`.

**Durée :** 1 jour.

- [ ] **Step 4.1 — Tests rouges streaming**

  Mock `litellm.acompletion` avec `stream=True` retournant un async generator de chunks.

  Tests :
  - `call_with_fallback_streaming(role, messages, on_token)` appelle `on_token` pour chaque chunk content.
  - Retourne le texte concaténé final à la fin.
  - Timeout correctement géré.

- [ ] **Step 4.2 — Implémenter `streaming.py`**

  Helper `async def stream_llm_response(llm_manager, role, messages, on_token, ...)` qui :
  - Appelle `acompletion(..., stream=True)`.
  - Itère sur chunks via `async for`.
  - Appelle `await on_token(chunk_content)` pour chaque morceau.
  - Retourne texte complet + compteur tokens.

- [ ] **Step 4.3 — Étendre LLMManager**

  Nouvelle méthode `call_with_fallback_streaming` qui wrappe `stream_llm_response` + fallback chain (si premier LLM down, bascule au 2e).

- [ ] **Step 4.4 — Commit**

---

## Task 5 : UI streaming + WS chat_token

**Files:** `backend/main.py` (MODIFIÉ), `backend/ws_streamer.py` (MODIFIÉ), `ui/src/ws.ts` (MODIFIÉ), `ui/src/components/tabs/ChatTab/MessageBubble.tsx` (MODIFIÉ), `ui/src/stores/pipelineStore.ts` (MODIFIÉ).

**Durée :** 1 jour.

- [ ] **Step 5.1 — Event WS `chat_token`**

  Backend émet `chat_token` par token reçu : `{session_id, token_text, stage}`. Stage permet de savoir si c'est pendant execute, review, etc.

  Frontend `ws.ts` : handler qui append le token au message courant dans `pipelineStore`.

- [ ] **Step 5.2 — Message bubble streaming**

  `MessageBubble` lit `pipelineStore.streamingBuffer`. Affiche le texte progressif avec un curseur clignotant.

  Quand `pipeline_complete` arrivé → fige le message, efface buffer.

- [ ] **Step 5.3 — Tests vitest**

  Simule événements `chat_token` séquentiels → vérifier que le buffer s'accumule puis se fige.

- [ ] **Step 5.4 — Commit**

---

# PHASE B3 — Stop + Budget (Tasks 6-7)

## Task 6 : Stop button + cancellation

**Files:** `backend/pipeline/orchestrator.py` (MODIFIÉ), `backend/main.py` (MODIFIÉ), `ui/src/components/Pipeline/TraceViewer.tsx` (MODIFIÉ), `tests/backend/test_pipeline_cancellation.py`.

**Durée :** 1 jour.

- [ ] **Step 6.1 — Tests rouges cancellation**

  - Lancer un pipeline, cancel après Stage5 → vérifier que rollback est effectué (stash_ref pop).
  - Cancel pendant Stage5 → `asyncio.CancelledError` propagée, tools interrompus, rollback.
  - Cancel avant Stage5 → pas de rollback nécessaire, return success=False, error="cancelled".

- [ ] **Step 6.2 — Event WS `pipeline_stop`**

  Backend : handler qui appelle `current_pipeline_task.cancel()`.

  Frontend : bouton Stop dans TraceViewer → envoie `pipeline_stop` + Cmd+. shortcut.

- [ ] **Step 6.3 — Orchestrator gère CancelledError**

  Dans `Pipeline.run()`, wrap le corps en try/except CancelledError → si stash_ref existe → pop → return PipelineResult(success=False, rollback_performed=True, error="cancelled by user").

- [ ] **Step 6.4 — UI Stop button**

  Bouton rouge "Stop" dans footer TraceViewer. Click → `ws.send("pipeline_stop", {reason: "user"})`. Raccourci Cmd+. (⌘. sur mac).

- [ ] **Step 6.5 — Commit**

---

## Task 7 : Budget cap par pipeline

**Files:** `backend/budget_tracker.py`, `backend/pipeline/orchestrator.py` (MODIFIÉ), `ui/src/components/Pipeline/BudgetIndicator.tsx`, `tests/backend/test_budget_tracker.py`.

**Durée :** 0.5 jour.

- [ ] **Step 7.1 — Tests rouges budget_tracker**

  - `BudgetTracker(cap_usd=1.0)`.
  - `track(llm, tokens_in, tokens_out)` accumule.
  - `current_usd()` retourne le cumul.
  - `would_exceed(additional_usd)` retourne True si projection dépasse.

- [ ] **Step 7.2 — Implémenter `budget_tracker.py`**

  Classe simple qui utilise `estimate_cost` de cost_estimator pour convertir tokens → USD.

- [ ] **Step 7.3 — Intégrer dans Pipeline**

  Pipeline crée un `BudgetTracker` par run. Après chaque stage, si `tracker.current_usd() > cap` → cancel pipeline + rollback + return success=False, error="budget cap exceeded".

  Cap configurable via settings (défaut $1.00).

- [ ] **Step 7.4 — UI BudgetIndicator**

  Jauge visuelle dans TraceViewer : "$0.05 / $1.00 (5%)". Passe au rouge à 80%.

- [ ] **Step 7.5 — Commit**

---

# PHASE B4 — Tests E2E + Release (Task 8)

## Task 8 : Tests E2E + push + tag alpha.2

**Files:** `tests/backend/test_pipeline_e2e_verify_retry.py`, README (MAJ), tag.

**Durée :** 1 jour.

- [ ] **Step 8.1 — Test E2E retry complet**

  Scripted LLM :
  - Passe 1 : crée fichier avec `print( "hi")` (ok syntaxe, mais imagine un vrai bug).
  - Actually : crée fichier avec `priit('hi')` (syntax error).
  - VERIFY rouge → Stage5 retry avec feedback.
  - Passe 2 : corrige en `print('hi')`.
  - VERIFY vert.

  Assertions : pipeline success, 2 attempts dans VerifyResult, fichier final correct.

- [ ] **Step 8.2 — Test E2E rollback**

  Scripted : 3 tentatives rouges → rollback → stash pop → fichier initial restauré.

- [ ] **Step 8.3 — Test E2E cancellation**

  Spawn pipeline dans task asyncio, cancel après 100ms, vérifier rollback effectué.

- [ ] **Step 8.4 — Test E2E budget exceeded**

  Cap à $0.001, lancer pipeline qui dépasse → cancel + rollback.

- [ ] **Step 8.5 — Suite tests complète**

  - `pytest tests/backend/` → 230+ verts.
  - `vitest run` → 125+ verts.
  - `cargo check` → ok.

- [ ] **Step 8.6 — README MAJ + push distant + tag v2.1.0-alpha.2**

- [ ] **Step 8.7 — Checkpoint fin Plan 5B**

  `docs/superpowers/checkpoints/2026-XX-plan-5B-done.md`.

- [ ] **Step 8.8 — Commit final**

---

## Vérification finale Plan 5B

- [ ] 230+ tests pytest verts.
- [ ] 125+ tests vitest verts.
- [ ] Prompt avec code volontairement buggé → VERIFY rouge → retry → corrigé → commit.
- [ ] Prompt avec 3 erreurs persistantes → rollback propre, aucun fichier modifié.
- [ ] Cmd+. pendant execution → rollback + pipeline interrompu.
- [ ] Streaming visible : texte s'affiche mot par mot dans ChatTab.
- [ ] Budget indicator passe au rouge à 80% du cap.

---

## Récap Plan 5B

**8 tasks, 4 phases** :

| Phase | Tasks | Impact | Durée |
|-------|-------|--------|-------|
| B1 VERIFY complet | 1-3 | Tests réels + retry loop | 3.5 jours |
| B2 Streaming | 4-5 | UX token-par-token | 2 jours |
| B3 Stop + Budget | 6-7 | Contrôle user + cap coût | 1.5 jour |
| B4 E2E + Release | 8 | Validation bout-en-bout | 1 jour |

**Total : ~8 jours (1.5 semaine full-time).**

**Post-Plan 5B :** Plan 5C attaquera CHALLENGE + PLAN consensus pour activer modes medium/complex.

---

*Plan 5B validation-ready après Plan 5A livré.*
