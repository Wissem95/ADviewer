# LocalCoder IDE v2.1 — Pipeline Rigoureux

**Date :** 2026-04-20
**Statut :** À valider
**Auteur :** Wissem × Claude
**Référence :** étend `specs/2026-04-10-localcoder-ide-v2-design.md`
**Remplace :** architecture AgentLoop 5-étapes mono-agent de Plan 2

---

## 1. Contexte et objectif

### 1.1 Le gap actuel

L'implémentation Plans 1-4 a livré l'infrastructure (routing, mémoire, locks, CI webhooks, GitHub mode) mais le cœur fonctionnel — transformer un prompt en modification de fichier garantie — n'existe pas :

- `AgentLoop.run()` produit du texte, n'écrit aucun fichier.
- `Orchestrator.handle()` ignore `decision.mode` (simple/medium/multi_agent), utilise toujours un seul LLM.
- Aucun mécanisme de grounding factuel, de consensus, de re-vérification.

### 1.2 La vision "zéro erreur"

Construire un agent qui :
- **Ne suppose jamais** : toute décision est ancrée dans des fichiers lus ou des tests passés.
- **Challenge ses propres plans** : au moins 2 LLMs valident les décisions critiques.
- **Vérifie mécaniquement** : tests réels exécutés avant tout commit.
- **Rollback automatiquement** : `git stash` avant modif, restauration si échec.
- **Estime le coût avant de dépenser** : preview tokens + $ avant validation user.

### 1.3 Cible réaliste

| Mode | Complexité | Succès visé | Coût/prompt | Durée |
|------|-----------|-------------|-------------|-------|
| simple | typo, rename, 1 fichier | 99% | ~$0.002 | 5-15s |
| medium | feature locale, 2-3 fichiers | 97% | ~$0.02 | 20-40s |
| complex | refacto, archi, ≥4 fichiers | 95%+ (avec re-vérif) | ~$0.08-0.15 | 2-8 min |

Les 1-5% d'échecs résiduels se traduisent par : **rollback propre + flag user**, jamais par du code corrompu en main.

---

## 2. Architecture globale

### 2.1 Vue d'ensemble

```
USER PROMPT
    │
    ▼
[ORCHESTRATOR — dispatch par étape]
    │
    ├─ ÉTAPE 0  ESTIMATE       (Flash)      ─── Preview coût ──► User confirme
    ├─ ÉTAPE 1  INTAKE          (Flash)
    ├─ ÉTAPE 2  CHALLENGE       (Pro)        [complex only]
    ├─ ÉTAPE 3  GROUND          (MiniMax)
    ├─ ÉTAPE 4  PLAN+CONSENSUS  (R1 + Pro)   [complex only pour 4b]
    ├─ ÉTAPE 5  EXECUTE         (MiniMax)
    ├─ ÉTAPE 6  SELF-CHECK      (MiniMax)
    ├─ ÉTAPE 7  VERIFY          (mécanique, pas de LLM)
    ├─ ÉTAPE 8  REVIEW          (Pro)
    ├─ ÉTAPE 9  SECOND-REVIEW   (R1)         [si étape 8 flag]
    └─ ÉTAPE 10 COMMIT + CI     (git + webhook) [mode projet]
```

### 2.2 Dispatch multi-LLM — un LLM par rôle

| Étape | LLM | Prix in/out par 1M | Raison du choix |
|-------|-----|---------------------|------------------|
| 0 ESTIMATE | Gemini 2.5 Flash | $0.075 / $0.30 | Rapide, JSON, pas cher |
| 1 INTAKE | Gemini 2.5 Flash | $0.075 / $0.30 | Classification rapide |
| 2 CHALLENGE | Gemini 2.5 Pro | $1.25 / $10.00 | Analyse critique, 1M contexte |
| 3 GROUND | MiniMax M2.5 | $0.118 / $0.99 | Coding SWE-bench 80%, exploration code |
| 4a PLAN | DeepSeek R1 | $0.55 / $2.19 | Reasoning spécialisé, architecture |
| 4b PLAN-REVIEW | Gemini 2.5 Pro | $1.25 / $10.00 | Contre-expertise, 1M contexte |
| 5 EXECUTE | MiniMax M2.5 | $0.118 / $0.99 | Coding champion |
| 6 SELF-CHECK | MiniMax M2.5 | $0.118 / $0.99 | Même LLM relit son travail |
| 7 VERIFY | ∅ (subprocess) | $0 | pytest/vitest/cargo/ruff/eslint |
| 8 REVIEW | Gemini 2.5 Pro | $1.25 / $10.00 | Review diff avec 1M contexte |
| 9 SECOND-REVIEW | DeepSeek R1 | $0.55 / $2.19 | Avis indépendant, reasoning |
| tests unitaires | Codestral 2 | $0.30 / $0.90 | Spécialiste génération tests |

### 2.3 Trois modes de pipeline

Les modes activent des sous-ensembles d'étapes selon la complexité détectée à l'étape 0 :

```
MODE SIMPLE   (score ≤ 4) : 0 → 1 → 3 → 5 → 7 → commit
MODE MEDIUM   (score ≤ 7) : 0 → 1 → 3 → 5 → 6 → 7 → 8 → commit
MODE COMPLEX  (score ≥ 8) : 0 → 1 → 2 → 3 → 4a → 4b → 5 → 6 → 7 → 8 → (9) → commit
```

