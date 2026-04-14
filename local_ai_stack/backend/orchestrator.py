"""Orchestrateur central — seul point d'entrée pour toute tâche.

Règle fondamentale :
- Les LLMs ne se parlent JAMAIS directement.
- Ils déposent leurs demandes à l'orchestrateur.
- L'orchestrateur dispatch, valide, écrit les fichiers, met à jour la roadmap.

Correction C1 : await self.router.route(...) — RouterEngine.route est async.
"""
import time
from dataclasses import dataclass
from typing import Optional

from backend.models import LLMRole
from backend.llm_manager import LLMManager
from backend.router_engine import RouterEngine
from backend.agent_loop import AgentLoop
from backend.memory import ShortTermMemory, LongTermMemory
from backend.roadmap import ProjectRoadmap
from backend.context_builder import build_context_for
from backend.ws_streamer import WSStreamer
from backend.file_lock import FileLock
from backend.task_queue import LLMTaskQueue


@dataclass
class OrchestratorRequest:
    """Requête entrante depuis l'UI (WebSocket ou REST)."""
    user_id: str
    prompt: str
    file_count: int = 0
    mention: Optional[str] = None  # "minimax" | "gemini" | "deepseek" | "codestral"


@dataclass
class OrchestratorResponse:
    """Réponse finale retournée à l'UI."""
    content: str
    llm_used: str
    role: LLMRole
    duration: float
    tokens: int
    routing_reason: str


class Orchestrator:
    """Chef d'orchestre. Une seule instance par processus FastAPI.

    Injecté dans main.py via le lifespan FastAPI.
    Les LLMs ne connaissent pas l'orchestrateur — ils reçoivent des prompts
    et retournent des strings. C'est l'orchestrateur qui interprète et agit.
    """

    def __init__(
        self,
        llm_manager: LLMManager,
        ws_streamer: WSStreamer,
        file_lock: FileLock,
        task_queue: LLMTaskQueue,
        db_path: str = "localcoder.db",
    ):
        self.llm = llm_manager
        self.ws = ws_streamer
        self.file_lock = file_lock
        self.task_queue = task_queue
        self.router = RouterEngine(db_path=db_path)
        self.short_memory = ShortTermMemory()
        self.long_memory = LongTermMemory(db_path=db_path)
        self.roadmap: Optional[ProjectRoadmap] = None

    async def handle(self, request: OrchestratorRequest) -> OrchestratorResponse:
        """Point d'entrée principal pour toute requête utilisateur.

        Pipeline :
        1. Routing → choix du LLM
        2. UI notification (event WebSocket)
        3. Construction du contexte ciblé (~2-3K tokens)
        4. Exécution via AgentLoop dans la TaskQueue
        5. Persistance de la décision en mémoire longue
        6. Retour de la réponse à l'UI
        """
        start = time.time()

        # 1. Routing — correction C1 : await
        decision = await self.router.route(
            prompt=request.prompt,
            file_count=request.file_count,
            mention=request.mention,
        )

        # 2. UI notification
        await self.ws.emit_routing(decision)

        # 3. Contexte ciblé
        context = build_context_for(
            llm=decision.llm,
            task=request.prompt,
            roadmap=self.roadmap,
        )

        # 4. AgentLoop dans la TaskQueue (1 tâche à la fois par LLM)
        agent_loop = AgentLoop(
            llm_manager=self.llm,
            file_lock=self.file_lock,
            ws_streamer=self.ws,
            decision=decision,
            context=context,
        )
        result = await self.task_queue.submit(
            llm=decision.llm,
            coro=agent_loop.run(request.prompt),
        )

        # 5. Mémoire longue + courte
        await self.long_memory.save_decision(
            session_id=self.short_memory.session_id,
            llm=decision.llm,
            dtype="routing",
            content=str(result.content)[:500],
            rationale=decision.reason,
        )
        self.short_memory.record_action(
            llm=decision.llm,
            action="handle",
            detail=request.prompt[:100],
        )

        return OrchestratorResponse(
            content=result.content,
            llm_used=decision.llm,
            role=decision.role,
            duration=time.time() - start,
            tokens=result.tokens,
            routing_reason=decision.reason,
        )

    # ── Mode projet ──────────────────────────────────────────────────────────

    async def set_roadmap(self, roadmap: ProjectRoadmap) -> None:
        """Active le mode projet avec une roadmap (Plan 4 utilisera ça)."""
        self.roadmap = roadmap

    async def clear_roadmap(self) -> None:
        """Désactive le mode projet (retour au mode conversation)."""
        self.roadmap = None
