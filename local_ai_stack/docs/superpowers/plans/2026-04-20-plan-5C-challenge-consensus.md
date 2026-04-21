# LocalCoder IDE v2.1 — Plan 5C : CHALLENGE + PLAN consensus (modes medium/complex)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`. TDD strict obligatoire.

**Goal :** Activer les modes medium et complex en implémentant Stage2Challenge (avocat du diable par Gemini Pro), Stage4aPlan (DeepSeek R1 architecture) et Stage4bPlanReview (consensus par Gemini Pro). Rendre le dispatch multi-LLM explicite dans le Pipeline orchestrator. Gérer le deadlock consensus avec modal user.

**Architecture :** Le Pipeline choisit la liste des stages selon `ctx.mode`. Mode medium = 0/1/3/5/6/7/8. Mode complex = 0/1/2/3/4a/4b/5/6/7/8/(9). Consensus R1+Pro sur PLAN avec 2 rounds max avant flag user.

**Tech stack ajouté :** Aucun (utilise litellm tool-calling existant).

**Prérequis :** Plans 5A + 5B complets.

**Durée estimée :** 1.5 semaine (8-10 jours full-time).

**Résultat attendu :**
- 270+ tests pytest verts.
- 140+ tests vitest verts.
- Un prompt complex active CHALLENGE + PLAN consensus.
- Si R1 et Pro désaccord après 2 rounds → modal UI affiche les 2 plans, user choisit.
- Mode medium active REVIEW (Stage8) mais pas CHALLENGE ni consensus PLAN.

---

## Fichiers créés ou modifiés

```
backend/
├── pipeline/
│   ├── stage_2_challenge.py            # CRÉÉ
│   ├── stage_4a_plan.py                # CRÉÉ
│   ├── stage_4b_plan_review.py         # CRÉÉ
│   ├── consensus.py                    # CRÉÉ — mécanisme consensus 2/2 plan
│   └── orchestrator.py                 # MODIFIÉ — stages_by_mode complet
├── prompts/
│   ├── stage_2_challenge.md            # CRÉÉ
│   ├── stage_4a_plan.md                # CRÉÉ
│   └── stage_4b_plan_review.md         # CRÉÉ
└── memory.py                           # MODIFIÉ — log llm_messages par consensus round

tests/backend/
├── test_stage_2_challenge.py           # CRÉÉ
├── test_stage_4a_plan.py               # CRÉÉ
├── test_stage_4b_plan_review.py        # CRÉÉ
├── test_consensus_mechanism.py         # CRÉÉ
├── test_pipeline_medium_mode.py        # CRÉÉ
└── test_pipeline_complex_mode.py       # CRÉÉ

ui/src/
├── components/
│   ├── Pipeline/
│   │   ├── ChallengePanel.tsx          # CRÉÉ — affiche risks/edge_cases/alternatives
│   │   ├── PlanDiffView.tsx            # CRÉÉ — affiche 2 plans côte à côte si deadlock
│   │   └── DeadlockModal.tsx           # CRÉÉ — modal décision user
│   └── tabs/RoutingTab/
│       └── TraceViewer.tsx             # MODIFIÉ — affiche consensus rounds
└── stores/
    └── pipelineStore.ts                # MODIFIÉ — consensus state
```

---

# PHASE C1 — Stage 2 CHALLENGE (Tasks 1-2)

## Task 1 : Prompt + implémentation Stage2Challenge

**Files:** `backend/prompts/stage_2_challenge.md`, `backend/pipeline/stage_2_challenge.py`.

**Durée :** 1 jour.

- [ ] **Step 1.1 — System prompt `stage_2_challenge.md`**

  Rôle : avocat du diable. Identifier 3 risks, 3 edge_cases, 1-2 alternatives, verdict severity.

  Output JSON strict : `{risks, edge_cases, alternatives, severity, blocking}`.

  Règles :
  - `severity = "critical"` si tu penses que le prompt est fondamentalement mauvais.
  - `blocking = true` si l'utilisateur devrait reconsidérer avant continuer.
  - Sois honnête : pas de politesse, identifie vraiment les problèmes.

