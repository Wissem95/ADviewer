# Corrections critiques avant implémentation — Review Opus 4.6

> Ces corrections doivent être appliquées pendant l'implémentation de chaque plan.
> L'exécuteur (subagent) doit lire ce fichier avant chaque tâche.

---

## PLAN 1 — Backend Foundation

### C13 : Ajouter `emit_step()` et fixer `emit_routing()` dans WSStreamer

Dans `backend/ws_streamer.py`, ajouter ces méthodes APRÈS `emit_agent_action()` :

```python
async def emit_step(self, step: str, llm: str, attempt: int = 1) -> None:
    """Émet l'étape courante de l'agent loop (PLAN, VERIFY, EXECUTE, CHECK, CONFIRM)."""
    await self.broadcast(WSEvent(
        type="agent_step",
        data={"step": step, "llm": llm, "attempt": attempt},
        session_id="system",
    ))

async def emit_routing(self, decision: "RoutingDecision") -> None:
    """Émet la décision de routage vers l'UI."""
    await self.broadcast(WSEvent(
        type="routing_decision",
        data={
            "id": str(id(decision)),
            "timestamp": int(__import__("time").time() * 1000),
            "prompt": decision.prompt[:200],
            "llm": decision.llm,
            "role": decision.role.value,
            "mode": decision.mode,
            "reason": decision.reason,
            "durationMs": 0,
            "tokens": 0,
        },
        session_id="system",
    ))
```

### C14 : Ajouter `submit()` dans LLMTaskQueue

Dans `backend/task_queue.py`, ajouter après `pending_count()` :

```python
async def submit(self, llm: str, coro) -> Any:
    """
    Soumet une coroutine à la queue du LLM et attend son résultat.
    Un seul job par LLM à la fois. Retourne le résultat directement.
    """
    import asyncio
    future: asyncio.Future = asyncio.get_event_loop().create_future()
    
    async def _wrapper():
        try:
            result = await coro
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
    
    await self.enqueue(llm, _wrapper)
    return await future
```

Ajouter `from typing import Any` en haut du fichier.

### C2 : Mettre à jour `RouterEngine.route()` signature

Remplacer dans `backend/router_engine.py` :
```python
async def route(self, prompt: str) -> RoutingDecision:
```
Par :
```python
async def route(
    self, 
    prompt: str, 
    file_count: int = 0,
    mention: str | None = None,
) -> RoutingDecision:
```

Et au début de `route()`, ajouter la logique mention avant la complexité :
```python
# Override manuel — @mention préfixé dans le prompt ou passé explicitement
if mention:
    mention_map = {
        "minimax": ("minimax/minimax-m2.5", LLMRole.CODING),
        "gemini": ("gemini/gemini-2.5-pro", LLMRole.ANALYSIS),
        "deepseek": ("deepseek/deepseek-r1", LLMRole.ARCHITECTURE),
        "codestral": ("mistral/codestral-2", LLMRole.TESTING),
    }
    if mention in mention_map:
        llm, role = mention_map[mention]
        return RoutingDecision(
            prompt=prompt, score=5, llm=llm, role=role,
            mode="medium", reason=f"Override manuel @{mention}",
        )
```

### C4 : Fixer la logique des seuils dans RouterEngine

Remplacer la logique de conversion score→mode par :

```python
# Utiliser le LEVEL de ComplexityResult, pas seulement le score
result = analyze_task_complexity(prompt, file_count)

# Mots-clés projet → multi_agent forcé
project_keywords = ["crée une app", "je veux construire", "nouveau projet", "génère le cdc"]
if any(kw in prompt.lower() for kw in project_keywords):
    result.score = 9
    result.level = "complex"
    result.reason = "Mode Projet détecté"

# Feedback routing — override si correction connue
corrected = await self._get_feedback_correction(prompt)
if corrected:
    # Retourner directement avec le LLM corrigé
    ...

# Décision finale basée sur level (plus robuste que le score brut)
if result.level == "simple" or result.score <= 4:
    return RoutingDecision(prompt=prompt, score=result.score, llm=ROLE_MODELS[LLMRole.CODING],
                           role=LLMRole.CODING, mode="simple", reason=result.reason)
elif result.level == "medium" or result.score <= 7:
    return RoutingDecision(prompt=prompt, score=result.score, llm=ROLE_MODELS[LLMRole.CODING],
                           role=LLMRole.CODING, mode="medium", reason=result.reason)
else:
    return RoutingDecision(prompt=prompt, score=result.score, llm=ROLE_MODELS[LLMRole.ARCHITECTURE],
                           role=LLMRole.ARCHITECTURE, mode="multi_agent", reason=result.reason)
```

