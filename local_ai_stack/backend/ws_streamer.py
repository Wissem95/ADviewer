# backend/ws_streamer.py
"""WebSocket Streamer — diffuse les events vers l'UI React.

Gère les connexions multiples, le broadcast, et les events spécifiques
(routing, agent_step) pour faciliter l'utilisation depuis orchestrator/agent_loop.

Correction C13 : emit_step() et emit_routing(decision) ajoutées.
"""
import time
import uuid
from typing import TYPE_CHECKING

from backend.models import WSEvent

if TYPE_CHECKING:
    from backend.models import RoutingDecision


class WSStreamer:
    """Gestionnaire des connexions WebSocket + broadcast d'events."""

    def __init__(self) -> None:
        self._connections: dict[str, object] = {}  # session_id → websocket

    async def connect(self, websocket) -> str:
        """Accepte une connexion et retourne un session_id."""
        await websocket.accept()
        session_id = str(uuid.uuid4())[:8]
        self._connections[session_id] = websocket
        return session_id

    def disconnect(self, session_id: str) -> None:
        self._connections.pop(session_id, None)

    async def broadcast(self, event: WSEvent) -> None:
        """Envoie l'event à toutes les connexions actives.

        Les erreurs d'envoi (client déconnecté) sont silencieuses.
        """
        payload = event.model_dump_json()
        dead: list[str] = []
        for sid, ws in list(self._connections.items()):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(sid)
        for sid in dead:
            self._connections.pop(sid, None)

    async def send_to(self, session_id: str, event: WSEvent) -> None:
        """Envoie l'event à une connexion spécifique."""
        ws = self._connections.get(session_id)
        if ws is None:
            return
        try:
            await ws.send_text(event.model_dump_json())
        except Exception:
            self._connections.pop(session_id, None)

    # ── Emitters haut niveau ─────────────────────────────────────────────────

    async def emit_step(self, step: str, llm: str, attempt: int = 1) -> None:
        """Émet l'étape courante de l'agent loop (PLAN, VERIFY, EXECUTE, CHECK, CONFIRM).

        Utilisé par AgentLoop et ProjectMode.
        """
        await self.broadcast(WSEvent(
            type="agent_step",
            data={"step": step, "llm": llm, "attempt": attempt},
            session_id="system",
        ))

    async def emit_routing(self, decision: "RoutingDecision") -> None:
        """Émet la décision de routage vers l'UI.

        Correction C13+I2 : prend un RoutingDecision complet.
        """
        await self.broadcast(WSEvent(
            type="routing_decision",
            data={
                "id": str(id(decision)),
                "timestamp": int(time.time() * 1000),
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

    async def emit_agent_action(self, llm: str, action: str, detail: str = "") -> None:
        """Émet une action d'agent générique."""
        await self.broadcast(WSEvent(
            type="agent_action",
            data={"llm": llm, "action": action, "detail": detail},
            session_id="system",
        ))

    async def emit_error(self, message: str) -> None:
        """Émet une erreur vers l'UI."""
        await self.broadcast(WSEvent(
            type="error",
            data={"message": message},
            session_id="system",
        ))
