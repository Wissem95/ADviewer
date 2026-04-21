# LocalCoder IDE v2.1 — Plan 5D : SELF-CHECK + REVIEW + SECOND-REVIEW (consensus 2/2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`. TDD strict obligatoire.

**Goal :** Ajouter les dernières couches de re-vérification pour atteindre le taux cible ~99% zéro-erreur. Stage6 SELF-CHECK (MiniMax relit son propre diff). Stage8 REVIEW (Gemini Pro review le diff). Stage9 SECOND-REVIEW (DeepSeek R1) déclenché conditionnellement si Stage8 flag major/critical. Mécanisme consensus 2/2 avec modal disagreement user.

**Architecture :** Stage6 réutilise MiniMax avec posture "reviewer" (même LLM, prompt différent). Stage8 = Gemini Pro autonome. Stage9 = DeepSeek R1 qui reçoit le diff + rapport Pro. Consensus 2/2 sur décision finale commit vs retry vs rollback.

**Tech stack ajouté :** Aucun.

**Prérequis :** Plans 5A + 5B + 5C complets. Pipeline complex active en mode stub pour 6/8/9, à remplacer par vrais stages.

**Durée estimée :** 1 semaine (5-7 jours full-time).

**Résultat attendu :**
- 310+ tests pytest verts.
- 155+ tests vitest verts.
- Pipeline complex avec mécanismes re-vérification complet.
- Bugs volontaires détectés par SELF-CHECK/REVIEW sans atteindre main.
- Consensus disagreement entre Pro et R1 → modal UI pour décision user.
- Taux d'erreur mesuré sur benchmark ~1-3% (vs ~10% sans ces stages).

---

## Fichiers créés ou modifiés

```
backend/
├── pipeline/
│   ├── stage_6_self_check.py           # CRÉÉ (remplace stub)
│   ├── stage_8_review.py               # CRÉÉ (remplace stub)
│   ├── stage_9_second_review.py        # CRÉÉ (remplace stub)
│   ├── review_consensus.py             # CRÉÉ — mécanisme consensus 8+9
│   └── orchestrator.py                 # MODIFIÉ — branchement 6/8/9 réels
├── prompts/
│   ├── stage_6_self_check.md           # CRÉÉ
│   ├── stage_8_review.md               # CRÉÉ
│   └── stage_9_second_review.md        # CRÉÉ

tests/backend/
├── test_stage_6_self_check.py          # CRÉÉ
├── test_stage_8_review.py              # CRÉÉ
├── test_stage_9_second_review.py       # CRÉÉ
├── test_review_consensus.py            # CRÉÉ
├── test_pipeline_e2e_full_complex.py   # CRÉÉ
└── test_pipeline_bug_detection.py      # CRÉÉ — benchmark détection bugs

ui/src/
├── components/
│   ├── Pipeline/
│   │   ├── ReviewPanel.tsx             # CRÉÉ — affiche findings Pro + R1
│   │   ├── ReviewDisagreementModal.tsx # CRÉÉ — modal décision consensus
│   │   └── SelfCheckBadge.tsx          # CRÉÉ — indicateur auto-corrections
│   └── tabs/RoutingTab/
│       └── TraceViewer.tsx             # MODIFIÉ — sections review expandables
└── stores/
    └── pipelineStore.ts                # MODIFIÉ — reviewResults, disagreement
```

---

# PHASE D1 — SELF-CHECK (Tasks 1-2)

## Task 1 : Prompt + implémentation Stage6SelfCheck

**Files:** `backend/prompts/stage_6_self_check.md`, `backend/pipeline/stage_6_self_check.py`, `tests/backend/test_stage_6_self_check.py`.

**Durée :** 1 jour.

- [ ] **Step 1.1 — System prompt `stage_6_self_check.md`**

  Rôle : "Tu as écrit ce code. Maintenant tu es reviewer strict. Cherche tes propres bugs."

  Instructions :
  1. Lis ton diff.
  2. Vérifie : imports manquants, typos, logique cassée, edge cases du plan oubliés.
  3. Si tu trouves des problèmes → utilise `patch_file` pour les corriger.
  4. Sinon, termine par un message : "Self-check OK" + confidence.

  Output attendu : soit tool_calls de correction, soit message final structuré.

- [ ] **Step 1.2 — Tests rouges Stage6**

  Scénarios :
  - Mock LLM dit "OK" sans tool_calls → SelfCheckResult(issues_found=[], confidence="high").
  - Mock LLM retourne tool_call patch_file puis "corrigé" → SelfCheckResult(corrections_applied=[...], confidence="medium").
  - Mock LLM boucle 20 tool_calls → budget dépassé, return sans crash.