- **Simple** : 3 LLM calls (Flash intake + MiniMax ground + MiniMax execute).
- **Medium** : 5 LLM calls (+ self-check + review).
- **Complex** : 9-10 LLM calls (consensus plan + second-review conditionnel).

Le mode `complex` est le **défaut** pour tout prompt ambigu. L'utilisateur peut forcer `simple` via bouton "Forcer mode simple" dans le modal ESTIMATE, ou via mention explicite.

---

## 3. Les 11 étapes en détail

Chaque étape est spécifiée par :
- **Contrat d'entrée** : ce qu'elle reçoit.
- **LLM & prompt** : quel modèle, quel system prompt.
- **Contrat de sortie** : ce qu'elle produit (types stricts).
- **Garantie** : invariant à la sortie.
- **Fallback** : comportement si échec.

### 3.1 ÉTAPE 0 — ESTIMATE

**Contrat d'entrée** : `{prompt: str, cwd: str, workspace_state: WorkspaceState}`

**LLM** : Gemini 2.5 Flash.
**System prompt** : `backend/prompts/stage_0_estimate.md` (à créer).
**Budget** : max 500 tokens input, 400 tokens output, timeout 5s.

**Contrat de sortie** :
```python
@dataclass
class EstimateResult:
    classification: Literal["simple", "medium", "complex"]
    complexity_score: int  # 0-10
    reason: str
    estimated_tokens: dict[str, StageEstimate]  # par étape
    estimated_cost_usd: float
    estimated_duration_seconds: int
    estimated_files_touched: list[str]  # best effort
    confidence: Literal["low", "medium", "high"]
    ambiguities: list[str]  # questions à poser si confidence=low
```

**Garantie** : aucun autre LLM appelé tant que l'utilisateur n'a pas confirmé (ou auto-approve si `cost < SEUIL_AUTO_APPROVE`).

**Fallback** : si Flash indisponible → fallback sur MiniMax. Si les deux → estimation par règles heuristiques (complexité basée sur nombre de fichiers mentionnés, longueur prompt, mots-clés).

**Event WS émis** : `pipeline_estimate` avec le payload complet.

**UI** : modal de confirmation si `cost > SEUIL` OU `classification == "complex"`.

### 3.2 ÉTAPE 1 — INTAKE

**Contrat d'entrée** : `{prompt, estimate, user_confirmed: True}`

**LLM** : Gemini 2.5 Flash.
**System prompt** : `backend/prompts/stage_1_intake.md`.

**Rôle** :
- Valide que le prompt n'est plus ambigu (sinon bloque et demande clarification user).
- Extrait entités : fichiers cibles, verbes d'action, contraintes.
- Reconfirme la classification de ESTIMATE (peut la corriger).

**Contrat de sortie** :
```python
@dataclass
class IntakeResult:
    prompt_cleaned: str  # reformulation non-ambiguë
    target_files_hint: list[str]
    action_verbs: list[str]  # "refactor", "add", "fix", ...
    constraints: list[str]
    mode_final: Literal["simple", "medium", "complex"]
    needs_clarification: bool
    clarification_questions: list[str]  # si needs_clarification
```

**Garantie** : à la sortie, on a un prompt traité sans ambiguïté connue.

**Fallback** : si ambiguïté irréductible → stop pipeline, affiche les questions à l'utilisateur.

**Event WS émis** : `stage_complete` avec `{stage: "intake", result}`.

### 3.3 ÉTAPE 2 — CHALLENGE (complex uniquement)

**Contrat d'entrée** : `{intake_result, grounded_context: None}`

**LLM** : Gemini 2.5 Pro.
**System prompt** : `backend/prompts/stage_2_challenge.md`.

**Rôle** : avocat du diable. Identifie angles morts.

**Contrat de sortie** :
```python
@dataclass
class ChallengeResult:
    risks: list[str]         # 3 risques principaux (régression, perf, sécu)
    edge_cases: list[str]    # 3 edge cases oubliés
    alternatives: list[str]  # 1-2 approches plus simples
    severity: Literal["minor", "major", "critical"]
    blocking: bool           # True si Pro pense que le prompt est une mauvaise idée
```

**Garantie** : toute décision ultérieure prend en compte les risques identifiés.

**Fallback** : si Pro indisponible → fallback R1 (cher mais dispo). Si `blocking == True` → demande validation user avant de continuer.

**Event WS émis** : `stage_complete` avec le rapport challenge affichable dans un panel dédié.

### 3.4 ÉTAPE 3 — GROUND

**Contrat d'entrée** : `{intake_result, challenge_result?}`

**LLM** : MiniMax M2.5 en mode **tools read-only**.
**System prompt** : `backend/prompts/stage_3_ground.md`.

**Tools disponibles** (read-only) :
- `read_file(path, max_bytes=100_000)` → contenu tronqué si trop gros.
- `grep_codebase(pattern, path_glob?)` → matches avec line numbers.
- `list_files(path, recursive=False)` → arborescence.

**Règles strictes imposées par le system prompt** :
1. Tu dois lire TOUS les fichiers mentionnés par INTAKE.
2. Tu dois grep tous les **appelants** des fonctions à modifier.
3. Tu dois CITER chaque fait (format `file.py:42`).
4. Interdiction d'affirmer sans citer.
5. Si tu ne peux pas prouver, tu dis "unknown".

