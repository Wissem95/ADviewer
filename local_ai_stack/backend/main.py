"""FastAPI application — point d'entrée du backend LocalCoder IDE.

Démarre via uvicorn (mode dev) ou comme subprocess de Tauri (mode prod).
Exposition sur 127.0.0.1:8765 uniquement (sécurité locale).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.models import LLMRole, LLMConfig, RoutingDecision
from backend.llm_manager import LLMManager, FALLBACK_CHAINS
from backend.router_engine import RouterEngine
from backend.file_lock import FileLock
from backend.task_queue import LLMTaskQueue
from backend.ws_streamer import WSStreamer


# ── Configuration des 5 LLMs ────────────────────────────────────────────────

DEFAULT_LLMS = [
    LLMConfig(id="minimax/minimax-m2.5", name="MiniMax M2.5", role=LLMRole.CODING, rpm=200),
    LLMConfig(id="gemini/gemini-2.5-pro", name="Gemini Pro", role=LLMRole.ANALYSIS, rpm=60),
    LLMConfig(id="gemini/gemini-2.5-flash", name="Gemini Flash", role=LLMRole.ROUTING, rpm=1000),
    LLMConfig(id="deepseek/deepseek-r1", name="DeepSeek R1", role=LLMRole.ARCHITECTURE, rpm=50),
    LLMConfig(id="mistral/codestral-2", name="Codestral 2", role=LLMRole.TESTING, rpm=100),
]


# ── Factory ──────────────────────────────────────────────────────────────────

def create_app(db_path: str = "localcoder.db") -> FastAPI:
    """Factory pattern pour créer l'app FastAPI.

    Args:
        db_path: Chemin vers la DB SQLite. Changeable pour les tests.
    """
    # ── Lifespan ─────────────────────────────────────────────────────────────

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Initialise les composants au démarrage, les nettoie à l'arrêt."""
        # Init router DB
        await app.state.router_engine.init_db()
        yield
        # Shutdown — rien à faire (SQLite se ferme proprement)

    app = FastAPI(
        title="LocalCoder IDE Backend",
        version="2.0.0",
        lifespan=lifespan,
    )

    # ── Injection des composants ─────────────────────────────────────────────

    app.state.llm_manager = LLMManager()
    app.state.router_engine = RouterEngine(db_path=db_path)
    app.state.file_lock = FileLock()
    app.state.task_queue = LLMTaskQueue()
    app.state.ws_streamer = WSStreamer()
    app.state.llm_configs = list(DEFAULT_LLMS)

    # ── Routes REST ──────────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        """Health check — utilisé par Tauri pour vérifier que le backend est prêt."""
        return {
            "status": "ok",
            "llms": [
                {"id": c.id, "name": c.name, "role": c.role.value, "enabled": c.enabled}
                for c in app.state.llm_configs
            ],
        }

    @app.post("/route")
    async def route(request: dict):
        """Analyse un prompt et retourne la décision de routage (sans exécution)."""
        router: RouterEngine = app.state.router_engine
        decision = await router.route(
            prompt=request["prompt"],
            file_count=request.get("file_count", 0),
            mention=request.get("mention"),
        )
        return {
            "llm": decision.llm,
            "role": decision.role.value,
            "mode": decision.mode,
            "score": decision.score,
            "reason": decision.reason,
        }

    @app.get("/llms")
    async def llms_list():
        """Liste les 5 LLMs avec leur statut actuel."""
        manager: LLMManager = app.state.llm_manager
        return [
            {
                "id": c.id,
                "name": c.name,
                "role": c.role.value,
                "enabled": not manager.is_disabled(c.id),
                "rpm": c.rpm,
            }
            for c in app.state.llm_configs
        ]

    @app.post("/llms/{llm_id:path}/disable")
    async def disable_llm(llm_id: str):
        """Désactive un LLM (ne sera plus utilisé par le routeur)."""
        app.state.llm_manager.disable(llm_id)
        return {"llm": llm_id, "status": "disabled"}

    @app.post("/llms/{llm_id:path}/enable")
    async def enable_llm(llm_id: str):
        """Réactive un LLM."""
        app.state.llm_manager.enable(llm_id)
        return {"llm": llm_id, "status": "enabled"}

    # ── WebSocket ────────────────────────────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket principal — temps réel entre backend et UI."""
        streamer: WSStreamer = app.state.ws_streamer
        session_id = await streamer.connect(websocket)
        try:
            while True:
                raw = await websocket.receive_text()
                # Le dispatching des messages WS sera étendu dans Plan 2 (correction I8)
        except WebSocketDisconnect:
            streamer.disconnect(session_id)

    return app


# ── Exécution directe (dev mode) ─────────────────────────────────────────────

# NE PAS inclure de if __name__ == "__main__" ici.
# Utiliser : uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload
# Ou : python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765

# Variable au niveau module pour uvicorn
app = create_app()
