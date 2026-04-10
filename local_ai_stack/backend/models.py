"""Modèles Pydantic partagés entre tous les modules backend.

Définir ces modèles dans un fichier séparé évite les imports circulaires
entre llm_manager, router_engine, agent_loop, orchestrator, etc.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class LLMRole(str, Enum):
    """Rôle fonctionnel d'un LLM dans le système."""
    CODING = "coding"
    ARCHITECTURE = "architecture"
    ANALYSIS = "analysis"
    TESTING = "testing"
    ROUTING = "routing"


class MessageType(str, Enum):
    """Type de message inter-LLMs (via orchestrateur)."""
    DECISION = "decision"
    QUESTION = "question"
    RESULT = "result"
    WARNING = "warning"
    CONTEXT = "context"


class TaskStatus(str, Enum):
    """État d'une tâche dans la roadmap."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"


# ── Configuration LLM ────────────────────────────────────────────────────────

class LLMConfig(BaseModel):
    """Configuration d'un LLM — chargée depuis config.yml ou défaut."""
    id: str                          # "minimax/minimax-m2.5"
    name: str                        # "MiniMax M2.5"
    role: LLMRole
    enabled: bool = True
    rpm: int = 60                    # Requests per minute (rate limit)


# ── Messages ──────────────────────────────────────────────────────────────────

class LLMMessage(BaseModel):
    """Message inter-LLMs déposé auprès de l'orchestrateur."""
    session_id: str
    from_llm: str
    to_llm: str                      # LLM cible ou "all"
    type: MessageType
    content: str
    replied: bool = False
    created_at: datetime = Field(default_factory=datetime.now)


# ── Routing ──────────────────────────────────────────────────────────────────

class RoutingDecision(BaseModel):
    """Décision de routage du RouterEngine pour un prompt donné."""
    prompt: str
    score: int                       # 1-10 (complexité)
    llm: str                         # Identifiant LiteLLM du modèle choisi
    role: LLMRole
    mode: str                        # "simple" | "medium" | "multi_agent"
    reason: str                      # Explication humaine


# ── Agent actions ─────────────────────────────────────────────────────────────

class AgentAction(BaseModel):
    """Une action d'un LLM dans l'agent loop (PLAN, VERIFY, etc.)."""
    llm: str
    step: str                        # "PLAN" | "VERIFY" | "EXECUTE" | "CHECK" | "CONFIRM"
    detail: str = ""
    ts: datetime = Field(default_factory=datetime.now)


# ── WebSocket events ─────────────────────────────────────────────────────────

class WSEvent(BaseModel):
    """Event WebSocket générique émis vers l'UI.

    Le champ `type` détermine le handler côté frontend.
    Le champ `data` peut être n'importe quel JSON-sérialisable.
    """
    type: str
    data: Any
    session_id: str = "system"       # "system" pour les broadcasts globaux
    ts: datetime = Field(default_factory=datetime.now)