- [ ] **Step 1.3 — Implémenter Stage6SelfCheck**

  `_llm_for_stage()` retourne `"minimax/minimax-m2.5"` (même que Stage5).

  `_execute` :
  - Récupère `ctx.stage_results["execute"].output.diffs`.
  - Construit user message avec le diff + le plan initial.
  - Boucle tool-calling avec `TOOLS_SCHEMA_WRITE` restreint à `[patch_file, read_file]` (pas de create/delete en self-check).
  - Parse message final pour `confidence` et `issues_found`.

  Retourne `SelfCheckResult(issues_found, corrections_applied, confidence)`.

- [ ] **Step 1.4 — Commit**

---

## Task 2 : UI SelfCheckBadge

**Files:** `ui/src/components/Pipeline/SelfCheckBadge.tsx`, `TraceViewer.tsx` (MODIFIÉ).

**Durée :** 0.5 jour.

- [ ] **Step 2.1 — SelfCheckBadge.tsx**

  Badge coloré selon confidence :
  - `high` + 0 corrections → vert "✓ Self-check OK".
  - `medium` + N corrections → orange "⚠ N corrections auto-appliquées".
  - `low` → rouge "⚠ doutes persistants".

- [ ] **Step 2.2 — Intégrer dans StageRow self_check**

  Expand affiche : liste corrections_applied + liste issues_found.

- [ ] **Step 2.3 — Commit**

---

# PHASE D2 — REVIEW Gemini Pro (Tasks 3-4)

## Task 3 : Prompt + implémentation Stage8Review

**Files:** `backend/prompts/stage_8_review.md`, `backend/pipeline/stage_8_review.py`, `tests/backend/test_stage_8_review.py`.

**Durée :** 1 jour.

- [ ] **Step 3.1 — System prompt `stage_8_review.md`**

  Rôle : reviewer expert externe post-VERIFY.

  Check-list imposée :
  1. Bugs logiques (off-by-one, race conditions, null checks).
  2. Régressions potentielles (appelants cassés).
  3. Code smells (duplication, fonctions trop longues).
  4. Sécurité (SQL injection, XSS, path traversal, secrets).
  5. Style / conventions projet.

  Output JSON strict :
  ```
  {
    "findings": [
      {"severity": "ok|minor|major|critical",
       "category": "bug|regression|smell|security|style",
       "location": "file:line",
       "description": "...",
       "suggested_fix": "..."}
    ],
    "severity_max": "...",
    "approve": true/false
  }
  ```

- [ ] **Step 3.2 — Tests rouges Stage8**

  Scénarios :
  - Mock Pro retourne findings [ok, minor] → approve=True, severity_max="minor".
  - Mock retourne 1 critical → approve=False, severity_max="critical".

- [ ] **Step 3.3 — Implémenter Stage8Review**

  `_llm_for_stage()` retourne `"gemini/gemini-2.5-pro"`.

  Tools autorisés en lecture : `read_file` (pour lire contexte étendu si besoin).

  Retourne `ReviewResult(findings, severity_max, approve)`.

- [ ] **Step 3.4 — Commit**

---

## Task 4 : UI ReviewPanel (Pro seul)

**Files:** `ui/src/components/Pipeline/ReviewPanel.tsx`.

**Durée :** 0.5 jour.

- [ ] **Step 4.1 — ReviewPanel.tsx**

  Tableau des findings :
  | Severity | Category | Location | Description | Fix suggested |
  |----------|----------|----------|-------------|---------------|

  Filtres : par severity, par category.
  Badge global "approve" / "reject".

- [ ] **Step 4.2 — Intégrer dans StageRow review**

- [ ] **Step 4.3 — Commit**

---

# PHASE D3 — SECOND-REVIEW + Consensus 2/2 (Tasks 5-7)

## Task 5 : Prompt + implémentation Stage9SecondReview

**Files:** `backend/prompts/stage_9_second_review.md`, `backend/pipeline/stage_9_second_review.py`, `tests/backend/test_stage_9_second_review.py`.

**Durée :** 1 jour.

- [ ] **Step 5.1 — System prompt `stage_9_second_review.md`**

  Rôle : arbitre indépendant. R1 reçoit diff + rapport Pro.

  3 questions imposées :
  1. "Es-tu d'accord avec les findings de Pro ?"
  2. "As-tu d'autres findings que Pro a manqués ?"
  3. "Verdict : approve / revise / reject ?"

  Output JSON strict :
  ```
  {
    "agrees_with_pro": true/false,
    "additional_findings": [Finding objects],
    "verdict": "approve|revise|reject",
    "reasoning": "..."
  }
  ```

