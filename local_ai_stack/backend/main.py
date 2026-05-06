"""FastAPI application — point d'entrée du backend LocalCoder IDE.

Démarre via uvicorn (mode dev) ou comme subprocess de Tauri (mode prod).
Exposition sur 127.0.0.1:8765 uniquement (sécurité locale).
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

import psutil
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from backend.models import LLMRole, LLMConfig, RoutingDecision, WSEvent
from backend.llm_manager import LLMManager, FALLBACK_CHAINS
from backend.router_engine import RouterEngine
from backend.file_lock import FileLock
from backend.task_queue import LLMTaskQueue
from backend.ws_streamer import WSStreamer
from backend.memory import LongTermMemory
from backend.orchestrator import Orchestrator, OrchestratorRequest


# ── Configuration des 5 LLMs ────────────────────────────────────────────────

DEFAULT_LLMS = [
    LLMConfig(id="minimax/minimax-m2.5", name="MiniMax M2.5", role=LLMRole.CODING, rpm=200),
    LLMConfig(id="gemini/gemini-2.5-pro", name="Gemini Pro", role=LLMRole.ANALYSIS, rpm=60),
    LLMConfig(id="gemini/gemini-2.5-flash", name="Gemini Flash", role=LLMRole.ROUTING, rpm=1000),
    LLMConfig(id="deepseek/deepseek-r1", name="DeepSeek R1", role=LLMRole.ARCHITECTURE, rpm=50),
    LLMConfig(id="mistral/codestral-2", name="Codestral 2", role=LLMRole.TESTING, rpm=100),
]


# ── Factory ──────────────────────────────────────────────────────────────────

async def _broadcast_sys_stats(ws_streamer: WSStreamer) -> None:
    """Émet les stats système toutes les 5s en broadcast WebSocket."""
    while True:
        try:
            await asyncio.sleep(5)
            stats = {
                "cpuPercent": psutil.cpu_percent(interval=None),
                "ramMB": int(psutil.virtual_memory().used / 1024 / 1024),
            }
            await ws_streamer.broadcast(
                WSEvent(type="sys_stats", data=stats, session_id="system")
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # Ne pas crasher le background task sur erreur psutil transitoire.
            pass


def create_app(db_path: str = "localcoder.db") -> FastAPI:
    """Factory pattern pour créer l'app FastAPI.

    Args:
        db_path: Chemin vers la DB SQLite. Changeable pour les tests.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Initialise LongTermMemory + RouterEngine + Orchestrator au démarrage."""
        # Init DB LongTermMemory (4 tables)
        long_memory = LongTermMemory(db_path=db_path)
        await long_memory.init()

        # Init RouterEngine DB (routing_feedback table)
        await app.state.router_engine.init_db()

        # Créer l'orchestrateur (partage les mêmes composants)
        app.state.orchestrator = Orchestrator(
            llm_manager=app.state.llm_manager,
            ws_streamer=app.state.ws_streamer,
            file_lock=app.state.file_lock,
            task_queue=app.state.task_queue,
            db_path=db_path,
        )
        # Forcer les mêmes instances de mémoire (pour cohérence)
        app.state.orchestrator.long_memory = long_memory

        # #IMP5 — psutil.cpu_percent(interval=None) retourne 0.0 au 1er
        # appel car il calcule la différence depuis le dernier. On "amorce"
        # le compteur ici pour que le 1er broadcast soit significatif.
        psutil.cpu_percent(interval=None)

        # Background task : broadcast CPU/RAM toutes les 5s (Plan 4 Task 6).
        sys_task = asyncio.create_task(
            _broadcast_sys_stats(app.state.ws_streamer)
        )

        yield

        # Shutdown : annule le broadcast_sys_stats proprement.
        sys_task.cancel()
        try:
            await sys_task
        except (asyncio.CancelledError, Exception):
            pass

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

    @app.post("/chat")
    async def chat(request: dict):
        """Endpoint chat — passe par l'orchestrateur (routing + execution)."""
        orch: Orchestrator = app.state.orchestrator
        req = OrchestratorRequest(
            user_id=request.get("user_id", "default"),
            prompt=request["prompt"],
            file_count=request.get("file_count", 0),
            mention=request.get("mention"),
        )
        response = await orch.handle(req)
        return {
            "content": response.content,
            "llm": response.llm_used,
            "role": response.role.value,
            "duration_ms": int(response.duration * 1000),
            "tokens": response.tokens,
            "reason": response.routing_reason,
        }

    @app.post("/ci-webhook")
    async def ci_webhook(request: Request):
        """Webhook GitHub Actions check_run/check_suite.

        Sécurité :
        - #CRIT4 : fail-secure. Si ``GITHUB_WEBHOOK_SECRET`` est vide, on
          refuse par défaut sauf si ``LOCALCODER_ALLOW_UNSIGNED_WEBHOOK=1``
          est explicitement positionné (dev/test local).
        - #CRIT3 : signature invalide ou secret manquant → 401 (non-2xx),
          ce qui permet à GitHub de relivrer le webhook et de remonter
          l'échec côté repo Settings > Webhooks.

        Config côté repo : Settings → Webhooks → POST /ci-webhook,
        content type application/json, events check_run + check_suite.
        """
        import hashlib
        import hmac
        import os

        raw_body = await request.body()
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET") or ""
        allow_unsigned = (
            os.environ.get("LOCALCODER_ALLOW_UNSIGNED_WEBHOOK", "").lower()
            in ("1", "true", "yes")
        )

        if secret:
            signature = request.headers.get("X-Hub-Signature-256", "")
            expected = (
                "sha256="
                + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
            )
            if not hmac.compare_digest(signature, expected):
                logger.warning(
                    "ci_webhook rejeté : signature invalide (header=%s...)",
                    signature[:20],
                )
                return JSONResponse(
                    status_code=401,
                    content={"ok": False, "error": "invalid signature"},
                )
        elif not allow_unsigned:
            # #CRIT4 fail-secure : pas de secret configuré, pas d'override.
            logger.warning(
                "ci_webhook rejeté : ni GITHUB_WEBHOOK_SECRET ni "
                "LOCALCODER_ALLOW_UNSIGNED_WEBHOOK configurés."
            )
            return JSONResponse(
                status_code=401,
                content={
                    "ok": False,
                    "error": (
                        "webhook unsigned refusé. Définir GITHUB_WEBHOOK_SECRET, "
                        "ou LOCALCODER_ALLOW_UNSIGNED_WEBHOOK=1 pour dev local."
                    ),
                },
            )

        try:
            payload = json.loads(raw_body.decode() or "{}")
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "invalid json"},
            )

        event = request.headers.get("X-GitHub-Event", "unknown")
        conclusion = (
            payload.get("check_run", {}).get("conclusion")
            or payload.get("check_suite", {}).get("conclusion")
        )
        pr_numbers = [
            p.get("number")
            for p in payload.get("check_run", {}).get("pull_requests", [])
        ] or [
            p.get("number")
            for p in payload.get("check_suite", {}).get("pull_requests", [])
        ]

        logger.info(
            "ci_webhook event=%s conclusion=%s pr=%s",
            event,
            conclusion,
            pr_numbers,
        )

        streamer: WSStreamer = app.state.ws_streamer
        for pr_number in pr_numbers:
            await streamer.broadcast(
                WSEvent(
                    type="ci_status",
                    data={
                        "ticketId": f"PR-{pr_number}",
                        "status": (
                            "success"
                            if conclusion == "success"
                            else "failure"
                            if conclusion in ("failure", "cancelled", "timed_out")
                            else "running"
                        ),
                        "url": payload.get("check_run", {}).get("html_url", ""),
                    },
                    session_id="system",
                )
            )

        return {
            "ok": True,
            "event": event,
            "conclusion": conclusion,
            "pr_numbers": pr_numbers,
        }

    @app.post("/project/start")
    async def project_start(request: dict):
        """Démarre le Mode Projet complet (CdC + Sprints + GitHub).

        Body: {description, github_token, repo_name}
        Retourne la roadmap générée.
        """
        orch: Orchestrator = app.state.orchestrator
        roadmap = await orch.run_project_mode(
            description=request["description"],
            github_token=request["github_token"],
            repo_name=request["repo_name"],
        )
        return {
            "project": roadmap.project,
            "session_id": roadmap.session_id,
            "tasks_count": len(roadmap.tasks),
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status,
                    "sprint": t.sprint,
                    "github_issue": t.github_issue,
                }
                for t in roadmap.tasks
            ],
        }

    @app.get("/project/status")
    async def project_status():
        """Retourne le statut de la roadmap active (Plan 4 l'utilisera pleinement)."""
        orch: Orchestrator = app.state.orchestrator
        if not orch.roadmap:
            return {"active": False}
        return {
            "active": True,
            "project": orch.roadmap.project,
            "tasks": [
                {"id": t.id, "title": t.title, "status": t.status, "sprint": t.sprint}
                for t in orch.roadmap.tasks
            ],
        }

    @app.post("/project/feedback")
    async def project_feedback(request: dict):
        """Correction de routage par l'utilisateur.
        Body: {"prompt": "...", "routed_to": "...", "corrected_to": "..."}
        """
        orch: Orchestrator = app.state.orchestrator
        await orch.long_memory.save_routing_feedback(
            prompt=request["prompt"],
            routed_to=request.get("routed_to", "unknown"),
            corrected_to=request["corrected_to"],
        )
        return {"saved": True}

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

    @app.get("/llms/health")
    async def llms_health():
        """Health check des 5 LLMs en parallèle.

        Retourne {llm_id: {ok, latency_ms, error}} pour chaque LLM configuré.
        Ne lève jamais : les erreurs sont remontées par LLM dans ``error``.
        """
        manager: LLMManager = app.state.llm_manager
        llm_ids = [c.id for c in app.state.llm_configs]
        results = await asyncio.gather(
            *(manager.health_check(llm_id) for llm_id in llm_ids)
        )
        return dict(zip(llm_ids, results))

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
        """WebSocket principal — temps réel entre backend et UI.

        Types de messages entrants (correction I8) :
        - "chat" : {prompt, mention?} → route via orchestrator → émet chat_response
        - "request_sys_stats" : accusé réception (Plan 4 émettra périodiquement)
        - "request_file_tree" : stub vide pour l'instant
        - "request_git_diff" : stub vide pour l'instant
        """
        streamer: WSStreamer = app.state.ws_streamer
        session_id = await streamer.connect(websocket)
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                    msg_type = msg.get("type")
                    data = msg.get("data", {})
                except (json.JSONDecodeError, TypeError):
                    continue

                if msg_type == "chat":
                    orch: Orchestrator = app.state.orchestrator
                    req = OrchestratorRequest(
                        user_id=session_id,
                        prompt=data.get("prompt", ""),
                        file_count=data.get("file_count", 0),
                        mention=data.get("mention"),
                    )
                    try:
                        response = await orch.handle(req)
                        await streamer.send_to(session_id, WSEvent(
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
                    except Exception as e:
                        await streamer.send_to(session_id, WSEvent(
                            type="error",
                            data={"message": str(e)[:300]},
                            session_id=session_id,
                        ))
                elif msg_type == "pipeline_stop":
                    # Plan 5B Task 6 : Stop button / Cmd+. côté UI.
                    # Si une task pipeline est en cours pour cette session, on
                    # la cancel ; sinon on log juste l'event.
                    pipelines = getattr(app.state, "pipeline_tasks", {})
                    task = pipelines.get(session_id)
                    if task is not None and not task.done():
                        task.cancel()
                elif msg_type == "request_file_tree":
                    # Stub — Plan 4 étendra avec un vrai scanner
                    await streamer.send_to(session_id, WSEvent(
                        type="file_tree", data=[], session_id=session_id,
                    ))
                elif msg_type == "request_git_diff":
                    await streamer.send_to(session_id, WSEvent(
                        type="git_diff_files", data=[], session_id=session_id,
                    ))
                # request_sys_stats : Plan 4 ajoutera le broadcast automatique
        except WebSocketDisconnect:
            streamer.disconnect(session_id)

    return app


# ── Exécution directe (dev mode) ─────────────────────────────────────────────

# NE PAS inclure de if __name__ == "__main__" ici.
# Utiliser : uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload

app = create_app()
