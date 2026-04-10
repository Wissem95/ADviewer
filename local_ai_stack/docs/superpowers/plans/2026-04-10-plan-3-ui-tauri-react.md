# LocalCoder IDE v2 — Plan 3 : UI Tauri + React

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire le shell natif Tauri + l'interface React complète : Activity Bar (FileTree, LLMStatus, GitPanel, SprintBoard), 4 tabs (Chat, Terminaux, Routing, Monitoring), StatusBar, et stores Zustand connectés au WebSocket FastAPI.

**Architecture:** Tauri comme shell natif macOS démarre FastAPI en subprocess, attend le health check, puis ouvre l'UI React. La communication temps réel se fait via WebSocket (`ws://localhost:8765/ws`). 4 stores Zustand gèrent l'état global. Chaque tab est lazy-loaded pour les performances.

**Tech Stack:** Tauri 2.x (Rust), React 19, TypeScript, Zustand 5, xterm.js 5, Vite, Tailwind CSS 3, shadcn/ui

**Prérequis :** Plan 1 et Plan 2 complets. Node.js 20+, Rust stable, Cargo installés.

**Spec de référence:** `docs/superpowers/specs/2026-04-10-localcoder-ide-v2-design.md` §1, §3

---

## Fichiers créés ou modifiés

```
ui/
├── src-tauri/
│   ├── Cargo.toml               # CRÉÉ — dépendances Rust
│   ├── tauri.conf.json          # CRÉÉ — config Tauri (titre, taille, permissions)
│   └── src/
│       └── main.rs              # CRÉÉ — shell Rust : spawn FastAPI + health check
│
└── src/
    ├── main.tsx                 # CRÉÉ — entrée React
    ├── App.tsx                  # CRÉÉ — layout principal + routing tabs
    ├── ws.ts                    # CRÉÉ — singleton WebSocket client
    │
    ├── stores/
    │   ├── llmStore.ts          # CRÉÉ — statut temps réel des LLMs
    │   ├── routingStore.ts      # CRÉÉ — historique routing + live decision
    │   ├── roadmapStore.ts      # CRÉÉ — roadmap projet courante
    │   └── sessionStore.ts      # CRÉÉ — session active (tokens, coût, branch)
    │
    ├── components/
    │   ├── ActivityBar/
    │   │   ├── ActivityBar.tsx  # CRÉÉ — colonne gauche + navigation icons
    │   │   ├── FileTree.tsx     # CRÉÉ — explorateur fichiers (fichiers modifiés en jaune)
    │   │   ├── LLMStatus.tsx    # CRÉÉ — statut LLMs (vert/orange/gris + pastilles)
    │   │   ├── GitPanel.tsx     # CRÉÉ — diff, stage, commit sans quitter l'app
    │   │   └── SprintBoard.tsx  # CRÉÉ — Kanban tickets en cours
    │   │
    │   ├── StatusBar/
    │   │   └── StatusBar.tsx    # CRÉÉ — barre inférieure (LLMs, branch, tokens, coût)
    │   │
    │   └── tabs/
    │       ├── ChatTab/
    │       │   ├── ChatTab.tsx       # CRÉÉ — chat universel
    │       │   ├── MessageBubble.tsx # CRÉÉ — message avec badge LLM
    │       │   └── ChatInput.tsx     # CRÉÉ — input avec @mentions
    │       ├── TerminalsTab/
    │       │   └── TerminalsTab.tsx  # CRÉÉ — grille xterm.js par LLM actif
    │       ├── RoutingTab/
    │       │   ├── RoutingLive.tsx   # CRÉÉ — animation routing en cours
    │       │   └── RoutingHistory.tsx# CRÉÉ — tableau historique routing
    │       └── MonitoringTab/
    │           └── MonitoringTab.tsx # CRÉÉ — CPU/RAM, tokens/min, latence, CI status
    │
    └── index.css                # CRÉÉ — Tailwind base + variables CSS
```

---

## Task 1 : Scaffold Tauri + React

**Files:**
- Create: `ui/` (structure complète via CLI)

- [ ] **Step 1.1 : Créer le projet Tauri avec template React-TypeScript**

```bash
cd /Users/wissem/local_ai_stack
npm create tauri-app@latest ui -- --template react-ts --manager npm
cd ui
```

Expected : `✅ Your application is ready!`

- [ ] **Step 1.2 : Installer les dépendances UI**

```bash
cd ui
npm install zustand@5 @xterm/xterm@5 @xterm/addon-fit@0.10 @xterm/addon-web-links@0.11
npm install tailwindcss@3 autoprefixer postcss
npm install @shadcn/ui lucide-react clsx
npm install -D @types/node
```

Expected : `added XXX packages`

- [ ] **Step 1.3 : Configurer Tailwind**

Créer `ui/tailwind.config.js` :

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#1e1e2e",
        panel: "#181825",
        border: "#313244",
        text: "#cdd6f4",
        muted: "#6c7086",
        accent: "#89b4fa",
        success: "#a6e3a1",
        warning: "#f9e2af",
        error: "#f38ba8",
      },
    },
  },
  plugins: [],
}
```

Créer `ui/postcss.config.js` :

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 1.4 : Créer ui/src/index.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg: #1e1e2e;
  --panel: #181825;
  --border: #313244;
  --text: #cdd6f4;
  --muted: #6c7086;
  --accent: #89b4fa;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  overflow: hidden;
  user-select: none;
}

/* Scrollbars custom */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--panel); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
```

- [ ] **Step 1.5 : Vérifier que le dev server démarre**

```bash
cd ui && npm run dev
```

Expected : `VITE v5.x.x ready in XXms — Local: http://localhost:1420/`
Ctrl+C pour arrêter.

- [ ] **Step 1.6 : Commit**

```bash
cd /Users/wissem/local_ai_stack
git add ui/
git commit -m "chore: scaffold Tauri + React with Tailwind and dependencies"
```

---

## Task 2 : Shell Tauri (main.rs) — spawn FastAPI + health check

**Files:**
- Modify: `ui/src-tauri/src/main.rs`
- Modify: `ui/src-tauri/tauri.conf.json`

- [ ] **Step 2.1 : Lire le main.rs généré par le scaffold**

```bash
cat ui/src-tauri/src/main.rs
```

- [ ] **Step 2.2 : Remplacer ui/src-tauri/src/main.rs par le shell complet**