### C7 : Ajouter `Optional` dans file_lock.py

Ajouter en haut de `backend/file_lock.py` :
```python
from typing import Optional
```

### I4 : Unifier l'ID Codestral partout

Utiliser **exclusivement** `mistral/codestral-2` dans :
- `backend/llm_manager.py` : `TESTING_FALLBACK = ["mistral/codestral-2", ...]`
- `backend/models.py` : constante si présente
- `ui/src/stores/llmStore.ts` : `id: "mistral/codestral-2"`
- `ui/src/components/tabs/ChatTab/MessageBubble.tsx` : LLM_COLORS et LLM_ICONS

### I15 : Bind sur 127.0.0.1 partout

Dans `backend/main.py` et `ui/src-tauri/src/main.rs` :
```python
# Python
uvicorn.run(app, host="127.0.0.1", port=8765)
```
```rust
// Rust — dans wait_for_backend et spawn_backend
Command::new(venv_python)
    .args(["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8765"])
```

---

## PLAN 2 — Intelligence Layer

### C1 : `await self.router.route()`

Dans `backend/orchestrator.py`, remplacer :
```python
decision = self.router.route(
    prompt=request.prompt,
    file_count=request.file_count,
    mention=request.mention,
)
```
Par :
```python
decision = await self.router.route(
    prompt=request.prompt,
    file_count=request.file_count,
    mention=request.mention,
)
```

### C8 : Fix lifespan dans main.py

Le lifespan DOIT être dans une closure pour accéder à app.state correctement.
Dans `backend/main.py`, l'ajout du lifespan doit se faire DANS `create_app()` :

```python
def create_app(configs=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Initialisation BD
        db_path = "localcoder.db"
        mem = LongTermMemory(db_path=db_path)
        await mem.init()
        # RouterEngine DB
        await app.state.router_engine.init_db()
        # Orchestrateur
        app.state.orchestrator = Orchestrator(
            llm_manager=app.state.llm_manager,
            ws_streamer=app.state.ws_streamer,
            file_lock=app.state.file_lock,
            task_queue=app.state.task_queue,
            db_path=db_path,
        )
        # Stats système en background
        asyncio.create_task(_broadcast_sys_stats(app.state.ws_streamer))
        yield
    
    app = FastAPI(title="LocalCoder IDE Backend", lifespan=lifespan)
    # ... le reste de la définition des routes
```

### C17 : Fixer `broadcast(dict)` → `broadcast(WSEvent(...))`

Dans `backend/main.py` Task 6 (`_broadcast_sys_stats`), remplacer :
```python
await ws_streamer.broadcast({"type": "sys_stats", "data": stats})
```
Par :
```python
from backend.models import WSEvent
await ws_streamer.broadcast(WSEvent(
    type="sys_stats",
    data=stats,
    session_id="system",
))
```

### C3 : Unifier routing_feedback dans LongTermMemory

- Retirer la table `routing_feedback` de `RouterEngine.init_db()`
- Dans `RouterEngine.route()`, consulter `LongTermMemory.get_feedback_for()` avant le calcul
- Injecter `LongTermMemory` dans `RouterEngine.__init__` via `db_path` partagé

### C6 : Fix retry AgentLoop — libérer les locks avant retry

Dans `backend/agent_loop.py`, dans la boucle retry du step CHECK, avant de relancer `_step_execute` :

```python
# Libérer les locks avant retry pour pouvoir les réacquérir
for filepath in list(self._locked_files):
    await self.file_lock.release(filepath, self.decision.llm)
self._locked_files.clear()

content, files_modified, tokens = await self._step_execute(retry_task, plan)
```

### I14 : Charger les system prompts dans LLMManager

Ajouter dans `backend/llm_manager.py` :