**Contrat de sortie** :
```python
@dataclass
class GroundedContext:
    files_read: dict[str, str]  # path → content (ou hash+excerpt si trop gros)
    greps_performed: list[GrepResult]
    facts: list[Fact]  # chaque fact a une citation {file, line, excerpt}
    unknowns: list[str]  # ce qu'on n'a pas pu vérifier
    budget_used_tokens: int
```

**Garantie** : zéro fact sans citation. Les unknowns sont remontés aux étapes suivantes pour qu'elles prennent le risque en connaissance de cause.

**Fallback** : max 20 tool calls. Si dépassé → stop et flag user.

**Event WS émis** : `stage_complete`, `tool_call` (un par appel de tool pour trace live).

### 3.5 ÉTAPE 4 — PLAN avec CONSENSUS

**Contrat d'entrée** : `{intake_result, challenge_result?, grounded_context}`

#### 4a — PLAN primaire

**LLM** : DeepSeek R1.
**System prompt** : `backend/prompts/stage_4a_plan.md`.

**Contrat de sortie** :
```python
@dataclass
class Plan:
    changes: list[PlannedChange]
    tests_to_run: list[str]  # pytest/vitest paths ou nodeids
    rollback_strategy: str
    rationale: str  # référence les facts de grounded_context
    estimated_risk: Literal["low", "medium", "high"]
    complexity_confirm: int  # 0-10

@dataclass
class PlannedChange:
    file: str
    operation: Literal["edit", "create", "delete", "patch"]
    description: str
    intended_diff_summary: str
```

#### 4b — CONSENSUS REVIEW (complex uniquement)

**LLM** : Gemini 2.5 Pro.
**System prompt** : `backend/prompts/stage_4b_plan_review.md`.

**Rôle** : relit le Plan produit par R1. Vote.

**Contrat de sortie** :
```python
@dataclass
class PlanReview:
    verdict: Literal["approve", "revise", "reject"]
    concerns: list[str]
    suggested_changes: list[str]  # modifs au plan
    merged_plan: Optional[Plan]  # si revise: plan fusionné proposé
```

**Algorithme consensus** :
```
round 1 : R1 produit plan P1
          Pro review P1 → verdict V1

si V1 == "approve" : plan_final = P1, continue à étape 5
si V1 == "reject"  : R1 re-plan avec concerns Pro
                     → P2
                     → Pro review P2 → V2
si V2 == "approve" : plan_final = P2, continue
si V2 == "reject"  : flag user (deadlock, 2 plans proposés côte à côte)
si V == "revise"   : plan_final = merged_plan de Pro (compromis)
```