- [ ] **Step 1.2 — Implémenter Stage2Challenge**

  Hérite de `Stage`, `name = "challenge"`.
  `_llm_for_stage()` retourne `"gemini/gemini-2.5-pro"`.
  `_execute(ctx)` lit le prompt + intake_result du ctx, appelle Gemini Pro, parse JSON output.

  Retourne dataclass `ChallengeResult(risks, edge_cases, alternatives, severity, blocking)`.

- [ ] **Step 1.3 — Tests rouges challenge**

  - Mock Gemini Pro retourne JSON avec severity="minor" → Stage OK, blocking=False.
  - Mock retourne severity="critical", blocking=True → Stage OK, mais event WS `challenge_blocking` émis.

- [ ] **Step 1.4 — Commit**

---

## Task 2 : UI ChallengePanel

**Files:** `ui/src/components/Pipeline/ChallengePanel.tsx`, `ui/src/stores/pipelineStore.ts` (MODIFIÉ).

**Durée :** 0.5 jour.

- [ ] **Step 2.1 — ChallengePanel.tsx**

  Affiche le ChallengeResult dans un panel expandable sous le TraceViewer :
  - Section "Risques" : liste bullet.
  - Section "Edge cases" : liste bullet.
  - Section "Alternatives" : liste bullet.
  - Badge severity en header.
  - Si blocking : banner jaune "Le LLM challenger pense que tu devrais reconsidérer. Continuer quand même ?" + bouton Continue/Cancel.

- [ ] **Step 2.2 — Store : state challenge + handler blocking**

  pipelineStore : `challenge: ChallengeResult | null`, `challengeBlocking: boolean`.

  Handler WS : `stage_complete` avec `stage="challenge"` → set state.

- [ ] **Step 2.3 — Tests vitest**

  Snapshot ChallengePanel avec different severities.

- [ ] **Step 2.4 — Commit**

---

# PHASE C2 — Stage 4a PLAN (Tasks 3-4)

## Task 3 : Prompt + implémentation Stage4aPlan

**Files:** `backend/prompts/stage_4a_plan.md`, `backend/pipeline/stage_4a_plan.py`.

**Durée :** 1.5 jour.

- [ ] **Step 3.1 — System prompt `stage_4a_plan.md`**

  Rôle : architecte planificateur.

  Input qu'il reçoit : intake + (challenge si complex) + grounded_context.

  Output JSON strict :
  ```
  {
    "changes": [
      {"file": "...", "operation": "edit|create|delete|patch",
       "description": "...", "intended_diff_summary": "..."}
    ],
    "tests_to_run": ["tests/backend/test_x.py::test_y", ...],
    "rollback_strategy": "...",
    "rationale": "justification citant les facts du grounded_context",
    "estimated_risk": "low|medium|high",
    "complexity_confirm": 0-10
  }
  ```

  Règles :
  - Chaque change doit être ancré dans un fact de grounded_context.
  - `tests_to_run` doit cibler précisément (pas de `tests/` seul).
  - Si challenge_result a flag des risques critiques, intégrer des mitigations dans le plan.

- [ ] **Step 3.2 — Implémenter Stage4aPlan**

  `_llm_for_stage()` retourne `"deepseek/deepseek-r1"`.

  `_execute` :
  - Charge system prompt + contexte (intake + challenge + grounded_context).
  - Appelle R1 avec temperature=0.3 (plus élevé pour créativité archi).
  - Parse JSON strict.
  - Retourne dataclass `Plan(changes, tests_to_run, rollback_strategy, rationale, ...)`.

- [ ] **Step 3.3 — Tests rouges Stage4a**

  - Mock R1 retourne plan valide → Plan dataclass correct.
  - Plan cite un fact absent du grounded_context → warning mais OK (pas bloquant, sera attrapé par 4b).
  - JSON invalide → raise avec message utilisable par orchestrator.