- [ ] **Step 5.2 — Tests rouges Stage9**

  Scénarios :
  - R1 agrees avec Pro approve → approve.
  - R1 disagrees, trouve bugs supplémentaires → verdict=reject.
  - R1 partial : agrees avec findings mais pense que c'est pas critique → verdict=approve.

- [ ] **Step 5.3 — Implémenter Stage9SecondReview**

  `_llm_for_stage()` retourne `"deepseek/deepseek-r1"`.

  Reçoit `ctx.stage_results["review"].output` + diffs.

  Retourne `SecondReviewResult(agrees_with_pro, additional_findings, verdict, reasoning)`.

- [ ] **Step 5.4 — Commit**

---

## Task 6 : Mécanisme consensus 2/2

**Files:** `backend/pipeline/review_consensus.py`, `backend/pipeline/orchestrator.py` (MODIFIÉ), `tests/backend/test_review_consensus.py`.

**Durée :** 1.5 jour.

- [ ] **Step 6.1 — `review_consensus.py`**

  Fonction `async def run_review_consensus(ctx, llm_manager, ws_streamer) -> ReviewConsensusResult`.

  Algorithme :
  ```
  stage_8 = Stage8Review → R_pro
  if R_pro.severity_max in {ok, minor}:
    return ReviewConsensusResult(verdict="approve", reason="pro_ok", second_review=None)

  # severity_max in {major, critical} → déclencher Stage9
  stage_9 = Stage9SecondReview avec R_pro en contexte → R_r1

  # Logique consensus 2/2:
  if R_pro.approve == False and R_r1.verdict == "reject":
    return ReviewConsensusResult(verdict="retry_execute", reason="consensus_reject",
                                  findings_merged=R_pro.findings + R_r1.additional_findings)
  if R_pro.approve == False and R_r1.verdict == "approve":
    # Pro inquiet, R1 zen → disagreement
    return ReviewConsensusResult(verdict="disagreement", awaiting_user=True,
                                  pro_report=R_pro, r1_report=R_r1)
  if R_pro.approve == True and R_r1.verdict in {"approve", "revise"}:
    return ReviewConsensusResult(verdict="approve", reason="consensus_approve")
  ```

  Émet events `consensus_review_round`, `consensus_disagreement_review` selon cas.

- [ ] **Step 6.2 — Tests rouges consensus review**

  6 scénarios couvrant tous les cas de la matrice :
  - Pro approve → skip R1, pipeline continue.
  - Pro critical + R1 agrees reject → retry_execute.
  - Pro critical + R1 approve → disagreement modal.
  - Pro major + R1 revise → approve.
  - Etc.

- [ ] **Step 6.3 — Intégrer dans Pipeline orchestrator**

  Mode medium : Stage7 → Stage8 seul → si approve, continue commit ; sinon retry_execute max 3x.

  Mode complex : Stage7 → `run_review_consensus` → selon verdict, continue / retry / disagreement user.

  Si `disagreement` → émet `pipeline_user_decision_needed` → attend `user_decision` → apply / rollback / retry.

- [ ] **Step 6.4 — Retry execute depuis review**

  Si consensus retry_execute : Pipeline retourne à Stage5 avec les findings merged en feedback. Max 3x.

- [ ] **Step 6.5 — Commit**

---

## Task 7 : UI ReviewDisagreementModal

**Files:** `ui/src/components/Pipeline/ReviewDisagreementModal.tsx`, `pipelineStore.ts` (MODIFIÉ).

**Durée :** 1 jour.

- [ ] **Step 7.1 — ReviewDisagreementModal.tsx**

  Modal full-screen quand disagreement :
  - Header : "⚖️ Reviewers en désaccord — ta décision"
  - Split view :
    - Gauche : "Gemini Pro dit" + liste findings avec severity.
    - Droite : "DeepSeek R1 dit" + verdict + reasoning + additional_findings.
  - Milieu : diff complet du code concerné (syntax highlighted).
  - Boutons bas :
    - "Appliquer quand même" (commit malgré les inquiétudes Pro).
    - "Rollback" (abandon, stash pop).
    - "Retry avec instructions" (textarea pour que user donne guidance à Stage5).

- [ ] **Step 7.2 — Store handler review disagreement**

  State : `reviewDisagreement: {pro_report, r1_report, diff} | null`.

  Handler WS `consensus_disagreement_review`.

  Action `resolveReviewDisagreement(choice, custom_instructions?)`.

- [ ] **Step 7.3 — Tests vitest**

- [ ] **Step 7.4 — Commit**

---

# PHASE D4 — Benchmark + Tests E2E (Tasks 8-9)

## Task 8 : Benchmark détection bugs