**Garantie** : en mode complex, aucun plan non-validé par 2 LLMs ne passe à EXECUTE. En mode simple/medium, le plan R1 passe direct (pas d'étape 4b).

**Coût consensus** : ~1.5-2x le coût d'un plan simple en mode complex.

**Event WS émis** : `stage_complete` (plan final), `consensus_round` par round.

### 3.6 ÉTAPE 5 — EXECUTE

**Contrat d'entrée** : `{plan_final, grounded_context}`

**LLM** : MiniMax M2.5 en mode **tools write**.
**System prompt** : `backend/prompts/stage_5_execute.md`.

**Préambule mécanique (orchestrator, pas LLM)** :
- `git stash push -m "pipeline_pre_execute_<uuid>"` → snapshot.
- Enregistrer le `stash_ref` pour rollback.

**Tools disponibles** (write) :
- `edit_file(path, new_content)` — full replace, file lock acquired.
- `patch_file(path, old_str, new_str)` — edit chirurgical (pour gros fichiers).
- `create_file(path, content)` — fail si existe.
- `delete_file(path)` — soft delete via git.

**Boucle interne** :
```
pour chaque PlannedChange dans plan_final.changes:
  tool_call = LLM décide du tool approprié
  exec tool
  new_content = read_file(path)
  diff = compute_diff(before, new_content)
  si diff est cohérent avec intended_diff_summary:
    continue
  sinon:
    inject diff observation dans contexte LLM
    retry tool_call (max 3 par change)
```

**Contrat de sortie** :
```python
@dataclass
class ExecuteResult:
    files_modified: list[str]
    diffs: dict[str, str]  # path → git diff
    stash_ref: str  # pour rollback
    tool_calls_log: list[ToolCall]
    budget_used_tokens: int
```

**Garantie** : tous les changements du plan ont été tentés. Si un change échoue 3x → rollback complet via `git stash pop`.

**Event WS émis** : `tool_call` par appel, `stage_progress` pour "2/4 fichiers".

### 3.7 ÉTAPE 6 — SELF-CHECK

**Contrat d'entrée** : `{execute_result, plan_final, grounded_context}`

**LLM** : MiniMax M2.5 (le MÊME qui a exécuté, pas un autre — c'est volontaire).
**System prompt** : `backend/prompts/stage_6_self_check.md`.

**Rôle** : l'executor relit son propre diff avec une posture critique.

Le prompt impose :
1. "Voici ton diff. Relis-le comme si tu étais un reviewer strict."
2. "Identifie : imports manquants, typos, logique cassée, edge cases oubliés du plan."
3. "Si tu trouves quelque chose → propose un edit_file de correction."
4. "Si rien trouvé → dis-le explicitement et justifie."

**Contrat de sortie** :
```python
@dataclass
class SelfCheckResult:
    issues_found: list[str]
    corrections_applied: list[ToolCall]
    confidence: Literal["high", "medium", "low"]
```

**Garantie** : l'executor a eu l'opportunité de rattraper ses propres bugs avant les tests.

**Pourquoi le même LLM ?** Les études LLM montrent que demander à un LLM de relire son propre travail avec un nouveau prompt ("tu es un reviewer") attrape 30-40% des bugs qu'il a laissés. Un autre LLM ferait ça en étape 8 (REVIEW), pas ici.

**Event WS émis** : `stage_complete` avec `{issues_found_count, corrections_count}`.

### 3.8 ÉTAPE 7 — VERIFY

**Pas de LLM.** Orchestrator lance des subprocess.

**Entrée** : `files_modified` de EXECUTE + `tests_to_run` du plan.

**Actions** :
```python
for file in files_modified:
    if file.endswith(".py"):
        run("ruff check", file)
    elif file.endswith((".ts", ".tsx")):
        run("npx eslint", file)

# Tests
for test in tests_to_run:
    if test.startswith("tests/backend/"):
        run("python -m pytest", test, "-v", "--tb=short")
    elif test.startswith("ui/"):
        run("cd ui && npx vitest run", test)

# Rust si touché
if any(f.endswith(".rs") for f in files_modified):
    run("cargo check", cwd="ui/src-tauri/")
```

**Algorithme retry** :
```
attempt = 1
while attempt <= 3:
    errors = run_all_verifications()
    if not errors: break
    inject errors into EXECUTE context
    go back to étape 5
    attempt += 1

si attempt > 3:
    git stash pop  # ROLLBACK COMPLET
    flag user avec les erreurs
    pipeline stop
```

**Contrat de sortie** :
```python
@dataclass
class VerifyResult:
    lint_errors: dict[str, list[str]]
    test_results: dict[str, TestRunResult]  # passed/failed/skipped par suite
    all_green: bool
    attempts_used: int
```

**Garantie** : si `all_green == False` après 3 tentatives → rollback total, aucune modification en main.

**Event WS émis** : `verify_progress` par test, `stage_complete` avec rapport final.

### 3.9 ÉTAPE 8 — REVIEW

**Contrat d'entrée** : `{execute_result.diffs, plan_final, grounded_context}`

**LLM** : Gemini 2.5 Pro (1M contexte, idéal pour charger tout le projet si besoin).
**System prompt** : `backend/prompts/stage_8_review.md`.

**Rôle** : reviewer expert externe. Cherche ce qui échappe aux tests.

**Check-list imposée** :
1. Bugs logiques (off-by-one, race conditions, null checks manquants).
2. Régressions potentielles (appelants cassés par le nouveau signature).
3. Code smells (duplication, fonctions trop longues, naming).
4. Sécurité (SQL injection, XSS, path traversal, secrets exposés).
5. Style / convention (aligné sur le reste du projet).

**Contrat de sortie** :
```python
@dataclass
class ReviewResult:
    findings: list[Finding]
    severity_max: Literal["ok", "minor", "major", "critical"]
    approve: bool  # True si severity_max in {ok, minor}

@dataclass
class Finding:
    severity: Literal["ok", "minor", "major", "critical"]
    category: Literal["bug", "regression", "smell", "security", "style"]
    location: str  # file:line
    description: str
    suggested_fix: Optional[str]
```

**Décision post-review** :
- `severity_max == "ok"` : passe directement à commit.
- `severity_max == "minor"` : passe à commit (les minors sont loggés mais pas bloquants).
- `severity_max == "major"` ou `"critical"` : déclenche étape 9 SECOND-REVIEW.

**Event WS émis** : `stage_complete` avec tous les findings.

### 3.10 ÉTAPE 9 — SECOND-REVIEW (conditionnel)

**Déclenché si** : étape 8 retourne `severity_max in {"major", "critical"}`.

**Contrat d'entrée** : `{execute_result.diffs, plan_final, grounded_context, review_result_pro}`

**LLM** : DeepSeek R1 (reasoning, indépendant de Pro).
**System prompt** : `backend/prompts/stage_9_second_review.md`.

**Rôle** : arbitre. R1 reçoit le diff ET le rapport de Pro.

**Trois questions imposées** :
1. "Es-tu d'accord avec les findings de Pro ?"
2. "As-tu d'autres findings que Pro a manqués ?"
3. "Recommandation finale : approve, revise, reject ?"

**Contrat de sortie** :
```python
@dataclass
class SecondReviewResult:
    agrees_with_pro: bool
    additional_findings: list[Finding]
    verdict: Literal["approve", "revise", "reject"]
    reasoning: str
```

**Algorithme consensus** :
```
si Pro.approve == True AND R1.verdict == "approve" :
    continue to commit
si Pro.approve == False AND R1.verdict == "reject" :
    retry étape 5 avec findings injectés (max 3 fois)
    si toujours rejected → rollback + flag user
si Pro.approve != R1.approve :
    DISAGREEMENT → flag user
    UI affiche les 2 avis côte à côte
    user choisit : "appliquer quand même" / "rollback" / "retry avec feedback"
```

**Garantie** : aucun commit sans consensus 2/2, sauf override explicite user.

**Event WS émis** : `stage_complete` + `consensus_disagreement` si applicable.

### 3.11 ÉTAPE 10 — COMMIT + CI

**Mode conversation (pas de roadmap active)** :
- `git add <files_modified>`
- `git commit -m "<message généré par LLM à partir du plan + review>"`
- Pas de push automatique. L'utilisateur push quand il veut.

**Mode projet (roadmap active)** :
- Branch déjà créée à étape 5 : `feature/T-XXX-<slug>`.
- `git commit -m "[T-XXX] <title> (#<issue>)"`
- `git push origin <branch>`
- `gh pr create --title "[T-XXX] <title> (#<issue>)" --body <body>`
- Attend webhook CI (infrastructure Phase 2 existante).
- CI vert → `gh pr merge --squash` → ticket suivant.
- CI rouge → retry Niveau 2 : re-exec étapes 5-9 (max 3 fois).

**Garantie** : un commit = un pipeline complet. Atomicité. Si étape 7 rouge → pas de commit, rollback. Si étape 9 disagreement → pas de commit, décision user.

**Event WS émis** : `commit_done`, `push_done`, `pr_created`, `ci_started`.

---

## 4. Mécanismes de re-vérification (détaillés)

### 4.1 Consensus PLAN (étape 4)

**Objectif** : -50% d'erreurs de conception (mauvais fichiers choisis, archi erronée).

**Mécanisme** : R1 propose, Pro dispose. Si désaccord → merge ou user tranche.

**Formulaire de vote Pro** :
```
approve   : "Je signe ce plan. Rien à ajouter."
revise    : "Je signe avec les modifications suivantes : [...]"
reject    : "Ce plan est mauvais parce que : [...]. Voici une alternative : [...]"
```

### 4.2 SELF-CHECK (étape 6)

**Objectif** : -30% d'erreurs de codage évidentes attrapées avant les tests.

**Mécanisme** : prompt "tu es un reviewer" au MÊME LLM qui a écrit. Force le changement de posture cognitive.

**Littérature** : technique connue sous le nom de "self-consistency" dans les papers LLM. Attrape 30-40% d'erreurs basiques.

### 4.3 VERIFY mécanique (étape 7)

**Objectif** : -70% d'erreurs qui atteindraient main.

**Mécanisme** : exécution de tests réels, pas mockés. Si rouge → rollback garanti.

**Pas de LLM** : c'est volontaire. Le LLM peut halluciner un "les tests passent". On lance le subprocess.

### 4.4 Cross-review consensus 2/2 (étapes 8+9)

**Objectif** : -40% de bugs subtils qui passeraient les tests (logique, sécurité, régression).

**Mécanisme** : 2 LLMs indépendants reviewent le diff. Consensus ou décision humaine.

**Calcul taux d'erreur combiné** :
```
Base       (1 LLM sans re-vérif) : 15-20% d'erreur sur complex
×0.5 (consensus plan)            : 7-10%
×0.7 (self-check)                : 5-7%
×0.3 (verify tests)              : 1.5-2%
×0.6 (cross-review 2/2)          : ~1%
                                   ══════════
Cible : ~99% de succès sur complex
```

---

## 5. Tool schemas complets

### 5.1 File ops

```python
TOOLS_FILE_OPS = [
    {
        "name": "read_file",
        "description": "Lit le contenu d'un fichier. Tronque si >100KB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relatif au workspace"},
                "max_bytes": {"type": "integer", "default": 100_000},
            },
            "required": ["path"],
        },
    },
    {
        "name": "edit_file",
        "description": "Remplace intégralement le contenu d'un fichier. Acquiert file lock.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "patch_file",
        "description": "Edit chirurgical : remplace une chaîne par une autre.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string", "description": "Chaîne unique à remplacer"},
                "new_str": {"type": "string"},
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
    {
        "name": "create_file",
        "description": "Crée un fichier. Échoue si existe.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "delete_file",
        "description": "Supprime un fichier via git rm.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
        "description": "Liste fichiers d'un dossier. Ignore .git, node_modules, venv, __pycache__.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        },
    },
]
```

### 5.2 Code search

```python
TOOLS_SEARCH = [
    {
        "name": "grep_codebase",
        "description": "Cherche un pattern regex dans le projet. Retourne fichier:ligne:match.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex"},
                "path_glob": {"type": "string", "default": "**/*"},
                "max_results": {"type": "integer", "default": 50},
            },
            "required": ["pattern"],
        },
    },
]
```

### 5.3 Test runners

```python
TOOLS_TEST_RUN = [
    {
        "name": "run_pytest",
        "description": "Lance pytest sur un chemin/nodeid. Retourne passed/failed/stdout tronqué.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "ex: tests/backend/test_foo.py::test_bar"},
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["target"],
        },
    },
    {
        "name": "run_vitest",
        "description": "Lance vitest sur un chemin. Retourne passed/failed/stdout tronqué.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["target"],
        },
    },
    {
        "name": "run_cargo_check",
        "description": "Lance cargo check dans ui/src-tauri/.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_lint",
        "description": "Lint ruff (py) ou eslint (ts/tsx) selon extension.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
]
```

### 5.4 Git ops

```python
TOOLS_GIT = [
    {
        "name": "git_diff",
        "description": "Retourne le git diff d'un fichier ou du working dir.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "default": ""}},
        },
    },
    {
        "name": "git_status",
        "description": "Retourne git status --short.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]
```

### 5.5 Contrôles par étape

Chaque étape n'a accès qu'à un sous-ensemble de tools :

| Étape | Tools autorisés |
|-------|-----------------|
| 0 ESTIMATE | aucun (juste le prompt) |
| 1 INTAKE | aucun |
| 2 CHALLENGE | aucun |
| 3 GROUND | read_file, grep_codebase, list_files, git_status |
| 4 PLAN | aucun (utilise grounded_context) |
| 5 EXECUTE | edit_file, patch_file, create_file, delete_file |
| 6 SELF-CHECK | read_file, patch_file (pour corrections) |
| 7 VERIFY | ∅ (pas de LLM) |
| 8 REVIEW | read_file (lecture seule pour vérification) |
| 9 SECOND-REVIEW | read_file |

**Garantie** : un LLM ne peut pas écrire hors de son étape autorisée.

---

## 6. Events WebSocket (contrat backend ↔ UI)

### 6.1 Nouveaux events

| Event | Direction | Payload |
|-------|-----------|---------|
| `pipeline_estimate` | BE→UI | `EstimateResult` complet |
| `pipeline_confirmed` | UI→BE | `{estimate_id, skip_stages?: list[str]}` |
| `pipeline_cancelled` | UI→BE | `{estimate_id, reason}` |
| `stage_start` | BE→UI | `{stage: str, llm: str, started_at}` |
| `stage_complete` | BE→UI | `{stage: str, result: dict, duration_ms, tokens, cost_usd}` |
| `stage_progress` | BE→UI | `{stage: str, current, total, detail}` |
| `tool_call` | BE→UI | `{stage, tool: str, args: dict, result_preview}` |
| `consensus_round` | BE→UI | `{stage: "plan", round: int, verdicts: list}` |
| `consensus_disagreement` | BE→UI | `{stage, verdicts: list, awaiting_user: bool}` |
| `pipeline_complete` | BE→UI | `{success: bool, stages: list, total_cost, duration}` |
| `pipeline_rollback` | BE→UI | `{reason, files_restored}` |
| `pipeline_user_decision_needed` | BE→UI | `{context, options, timeout_s}` |
| `user_decision` | UI→BE | `{decision, reason?}` |
| `pipeline_stop` | UI→BE | `{reason}` |

### 6.2 Events existants conservés

`chat_response`, `routing_decision`, `agent_step`, `agent_log`, `ci_status`, `sys_stats`, `token_usage`, `llm_status`, `git_status` : inchangés.

`agent_step` est déprécié au profit de `stage_start`/`stage_complete` mais gardé pour rétrocompat 1 version.

---

## 7. UX specifications

### 7.1 Modal ESTIMATE

**Déclencheur** : `cost_estimé > SEUIL_AUTO_APPROVE` OU `mode == "complex"`.

**Contenu** :
- Titre + résumé prompt
- Classification + raison + score complexité
- Breakdown par étape (tableau : étape, LLM, tokens in/out, coût)
- Total coût + durée estimée + confidence
- Fichiers probablement touchés
- Boutons : `Annuler` / `Forcer mode simple` / `Forcer mode medium` / `Lancer (~$X.XX)`
- Option avancée (repliée) : `Skip CHALLENGE` / `Skip REVIEW` pour utilisateurs experts

**Settings associées** :
- `SEUIL_AUTO_APPROVE` : défaut $0.05, paramétrable.
- `ALWAYS_CONFIRM_COMPLEX` : défaut true.
- `DEFAULT_MODE_FOR_AMBIGUOUS` : défaut "complex".

### 7.2 Trace viewer (RoutingTab élargi)

Remplace l'actuel RoutingLive. Affiche le pipeline en cours :

```
┌─────────────────────────────────────────────────────────┐
│ Pipeline actif — Prompt : "Refactor auth JWT"           │
│ Mode : COMPLEX | 10 étapes                               │
│ Durée : 1m 23s / ~3m | Coût : $0.024 / ~$0.087          │
├─────────────────────────────────────────────────────────┤
│ ▼ 0 ESTIMATE   [Flash]    ✅ 0.4s   $0.0001             │
│ ▼ 1 INTAKE     [Flash]    ✅ 0.6s   $0.0001             │
│ ▼ 2 CHALLENGE  [Pro]      ✅ 3.2s   $0.011              │
│ ▼ 3 GROUND     [MiniMax]  ✅ 8.1s   $0.0008             │
│    📎 Fichiers lus : auth.py, test_auth.py, middleware.py│
│    🔍 5 greps effectués                                 │
│ ▼ 4a PLAN      [R1]       ✅ 12s    $0.006              │
│ ▼ 4b CONSENSUS [Pro]      ✅ 9s     $0.019 ⚖️ approved   │
│ ▶ 5 EXECUTE    [MiniMax]  🔄 18s    $0.004 (2/4 files)  │
│   6 SELF-CHECK [MiniMax]  ⏳                            │
│   7 VERIFY     [pytest]   ⏳                            │
│   8 REVIEW     [Pro]      ⏳                            │
│   9 REVIEW2    [R1]       ⏳                            │
├─────────────────────────────────────────────────────────┤
│ [Stop pipeline] [Voir logs complets]                    │
└─────────────────────────────────────────────────────────┘
```

Click sur une étape → panel latéral avec détail (prompt system, réponse LLM, tool calls, coût précis).

### 7.3 Historique des pipelines (MonitoringTab)

Tableau des derniers pipelines exécutés :

| Date | Prompt | Mode | Étapes | Coût estimé | Coût réel | Delta | Durée | Statut |
|------|--------|------|--------|-------------|-----------|-------|-------|--------|
| 15:23 | Refactor auth | complex | 10 | $0.087 | $0.094 | +8% | 3m12s | ✅ |
| 14:05 | Fix typo | simple | 5 | $0.002 | $0.002 | 0% | 12s | ✅ |
| 12:40 | Add endpoint /ping | medium | 7 | $0.015 | $0.018 | +20% | 34s | ✅ |

Bouton "Rejouer" par pipeline : relance avec le même prompt (utile pour comparer).

### 7.4 Stop button

Raccourci `Cmd+.` ou bouton Stop dans trace viewer.

**Comportement** :
- Annule la tâche asyncio en cours.
- Lance rollback via `git stash pop` si étape ≥ 5.
- Affiche "Pipeline interrompu, état restauré".
- Sauvegarde partial log en LongTermMemory pour analyse.

### 7.5 Disagreement modal (consensus échec)

Quand étape 9 remonte disagreement :

```
┌─────────────────────────────────────────────────────────┐
│ ⚖️ Consensus impossible — ta décision                   │
├─────────────────────────────────────────────────────────┤
│ Gemini Pro dit :                                        │
│   "REJECT : auth.py ligne 42 ouvre une SQL injection"  │
│                                                         │
│ DeepSeek R1 dit :                                       │
│   "APPROVE : le paramètre est sanitized en amont"       │
│                                                         │
│ Voir le diff : [lien]                                   │
├─────────────────────────────────────────────────────────┤
│ [Appliquer] [Rollback] [Retry avec instructions]        │
└─────────────────────────────────────────────────────────┘
```

---

## 8. Garanties formelles

### 8.1 Invariants du pipeline

1. **Aucun fichier modifié sans `git stash` préalable** (étape 5).
2. **Aucun commit sans `all_green == True`** à étape 7.
3. **Aucun commit sans validation reviewer** en mode medium/complex (étapes 8/9).
4. **Aucun fact sans citation** dans GroundedContext (étape 3).
5. **Aucun passage à étape 5 sans plan validé** par consensus en mode complex (étape 4b).
6. **Rollback garanti** si étape 7 échoue après 3 retries.
7. **User confirmation obligatoire** avant tout appel LLM si `cost > SEUIL` (étape 0).
8. **Cap budget par pipeline** : max $1.00 par défaut (configurable). Si dépassé → stop.

### 8.2 Taux d'erreur ciblés

| Mode | Taux succès cible | Taux rollback propre | Taux corruption main |
|------|-------------------|----------------------|-----------------------|
| simple | 99% | 0.9% | <0.1% |
| medium | 97% | 2.9% | <0.1% |
| complex | 95-99% | 0.9-4.9% | <0.1% |

"Corruption main" = modification indésirable qui atteint la branche main. C'est le taux qu'on veut à 0%. Les mécanismes verify+review+consensus garantissent que seuls les rollbacks propres se produisent en cas d'échec.

### 8.3 Coûts attendus (référence 2026)

| Scénario | Prompts/jour | Coût/mois |
|----------|-------------|-----------|
| Usage léger | 10 simples | ~$3 |
| Usage modéré | 20 simples + 5 medium + 2 complex | ~$30 |
| Usage intensif | 50 simples + 20 medium + 10 complex | ~$150-200 |
| Mode projet quotidien | 100+ dont 30 complex | ~$300-400 |

---

## 9. Calibration empirique

### 9.1 Suivi delta estimé/réel

Chaque pipeline log en LongTermMemory (nouvelle table `pipeline_runs`) :
```sql
CREATE TABLE pipeline_runs (
    id               INTEGER PRIMARY KEY,
    session_id       TEXT,
    prompt           TEXT,
    mode             TEXT,
    estimated_cost   REAL,
    actual_cost      REAL,
    estimated_tokens INTEGER,
    actual_tokens    INTEGER,
    estimated_duration_s INTEGER,
    actual_duration_s REAL,
    success          BOOLEAN,
    rollback_reason  TEXT,
    stages_json      TEXT,
    created_at       TIMESTAMP
);
```

### 9.2 Ajustement automatique de l'estimateur

Après 50 runs, un job calcule le facteur de correction par mode :
```python
correction_factor[mode] = mean(actual_cost / estimated_cost for runs[-50:] if runs.mode == mode)
```

Appliqué à l'étape 0 sous forme de `estimated_cost_corrected = estimated_cost * correction_factor[mode]`.

Cible : delta < 10% après 2 semaines d'usage réel.

---

## 10. Gestion des erreurs — matrice

| Erreur | Détectée à | Action |
|--------|-----------|--------|
| Prompt ambigu | 1 INTAKE | Demande clarification user |
| API LLM down | n'importe | Fallback chain → autre LLM |
| Rate limit | n'importe | Wait + retry (rate_limiter existant) |
| Tool read hors workspace | 3 GROUND | Refuse + log security |
| Budget cap dépassé | n'importe | Stop + flag user |
| Plan consensus deadlock | 4b | Flag user avec 2 plans |
| Tool edit timeout | 5 EXECUTE | Retry 3x puis rollback |
| Tests rouges après 3 retries | 7 VERIFY | Rollback total + flag user |
| Review disagreement | 9 | Modal user : apply/rollback/retry |
| User stop manuel | n'importe après 5 | Rollback + save partial trace |
| Crash backend | n'importe | Tauri affiche bannière + relance |
| Workspace dirty au démarrage | pre-0 | Bloque pipeline, exige clean state |

---

## 11. Migration depuis l'architecture actuelle

### 11.1 Ce qui est GARDÉ

- `LLMManager` + fallback chain + rate limiting (Plan 1).
- `RouterEngine.route()` pour classification (étendu, pas remplacé).
- `FileLock` async (Plan 1).
- `LLMTaskQueue` pour limiter concurrency par LLM (Plan 1).
- `WSStreamer` pour events (Plan 1, enrichi).
- `LongTermMemory` + `ShortTermMemory` (Plan 2, étendu avec `pipeline_runs`).
- `ProjectRoadmap` + mode projet + webhooks CI (Plans 2+4).
- `git_service.py`, `github_service.py` (Plan 4).

### 11.2 Ce qui est REFONDU

- `AgentLoop` → remplacé par `Pipeline` (11 étapes).
- `Orchestrator.handle()` → dispatch vers `Pipeline` au lieu d'AgentLoop.
- `context_builder.py` → intégré à l'étape 3 GROUND.

### 11.3 Ce qui est AJOUTÉ

- `backend/pipeline/` package complet avec une classe par étape.
- `backend/tools/` (file_ops, search, test_runners, git_ops).
- `backend/cost_estimator.py` pour étape 0.
- `backend/prompts/stage_*.md` (un par étape).
- UI : trace viewer, modal ESTIMATE, disagreement modal.

### 11.4 Tests existants

- Tests AgentLoop : supprimés (remplacés par tests pipeline).
- Tests Orchestrator : adaptés pour nouveau flow.
- Nouveaux tests : `test_stage_N_*.py` par étape + `test_pipeline_e2e.py`.

---

## 12. Roadmap d'implémentation

### Plan 5A — Fondations pipeline + grounding + ESTIMATE (1.5 sem)
- Package `backend/pipeline/` avec classes `Stage0Estimate`, `Stage1Intake`, `Stage3Ground`, `Stage5Execute` (minimal viable).
- Package `backend/tools/` complet (file_ops, search).
- `CostEstimator` + table `pipeline_runs`.
- UI modal ESTIMATE + trace viewer squelette.
- LLMs réels connectés (Task 1 Plan 5 initial).
- Tokenizer tiktoken.

### Plan 5B — VERIFY + rollback + streaming (1 sem)
- `Stage7Verify` avec subprocess pytest/vitest/cargo.
- Rollback git stash automatique.
- Streaming litellm `stream=True` + events `chat_token`.
- Stop button UI + `pipeline_stop` event.
- Cap budget par pipeline.

### Plan 5C — CHALLENGE + PLAN consensus (1.5 sem)
- `Stage2Challenge`, `Stage4PlanConsensus`.
- Prompts MD par rôle (challenger, planner, plan-reviewer).
- Dispatch multi-LLM explicite dans Orchestrator.
- Mémoire inter-LLM (`llm_messages` table).

### Plan 5D — SELF-CHECK + REVIEW + SECOND-REVIEW (1 sem)
- `Stage6SelfCheck`, `Stage8Review`, `Stage9SecondReview`.
- Mécanisme consensus 2/2 avec modal disagreement.
- Tests E2E pipeline complet mode complex.

### Plan 5E — UX raffinée + Settings + Cost tracking (1 sem)
- Toasts (Sonner), syntax highlighting (shiki), command palette (cmdk).
- Settings UI + persistence settings.json auto-load boot.
- Cost tracking temps réel avec delta estimé/réel.
- Calibration automatique correction_factor.

### Plan 5F — Packaging + Ollama + release v2.0.0 (1 sem)
- Packaging Tauri DMG/DEB/MSI (unsigned v2.0, signed v2.0.1).
- Menu bar macOS natif.
- Mode Ollama privacy-first (pipeline dégradé simple).
- `.github/workflows/release.yml`.
- Documentation user (USER_GUIDE, API_KEYS_SETUP, TROUBLESHOOTING).
- Tag v2.0.0.

**Durée totale : 6-8 semaines full-time.**

---

## 13. Ce qui est reporté en v2.2+

- DB cleanup automatique (apscheduler) → v2.2.
- Migration complète structlog → v2.2 (v2.0 utilise json-formatter minimal).
- Multi-workspace runtime switching → v2.2.
- Templates CdC SaaS/API/Mobile/CLI → v2.2.
- Signing macOS + Windows (nécessite budget $500/an) → v2.0.1.
- Patterns auto-appris via embeddings → v3.0.
- Collaboration multi-user → v3.0.

---

## 14. Glossaire

- **Pipeline** : les 11 étapes exécutées pour un prompt utilisateur.
- **Stage** : une étape du pipeline (Stage0, Stage1, ..., Stage10).
- **Mode** : simple / medium / complex. Détermine quelles étapes sont activées.
- **Consensus** : accord entre 2 LLMs (PLAN étape 4, REVIEW étapes 8+9).
- **Grounded context** : contexte construit uniquement à partir de fichiers lus ou greps effectués. Pas d'hypothèses.
- **Rollback** : `git stash pop` pour restaurer l'état pré-pipeline.
- **Auto-approve seuil** : coût en dessous duquel le modal ESTIMATE est skippé.
- **Tool call** : invocation d'un tool (edit_file, read_file, etc.) par un LLM pendant une étape.

---

*Spec produite le 2026-04-20. Validation utilisateur requise avant démarrage Plan 5A.*