- [ ] **Step 3.4 — Commit**

---

## Task 4 : UI Plan display dans TraceViewer

**Files:** `ui/src/components/Pipeline/PlanDiffView.tsx`, `TraceViewer.tsx` (MODIFIÉ).

**Durée :** 0.5 jour.

- [ ] **Step 4.1 — PlanDiffView.tsx**

  Composant qui affiche un Plan : liste des changes avec icône opération + description, tests à lancer, risk badge.

- [ ] **Step 4.2 — Intégrer sous StageRow plan**

  Si stage "plan" complete → StageRow expand affiche PlanDiffView.

- [ ] **Step 4.3 — Commit**

---

# PHASE C3 — Stage 4b PLAN REVIEW + Consensus (Tasks 5-7)

## Task 5 : Prompt + implémentation Stage4bPlanReview

**Files:** `backend/prompts/stage_4b_plan_review.md`, `backend/pipeline/stage_4b_plan_review.py`, `tests/backend/test_stage_4b_plan_review.py`.

**Durée :** 1 jour.

- [ ] **Step 5.1 — System prompt `stage_4b_plan_review.md`**

  Rôle : reviewer du plan R1.

  Output JSON strict :
  ```
  {
    "verdict": "approve|revise|reject",
    "concerns": ["..."],
    "suggested_changes": ["..."],
    "merged_plan": {...}  // null sauf si verdict="revise"
  }
  ```

  Règles :
  - approve = plan correct tel quel.
  - revise = plan correct dans ses grandes lignes mais nécessite des ajustements. Dans ce cas, produit un merged_plan avec les ajustements intégrés.
  - reject = plan fondamentalement mauvais. Explique pourquoi dans concerns.

- [ ] **Step 5.2 — Implémenter Stage4bPlanReview**

  `_llm_for_stage()` retourne `"gemini/gemini-2.5-pro"`.

  Reçoit le Plan de R1 dans ctx. Appelle Pro avec le plan en input. Parse verdict.

  Retourne `PlanReview(verdict, concerns, suggested_changes, merged_plan)`.

- [ ] **Step 5.3 — Tests rouges Stage4b**

  3 scénarios : approve, revise avec merged_plan, reject avec concerns.

- [ ] **Step 5.4 — Commit**

---

## Task 6 : Mécanisme consensus

**Files:** `backend/pipeline/consensus.py`, `backend/pipeline/orchestrator.py` (MODIFIÉ), `tests/backend/test_consensus_mechanism.py`.

**Durée :** 1.5 jour.

- [ ] **Step 6.1 — `backend/pipeline/consensus.py`**

  Fonction `async def run_plan_consensus(llm_manager, ws_streamer, ctx, max_rounds=2) -> PlanConsensusResult` :

  Algorithme :
  ```
  round 1:
    stage_4a = Stage4aPlan → P1
    stage_4b = Stage4bPlanReview sur P1 → V1

  if V1 == approve: return plan=P1, rounds=1, deadlock=False
  if V1 == revise:  return plan=V1.merged_plan, rounds=1, deadlock=False
  if V1 == reject:
    round 2:
      re-run stage_4a avec feedback V1.concerns → P2
      re-run stage_4b sur P2 → V2

      if V2 == approve: return plan=P2, rounds=2, deadlock=False
      if V2 == revise:  return plan=V2.merged_plan, rounds=2, deadlock=False
      if V2 == reject:  return plan=None, rounds=2, deadlock=True,
                               plans=[P1, P2] (pour choix user)
  ```

  Émet event WS `consensus_round` à chaque round avec `{round, verdict, plan_summary}`.

  Émet `consensus_disagreement` si deadlock.

- [ ] **Step 6.2 — Tests rouges consensus**

  4 scénarios :
  - V1=approve round 1 → return P1.
  - V1=revise → return merged_plan.
  - V1=reject puis V2=approve → return P2.
  - V1=reject puis V2=reject → deadlock=True, plans list.