```rust
// ui/src-tauri/src/main.rs
// Shell Tauri minimal — démarre FastAPI et attend le health check.
// Règle : FastAPI est un processus enfant, pas un daemon.
// Fermeture de Tauri → SIGTERM envoyé au processus enfant.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use tauri::{Manager, Runtime};

// ── Health check ────────────────────────────────────────────────────────────

fn wait_for_backend(url: &str, max_retries: u32, delay_ms: u64) -> bool {
    for _ in 0..max_retries {
        if let Ok(resp) = ureq::get(url).call() {
            if resp.status() == 200 {
                return true;
            }
        }
        thread::sleep(Duration::from_millis(delay_ms));
    }
    false
}

// ── Démarrage FastAPI ────────────────────────────────────────────────────────

fn spawn_backend() -> Option<Child> {
    // Cherche le venv Python dans le répertoire parent (local_ai_stack/)
    let venv_python = if cfg!(target_os = "windows") {
        "../venv/Scripts/python.exe"
    } else {
        "../venv/bin/python"
    };

    Command::new(venv_python)
        .args(["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8765"])
        .current_dir("..")
        .spawn()
        .ok()
}

// ── Main ─────────────────────────────────────────────────────────────────────

fn main() {
    let backend: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let backend_clone = Arc::clone(&backend);

    // Démarre FastAPI avant d'ouvrir la fenêtre
    {
        let mut guard = backend.lock().unwrap();
        *guard = spawn_backend();
    }

    // Attend que FastAPI soit prêt (max 5s, retry 500ms)
    let ready = wait_for_backend("http://127.0.0.1:8765/health", 10, 500);
    if !ready {
        eprintln!("[Tauri] FastAPI n'a pas démarré en 5s — vérifiez le backend.");
    }

    tauri::Builder::default()
        .setup(|app| {
            // Fenêtre principale
            let window = app.get_webview_window("main").unwrap();
            window.set_title("LocalCoder IDE v2").unwrap();
            Ok(())
        })
        .on_window_event(move |_window, event| {
            // Fermeture de la fenêtre → SIGTERM au backend
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let mut guard = backend_clone.lock().unwrap();
                if let Some(child) = guard.as_mut() {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 2.3 : Ajouter ureq dans Cargo.toml**

```bash
# Ouvrir ui/src-tauri/Cargo.toml et ajouter dans [dependencies] :
# ureq = "2"
```

Éditer `ui/src-tauri/Cargo.toml` — ajouter dans `[dependencies]` :

```toml
ureq = "2"
```

- [ ] **Step 2.4 : Configurer ui/src-tauri/tauri.conf.json**

Remplacer le contenu de `tauri.conf.json` par :

```json
{
  "productName": "LocalCoder IDE",
  "version": "2.0.0",
  "identifier": "com.localcoder.ide",
  "build": {
    "frontendDist": "../dist",
    "devUrl": "http://localhost:1420",
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build"
  },
  "app": {
    "withGlobalTauri": false,
    "windows": [
      {
        "label": "main",
        "title": "LocalCoder IDE v2",
        "width": 1400,
        "height": 900,
        "minWidth": 1000,
        "minHeight": 600,
        "resizable": true,
        "fullscreen": false
      }
    ]
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": []
  }
}
```

- [ ] **Step 2.5 : Vérifier que Rust compile**

```bash
cd ui/src-tauri && cargo check 2>&1 | tail -5
```

Expected : `Finished \`dev\` profile` (ou warnings, mais pas d'erreurs)

- [ ] **Step 2.6 : Commit**

```bash
cd /Users/wissem/local_ai_stack
git add ui/src-tauri/
git commit -m "feat: Tauri shell spawns FastAPI subprocess with health check and SIGTERM on close"
```

---

## Task 3 : WebSocket client singleton (ws.ts)

**Files:**
- Create: `ui/src/ws.ts`

Pas de tests automatisés (WebSocket réel → testé via le navigateur).

- [ ] **Step 3.1 : Créer ui/src/ws.ts**

```typescript
// ui/src/ws.ts
// Singleton WebSocket — une seule connexion partagée entre tous les stores.
// Reconnexion automatique toutes les 2s si la connexion est perdue.
// Les handlers sont enregistrés par type de message.

type WSHandler = (data: unknown) => void;

class WSClient {
  private socket: WebSocket | null = null;
  private handlers: Map<string, WSHandler[]> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  readonly url = "ws://127.0.0.1:8765/ws";

  connect(): void {
    if (this.socket?.readyState === WebSocket.OPEN) return;

    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      console.log("[WS] Connected to backend");
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as { type: string; data: unknown };
        const handlers = this.handlers.get(msg.type) ?? [];
        handlers.forEach((h) => h(msg.data));
      } catch {
        // Message non-JSON ignoré silencieusement
      }
    };

    this.socket.onclose = () => {
      console.log("[WS] Disconnected — retrying in 2s");
      this.reconnectTimer = setTimeout(() => this.connect(), 2000);
    };

    this.socket.onerror = (err) => {
      console.error("[WS] Error:", err);
    };
  }

  on(type: string, handler: WSHandler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, []);
    }
    this.handlers.get(type)!.push(handler);
    // Retourne une fonction de cleanup
    return () => {
      const list = this.handlers.get(type) ?? [];
      const idx = list.indexOf(handler);
      if (idx !== -1) list.splice(idx, 1);
    };
  }

  send(type: string, data: unknown): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type, data }));
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    this.socket?.close();
  }
}

// Singleton exporté — une seule instance dans toute l'app
export const ws = new WSClient();
```

- [ ] **Step 3.2 : Commit**

```bash
git add ui/src/ws.ts
git commit -m "feat: WebSocket singleton client with auto-reconnect and typed handlers"
```

---

## Task 4 : Stores Zustand

**Files:**
- Create: `ui/src/stores/llmStore.ts`
- Create: `ui/src/stores/routingStore.ts`
- Create: `ui/src/stores/roadmapStore.ts`
- Create: `ui/src/stores/sessionStore.ts`

- [ ] **Step 4.1 : Créer ui/src/stores/llmStore.ts**

```typescript
// ui/src/stores/llmStore.ts
// Statut temps réel des LLMs — mis à jour via WebSocket.
import { create } from "zustand";
import { ws } from "../ws";

export type LLMStatus = "idle" | "busy" | "disabled" | "error";

export interface LLMInfo {
  id: string;        // "minimax/minimax-m2.5"
  name: string;      // "MiniMax M2.5"
  role: string;      // "coding" | "architecture" | "testing" | "analysis" | "routing"
  status: LLMStatus;
  currentTask: string | null;
  tokensToday: number;
  latencyMs: number; // dernière latence mesurée
}

interface LLMStore {
  llms: LLMInfo[];
  setStatus: (id: string, status: LLMStatus, task?: string) => void;
  setDisabled: (id: string, disabled: boolean) => void;
  updateTokens: (id: string, tokens: number) => void;
  updateLatency: (id: string, latencyMs: number) => void;
}

const DEFAULT_LLMS: LLMInfo[] = [
  { id: "minimax/minimax-m2.5", name: "MiniMax M2.5", role: "coding", status: "idle", currentTask: null, tokensToday: 0, latencyMs: 0 },
  { id: "gemini/gemini-2.5-pro", name: "Gemini Pro", role: "analysis", status: "idle", currentTask: null, tokensToday: 0, latencyMs: 0 },
  { id: "gemini/gemini-2.5-flash", name: "Gemini Flash", role: "routing", status: "idle", currentTask: null, tokensToday: 0, latencyMs: 0 },
  { id: "deepseek/deepseek-r1", name: "DeepSeek R1", role: "architecture", status: "idle", currentTask: null, tokensToday: 0, latencyMs: 0 },
  { id: "mistral/codestral-2", name: "Codestral 2", role: "testing", status: "idle", currentTask: null, tokensToday: 0, latencyMs: 0 },
];

export const useLLMStore = create<LLMStore>((set) => ({
  llms: DEFAULT_LLMS,

  setStatus: (id, status, task) =>
    set((state) => ({
      llms: state.llms.map((llm) =>
        llm.id === id ? { ...llm, status, currentTask: task ?? llm.currentTask } : llm
      ),
    })),

  setDisabled: (id, disabled) =>
    set((state) => ({
      llms: state.llms.map((llm) =>
        llm.id === id ? { ...llm, status: disabled ? "disabled" : "idle" } : llm
      ),
    })),

  updateTokens: (id, tokens) =>
    set((state) => ({
      llms: state.llms.map((llm) =>
        llm.id === id ? { ...llm, tokensToday: llm.tokensToday + tokens } : llm
      ),
    })),

  updateLatency: (id, latencyMs) =>
    set((state) => ({
      llms: state.llms.map((llm) =>
        llm.id === id ? { ...llm, latencyMs } : llm
      ),
    })),
}));

// Connecter aux events WebSocket au montage de l'app
export function connectLLMStore(): () => void {
  const cleanups = [
    ws.on("llm_status", (data) => {
      const { id, status, task } = data as { id: string; status: LLMStatus; task?: string };
      useLLMStore.getState().setStatus(id, status, task);
    }),
    ws.on("llm_tokens", (data) => {
      const { id, tokens } = data as { id: string; tokens: number };
      useLLMStore.getState().updateTokens(id, tokens);
    }),
    ws.on("llm_latency", (data) => {
      const { id, latencyMs } = data as { id: string; latencyMs: number };
      useLLMStore.getState().updateLatency(id, latencyMs);
    }),
  ];
  return () => cleanups.forEach((c) => c());
}
```

- [ ] **Step 4.2 : Créer ui/src/stores/routingStore.ts**

```typescript
// ui/src/stores/routingStore.ts
// Historique et décision live de routing — mis à jour via WebSocket.
import { create } from "zustand";
import { ws } from "../ws";

export interface RoutingEntry {
  id: string;
  timestamp: number;
  prompt: string;
  llm: string;
  role: string;
  mode: string;
  reason: string;
  durationMs: number;
  tokens: number;
}

export interface LiveRouting {
  prompt: string;
  llm: string;
  step: string;   // "PLAN" | "VERIFY" | "EXECUTE" | "CHECK" | "CONFIRM"
  attempt: number;
}

interface RoutingStore {
  history: RoutingEntry[];
  live: LiveRouting | null;
  addEntry: (entry: RoutingEntry) => void;
  setLive: (live: LiveRouting | null) => void;
}

export const useRoutingStore = create<RoutingStore>((set) => ({
  history: [],
  live: null,

  addEntry: (entry) =>
    set((state) => ({
      history: [entry, ...state.history].slice(0, 100), // max 100 entrées
    })),

  setLive: (live) => set({ live }),
}));

export function connectRoutingStore(): () => void {
  const cleanups = [
    ws.on("routing_decision", (data) => {
      const entry = data as RoutingEntry;
      useRoutingStore.getState().addEntry(entry);
      useRoutingStore.getState().setLive({
        prompt: entry.prompt,
        llm: entry.llm,
        step: "PLAN",
        attempt: 1,
      });
    }),
    ws.on("agent_step", (data) => {
      const { step, attempt } = data as { step: string; attempt: number };
      const state = useRoutingStore.getState();
      if (state.live) {
        state.setLive({ ...state.live, step, attempt });
      }
    }),
    ws.on("task_complete", () => {
      useRoutingStore.getState().setLive(null);
    }),
  ];
  return () => cleanups.forEach((c) => c());
}
```

- [ ] **Step 4.3 : Créer ui/src/stores/roadmapStore.ts**

```typescript
// ui/src/stores/roadmapStore.ts
// Roadmap projet courante — synchronisée depuis le backend.
import { create } from "zustand";
import { ws } from "../ws";

export interface SubTask {
  id: string;
  text: string;
  done: boolean;
}

export interface RoadmapTask {
  id: string;
  title: string;
  status: "pending" | "in_progress" | "done" | "failed" | "blocked";
  assignedTo: string;
  subtasks: SubTask[];
  sprint: string;
  estimatedComplexity: number;
  githubIssue: number | null;
}

export interface Roadmap {
  project: string;
  sessionId: string;
  tasks: RoadmapTask[];
}

interface RoadmapStore {
  roadmap: Roadmap | null;
  setRoadmap: (roadmap: Roadmap) => void;
  clearRoadmap: () => void;
  updateTaskStatus: (taskId: string, status: RoadmapTask["status"]) => void;
}

export const useRoadmapStore = create<RoadmapStore>((set) => ({
  roadmap: null,
  setRoadmap: (roadmap) => set({ roadmap }),
  clearRoadmap: () => set({ roadmap: null }),
  updateTaskStatus: (taskId, status) =>
    set((state) => {
      if (!state.roadmap) return state;
      return {
        roadmap: {
          ...state.roadmap,
          tasks: state.roadmap.tasks.map((t) =>
            t.id === taskId ? { ...t, status } : t
          ),
        },
      };
    }),
}));

export function connectRoadmapStore(): () => void {
  const cleanups = [
    ws.on("roadmap_update", (data) => {
      useRoadmapStore.getState().setRoadmap(data as Roadmap);
    }),
    ws.on("task_status", (data) => {
      const { id, status } = data as { id: string; status: RoadmapTask["status"] };
      useRoadmapStore.getState().updateTaskStatus(id, status);
    }),
    ws.on("project_mode_off", () => {
      useRoadmapStore.getState().clearRoadmap();
    }),
  ];
  return () => cleanups.forEach((c) => c());
}
```

- [ ] **Step 4.4 : Créer ui/src/stores/sessionStore.ts**

```typescript
// ui/src/stores/sessionStore.ts
// Session active : tokens, coût estimé, branche git.
import { create } from "zustand";
import { ws } from "../ws";

interface SessionStore {
  branch: string;
  modifiedFiles: number;
  tokensToday: number;
  estimatedCostUSD: number;
  backendStatus: "connecting" | "ready" | "error";
  setBackendStatus: (s: "connecting" | "ready" | "error") => void;
  setBranch: (branch: string, modifiedFiles: number) => void;
  addTokens: (tokens: number, costUSD: number) => void;
}

export const useSessionStore = create<SessionStore>((set) => ({
  branch: "main",
  modifiedFiles: 0,
  tokensToday: 0,
  estimatedCostUSD: 0,
  backendStatus: "connecting",

  setBackendStatus: (backendStatus) => set({ backendStatus }),
  setBranch: (branch, modifiedFiles) => set({ branch, modifiedFiles }),
  addTokens: (tokens, costUSD) =>
    set((state) => ({
      tokensToday: state.tokensToday + tokens,
      estimatedCostUSD: state.estimatedCostUSD + costUSD,
    })),
}));

export function connectSessionStore(): () => void {
  const cleanups = [
    ws.on("git_status", (data) => {
      const { branch, modifiedFiles } = data as { branch: string; modifiedFiles: number };
      useSessionStore.getState().setBranch(branch, modifiedFiles);
    }),
    ws.on("token_usage", (data) => {
      const { tokens, costUSD } = data as { tokens: number; costUSD: number };
      useSessionStore.getState().addTokens(tokens, costUSD);
    }),
  ];
  return () => cleanups.forEach((c) => c());
}
```

- [ ] **Step 4.5 : Commit**

```bash
git add ui/src/stores/ ui/src/ws.ts
git commit -m "feat: add 4 Zustand stores (llm, routing, roadmap, session) with WebSocket bindings"
```

---

## Task 5 : App.tsx — layout principal et tabs

**Files:**
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/main.tsx`

- [ ] **Step 5.1 : Modifier ui/src/main.tsx**

```tsx
// ui/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { ws } from "./ws";
import { connectLLMStore } from "./stores/llmStore";
import { connectRoutingStore } from "./stores/routingStore";
import { connectRoadmapStore } from "./stores/roadmapStore";
import { connectSessionStore } from "./stores/sessionStore";
import { useSessionStore } from "./stores/sessionStore";

// Démarrage WebSocket + stores
ws.connect();
connectLLMStore();
connectRoutingStore();
connectRoadmapStore();
connectSessionStore();

// Marquer backend prêt quand la connexion WS est établie
ws.on("health", () => {
  useSessionStore.getState().setBackendStatus("ready");
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 5.2 : Réécrire ui/src/App.tsx**

```tsx
// ui/src/App.tsx
// Layout principal : ActivityBar gauche | Zone principale | StatusBar bas
import { useState, lazy, Suspense } from "react";
import { ActivityBar } from "./components/ActivityBar/ActivityBar";
import { StatusBar } from "./components/StatusBar/StatusBar";

// Lazy loading des tabs pour performance
const ChatTab = lazy(() => import("./components/tabs/ChatTab/ChatTab"));
const TerminalsTab = lazy(() => import("./components/tabs/TerminalsTab/TerminalsTab"));
const RoutingTab = lazy(() => import("./components/tabs/RoutingTab/RoutingTab"));
const MonitoringTab = lazy(() => import("./components/tabs/MonitoringTab/MonitoringTab"));

type Tab = "chat" | "terminals" | "routing" | "monitoring";

const TAB_LABELS: Record<Tab, string> = {
  chat: "Chat",
  terminals: "Terminaux",
  routing: "Routing Flow",
  monitoring: "Monitoring",
};

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#1e1e2e]">
      {/* Zone principale = ActivityBar + Contenu */}
      <div className="flex flex-1 overflow-hidden">
        {/* Colonne gauche — Activity Bar */}
        <ActivityBar />

        {/* Zone centrale — Tabs + Contenu */}
        <div className="flex flex-col flex-1 overflow-hidden">
          {/* Tab bar */}
          <div className="flex border-b border-[#313244] bg-[#181825] shrink-0">
            {(Object.keys(TAB_LABELS) as Tab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={[
                  "px-4 py-2 text-sm font-medium transition-colors",
                  activeTab === tab
                    ? "text-[#cdd6f4] border-b-2 border-[#89b4fa] bg-[#1e1e2e]"
                    : "text-[#6c7086] hover:text-[#cdd6f4]",
                ].join(" ")}
              >
                {TAB_LABELS[tab]}
              </button>
            ))}
          </div>

          {/* Contenu du tab actif */}
          <div className="flex-1 overflow-hidden">
            <Suspense fallback={<div className="p-4 text-[#6c7086]">Chargement...</div>}>
              {activeTab === "chat" && <ChatTab />}
              {activeTab === "terminals" && <TerminalsTab />}
              {activeTab === "routing" && <RoutingTab />}
              {activeTab === "monitoring" && <MonitoringTab />}
            </Suspense>
          </div>
        </div>
      </div>

      {/* Status Bar — toujours visible */}
      <StatusBar />
    </div>
  );
}
```

- [ ] **Step 5.3 : Créer un RoutingTab stub pour que l'app compile**

Créer `ui/src/components/tabs/RoutingTab/RoutingTab.tsx` :

```tsx
// ui/src/components/tabs/RoutingTab/RoutingTab.tsx
import { RoutingLive } from "./RoutingLive";
import { RoutingHistory } from "./RoutingHistory";

export default function RoutingTab() {
  return (
    <div className="flex flex-col h-full p-4 gap-4">
      <RoutingLive />
      <RoutingHistory />
    </div>
  );
}
```

- [ ] **Step 5.4 : Commit**

```bash
git add ui/src/App.tsx ui/src/main.tsx ui/src/components/tabs/RoutingTab/
git commit -m "feat: main layout with tab bar, lazy-loaded tabs, ActivityBar and StatusBar slots"
```

---

## Task 6 : StatusBar

**Files:**
- Create: `ui/src/components/StatusBar/StatusBar.tsx`

- [ ] **Step 6.1 : Créer StatusBar.tsx**

```tsx
// ui/src/components/StatusBar/StatusBar.tsx
// Barre inférieure toujours visible : pastilles LLMs, branch git, tokens, coût.
import { useLLMStore } from "../../stores/llmStore";
import { useSessionStore } from "../../stores/sessionStore";

const STATUS_COLOR: Record<string, string> = {
  idle: "bg-[#a6e3a1]",     // vert
  busy: "bg-[#f9e2af]",     // orange
  disabled: "bg-[#6c7086]", // gris
  error: "bg-[#f38ba8]",    // rouge
};

export function StatusBar() {
  const llms = useLLMStore((s) => s.llms);
  const { branch, modifiedFiles, tokensToday, estimatedCostUSD, backendStatus } =
    useSessionStore();

  return (
    <div className="flex items-center gap-4 px-3 py-1 bg-[#89b4fa] text-[#1e1e2e] text-xs font-mono shrink-0">
      {/* Pastilles LLMs */}
      <div className="flex items-center gap-1.5">
        {llms.map((llm) => (
          <div key={llm.id} className="flex items-center gap-1" title={`${llm.name}: ${llm.status}`}>
            <span className={`w-2 h-2 rounded-full ${STATUS_COLOR[llm.status]}`} />
            <span className="text-[10px]">{llm.name.split(" ")[0]}</span>
          </div>
        ))}
      </div>

      <span className="opacity-40">|</span>

      {/* Branch git */}
      <span>
        ⎇ {branch}
        {modifiedFiles > 0 && (
          <span className="ml-1 opacity-70">({modifiedFiles} modifiés)</span>
        )}
      </span>

      <span className="opacity-40">|</span>

      {/* Tokens + Coût */}
      <span>
        {tokensToday.toLocaleString()} tokens • ${estimatedCostUSD.toFixed(3)}
      </span>

      {/* Backend status — à droite */}
      <div className="ml-auto flex items-center gap-1">
        <span
          className={`w-2 h-2 rounded-full ${
            backendStatus === "ready" ? "bg-[#a6e3a1]" :
            backendStatus === "error" ? "bg-[#f38ba8]" :
            "bg-[#f9e2af]"
          }`}
        />
        <span>
          {backendStatus === "ready" ? "Backend prêt" :
           backendStatus === "error" ? "Backend erreur" :
           "Connexion..."}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 6.2 : Commit**

```bash
git add ui/src/components/StatusBar/
git commit -m "feat: StatusBar with LLM pastilles, git branch, tokens and cost"
```

---

## Task 7 : Activity Bar + panneaux gauche

**Files:**
- Create: `ui/src/components/ActivityBar/ActivityBar.tsx`
- Create: `ui/src/components/ActivityBar/FileTree.tsx`
- Create: `ui/src/components/ActivityBar/LLMStatus.tsx`
- Create: `ui/src/components/ActivityBar/GitPanel.tsx`
- Create: `ui/src/components/ActivityBar/SprintBoard.tsx`

- [ ] **Step 7.1 : Créer ActivityBar.tsx**

```tsx
// ui/src/components/ActivityBar/ActivityBar.tsx
// Colonne gauche : icons navigation + panneau actif.
import { useState } from "react";
import { FileTree } from "./FileTree";
import { LLMStatus } from "./LLMStatus";
import { GitPanel } from "./GitPanel";
import { SprintBoard } from "./SprintBoard";

type Panel = "files" | "llms" | "git" | "sprints";

const ICONS: Record<Panel, string> = {
  files: "📁",
  llms: "🤖",
  git: "⎇",
  sprints: "📋",
};

const PANELS: Record<Panel, React.ComponentType> = {
  files: FileTree,
  llms: LLMStatus,
  git: GitPanel,
  sprints: SprintBoard,
};

export function ActivityBar() {
  const [activePanel, setActivePanel] = useState<Panel>("files");
  const ActivePanel = PANELS[activePanel];

  return (
    <div className="flex shrink-0 border-r border-[#313244]">
      {/* Icons bar — 40px */}
      <div className="flex flex-col items-center py-2 gap-1 w-10 bg-[#181825]">
        {(Object.keys(ICONS) as Panel[]).map((panel) => (
          <button
            key={panel}
            onClick={() => setActivePanel(panel)}
            title={panel}
            className={[
              "w-8 h-8 flex items-center justify-center rounded text-base transition-colors",
              activePanel === panel
                ? "bg-[#313244] text-[#cdd6f4]"
                : "text-[#6c7086] hover:text-[#cdd6f4]",
            ].join(" ")}
          >
            {ICONS[panel]}
          </button>
        ))}
      </div>

      {/* Panneau actif — 220px */}
      <div className="w-56 bg-[#181825] overflow-y-auto">
        <ActivePanel />
      </div>
    </div>
  );
}
```

- [ ] **Step 7.2 : Créer FileTree.tsx**

```tsx
// ui/src/components/ActivityBar/FileTree.tsx
// Explorateur fichiers minimaliste. Fichiers modifiés en jaune.
// Les fichiers viennent du WebSocket event "file_tree".
import { useState, useEffect } from "react";
import { ws } from "../../ws";

interface FileNode {
  name: string;
  path: string;
  type: "file" | "dir";
  modified: boolean;
  children?: FileNode[];
}

export function FileTree() {
  const [tree, setTree] = useState<FileNode[]>([]);

  useEffect(() => {
    const cleanup = ws.on("file_tree", (data) => {
      setTree(data as FileNode[]);
    });
    // Demander l'arbre au montage
    ws.send("request_file_tree", {});
    return cleanup;
  }, []);

  function renderNode(node: FileNode, depth: number): React.ReactNode {
    return (
      <div key={node.path}>
        <div
          className={[
            "flex items-center gap-1 px-2 py-0.5 cursor-pointer hover:bg-[#313244] rounded text-xs",
            node.modified ? "text-[#f9e2af]" : "text-[#cdd6f4]",
          ].join(" ")}
          style={{ paddingLeft: `${8 + depth * 12}px` }}
        >
          <span>{node.type === "dir" ? "📂" : "📄"}</span>
          <span>{node.name}</span>
          {node.modified && <span className="ml-auto text-[#f9e2af] text-[9px]">M</span>}
        </div>
        {node.children?.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  }

  if (tree.length === 0) {
    return (
      <div className="p-3 text-[#6c7086] text-xs">
        <p className="font-medium mb-1">Fichiers</p>
        <p className="opacity-60">Aucun fichier chargé</p>
      </div>
    );
  }

  return (
    <div className="py-2">
      <p className="px-3 py-1 text-[#6c7086] text-[10px] uppercase tracking-wider font-medium">
        Fichiers
      </p>
      {tree.map((node) => renderNode(node, 0))}
    </div>
  );
}
```

- [ ] **Step 7.3 : Créer LLMStatus.tsx**

```tsx
// ui/src/components/ActivityBar/LLMStatus.tsx
// Panneau statut temps réel des LLMs avec bouton désactiver/activer.
import { useLLMStore } from "../../stores/llmStore";

const STATUS_LABEL: Record<string, string> = {
  idle: "Disponible",
  busy: "En cours...",
  disabled: "Désactivé",
  error: "Erreur",
};

const STATUS_DOT: Record<string, string> = {
  idle: "bg-[#a6e3a1]",
  busy: "bg-[#f9e2af] animate-pulse",
  disabled: "bg-[#6c7086]",
  error: "bg-[#f38ba8]",
};

export function LLMStatus() {
  const { llms, setDisabled } = useLLMStore();

  return (
    <div className="py-2">
      <p className="px-3 py-1 text-[#6c7086] text-[10px] uppercase tracking-wider font-medium">
        LLMs
      </p>
      {llms.map((llm) => (
        <div key={llm.id} className="px-3 py-2 border-b border-[#313244]">
          <div className="flex items-center gap-2 mb-1">
            <span className={`w-2 h-2 rounded-full shrink-0 ${STATUS_DOT[llm.status]}`} />
            <span className="text-xs font-medium text-[#cdd6f4] truncate">{llm.name}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-[#6c7086]">
              {STATUS_LABEL[llm.status]}
              {llm.status === "busy" && llm.currentTask && (
                <span className="ml-1 opacity-70 truncate block max-w-[120px]">
                  {llm.currentTask}
                </span>
              )}
            </span>
            {llm.status !== "busy" && (
              <button
                onClick={() => setDisabled(llm.id, llm.status !== "disabled")}
                className="text-[9px] px-1.5 py-0.5 rounded bg-[#313244] text-[#6c7086] hover:text-[#cdd6f4]"
              >
                {llm.status === "disabled" ? "Activer" : "Désact."}
              </button>
            )}
          </div>
          <div className="mt-1 text-[10px] text-[#6c7086]">
            {llm.tokensToday.toLocaleString()} tokens • {llm.latencyMs}ms
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 7.4 : Créer GitPanel.tsx**

```tsx
// ui/src/components/ActivityBar/GitPanel.tsx
// Panneau Git minimal : fichiers modifiés, stage, commit message.
import { useState, useEffect } from "react";
import { ws } from "../../ws";

interface GitFile {
  path: string;
  status: "modified" | "added" | "deleted" | "untracked";
}

export function GitPanel() {
  const [files, setFiles] = useState<GitFile[]>([]);
  const [commitMsg, setCommitMsg] = useState("");
  const [staged, setStaged] = useState<Set<string>>(new Set());

  useEffect(() => {
    const cleanup = ws.on("git_diff_files", (data) => {
      setFiles(data as GitFile[]);
    });
    ws.send("request_git_diff", {});
    return cleanup;
  }, []);

  function toggleStage(path: string) {
    setStaged((prev) => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  }

  function handleCommit() {
    if (!commitMsg.trim() || staged.size === 0) return;
    ws.send("git_commit", { files: [...staged], message: commitMsg });
    setCommitMsg("");
    setStaged(new Set());
  }

  const STATUS_COLORS: Record<string, string> = {
    modified: "text-[#f9e2af]",
    added: "text-[#a6e3a1]",
    deleted: "text-[#f38ba8]",
    untracked: "text-[#6c7086]",
  };

  return (
    <div className="py-2 flex flex-col h-full">
      <p className="px-3 py-1 text-[#6c7086] text-[10px] uppercase tracking-wider font-medium">
        Git
      </p>

      {/* Fichiers modifiés */}
      <div className="flex-1 overflow-y-auto">
        {files.length === 0 ? (
          <p className="px-3 py-2 text-[#6c7086] text-xs opacity-60">Aucun changement</p>
        ) : (
          files.map((f) => (
            <div
              key={f.path}
              className="flex items-center gap-2 px-3 py-1 hover:bg-[#313244] cursor-pointer"
              onClick={() => toggleStage(f.path)}
            >
              <input
                type="checkbox"
                checked={staged.has(f.path)}
                readOnly
                className="w-3 h-3"
              />
              <span className={`text-[10px] truncate ${STATUS_COLORS[f.status]}`}>
                {f.path.split("/").pop()}
              </span>
            </div>
          ))
        )}
      </div>

      {/* Commit */}
      <div className="px-2 pb-2 border-t border-[#313244] pt-2">
        <input
          type="text"
          value={commitMsg}
          onChange={(e) => setCommitMsg(e.target.value)}
          placeholder="Message de commit..."
          className="w-full bg-[#313244] text-[#cdd6f4] text-xs px-2 py-1 rounded outline-none placeholder-[#6c7086] mb-1"
        />
        <button
          onClick={handleCommit}
          disabled={!commitMsg.trim() || staged.size === 0}
          className="w-full py-1 rounded bg-[#89b4fa] text-[#1e1e2e] text-xs font-medium disabled:opacity-40"
        >
          Commit ({staged.size})
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 7.5 : Créer SprintBoard.tsx**

```tsx
// ui/src/components/ActivityBar/SprintBoard.tsx
// Kanban minimal des tickets en cours — synchronisé avec roadmapStore.
import { useRoadmapStore } from "../../stores/roadmapStore";

const STATUS_COLORS: Record<string, string> = {
  pending: "text-[#6c7086]",
  in_progress: "text-[#f9e2af]",
  done: "text-[#a6e3a1]",
  failed: "text-[#f38ba8]",
  blocked: "text-[#cba6f7]",
};

const STATUS_ICONS: Record<string, string> = {
  pending: "○",
  in_progress: "◐",
  done: "●",
  failed: "✕",
  blocked: "⊘",
};

export function SprintBoard() {
  const roadmap = useRoadmapStore((s) => s.roadmap);

  if (!roadmap) {
    return (
      <div className="p-3 text-[#6c7086] text-xs">
        <p className="font-medium mb-1">Sprints</p>
        <p className="opacity-60">Aucun projet actif.</p>
        <p className="opacity-40 mt-1">Décris une app dans le chat pour démarrer.</p>
      </div>
    );
  }

  // Grouper par sprint
  const sprints = [...new Set(roadmap.tasks.map((t) => t.sprint))];

  return (
    <div className="py-2">
      <p className="px-3 py-1 text-[#6c7086] text-[10px] uppercase tracking-wider font-medium">
        {roadmap.project}
      </p>
      {sprints.map((sprint) => (
        <div key={sprint} className="mb-2">
          <p className="px-3 py-0.5 text-[#89b4fa] text-[10px] font-medium">{sprint}</p>
          {roadmap.tasks
            .filter((t) => t.sprint === sprint)
            .map((task) => (
              <div key={task.id} className="px-3 py-1 hover:bg-[#313244]">
                <div className="flex items-start gap-1.5">
                  <span className={`text-[10px] mt-0.5 ${STATUS_COLORS[task.status]}`}>
                    {STATUS_ICONS[task.status]}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] text-[#cdd6f4] truncate">{task.title}</p>
                    <p className="text-[9px] text-[#6c7086]">
                      [{task.id}] • score {task.estimatedComplexity}/10
                    </p>
                  </div>
                </div>
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 7.6 : Commit**

```bash
git add ui/src/components/ActivityBar/
git commit -m "feat: ActivityBar with FileTree, LLMStatus, GitPanel and SprintBoard panels"
```

---

## Task 8 : ChatTab

**Files:**
- Create: `ui/src/components/tabs/ChatTab/ChatTab.tsx`
- Create: `ui/src/components/tabs/ChatTab/MessageBubble.tsx`
- Create: `ui/src/components/tabs/ChatTab/ChatInput.tsx`

- [ ] **Step 8.1 : Créer MessageBubble.tsx**

```tsx
// ui/src/components/tabs/ChatTab/MessageBubble.tsx
// Un message dans le chat — avec badge LLM, durée, tokens.
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  llm?: string;
  llmName?: string;
  durationMs?: number;
  tokens?: number;
  timestamp: number;
}

const LLM_COLORS: Record<string, string> = {
  "minimax/minimax-m2.5": "bg-[#89b4fa] text-[#1e1e2e]",
  "deepseek/deepseek-r1": "bg-[#cba6f7] text-[#1e1e2e]",
  "gemini/gemini-2.5-pro": "bg-[#a6e3a1] text-[#1e1e2e]",
  "gemini/gemini-2.5-flash": "bg-[#94e2d5] text-[#1e1e2e]",
  "mistral/codestral-2": "bg-[#f9e2af] text-[#1e1e2e]",
};

const LLM_ICONS: Record<string, string> = {
  "minimax/minimax-m2.5": "💻",
  "deepseek/deepseek-r1": "💡",
  "gemini/gemini-2.5-pro": "🔍",
  "gemini/gemini-2.5-flash": "⚡",
  "mistral/codestral-2": "🧪",
};

export function MessageBubble({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end mb-3">
        <div className="max-w-[70%] bg-[#313244] rounded-2xl rounded-tr-sm px-4 py-2">
          <p className="text-sm text-[#cdd6f4] whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  const colorClass = message.llm ? LLM_COLORS[message.llm] ?? "bg-[#6c7086] text-white" : "bg-[#6c7086] text-white";
  const icon = message.llm ? LLM_ICONS[message.llm] ?? "🤖" : "🤖";

  return (
    <div className="flex flex-col gap-1 mb-4">
      {/* Badge LLM */}
      {message.llmName && (
        <div className="flex items-center gap-2">
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${colorClass}`}>
            {icon} {message.llmName}
          </span>
          {message.durationMs && (
            <span className="text-[10px] text-[#6c7086]">
              {(message.durationMs / 1000).toFixed(1)}s
              {message.tokens ? ` • ${message.tokens} tokens` : ""}
            </span>
          )}
        </div>
      )}
      {/* Contenu */}
      <div className="max-w-[85%] bg-[#181825] border border-[#313244] rounded-2xl rounded-tl-sm px-4 py-3">
        <p className="text-sm text-[#cdd6f4] whitespace-pre-wrap leading-relaxed">
          {message.content}
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 8.2 : Créer ChatInput.tsx**

```tsx
// ui/src/components/tabs/ChatTab/ChatInput.tsx
// Zone de saisie avec boutons @mention et envoi.
import { useState, useRef } from "react";

const MENTIONS = [
  { key: "minimax", label: "@minimax" },
  { key: "gemini", label: "@gemini" },
  { key: "deepseek", label: "@deepseek" },
  { key: "codestral", label: "@codestral" },
];

interface ChatInputProps {
  onSend: (prompt: string, mention: string | null) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [activeMention, setActiveMention] = useState<string | null>(null);
  const ref = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, activeMention);
    setValue("");
    setActiveMention(null);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="border-t border-[#313244] p-3 bg-[#181825]">
      {/* Boutons @mention */}
      <div className="flex gap-1 mb-2">
        {MENTIONS.map((m) => (
          <button
            key={m.key}
            onClick={() => setActiveMention(activeMention === m.key ? null : m.key)}
            className={[
              "text-[10px] px-2 py-0.5 rounded-full border transition-colors",
              activeMention === m.key
                ? "bg-[#89b4fa] border-[#89b4fa] text-[#1e1e2e] font-medium"
                : "border-[#313244] text-[#6c7086] hover:text-[#cdd6f4]",
            ].join(" ")}
          >
            {m.label}
          </button>
        ))}
        <span className="ml-auto text-[#6c7086] text-[10px] self-center">
          {activeMention ? `→ ${activeMention}` : "Auto-routing"}
        </span>
      </div>

      {/* Textarea + bouton envoyer */}
      <div className="flex gap-2">
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Décris ta tâche... (Enter pour envoyer, Shift+Enter pour nouvelle ligne)"
          disabled={disabled}
          rows={3}
          className="flex-1 bg-[#313244] text-[#cdd6f4] text-sm px-3 py-2 rounded-lg outline-none
                     placeholder-[#6c7086] resize-none disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={!value.trim() || disabled}
          className="px-4 py-2 bg-[#89b4fa] text-[#1e1e2e] rounded-lg font-medium text-sm
                     disabled:opacity-40 hover:bg-[#74c7ec] transition-colors self-end"
        >
          ↵
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 8.3 : Créer ChatTab.tsx**

```tsx
// ui/src/components/tabs/ChatTab/ChatTab.tsx
// Chat universel — affiche les messages et route via WebSocket.
import { useState, useEffect, useRef } from "react";
import { ws } from "../../../ws";
import { MessageBubble, type Message } from "./MessageBubble";
import { ChatInput } from "./ChatInput";

export default function ChatTab() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cleanup = ws.on("chat_response", (data) => {
      const resp = data as {
        content: string;
        llm: string;
        llmName: string;
        tokens: number;
        durationMs: number;
      };
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: resp.content,
          llm: resp.llm,
          llmName: resp.llmName,
          tokens: resp.tokens,
          durationMs: resp.durationMs,
          timestamp: Date.now(),
        },
      ]);
      setIsLoading(false);
    });
    return cleanup;
  }, []);

  // Auto-scroll vers le bas à chaque nouveau message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  function handleSend(prompt: string, mention: string | null) {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: prompt,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    ws.send("chat", { prompt, mention });
  }

  return (
    <div className="flex flex-col h-full">
      {/* Zone de messages */}
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-[#6c7086] text-sm">
            <div className="text-center">
              <p className="text-2xl mb-2">🤖</p>
              <p>Décris une tâche ou un projet.</p>
              <p className="text-xs mt-1 opacity-60">Le système choisit le bon LLM automatiquement.</p>
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isLoading && (
          <div className="flex items-center gap-2 text-[#6c7086] text-sm mb-4">
            <div className="flex gap-1">
              <span className="animate-bounce" style={{ animationDelay: "0ms" }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: "150ms" }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: "300ms" }}>●</span>
            </div>
            <span>En cours de traitement...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Zone de saisie */}
      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
```

- [ ] **Step 8.4 : Commit**

```bash
git add ui/src/components/tabs/ChatTab/
git commit -m "feat: ChatTab with MessageBubble (LLM badges), ChatInput (@mentions) and WebSocket"
```

---

## Task 9 : TerminalsTab, RoutingTab, MonitoringTab

**Files:**
- Create: `ui/src/components/tabs/TerminalsTab/TerminalsTab.tsx`
- Create: `ui/src/components/tabs/RoutingTab/RoutingLive.tsx`
- Create: `ui/src/components/tabs/RoutingTab/RoutingHistory.tsx`
- Create: `ui/src/components/tabs/MonitoringTab/MonitoringTab.tsx`

- [ ] **Step 9.1 : Créer TerminalsTab.tsx**

```tsx
// ui/src/components/tabs/TerminalsTab/TerminalsTab.tsx
// Grille de terminaux xterm.js — un par LLM actif.
// Chaque terminal stream les logs de l'agent loop en temps réel.
import { useEffect, useRef, useState } from "react";
import { useLLMStore } from "../../../stores/llmStore";
import { ws } from "../../../ws";

// Import dynamique de xterm pour éviter les erreurs SSR
let Terminal: typeof import("@xterm/xterm").Terminal;
let FitAddon: typeof import("@xterm/addon-fit").FitAddon;

async function loadXterm() {
  const [xtermMod, fitMod] = await Promise.all([
    import("@xterm/xterm"),
    import("@xterm/addon-fit"),
  ]);
  Terminal = xtermMod.Terminal;
  FitAddon = fitMod.FitAddon;
}

function LLMTerminal({ llmId, llmName }: { llmId: string; llmName: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const termRef = useRef<InstanceType<typeof Terminal> | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    let term: InstanceType<typeof Terminal>;
    let fitAddon: InstanceType<typeof FitAddon>;

    loadXterm().then(() => {
      term = new Terminal({
        theme: { background: "#181825", foreground: "#cdd6f4", cursor: "#89b4fa" },
        fontSize: 12,
        fontFamily: "JetBrains Mono, Fira Code, monospace",
        rows: 20,
      });
      fitAddon = new FitAddon();
      term.loadAddon(fitAddon);
      term.open(ref.current!);
      fitAddon.fit();
      termRef.current = term;
      term.writeln(`\x1b[36m[${llmName}]\x1b[0m Terminal prêt.`);
    });

    const cleanup = ws.on("agent_log", (data) => {
      const { llm, line } = data as { llm: string; line: string };
      if (llm === llmId && termRef.current) {
        termRef.current.writeln(line);
      }
    });

    return () => {
      cleanup();
      term?.dispose();
    };
  }, [llmId, llmName]);

  return (
    <div className="flex flex-col h-full bg-[#181825] rounded-lg overflow-hidden border border-[#313244]">
      <div className="flex items-center gap-2 px-3 py-1 border-b border-[#313244] bg-[#313244]">
        <span className="w-2 h-2 rounded-full bg-[#a6e3a1]" />
        <span className="text-xs text-[#cdd6f4] font-medium">{llmName}</span>
      </div>
      <div ref={ref} className="flex-1 p-1" />
    </div>
  );
}

export default function TerminalsTab() {
  const llms = useLLMStore((s) => s.llms.filter((l) => l.status !== "disabled"));

  if (llms.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-[#6c7086] text-sm">
        Aucun LLM actif.
      </div>
    );
  }

  // Grille responsive : 1 colonne si 1 LLM, 2 colonnes sinon
  const gridClass = llms.length === 1 ? "grid-cols-1" : "grid-cols-2";

  return (
    <div className={`grid ${gridClass} gap-2 p-3 h-full`}>
      {llms.map((llm) => (
        <LLMTerminal key={llm.id} llmId={llm.id} llmName={llm.name} />
      ))}
    </div>
  );
}
```

- [ ] **Step 9.2 : Créer RoutingLive.tsx**

```tsx
// ui/src/components/tabs/RoutingTab/RoutingLive.tsx
// Animation du routing en cours — étape active de l'agent loop.
import { useRoutingStore } from "../../../stores/routingStore";

const STEPS = ["PLAN", "VERIFY", "EXECUTE", "CHECK", "CONFIRM"];

const STEP_ICONS: Record<string, string> = {
  PLAN: "📋",
  VERIFY: "🔍",
  EXECUTE: "⚙️",
  CHECK: "✅",
  CONFIRM: "🎉",
};

export function RoutingLive() {
  const live = useRoutingStore((s) => s.live);

  if (!live) {
    return (
      <div className="rounded-lg bg-[#181825] border border-[#313244] p-4 text-[#6c7086] text-sm">
        Aucune tâche en cours.
      </div>
    );
  }

  const activeIdx = STEPS.indexOf(live.step);

  return (
    <div className="rounded-lg bg-[#181825] border border-[#313244] p-4">
      <div className="flex items-start gap-3 mb-4">
        <span className="text-lg">🔄</span>
        <div>
          <p className="text-xs text-[#6c7086] mb-0.5">Prompt en cours</p>
          <p className="text-sm text-[#cdd6f4] font-medium line-clamp-2">{live.prompt}</p>
        </div>
        <div className="ml-auto text-right">
          <p className="text-[10px] text-[#6c7086]">LLM cible</p>
          <p className="text-xs text-[#89b4fa] font-medium">{live.llm.split("/").pop()}</p>
          {live.attempt > 1 && (
            <p className="text-[9px] text-[#f9e2af]">Tentative {live.attempt}/3</p>
          )}
        </div>
      </div>

      {/* Pipeline des étapes */}
      <div className="flex items-center gap-0">
        {STEPS.map((step, idx) => {
          const isDone = idx < activeIdx;
          const isActive = idx === activeIdx;
          const isPending = idx > activeIdx;

          return (
            <div key={step} className="flex items-center flex-1">
              <div className="flex flex-col items-center flex-1">
                <div
                  className={[
                    "w-8 h-8 rounded-full flex items-center justify-center text-sm transition-all",
                    isDone ? "bg-[#a6e3a1] text-[#1e1e2e]" :
                    isActive ? "bg-[#89b4fa] text-[#1e1e2e] animate-pulse" :
                    "bg-[#313244] text-[#6c7086]",
                  ].join(" ")}
                >
                  {isDone ? "✓" : STEP_ICONS[step]}
                </div>
                <p className={`text-[9px] mt-1 ${isActive ? "text-[#89b4fa] font-medium" : "text-[#6c7086]"}`}>
                  {step}
                </p>
              </div>
              {idx < STEPS.length - 1 && (
                <div className={`h-0.5 w-full ${idx < activeIdx ? "bg-[#a6e3a1]" : "bg-[#313244]"}`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 9.3 : Créer RoutingHistory.tsx**

```tsx
// ui/src/components/tabs/RoutingTab/RoutingHistory.tsx
// Tableau des 100 dernières décisions de routage.
import { useRoutingStore } from "../../../stores/routingStore";

const MODE_COLORS: Record<string, string> = {
  simple: "text-[#a6e3a1]",
  medium: "text-[#f9e2af]",
  multi_agent: "text-[#f38ba8]",
};

export function RoutingHistory() {
  const history = useRoutingStore((s) => s.history);

  return (
    <div className="flex-1 overflow-hidden flex flex-col rounded-lg bg-[#181825] border border-[#313244]">
      <div className="px-4 py-2 border-b border-[#313244]">
        <h3 className="text-xs font-medium text-[#6c7086] uppercase tracking-wider">
          Historique ({history.length})
        </h3>
      </div>
      <div className="flex-1 overflow-y-auto">
        {history.length === 0 ? (
          <p className="p-4 text-[#6c7086] text-sm">Aucune décision enregistrée.</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#313244]">
                <th className="px-3 py-2 text-left text-[#6c7086] font-medium">Prompt</th>
                <th className="px-3 py-2 text-left text-[#6c7086] font-medium">LLM</th>
                <th className="px-3 py-2 text-left text-[#6c7086] font-medium">Mode</th>
                <th className="px-3 py-2 text-left text-[#6c7086] font-medium">Durée</th>
                <th className="px-3 py-2 text-left text-[#6c7086] font-medium">Tokens</th>
              </tr>
            </thead>
            <tbody>
              {history.map((entry) => (
                <tr key={entry.id} className="border-b border-[#313244] hover:bg-[#313244]">
                  <td className="px-3 py-2 text-[#cdd6f4] max-w-[200px]">
                    <span className="block truncate" title={entry.prompt}>
                      {entry.prompt}
                    </span>
                    <span className="text-[9px] text-[#6c7086]">{entry.reason}</span>
                  </td>
                  <td className="px-3 py-2 text-[#89b4fa]">{entry.llm.split("/").pop()}</td>
                  <td className="px-3 py-2">
                    <span className={`font-medium ${MODE_COLORS[entry.mode] ?? "text-[#6c7086]"}`}>
                      {entry.mode}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-[#6c7086]">
                    {(entry.durationMs / 1000).toFixed(1)}s
                  </td>
                  <td className="px-3 py-2 text-[#6c7086]">{entry.tokens.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 9.4 : Créer MonitoringTab.tsx**

```tsx
// ui/src/components/tabs/MonitoringTab/MonitoringTab.tsx
// CPU/RAM par processus, tokens/min, latence, statut CI GitHub.
import { useLLMStore } from "../../../stores/llmStore";
import { useSessionStore } from "../../../stores/sessionStore";
import { useState, useEffect } from "react";
import { ws } from "../../../ws";

interface SystemStats {
  cpuPercent: number;
  ramMB: number;
}

interface CIStatus {
  ticketId: string;
  status: "pending" | "running" | "success" | "failure";
  url: string;
}

export default function MonitoringTab() {
  const llms = useLLMStore((s) => s.llms);
  const { tokensToday, estimatedCostUSD } = useSessionStore();
  const [sysStats, setSysStats] = useState<SystemStats>({ cpuPercent: 0, ramMB: 0 });
  const [ciStatuses, setCIStatuses] = useState<CIStatus[]>([]);

  useEffect(() => {
    const cleanups = [
      ws.on("sys_stats", (data) => setSysStats(data as SystemStats)),
      ws.on("ci_status", (data) => {
        const status = data as CIStatus;
        setCIStatuses((prev) => {
          const idx = prev.findIndex((s) => s.ticketId === status.ticketId);
          if (idx === -1) return [...prev, status];
          return prev.map((s, i) => (i === idx ? status : s));
        });
      }),
    ];
    ws.send("request_sys_stats", {});
    return () => cleanups.forEach((c) => c());
  }, []);

  const CI_COLORS: Record<string, string> = {
    pending: "text-[#6c7086]",
    running: "text-[#f9e2af] animate-pulse",
    success: "text-[#a6e3a1]",
    failure: "text-[#f38ba8]",
  };

  return (
    <div className="p-4 grid grid-cols-2 gap-4 h-full overflow-y-auto">
      {/* Section système */}
      <div className="bg-[#181825] rounded-lg border border-[#313244] p-4">
        <h3 className="text-xs font-medium text-[#6c7086] uppercase tracking-wider mb-3">
          Système
        </h3>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-[#6c7086]">CPU</span>
            <span className="text-[#cdd6f4]">{sysStats.cpuPercent.toFixed(1)}%</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-[#6c7086]">RAM</span>
            <span className="text-[#cdd6f4]">{sysStats.ramMB} MB</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-[#6c7086]">Tokens aujourd'hui</span>
            <span className="text-[#cdd6f4]">{tokensToday.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-[#6c7086]">Coût estimé</span>
            <span className="text-[#cdd6f4]">${estimatedCostUSD.toFixed(4)}</span>
          </div>
        </div>
      </div>

      {/* Section LLMs — latence + tokens/min */}
      <div className="bg-[#181825] rounded-lg border border-[#313244] p-4">
        <h3 className="text-xs font-medium text-[#6c7086] uppercase tracking-wider mb-3">
          LLMs — Latence
        </h3>
        <div className="space-y-2">
          {llms.map((llm) => (
            <div key={llm.id} className="flex items-center gap-2">
              <span className="text-[10px] text-[#cdd6f4] w-24 truncate">{llm.name}</span>
              <div className="flex-1 bg-[#313244] rounded-full h-1.5">
                <div
                  className="bg-[#89b4fa] h-1.5 rounded-full transition-all"
                  style={{ width: `${Math.min((llm.latencyMs / 10000) * 100, 100)}%` }}
                />
              </div>
              <span className="text-[10px] text-[#6c7086] w-12 text-right">
                {llm.latencyMs > 0 ? `${(llm.latencyMs / 1000).toFixed(1)}s` : "—"}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Section CI GitHub */}
      <div className="col-span-2 bg-[#181825] rounded-lg border border-[#313244] p-4">
        <h3 className="text-xs font-medium text-[#6c7086] uppercase tracking-wider mb-3">
          CI GitHub — Statut Tickets
        </h3>
        {ciStatuses.length === 0 ? (
          <p className="text-[#6c7086] text-sm">Aucun CI en cours.</p>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            {ciStatuses.map((ci) => (
              <div
                key={ci.ticketId}
                className="flex items-center gap-2 bg-[#313244] rounded px-3 py-2"
              >
                <span className={`text-xs font-medium ${CI_COLORS[ci.status]}`}>
                  {ci.status === "success" ? "✅" :
                   ci.status === "failure" ? "❌" :
                   ci.status === "running" ? "🔄" : "⏳"}
                  {" "}{ci.ticketId}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 9.5 : Commit**

```bash
git add ui/src/components/tabs/
git commit -m "feat: TerminalsTab (xterm.js), RoutingTab (live + history), MonitoringTab (CI status)"
```

---

## Task 10 : Build et vérification finale

- [ ] **Step 10.1 : Vérifier TypeScript sans erreurs**

```bash
cd ui && npx tsc --noEmit 2>&1 | head -30
```

Expected : Aucune erreur (warnings tolérés).

- [ ] **Step 10.2 : Démarrer le dev mode et vérifier l'UI**

```bash
# Terminal 1 — backend
cd /Users/wissem/local_ai_stack && source venv/bin/activate && uvicorn backend.main:app --port 8765 --reload

# Terminal 2 — UI
cd /Users/wissem/local_ai_stack/ui && npm run dev
```

Ouvrir `http://localhost:1420` dans un navigateur et vérifier :
- [ ] Le layout s'affiche (ActivityBar + Tabs + StatusBar)
- [ ] Le Tab Chat est visible avec le placeholder
- [ ] Les 4 icônes de l'Activity Bar sont cliquables
- [ ] La StatusBar affiche "Connexion..."
- [ ] Aucune erreur dans la console navigateur

- [ ] **Step 10.3 : Commit final**

```bash
cd /Users/wissem/local_ai_stack
git add ui/
git commit -m "chore: Plan 3 complete — Tauri + React UI fully built"
```

---

*Plan 3 terminé — UI Tauri + React complète avec tous les composants. Passer à Plan 4 : GitHub Integration + Mode Projet.*
