# LocalCoder IDE v2.1 — Plan 5F : Packaging + Ollama + Release v2.0.0

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`. TDD strict obligatoire.

**Goal :** Finaliser la v2.0.0 publique. Packaging Tauri cross-platform (DMG macOS, DEB Linux, MSI Windows — unsigned en v2.0, signing en v2.0.1). Menu bar macOS natif. Mode Ollama privacy-first (pipeline dégradé 100% local). Workflow GitHub Actions release. Documentation utilisateur complète (USER_GUIDE, API_KEYS_SETUP, TROUBLESHOOTING). Tag v2.0.0.

**Architecture :** Tauri 2.x bundle targets all (DMG/AppImage/DEB/MSI). Mode Ollama détecté au boot via `localhost:11434/api/tags`, ajouté comme fallback en bout de chain. Settings toggle "Privacy-first" force pipeline simple + Ollama only. Menu bar macOS via tauri Menu API.

**Tech stack ajouté :** `tauri-plugin-updater`, `@tauri-apps/plugin-updater`, `aiohttp` (déjà dispo).

**Prérequis :** Plans 5A-E complets. Pipeline 11 étapes fonctionnel + UX raffinée.

**Durée estimée :** 1 semaine (5-7 jours full-time).

**Résultat attendu :**
- Build DMG/DEB/MSI disponibles localement.
- Workflow GitHub Actions qui produit les artefacts à chaque tag.
- Mode Ollama détecté + toggle UI.
- Menu bar macOS natif (About, Preferences Cmd+,, Command Palette Cmd+K, fullscreen).
- Documentation USER_GUIDE, API_KEYS_SETUP, TROUBLESHOOTING.
- Tag v2.0.0 publié sur GitHub Releases avec artefacts attachés.
- README avec badge version + lien Releases.

---

## Fichiers créés ou modifiés

```
ui/src-tauri/
├── Cargo.toml                          # MODIFIÉ — tauri-plugin-updater, -store déjà (Plan 5E)
├── tauri.conf.json                     # MODIFIÉ — updater endpoint, icon custom
├── icons/                              # REMPLACÉ — logo LocalCoder 1024x1024
└── src/
    ├── lib.rs                          # MODIFIÉ — plugins + menu register
    └── menu.rs                         # CRÉÉ — menu bar macOS

backend/
├── ollama_detector.py                  # CRÉÉ — detect_ollama()
├── llm_manager.py                      # MODIFIÉ — support Ollama en fallback
└── models.py                           # MODIFIÉ — LLMConfig.is_local

tests/backend/
├── test_ollama_detector.py             # CRÉÉ
└── test_llm_manager_ollama.py          # CRÉÉ

ui/src/
├── components/
│   └── Settings/
│       └── PrivacyModeToggle.tsx       # CRÉÉ
└── stores/
    └── settingsStore.ts                # MODIFIÉ — privacy_mode flag

.github/workflows/
└── release.yml                         # CRÉÉ — build cross-platform sur tag

docs/
├── USER_GUIDE.md                       # CRÉÉ
├── API_KEYS_SETUP.md                   # CRÉÉ
├── TROUBLESHOOTING.md                  # CRÉÉ
└── OLLAMA_SETUP.md                     # CRÉÉ