- [ ] **Step 6.3 — Intégrer consensus dans Pipeline**

  Pipeline orchestrator : en mode complex, après Stage3Ground → appelle `run_plan_consensus` au lieu d'instancier Stage4a et Stage4b séparément.

  Si deadlock → émet event `pipeline_user_decision_needed` avec les 2 plans → attend `user_decision` event.

  Si user choisit plan 1 ou 2 → continue Stage5.
  Si user cancel → rollback + return.

- [ ] **Step 6.4 — Persistance consensus en LongTermMemory**

  Ajouter rows dans `llm_messages` table pour chaque round (from_llm=r1, to_llm=pro, type="plan_review"). Utile pour audit + apprentissage futur.

- [ ] **Step 6.5 — Commit**

---

## Task 7 : UI DeadlockModal

**Files:** `ui/src/components/Pipeline/DeadlockModal.tsx`, `ui/src/stores/pipelineStore.ts` (MODIFIÉ).

**Durée :** 1 jour.

- [ ] **Step 7.1 — DeadlockModal.tsx**

  Modal full-screen quand `pipelineStore.deadlock != null` :
  - Titre : "⚖️ Consensus impossible — ta décision"
  - Deux PlanDiffView côte à côte : "Plan R1" (gauche) / "Plan R1 v2 après feedback" (droite).
  - Dessous : concerns de Pro à chaque round.
  - Boutons : "Utiliser Plan R1", "Utiliser Plan R1 v2", "Annuler pipeline".

- [ ] **Step 7.2 — Store handler deadlock**

  pipelineStore :
  - State : `deadlock: {round1_plan, round2_plan, pro_concerns} | null`.
  - Handler WS `pipeline_user_decision_needed` avec type="plan_deadlock" → set deadlock.
  - Action `resolveDeadlock(choice: "plan1" | "plan2" | "cancel")` → envoie `user_decision` event.

- [ ] **Step 7.3 — Tests vitest**

  Snapshot modal + simule click "Plan 1" → vérifier WS send correct.

- [ ] **Step 7.4 — Commit**

---

# PHASE C4 — Pipeline modes + dispatch (Tasks 8-9)

## Task 8 : Pipeline modes medium/complex activés

**Files:** `backend/pipeline/orchestrator.py` (MODIFIÉ), `backend/router_engine.py` (MODIFIÉ), `tests/backend/test_pipeline_medium_mode.py`, `test_pipeline_complex_mode.py`.

**Durée :** 1 jour.

- [ ] **Step 8.1 — Compléter `stages_by_mode`**

  ```python
  stages_by_mode = {
      PipelineMode.SIMPLE:  [Stage0, Stage1, Stage3, Stage5, Stage7],
      PipelineMode.MEDIUM:  [Stage0, Stage1, Stage3, Stage5, Stage6, Stage7, Stage8],
      PipelineMode.COMPLEX: [Stage0, Stage1, Stage2, Stage3, run_plan_consensus,
                             Stage5, Stage6, Stage7, Stage8, Stage9_conditional],
  }
  ```

  Note : Stage6 (SELF-CHECK), Stage8 (REVIEW), Stage9 (SECOND-REVIEW) arrivent en Plan 5D. Pour ce Plan 5C, on met des stubs qui retournent success immédiat pour 6/8/9.

- [ ] **Step 8.2 — RouterEngine : force mode user-override**

  Si user a cliqué "Forcer simple" dans EstimateModal → PipelineContext.mode = SIMPLE peu importe ESTIMATE output.

- [ ] **Step 8.3 — Tests rouges pipeline_medium_mode**

  Scripted LLMs pour toutes les étapes mode medium, vérifier que Stage2 est SKIP (pas appelé) et Stage8 est appelé.

- [ ] **Step 8.4 — Tests rouges pipeline_complex_mode**

  Full pipeline complex, consensus approve round 1, vérifier :
  - 8 calls LLM (estimate, intake, challenge, ground, plan_r1, plan_pro, execute, review).
  - `ctx.stage_results` contient toutes les entrées.
  - `total_cost_usd` proche de l'estimation.