```python
from pathlib import Path

def _load_system_prompt(role: LLMRole) -> str:
    """Charge le system prompt MD du rôle, ou retourne '' si absent."""
    role_to_file = {
        LLMRole.CODING: "system_minimax.md",
        LLMRole.ARCHITECTURE: "system_deepseek_r1.md",
        LLMRole.TESTING: "system_codestral.md",
        LLMRole.ANALYSIS: "system_gemini_pro.md",
        LLMRole.ROUTING: "system_gemini_flash.md",
    }
    filename = role_to_file.get(role, "")
    if not filename:
        return ""
    prompt_path = Path(__file__).parent / "prompts" / filename
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return ""
```

Et dans `call_with_fallback()`, si le premier message n'est pas un system message :
```python
system_prompt = _load_system_prompt(role)
if system_prompt and (not messages or messages[0].get("role") != "system"):
    messages = [{"role": "system", "content": system_prompt}] + messages
```

### I8 : Handler WebSocket pour le chat

Dans `backend/main.py`, dans le handler WebSocket `/ws`, ajouter le dispatch `type == "chat"` :

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_id = await app.state.ws_streamer.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                msg_type = msg.get("type")
                data = msg.get("data", {})

                if msg_type == "chat":
                    # Dispatcher vers l'orchestrateur
                    orch: Orchestrator = app.state.orchestrator
                    req = OrchestratorRequest(
                        user_id=session_id,
                        prompt=data.get("prompt", ""),
                        mention=data.get("mention"),
                    )
                    response = await orch.handle(req)
                    await app.state.ws_streamer.send_to(session_id, WSEvent(
                        type="chat_response",
                        data={
                            "content": response.content,
                            "llm": response.llm_used,
                            "llmName": response.llm_used.split("/")[-1],
                            "tokens": response.tokens,
                            "durationMs": int(response.duration * 1000),
                        },
                        session_id=session_id,
                    ))
                elif msg_type == "request_file_tree":
                    # TODO Plan 4+ — pour l'instant retourner vide
                    await app.state.ws_streamer.send_to(session_id, WSEvent(
                        type="file_tree", data=[], session_id=session_id
                    ))
                elif msg_type == "request_git_diff":
                    await app.state.ws_streamer.send_to(session_id, WSEvent(
                        type="git_diff_files", data=[], session_id=session_id
                    ))
                elif msg_type == "request_sys_stats":
                    pass  # émis automatiquement toutes les 5s
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        app.state.ws_streamer.disconnect(session_id)
```

---

## PLAN 3 — UI Tauri + React

### C15 : Fixer import xterm.js dynamique

Dans `ui/src/components/tabs/TerminalsTab/TerminalsTab.tsx`, remplacer le bloc d'import :

```tsx
// SUPPRIMER ces lignes (hors composant) :
// let Terminal: typeof import("@xterm/xterm").Terminal;
// let FitAddon: typeof import("@xterm/addon-fit").FitAddon;
// async function loadXterm() { ... }