**Files:** `tests/backend/test_pipeline_bug_detection.py`, `tests/fixtures/bug_scenarios.py`.

**Durée :** 1 jour.

- [ ] **Step 8.1 — Fixtures `bug_scenarios.py`**

  10 scénarios de bugs volontaires :
  1. Off-by-one (loop range n vs n+1).
  2. Null check manquant.
  3. SQL injection (f-string).
  4. Import manquant.
  5. Typo dans nom de fonction.
  6. Race condition (shared mutable state).
  7. Path traversal (pas de `resolve()`).
  8. Secret hardcodé.
  9. Régression : change signature sans update callers.
  10. Edge case : division par zéro.

  Chaque scénario = `{bug_type, prompt, scripted_execute_response, expected_detection_stage}`.

- [ ] **Step 8.2 — Test paramétré**

  `@pytest.mark.parametrize("scenario", BUG_SCENARIOS)` → run pipeline avec bug → vérifier :
  - `scenario["expected_detection_stage"]` en `{"self_check", "verify", "review", "second_review"}`.
  - Pipeline ne commit PAS le code buggé (rollback ou retry corrigé).

- [ ] **Step 8.3 — Mesurer taux détection**

  Log le résultat par scénario. Afficher tableau final :
  - X/10 bugs détectés par self_check.
  - Y/10 par verify.
  - Z/10 par review.
  - W/10 par second_review.
  - 0/10 ayant atteint commit.

  **Cible : 10/10 non-commité.**

- [ ] **Step 8.4 — Commit**

---

## Task 9 : Tests E2E full complex + release

**Files:** `tests/backend/test_pipeline_e2e_full_complex.py`, README MAJ, tag.

**Durée :** 1 jour.

- [ ] **Step 9.1 — Test E2E "happy path" complex**

  Prompt complex → 11 étapes → commit.

  Scripted responses pour toutes étapes : estimate, intake, challenge, ground, plan_r1=approve, plan_pro=approve, execute, self_check=ok, verify=green, review=ok, (pas de second_review).

  Assertions :
  - 10 LLM calls (tous sauf Stage9).
  - total_cost < $0.15.
  - Fichier final correct.
  - Pipeline_complete event émis.

- [ ] **Step 9.2 — Test E2E "second review triggered"**

  Stage8 retourne severity=major → Stage9 appelé → R1 agrees approve → pipeline continue.

- [ ] **Step 9.3 — Test E2E "disagreement resolved by user"**

  Pro critical + R1 approve → pipeline_user_decision_needed émis. Simuler user_decision="apply" → commit quand même avec warning loggé.

- [ ] **Step 9.4 — Test E2E "consensus reject → retry → success"**

  Round 1 : execute produit code avec bug → self_check ne détecte pas → verify vert (le bug n'est pas un test fail) → review Pro critical + R1 reject → retry_execute.

  Round 2 : execute corrige → verify vert → review ok → commit.

  Vérifie `attempts_used_execute=2`.

- [ ] **Step 9.5 — Suite tests complète**

  - pytest → 310+ verts.
  - vitest → 155+ verts.

- [ ] **Step 9.6 — Push distant + tag v2.1.0-alpha.4**

- [ ] **Step 9.7 — Checkpoint Plan 5D avec métriques benchmark**

- [ ] **Step 9.8 — Commit final**

---

## Vérification finale Plan 5D

- [ ] 310+ tests pytest verts.
- [ ] 155+ tests vitest verts.
- [ ] Benchmark : 10/10 bugs volontaires détectés (aucun n'atteint commit).
- [ ] Pipeline complex : Stage6 SELF-CHECK actif, Stage8 REVIEW actif, Stage9 conditionnel.
- [ ] Disagreement Pro/R1 → modal user, choix appliqué.
- [ ] Taux d'erreur complex sur benchmark : < 3%.

---

## Récap Plan 5D

**9 tasks, 4 phases** :

| Phase | Tasks | Impact | Durée |
|-------|-------|--------|-------|
| D1 SELF-CHECK | 1-2 | Executor relit son propre diff | 1.5 jour |
| D2 REVIEW Pro | 3-4 | Premier reviewer externe | 1.5 jour |
| D3 SECOND-REVIEW + consensus | 5-7 | Arbitre R1 + modal disagreement | 3.5 jours |
| D4 Benchmark + E2E | 8-9 | Validation taux zéro-erreur | 2 jours |

**Total : ~8.5 jours (1.5 semaine full-time).**

**Post-Plan 5D :** Le pipeline est COMPLET. Plans 5E (UX) et 5F (packaging) finalisent la v2.0.0.

---

*Plan 5D validation-ready après Plan 5C livré. À la fin de 5D, le taux d'erreur cible est atteint.*