README.md                               # MODIFIÉ — badges, install, liens
```

---

# PHASE F1 — Mode Ollama (Tasks 1-3)

## Task 1 : Détecteur Ollama

**Files:** `backend/ollama_detector.py`, `tests/backend/test_ollama_detector.py`.

**Durée :** 0.5 jour.

- [ ] **Step 1.1 — Tests rouges ollama_detector**

  - `detect_ollama()` retourne list modèles installés si localhost:11434 up.
  - `detect_ollama()` retourne `[]` si timeout / connection refused.
  - `detect_ollama(host="custom:port")` permet override.

- [ ] **Step 1.2 — Implémenter `ollama_detector.py`**

  ```python
  async def detect_ollama(host="http://localhost:11434", timeout=2) -> list[str]:
      try:
          async with aiohttp.ClientSession() as session:
              async with session.get(f"{host}/api/tags", timeout=timeout) as resp:
                  data = await resp.json()
                  return [m["name"] for m in data.get("models", [])]
      except (aiohttp.ClientError, asyncio.TimeoutError, Exception):
          return []
  ```

- [ ] **Step 1.3 — Commit**

---

## Task 2 : LLMManager Ollama support

**Files:** `backend/llm_manager.py` (MODIFIÉ), `backend/models.py` (MODIFIÉ), `tests/backend/test_llm_manager_ollama.py`.

**Durée :** 1 jour.

- [ ] **Step 2.1 — Étendre LLMConfig**

  Ajouter `is_local: bool = False` dans dataclass `LLMConfig`. Valeurs par défaut dans DEFAULT_LLMS inchangées.

- [ ] **Step 2.2 — Ajouter Ollama fallback conditionnel**

  Dans `LLMManager.__init__`, appeler `detect_ollama()` de manière async (via `asyncio.run` au startup ou lazy au premier call).

  Si au moins un modèle Ollama détecté → ajouter `ollama/qwen2.5-coder:14b` (ou premier coder détecté) en fin de chaque FALLBACK_CHAIN comme privacy-first fallback.

  LiteLLM supporte Ollama nativement via `model="ollama/model-name"`.

- [ ] **Step 2.3 — Tests**

  - Mock `detect_ollama` retourne `["qwen2.5-coder:14b"]` → vérifier ajout dans chains.
  - Mock retourne `[]` → chains inchangées.
  - Integration test : route en mode Ollama → acompletion appelle `ollama/...`.

- [ ] **Step 2.4 — Commit**

---

## Task 3 : UI PrivacyModeToggle + pipeline dégradé

**Files:** `ui/src/components/Settings/PrivacyModeToggle.tsx`, `ui/src/stores/settingsStore.ts` (MODIFIÉ), `backend/pipeline/orchestrator.py` (MODIFIÉ).

**Durée :** 1 jour.

- [ ] **Step 3.1 — PrivacyModeToggle.tsx**

  Toggle dans Settings → Pipeline section : "Privacy-first mode (Ollama only)".

  Si activé + Ollama non détecté → toast.error("Ollama non détecté. Installer depuis https://ollama.ai") + toggle revient à off.

  Si activé + Ollama OK → badge vert "Mode local actif" dans StatusBar.

- [ ] **Step 3.2 — Backend mode dégradé**

  Si `settings.privacy_mode == True` :
  - Pipeline force mode SIMPLE (5 étapes : 0/1/3/5/7).
  - Toutes les stages routent vers `ollama/*` uniquement.
  - Skip Stage0 ESTIMATE si Ollama détecté (classif locale à Ollama, coût = 0).
  - Modal ESTIMATE mentionne "Mode local — coût $0.00".

- [ ] **Step 3.3 — Endpoint GET /ollama/status**

  Retourne `{available: bool, models: [...]}`. UI appelle pour feedback.

- [ ] **Step 3.4 — Tests**

  - Mock privacy_mode=True + Ollama dispo → pipeline mode SIMPLE + LLMs Ollama uniquement.
  - privacy_mode=True + Ollama absent → pipeline refuse de démarrer + erreur claire.

- [ ] **Step 3.5 — Commit**

---

# PHASE F2 — Packaging Tauri (Tasks 4-6)

## Task 4 : Icônes + configuration bundle

**Files:** `ui/src-tauri/icons/`, `ui/src-tauri/tauri.conf.json` (MODIFIÉ).

**Durée :** 0.5 jour.

- [ ] **Step 4.1 — Logo LocalCoder 1024x1024 PNG**

  Fournir ou générer logo simple. Placer dans `ui/src-tauri/icons/source.png`.

- [ ] **Step 4.2 — Générer tous les formats**

  `npx @tauri-apps/cli icon ui/src-tauri/icons/source.png` → produit 32x32, 128x128, 128x128@2x, icon.icns (macOS), icon.ico (Windows).

- [ ] **Step 4.3 — Config bundle**

  `tauri.conf.json` :
  - `productName: "LocalCoder IDE"`.
  - `version: "2.0.0"`.
  - `identifier: "com.localcoder.ide"`.
  - `bundle.targets: "all"` (dmg, deb, appimage, msi, nsis).
  - `bundle.icon` liste complète.
  - Window config : width 1400, height 900, minWidth 1000.

- [ ] **Step 4.4 — Commit**

---

## Task 5 : Menu bar macOS natif

**Files:** `ui/src-tauri/src/menu.rs`, `ui/src-tauri/src/lib.rs` (MODIFIÉ).

**Durée :** 1 jour.

- [ ] **Step 5.1 — menu.rs**

  Fonction `build_menu(app) -> Menu<Wry>` avec 3 submenus :

  1. **LocalCoder** :
     - About LocalCoder
     - separator
     - Preferences... (Cmd+,)
     - separator
     - Hide LocalCoder (Cmd+H)
     - Quit LocalCoder (Cmd+Q)

  2. **Édition** :
     - Undo (Cmd+Z)
     - Redo (Cmd+Shift+Z)
     - separator
     - Cut / Copy / Paste / Select All (via PredefinedMenuItem)

  3. **Affichage** :
     - Command Palette (Cmd+K)
     - separator
     - Toggle Fullscreen (Cmd+Ctrl+F)

- [ ] **Step 5.2 — Register menu + on_menu_event dans lib.rs**

  `Builder::default().menu(build_menu).on_menu_event(|app, event| match event.id() { ... })` :
  - `"settings"` → `app.emit("open-settings", ())`.
  - `"cmd_palette"` → `app.emit("open-command-palette", ())`.

  Côté UI, listener via `@tauri-apps/api/event listen("open-settings")` → switch to Settings tab.

- [ ] **Step 5.3 — Test manuel**

  Build + run, vérifier menu bar fonctionne.

- [ ] **Step 5.4 — Commit**

---

## Task 6 : Build local + test DMG

**Files:** pas de nouveaux fichiers, commandes.

**Durée :** 1 jour.

- [ ] **Step 6.1 — `cd ui && npm run tauri build`**

  Produit :
  - macOS : `target/release/bundle/dmg/LocalCoder_2.0.0_aarch64.dmg` (ou x86_64).
  - Linux : `target/release/bundle/deb/localcoder-ide_2.0.0_amd64.deb` + `appimage/*.AppImage`.
  - Windows : `target/release/bundle/msi/LocalCoder_2.0.0_x64.msi`.

- [ ] **Step 6.2 — Test install DMG macOS**

  - Double-click DMG → fenêtre finder avec app + shortcut Applications.
  - Glisse-dépose dans Applications.
  - Launch → warning "app non signée" → Ctrl-click "Ouvrir" → confirme.
  - App tourne, backend spawn OK, UI fonctionne.

- [ ] **Step 6.3 — Document process install non-signé**

  Dans `docs/TROUBLESHOOTING.md`, expliquer :
  - macOS : Ctrl-click Ouvrir sur première fois.
  - Windows : "More info" → "Run anyway" sur SmartScreen.
  - Note que signing arrive en v2.0.1.

- [ ] **Step 6.4 — Commit**

---

# PHASE F3 — GitHub Actions release (Task 7)

## Task 7 : Workflow release.yml

**Files:** `.github/workflows/release.yml`.

**Durée :** 1 jour.

- [ ] **Step 7.1 — Créer workflow**

  `.github/workflows/release.yml` :
  - Trigger : `on: push: tags: ['v*']`.
  - Matrix : `macos-latest`, `ubuntu-latest`, `windows-latest`.
  - Steps :
    1. Checkout.
    2. Setup Node 20.
    3. Setup Rust stable.
    4. (Linux only) install libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf.
    5. `npm install` in ui/.
    6. `npm run tauri build`.
    7. Upload artefacts via `softprops/action-gh-release`.

  Outputs : DMG + DEB + AppImage + MSI attachés à la Release.

- [ ] **Step 7.2 — Test sur branche dédiée**

  Créer tag test `v2.0.0-test.1`, pousser, vérifier workflow lance + produit les artefacts.

  Supprimer le tag test après.

- [ ] **Step 7.3 — Notes release auto-générées**

  Champ `body` du release via `softprops/action-gh-release` : lit le changelog ou commits depuis le tag précédent.

- [ ] **Step 7.4 — Commit**

---

# PHASE F4 — Documentation user (Task 8)

## Task 8 : USER_GUIDE + API_KEYS_SETUP + TROUBLESHOOTING + OLLAMA_SETUP

**Files:** `docs/USER_GUIDE.md`, `docs/API_KEYS_SETUP.md`, `docs/TROUBLESHOOTING.md`, `docs/OLLAMA_SETUP.md`, `README.md` (MODIFIÉ).

**Durée :** 1.5 jour.

- [ ] **Step 8.1 — docs/USER_GUIDE.md**

  Sections :
  1. **Installation** : DMG/DEB/MSI liens + warnings non-signed.
  2. **Première configuration** : Settings → API Keys → tester connexion LLMs.
  3. **Ton premier prompt** : exemple "Crée un fichier hello.py" → modal ESTIMATE → Trace Viewer → résultat.
  4. **Les 3 modes (simple/medium/complex)** : explication + quand chaque mode se déclenche.
  5. **Mode projet** : CdC → Sprints → Tickets → CI auto-merge.
  6. **Tips & tricks** : @mentions (`@deepseek`), Cmd+K palette, Cmd+. stop, skip stages avancés.
  7. **FAQ** : 10 questions fréquentes.

- [ ] **Step 8.2 — docs/API_KEYS_SETUP.md**

  Pour chaque provider (DeepSeek, MiniMax, Google AI, Mistral) :
  - Lien d'inscription.
  - Étapes pour générer API key.
  - Screenshots.
  - Coût estimé par mois selon usage léger / intensif.
  - Où coller dans LocalCoder (Settings → API Keys).

- [ ] **Step 8.3 — docs/TROUBLESHOOTING.md**

  Problèmes fréquents + solutions :
  - "Backend ne démarre pas" → vérifier logs `~/Library/Logs/LocalCoder/`.
  - "Macos dit app endommagée" → Ctrl-click Ouvrir.
  - "Ollama non détecté" → vérifier `curl localhost:11434`.
  - "LLM rate limit 429" → ralentir, fallback chain va basculer.
  - "CI webhook ne fonctionne pas" → vérifier GITHUB_WEBHOOK_SECRET.
  - "Pipeline coincé" → Cmd+. stop + vérifier logs.
  - "Estimation très au-dessus du réel" → calibration après 10+ runs.

- [ ] **Step 8.4 — docs/OLLAMA_SETUP.md**

  - Install Ollama : lien ollama.ai + commande `brew install ollama`.
  - Pull modèles recommandés : `ollama pull qwen2.5-coder:14b` ou `deepseek-coder-v2:16b`.
  - Vérification : `curl localhost:11434/api/tags`.
  - Activer privacy mode dans Settings.
  - Limitations du mode local (pipeline simple, pas de consensus multi-LLM).

- [ ] **Step 8.5 — README.md update**

  - Badges : version, license, tests passing.
  - Install : liens Releases + commandes une-ligne.
  - Quick start : 5 étapes 2 minutes.
  - Liens vers docs/USER_GUIDE, API_KEYS_SETUP, etc.
  - Screenshot de l'app (optionnel).
  - Roadmap v2.1+.
  - Contributing.

- [ ] **Step 8.6 — Commit**

---

# PHASE F5 — Release v2.0.0 (Task 9)

## Task 9 : Release finale

**Files:** `CHANGELOG.md` (CRÉÉ), tag git, release GitHub.

**Durée :** 0.5 jour.

- [ ] **Step 9.1 — CHANGELOG.md**

  Format Keep a Changelog. Section v2.0.0 avec :
  - Added : pipeline 11 étapes, tool-calling, Ollama mode, cost tracking, Settings UI, packaging, menu macOS.
  - Changed : AgentLoop remplacé par Pipeline.
  - Deprecated : events `agent_step` (remplacés par stage_start/complete).
  - Fixed : tous les correctifs des Plans 5A-F.
  - Removed : mock code AgentLoop.

- [ ] **Step 9.2 — Suite tests finale**

  - pytest → 340+ verts.
  - vitest → 180+ verts.
  - cargo check → ok.
  - Build DMG local OK.

- [ ] **Step 9.3 — Manual E2E**

  10 points de vérification manuels (voir spec §7 du Plan 5 initial) :
  1. Install DMG.
  2. Settings API key + test vert.
  3. Prompt simple via chat → fichier créé.
  4. Cmd+K palette fonctionnelle.
  5. Privacy mode avec Ollama.
  6. MonitoringTab coût temps réel.
  7. Settings disable MiniMax → prochain prompt route ailleurs.
  8. Shutdown propre app → backend se termine.

- [ ] **Step 9.4 — Tag v2.0.0**

  `git tag v2.0.0 -m "LocalCoder IDE v2.0.0 — Pipeline rigoureux + packaging public"` + push tag.

  GitHub Actions déclenche automatiquement `release.yml` → build 3 plateformes → upload artefacts.

- [ ] **Step 9.5 — Attendre workflow complete (~30-45 min)**

  Vérifier artefacts DMG/DEB/AppImage/MSI bien attachés sur la release.

- [ ] **Step 9.6 — README badge version MAJ**

  Badge shields.io pointant sur la release.

- [ ] **Step 9.7 — Annonce (optionnelle)**

  - Post sur Twitter/Mastodon.
  - Share lien vers README + Releases.

- [ ] **Step 9.8 — Checkpoint finale `plan-5F-done.md`**

- [ ] **Step 9.9 — Commit final**

---

## Vérification finale Plan 5F

- [ ] Ollama détecté + mode privacy-first fonctionnel.
- [ ] Menu bar macOS natif avec shortcuts opérationnels.
- [ ] Build DMG/DEB/AppImage/MSI produits localement.
- [ ] Workflow GitHub Actions `release.yml` déclenché sur tag.
- [ ] Documentation USER_GUIDE, API_KEYS_SETUP, TROUBLESHOOTING, OLLAMA_SETUP complète.
- [ ] Tag v2.0.0 pushé + artefacts publiés sur GitHub Releases.
- [ ] README avec badges + liens + screenshots.

---

## Récap Plan 5F

**9 tasks, 5 phases** :

| Phase | Tasks | Impact | Durée |
|-------|-------|--------|-------|
| F1 Ollama | 1-3 | Mode privacy-first local | 2.5 jours |
| F2 Packaging | 4-6 | DMG/DEB/MSI + menu macOS | 2.5 jours |
| F3 CI release | 7 | GitHub Actions cross-platform | 1 jour |
| F4 Docs user | 8 | USER_GUIDE + troubleshooting | 1.5 jour |
| F5 Release v2.0.0 | 9 | Tag + GitHub Release publique | 0.5 jour |

**Total : ~8 jours (1.5 semaine full-time).**

**Post-Plan 5F :** v2.0.0 publiée. Roadmap v2.1+ possible (signing, multi-workspace, templates CdC, structlog complet, embeddings patterns, collaboration).

---

## Post-v2.0.0 : roadmap v2.1+

Voir spec `docs/superpowers/specs/2026-04-20-pipeline-rigoureux.md` §13 pour :
- v2.0.1 : signing macOS + Windows (coût ~$500/an).
- v2.1 : DB cleanup auto, multi-workspace, structlog migration, templates CdC.
- v2.2 : patterns auto-appris via embeddings.
- v3.0 : collaboration multi-user, plugins marketplace.

---

*Plan 5F finalise le cycle v2.0. À la fin : release publique + documentation.*