// Dans le useEffect de LLMTerminal, remplacer par import dynamique inline :
useEffect(() => {
  if (!ref.current) return;
  let term: InstanceType<typeof import("@xterm/xterm").Terminal> | null = null;
  
  (async () => {
    const { Terminal } = await import("@xterm/xterm");
    const { FitAddon } = await import("@xterm/addon-fit");
    
    term = new Terminal({
      theme: { background: "#181825", foreground: "#cdd6f4", cursor: "#89b4fa" },
      fontSize: 12,
      fontFamily: "JetBrains Mono, Fira Code, monospace",
      rows: 20,
    });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(ref.current!);
    fitAddon.fit();
    termRef.current = term;
    term.writeln(`\x1b[36m[${llmName}]\x1b[0m Terminal prêt.`);
  })();
  
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
```

### C16 : WebSocket `send` avant OPEN → buffer

Dans `ui/src/ws.ts`, ajouter une queue des messages en attente :

```typescript
class WSClient {
  private pendingMessages: Array<{type: string; data: unknown}> = [];
  
  connect(): void {
    // ...
    this.socket.onopen = () => {
      console.log("[WS] Connected to backend");
      // Vider la queue des messages en attente
      while (this.pendingMessages.length > 0) {
        const msg = this.pendingMessages.shift()!;
        this.socket!.send(JSON.stringify(msg));
      }
      // ...
    };
  }

  send(type: string, data: unknown): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type, data }));
    } else {
      // Buffer le message pour envoi après connexion
      this.pendingMessages.push({ type, data });
    }
  }
}
```

### I9 : shadcn/ui CLI (pas npm install)

Dans Task 1, **remplacer** :
```bash
npm install @shadcn/ui lucide-react clsx
```
Par :
```bash
npm install lucide-react clsx
npx shadcn@latest init --yes
# Puis ajouter les composants si utilisés
```

### I7 : Event `health` depuis le backend ou `onopen`

Dans `ui/src/ws.ts`, modifier `onopen` pour émettre directement l'event health :

```typescript
this.socket.onopen = () => {
  console.log("[WS] Connected to backend");
  // Émettre l'event health localement (pas besoin que le backend l'envoie)
  const handlers = this.handlers.get("health") ?? [];
  handlers.forEach((h) => h({}));
  // ... vider pending queue ...
};
```

---

## PLAN 4 — GitHub + Mode Projet

### C9 : Fixer checkout dans execute_ticket

Dans `backend/project_mode.py`, dans `execute_ticket()`, ajouter au début :

```python
async def execute_ticket(self, task, roadmap, agent_loop_coro) -> bool:
    # Mémoriser la branche initiale avant tout
    initial_branch = self.git.get_current_branch()
    # ...
    
    # REMPLACER les deux occurrences de :
    # self.git.checkout(self.git.repo.heads[0].name)
    # Par :
    self.git.checkout(initial_branch)
```

### C10 : Fixer push redondant

Dans `backend/project_mode.py`, remplacer :
```python
self.git.push(branch="feature/" + branch_name.split("/", 1)[-1])
```
Par :
```python
self.git.push(branch=branch_name)
```

### I11 : Documenter retry CI Niveau 2 comme stub

Dans `backend/project_mode.py`, ajouter un commentaire clair au début de `execute_ticket()` :

```python
"""
IMPLÉMENTATION CI NIVEAU 2 — STUB MVP

La boucle `for ci_attempt` est prête structurellement mais le retry CI réel
n'est pas encore implémenté (nécessite un webhook GitHub → /ci-webhook).
Pour l'instant, on marque la tâche `done` optimiste après la création de la PR.
Le GitHub Actions valide de son côté.

Le retry complet sera implémenté en Phase 2 via un endpoint POST /ci-webhook
qui reçoit les notifications GitHub Actions et relance execute_ticket si CI rouge.
"""
```

---

## Contrats WebSocket (frontend ↔ backend)

Tous les events WS entre backend et frontend :

| Event (type) | Direction | Data shape |
|---|---|---|
| `chat` | UI→Backend | `{prompt, mention}` |
| `chat_response` | Backend→UI | `{content, llm, llmName, tokens, durationMs}` |
| `routing_decision` | Backend→UI | `{id, timestamp, prompt, llm, role, mode, reason, durationMs, tokens}` |
| `agent_step` | Backend→UI | `{step, llm, attempt}` |
| `task_complete` | Backend→UI | `{taskId}` |
| `llm_status` | Backend→UI | `{id, status, task?}` |
| `llm_tokens` | Backend→UI | `{id, tokens}` |
| `llm_latency` | Backend→UI | `{id, latencyMs}` |
| `roadmap_update` | Backend→UI | `Roadmap JSON` |
| `task_status` | Backend→UI | `{id, status}` |
| `git_status` | Backend→UI | `{branch, modifiedFiles}` |
| `sys_stats` | Backend→UI | `{cpuPercent, ramMB}` |
| `agent_log` | Backend→UI | `{llm, line}` |
| `ci_status` | Backend→UI | `{ticketId, status, url}` |
| `file_tree` | Backend→UI | `FileNode[]` |
| `git_diff_files` | Backend→UI | `GitFile[]` |
| `health` | local event | `{}` (émis depuis ws.onopen) |
| `request_file_tree` | UI→Backend | `{}` |
| `request_git_diff` | UI→Backend | `{}` |
| `request_sys_stats` | UI→Backend | `{}` |
| `git_commit` | UI→Backend | `{files, message}` |

---

*Ce fichier est la source de vérité pour les corrections. Toujours consulter avant d'implémenter.*