- [ ] **Step 8.5 — Commit**

---

## Task 9 : Logs inter-LLM visibles dans UI

**Files:** `ui/src/components/Pipeline/TraceViewer.tsx` (MODIFIÉ), `ui/src/stores/pipelineStore.ts` (MODIFIÉ).

**Durée :** 0.5 jour.

- [ ] **Step 9.1 — Consensus rounds visibles**

  StageRow pour "plan" affiche en expand :
  - Round 1 : verdict Pro + concerns éventuels.
  - Round 2 (si applicable) : verdict final.
  - Badge "approved" / "revised" / "deadlock".

- [ ] **Step 9.2 — Event `consensus_round` handling**

  Store : `consensusRounds: ConsensusRound[]`. Handler append à chaque event.

- [ ] **Step 9.3 — Commit**

---

# PHASE C5 — Tests E2E + Release (Task 10)

## Task 10 : Tests E2E medium/complex + release

**Files:** `tests/backend/test_pipeline_e2e_medium.py`, `test_pipeline_e2e_complex.py`, README MAJ, tag.

**Durée :** 1 jour.

- [ ] **Step 10.1 — Test E2E mode medium**

  Prompt medium ("ajoute endpoint /ping dans main.py") avec ScriptedLLM complet mode medium.

  Assertions : pipeline success, fichier modifié, Stage8 REVIEW (stub) appelé.

- [ ] **Step 10.2 — Test E2E mode complex avec consensus approve**

  Prompt complex ("refactor auth en 3 fichiers"). Challenge retourne risques. Plan R1 + Pro approve direct.

  Assertions : pipeline success, 8 LLM calls, challenge_result persisté.

- [ ] **Step 10.3 — Test E2E deadlock**

  R1 et Pro en désaccord 2 rounds. Vérifier :
  - Event `consensus_disagreement` émis.
  - Pipeline bloque en attente user_decision.
  - Simuler `user_decision = "plan1"` → pipeline continue avec plan1.
  - Simuler `user_decision = "cancel"` → rollback + success=False.

- [ ] **Step 10.4 — Suite tests complète**

  - pytest → 270+ verts.
  - vitest → 140+ verts.

- [ ] **Step 10.5 — Push distant + tag v2.1.0-alpha.3**

- [ ] **Step 10.6 — Checkpoint Plan 5C**

- [ ] **Step 10.7 — Commit final**

---

## Vérification finale Plan 5C

- [ ] 270+ tests pytest verts.
- [ ] 140+ tests vitest verts.
- [ ] Prompt "refactor X" (complex) active CHALLENGE + PLAN consensus R1+Pro.
- [ ] Si R1/Pro d'accord round 1 → pipeline continue direct.
- [ ] Si R1/Pro deadlock 2 rounds → modal UI avec 2 plans, user choisit.
- [ ] Prompt medium n'appelle pas CHALLENGE (seulement REVIEW stub).
- [ ] RoutingTab TraceViewer affiche consensus rounds.

---

## Récap Plan 5C

**10 tasks, 5 phases** :

| Phase | Tasks | Impact | Durée |
|-------|-------|--------|-------|
| C1 CHALLENGE | 1-2 | Avocat du diable Gemini Pro | 1.5 jour |
| C2 PLAN R1 | 3-4 | Plan architectural détaillé | 2 jours |
| C3 PLAN REVIEW + consensus | 5-7 | Accord 2/2 R1+Pro | 3.5 jours |
| C4 Pipeline modes complet | 8-9 | Dispatch multi-LLM explicite | 1.5 jour |
| C5 E2E + Release | 10 | Validation medium/complex | 1 jour |

**Total : ~9.5 jours (1.5-2 semaines full-time).**

**Post-Plan 5C :** Plan 5D ajoutera SELF-CHECK + REVIEW + SECOND-REVIEW avec consensus 2/2 pour le cross-review final.

---

*Plan 5C validation-ready après Plan 5B livré.*
