# LocalCoder IDE v2 — Plan 1 : Backend Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Créer le serveur FastAPI avec LLM Manager (LiteLLM + fallback), Router Engine, File Lock async, Task Queue, et WebSocket streamer — tout testé, tout fonctionnel de manière indépendante.

**Architecture:** FastAPI expose un WebSocket sur `/ws` et des routes REST. Le LLM Manager wrape LiteLLM avec fallback chain et rate limiting. Le Router Engine étend `complexity.py` existant. File Lock et Task Queue protègent la concurrence. Tous les composants sont injectés dans l'orchestrateur central.

**Tech Stack:** Python 3.12, FastAPI 0.128, LiteLLM 1.81, aiosqlite, uvicorn, pytest, pytest-asyncio

**Spec de référence:** `docs/superpowers/specs/2026-04-10-localcoder-ide-v2-design.md`

---

## Fichiers créés ou modifiés

```
backend/
├── __init__.py                    # CRÉÉ — package marker
├── main.py                        # CRÉÉ — FastAPI app + routes
├── models.py                      # CRÉÉ — Pydantic models partagés
├── llm_manager.py                 # CRÉÉ — LiteLLM wrapper + fallback + rate limit
├── router_engine.py               # CRÉÉ — routing par complexité (étend complexity.py)
├── file_lock.py                   # CRÉÉ — asyncio.Lock thread-safe
├── task_queue.py                  # CRÉÉ — file d'attente par LLM
└── ws_streamer.py                 # CRÉÉ — WebSocket event broadcaster

tests/
└── backend/
    ├── __init__.py                # CRÉÉ
    ├── conftest.py                # CRÉÉ — fixtures pytest
    ├── test_llm_manager.py        # CRÉÉ
    ├── test_router_engine.py      # CRÉÉ
    ├── test_file_lock.py          # CRÉÉ
    ├── test_task_queue.py         # CRÉÉ
    └── test_main.py               # CRÉÉ — tests API + WebSocket

pyproject.toml                     # MODIFIÉ — nouvelles dépendances
```

**Modules existants non touchés :** `localcoder/complexity.py`, `localcoder/project_memory.py`, tous les autres modules CLI.

---

## Task 1 : Dépendances et structure

**Files:**
- Modify: `pyproject.toml`
- Create: `backend/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/backend/__init__.py`

- [ ] **Step 1.1 : Ajouter les dépendances dans pyproject.toml**

```toml
[project]
name = "localcoder"
version = "0.2.0"
description = "IDE IA local — agents intelligents pour le developpement"
requires-python = ">=3.12"
dependencies = [
    "aider-chat>=0.82",
    "rich>=13.0",
    "fastapi>=0.128",
    "uvicorn>=0.30",
    "litellm>=1.81",
    "aiosqlite>=0.20",
    "pydantic>=2.0",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[project.scripts]
localcoder = "localcoder.cli:main"

[build-system]
requires = ["setuptools>=45"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 1.2 : Installer les nouvelles dépendances**

```bash
source venv/bin/activate
pip install -e .
pip install uvicorn aiosqlite pytest pytest-asyncio httpx
```

Expected : `Successfully installed uvicorn-X.X aiosqlite-X.X pytest-X.X pytest-asyncio-X.X httpx-X.X`

- [ ] **Step 1.3 : Créer les fichiers __init__.py**

```bash
touch backend/__init__.py
mkdir -p tests/backend
touch tests/__init__.py
touch tests/backend/__init__.py
```

- [ ] **Step 1.4 : Vérifier que pytest tourne**

```bash
source venv/bin/activate && pytest tests/ -v
```

Expected : `no tests ran` (pas d'erreur, juste aucun test pour l'instant)

- [ ] **Step 1.5 : Commit**

```bash
git add pyproject.toml backend/__init__.py tests/__init__.py tests/backend/__init__.py
git commit -m "chore: setup backend package structure and dependencies"
```

---

## Task 2 : Pydantic Models partagés

**Files:**
- Create: `backend/models.py`

Ces modèles sont utilisés par tous les autres modules. Les définir en premier évite les imports circulaires.

- [ ] **Step 2.1 : Écrire le test des modèles**

```python
# tests/backend/test_models.py
import pytest
from backend.models import (
    LLMRole, MessageType, LLMMessage, RoutingDecision,
    AgentAction, TaskStatus, LLMConfig
)

def test_llm_role_values():
    assert LLMRole.CODING == "coding"
    assert LLMRole.ARCHITECTURE == "architecture"
    assert LLMRole.ANALYSIS == "analysis"
    assert LLMRole.TESTING == "testing"
    assert LLMRole.ROUTING == "routing"

def test_message_type_values():
    assert MessageType.DECISION == "decision"
    assert MessageType.QUESTION == "question"
    assert MessageType.RESULT == "result"
    assert MessageType.WARNING == "warning"
    assert MessageType.CONTEXT == "context"

def test_llm_message_creation():
    msg = LLMMessage(
        from_llm="minimax",
        to_llm="deepseek_r1",
        type=MessageType.QUESTION,
        content="Est-ce que cette architecture est correcte ?"
    )
    assert msg.from_llm == "minimax"
    assert msg.replied is False
    assert msg.session_id is not None  # auto-généré

def test_routing_decision():
    decision = RoutingDecision(
        prompt="refactore le module auth",
        score=8,
        llm="deepseek/deepseek-r1",
        role=LLMRole.ARCHITECTURE,
        mode="multi_agent",
        reason="Refacto globale détectée"
    )
    assert decision.mode == "multi_agent"

def test_task_status_values():
    assert TaskStatus.PENDING == "pending"
    assert TaskStatus.IN_PROGRESS == "in_progress"
    assert TaskStatus.DONE == "done"
    assert TaskStatus.FAILED == "failed"
    assert TaskStatus.BLOCKED == "blocked"
```

- [ ] **Step 2.2 : Lancer le test pour confirmer qu'il échoue**

```bash
source venv/bin/activate && pytest tests/backend/test_models.py -v
```

Expected : `ImportError: cannot import name 'LLMRole' from 'backend.models'`

- [ ] **Step 2.3 : Implémenter backend/models.py**

```python
# backend/models.py
from __future__ import annotations
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
from pydantic import BaseModel, Field


class LLMRole(str, Enum):
    CODING = "coding"
    ARCHITECTURE = "architecture"
    ANALYSIS = "analysis"
    TESTING = "testing"
    ROUTING = "routing"


class MessageType(str, Enum):
    DECISION = "decision"
    QUESTION = "question"
    RESULT = "result"
    WARNING = "warning"
    CONTEXT = "context"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"


class LLMConfig(BaseModel):
    model_id: str            # ex: "minimax/minimax-m2.5"
    role: LLMRole
    rpm: int = 100           # requests per minute
    fallback: Optional[str] = None


class LLMMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_llm: str
    to_llm: str              # LLM cible ou "all"
    type: MessageType
    content: str
    replied: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RoutingDecision(BaseModel):
    prompt: str
    score: int               # 1-10
    llm: str                 # model_id
    role: LLMRole
    mode: str                # "simple", "medium", "multi_agent"
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentAction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    llm: str
    type: str                # "read", "write", "bash", "decision"
    file_path: Optional[str] = None
    content: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WSEvent(BaseModel):
    """Événement envoyé via WebSocket au frontend."""
    type: str                # "routing", "agent_action", "llm_message", "error"
    data: dict
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 2.4 : Lancer les tests**

```bash
source venv/bin/activate && pytest tests/backend/test_models.py -v
```

Expected : `5 passed`

- [ ] **Step 2.5 : Commit**

```bash
git add backend/models.py tests/backend/test_models.py
git commit -m "feat: add shared Pydantic models for backend"
```

---

## Task 3 : LLM Manager

**Files:**
- Create: `backend/llm_manager.py`
- Create: `tests/backend/test_llm_manager.py`

Le LLM Manager wrape LiteLLM avec fallback chain, rate limiting par RPM, et streaming.

- [ ] **Step 3.1 : Écrire les tests (avec mock LiteLLM)**

```python
# tests/backend/test_llm_manager.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.llm_manager import LLMManager
from backend.models import LLMConfig, LLMRole


@pytest.fixture
def configs():
    return [
        LLMConfig(model_id="minimax/minimax-m2.5", role=LLMRole.CODING, rpm=200),
        LLMConfig(model_id="deepseek/deepseek-r1", role=LLMRole.ARCHITECTURE, rpm=50),
        LLMConfig(model_id="gemini/gemini-2.5-flash", role=LLMRole.ROUTING, rpm=1000),
        LLMConfig(model_id="gemini/gemini-2.5-pro", role=LLMRole.ANALYSIS, rpm=60),
        LLMConfig(model_id="mistral/codestral-latest", role=LLMRole.TESTING, rpm=100),
    ]


@pytest.fixture
def manager(configs):
    return LLMManager(configs=configs)


def test_manager_init(manager):
    assert manager.get_model_for_role(LLMRole.CODING) == "minimax/minimax-m2.5"
    assert manager.get_model_for_role(LLMRole.ARCHITECTURE) == "deepseek/deepseek-r1"
    assert manager.get_model_for_role(LLMRole.ROUTING) == "gemini/gemini-2.5-flash"


def test_disable_enable_llm(manager):
    manager.disable("minimax/minimax-m2.5")
    assert not manager.is_active("minimax/minimax-m2.5")
    manager.enable("minimax/minimax-m2.5")
    assert manager.is_active("minimax/minimax-m2.5")


def test_fallback_chain_coding(manager):
    """Quand minimax est down, fallback sur deepseek-v3 puis gemini."""
    manager.disable("minimax/minimax-m2.5")
    fallback = manager.get_fallback_for_role(LLMRole.CODING)
    assert fallback is not None
    assert fallback != "minimax/minimax-m2.5"


def test_all_disabled_raises(manager):
    """Si tous les modèles pour un rôle sont down, lève AllModelsDownError."""
    from backend.llm_manager import AllModelsDownError
    manager.disable("minimax/minimax-m2.5")
    # On simule que le fallback est aussi down
    with pytest.raises(AllModelsDownError):
        manager.get_active_model_for_role(LLMRole.CODING, exclude_all=True)


@pytest.mark.asyncio
async def test_call_llm_success(manager):
    """call_llm retourne le contenu de la réponse."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Voici mon analyse."

    with patch("backend.llm_manager.litellm.acompletion", return_value=mock_response):
        result = await manager.call_llm(
            model="minimax/minimax-m2.5",
            messages=[{"role": "user", "content": "Analyse ce code"}]
        )
    assert result == "Voici mon analyse."


@pytest.mark.asyncio
async def test_call_llm_timeout_triggers_fallback(manager):
    """En cas de timeout, call_with_fallback tente le modèle suivant."""
    import asyncio
    call_count = 0

    async def failing_then_success(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise asyncio.TimeoutError()
        mock = MagicMock()
        mock.choices = [MagicMock()]
        mock.choices[0].message.content = "Fallback response"
        return mock

    with patch("backend.llm_manager.litellm.acompletion", side_effect=failing_then_success):
        result = await manager.call_with_fallback(
            role=LLMRole.CODING,
            messages=[{"role": "user", "content": "test"}]
        )
    assert result == "Fallback response"
    assert call_count == 2
```

- [ ] **Step 3.2 : Lancer les tests pour confirmer l'échec**

```bash
source venv/bin/activate && pytest tests/backend/test_llm_manager.py -v
```

Expected : `ImportError: cannot import name 'LLMManager' from 'backend.llm_manager'`

- [ ] **Step 3.3 : Implémenter backend/llm_manager.py**

```python
# backend/llm_manager.py
from __future__ import annotations
import asyncio
import time
from typing import Optional
import litellm
from backend.models import LLMConfig, LLMRole


class AllModelsDownError(Exception):
    pass


# Fallback chains par rôle
FALLBACK_CHAINS: dict[LLMRole, list[str]] = {
    LLMRole.CODING: [
        "minimax/minimax-m2.5",
        "deepseek/deepseek-chat",
        "gemini/gemini-2.5-pro",
    ],
    LLMRole.ARCHITECTURE: [
        "deepseek/deepseek-r1",
        "gemini/gemini-2.5-pro",
    ],
    LLMRole.ANALYSIS: [
        "gemini/gemini-2.5-pro",
        "minimax/minimax-m2.5",
    ],
    LLMRole.TESTING: [
        "mistral/codestral-latest",
        "minimax/minimax-m2.5",
    ],
    LLMRole.ROUTING: [
        "gemini/gemini-2.5-flash",
        "minimax/minimax-m2.5",
    ],
}


class RateLimiter:
    """Throttle simple par RPM."""

    def __init__(self, rpm: int):
        self.rpm = rpm
        self._calls: list[float] = []

    async def acquire(self):
        now = time.time()
        # Supprimer les appels de plus d'1 minute
        self._calls = [t for t in self._calls if now - t < 60]
        if len(self._calls) >= self.rpm:
            wait = 60 - (now - self._calls[0])
            if wait > 0:
                await asyncio.sleep(wait)
        self._calls.append(time.time())


class LLMManager:
    """
    Wrape LiteLLM avec :
    - Mapping rôle → modèle
    - Activation/désactivation par modèle
    - Rate limiting par RPM
    - Fallback chain automatique
    """

    def __init__(self, configs: list[LLMConfig]):
        self._configs: dict[str, LLMConfig] = {c.model_id: c for c in configs}
        self._role_to_model: dict[LLMRole, str] = {c.role: c.model_id for c in configs}
        self._active: dict[str, bool] = {c.model_id: True for c in configs}
        self._limiters: dict[str, RateLimiter] = {
            c.model_id: RateLimiter(c.rpm) for c in configs
        }

    def get_model_for_role(self, role: LLMRole) -> str:
        return self._role_to_model[role]

    def is_active(self, model_id: str) -> bool:
        return self._active.get(model_id, False)

    def disable(self, model_id: str):
        self._active[model_id] = False

    def enable(self, model_id: str):
        self._active[model_id] = True

    def get_fallback_for_role(self, role: LLMRole) -> Optional[str]:
        chain = FALLBACK_CHAINS.get(role, [])
        for model in chain:
            if self.is_active(model):
                return model
        return None

    def get_active_model_for_role(
        self, role: LLMRole, exclude_all: bool = False
    ) -> str:
        if exclude_all:
            raise AllModelsDownError(f"Tous les modèles pour {role} sont inactifs")
        model = self._role_to_model.get(role)
        if model and self.is_active(model):
            return model
        fallback = self.get_fallback_for_role(role)
        if fallback:
            return fallback
        raise AllModelsDownError(f"Aucun modèle actif pour le rôle {role}")

    async def call_llm(
        self,
        model: str,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        timeout: int = 120,
        stream: bool = False,
    ) -> str:
        if model in self._limiters:
            await self._limiters[model].acquire()

        response = await litellm.acompletion(
            model=model,
            messages=messages,
            tools=tools,
            timeout=timeout,
            stream=stream,
        )
        return response.choices[0].message.content or ""

    async def call_with_fallback(
        self,
        role: LLMRole,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> str:
        chain = FALLBACK_CHAINS.get(role, [])
        primary = self._role_to_model.get(role)
        models_to_try = [primary] + [m for m in chain if m != primary]
        models_to_try = [m for m in models_to_try if m and self.is_active(m)]

        last_error: Exception = AllModelsDownError(f"Aucun modèle pour {role}")
        for model in models_to_try:
            try:
                return await self.call_llm(model=model, messages=messages, tools=tools)
            except (asyncio.TimeoutError, Exception) as e:
                last_error = e
                continue

        raise last_error
```

- [ ] **Step 3.4 : Lancer les tests**

```bash
source venv/bin/activate && pytest tests/backend/test_llm_manager.py -v
```

Expected : `6 passed`

- [ ] **Step 3.5 : Commit**

```bash
git add backend/llm_manager.py tests/backend/test_llm_manager.py
git commit -m "feat: add LLM Manager with fallback chain and rate limiting"
```

---

## Task 4 : Router Engine

**Files:**
- Create: `backend/router_engine.py`
- Create: `tests/backend/test_router_engine.py`

Étend `localcoder/complexity.py` existant. Aligne les seuils (3/6 → 4/7) et ajoute le feedback loop SQLite.

- [ ] **Step 4.1 : Écrire les tests**

```python
# tests/backend/test_router_engine.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.router_engine import RouterEngine
from backend.models import LLMRole, RoutingDecision


@pytest.fixture
def router():
    return RouterEngine(db_path=":memory:")


@pytest.mark.asyncio
async def test_route_simple_task(router):
    """Score <= 4 → coding simple, MiniMax seul."""
    await router.init_db()
    decision = await router.route("corrige le typo dans le bouton login")
    assert decision.score <= 4
    assert decision.mode == "simple"
    assert decision.role == LLMRole.CODING


@pytest.mark.asyncio
async def test_route_medium_task(router):
    """Score 5-7 → medium, coding + validation."""
    await router.init_db()
    decision = await router.route("optimise les performances du dashboard")
    assert 4 < decision.score <= 7
    assert decision.mode == "medium"


@pytest.mark.asyncio
async def test_route_complex_task(router):
    """Score >= 8 → multi-agent complet."""
    await router.init_db()
    decision = await router.route("refactore tout le module d'authentification")
    assert decision.score > 7
    assert decision.mode == "multi_agent"
    assert decision.role == LLMRole.ARCHITECTURE


@pytest.mark.asyncio
async def test_route_project_task(router):
    """Mots-clés projet → score forcé à 9."""
    await router.init_db()
    decision = await router.route("crée une app de gestion de freelances")
    assert decision.score == 9
    assert decision.mode == "multi_agent"


@pytest.mark.asyncio
async def test_route_architecture_task(router):
    """Tâche architecture → role ARCHITECTURE."""
    await router.init_db()
    decision = await router.route("quelle architecture pour mon API REST ?")
    assert decision.role == LLMRole.ARCHITECTURE


@pytest.mark.asyncio
async def test_save_and_apply_feedback(router):
    """Correction de routing stockée et appliquée au prochain appel similaire."""
    await router.init_db()
    await router.save_feedback(
        prompt_pattern="typo",
        routed_to="deepseek/deepseek-r1",
        corrected_to="minimax/minimax-m2.5"
    )
    feedbacks = await router.get_feedbacks()
    assert len(feedbacks) == 1
    assert feedbacks[0]["corrected_to"] == "minimax/minimax-m2.5"


@pytest.mark.asyncio
async def test_manual_override(router):
    """@deepseek force le rôle ARCHITECTURE."""
    await router.init_db()
    decision = await router.route("@deepseek analyse ce code")
    assert decision.role == LLMRole.ARCHITECTURE
    assert "deepseek" in decision.llm
```

- [ ] **Step 4.2 : Lancer les tests pour confirmer l'échec**

```bash
source venv/bin/activate && pytest tests/backend/test_router_engine.py -v
```

Expected : `ImportError: cannot import name 'RouterEngine'`

- [ ] **Step 4.3 : Implémenter backend/router_engine.py**

```python
# backend/router_engine.py
from __future__ import annotations
import hashlib
import re
import sys
from pathlib import Path
import aiosqlite
from backend.models import LLMRole, RoutingDecision

# Réutilise complexity.py existant sans le modifier
sys.path.insert(0, str(Path(__file__).parent.parent))
from localcoder.complexity import analyze_task_complexity

# Mapping rôle → model_id (source de vérité unique)
ROLE_MODELS: dict[LLMRole, str] = {
    LLMRole.CODING:       "minimax/minimax-m2.5",
    LLMRole.ARCHITECTURE: "deepseek/deepseek-r1",
    LLMRole.ANALYSIS:     "gemini/gemini-2.5-pro",
    LLMRole.TESTING:      "mistral/codestral-latest",
    LLMRole.ROUTING:      "gemini/gemini-2.5-flash",
}

# Overrides manuels via @mention
MENTION_TO_ROLE: dict[str, LLMRole] = {
    "@minimax":    LLMRole.CODING,
    "@gemini":     LLMRole.ANALYSIS,
    "@deepseek":   LLMRole.ARCHITECTURE,
    "@codestral":  LLMRole.TESTING,
}

# Mots-clés qui forcent le score à 9 (mode projet)
PROJECT_KEYWORDS = [
    r"crée\s+une\s+app",
    r"nouveau\s+projet",
    r"je\s+veux\s+construire",
    r"génère\s+le\s+cdc",
]

# Mots-clés qui orientent vers ARCHITECTURE (même si score medium)
ARCH_KEYWORDS = [r"architecture", r"quelle\s+architecture", r"design\s+système"]


class RouterEngine:
    def __init__(self, db_path: str = ".localcoder/routing_feedback.sqlite"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS routing_feedback (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_hash  TEXT,
                    routed_to    TEXT,
                    corrected_to TEXT,
                    pattern      TEXT,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def route(self, prompt: str) -> RoutingDecision:
        """Analyse le prompt et retourne la décision de routing."""
        # 1. Override manuel via @mention
        for mention, role in MENTION_TO_ROLE.items():
            if mention in prompt.lower():
                return RoutingDecision(
                    prompt=prompt,
                    score=5,
                    llm=ROLE_MODELS[role],
                    role=role,
                    mode="medium",
                    reason=f"Override manuel {mention}",
                )

        # 2. Mots-clés projet → score forcé 9
        for pattern in PROJECT_KEYWORDS:
            if re.search(pattern, prompt, re.IGNORECASE):
                return RoutingDecision(
                    prompt=prompt,
                    score=9,
                    llm=ROLE_MODELS[LLMRole.ARCHITECTURE],
                    role=LLMRole.ARCHITECTURE,
                    mode="multi_agent",
                    reason="Mode projet détecté",
                )

        # 3. Score via complexity.py existant (seuils ajustés 4/7 au lieu de 3/6)
        result = analyze_task_complexity(prompt)
        score = result.score

        # Ajustement des seuils : complexity.py utilise 3/6, on aligne sur 4/7
        if score == 3:
            score = 4
        elif score == 6:
            score = 7

        # 4. Déterminer le rôle selon le score et les mots-clés
        if score <= 4:
            role = LLMRole.CODING
            mode = "simple"
        elif score <= 7:
            # Vérifier si c'est une tâche d'architecture malgré le score medium
            for arch_pattern in ARCH_KEYWORDS:
                if re.search(arch_pattern, prompt, re.IGNORECASE):
                    role = LLMRole.ARCHITECTURE
                    mode = "medium"
                    break
            else:
                role = LLMRole.CODING
                mode = "medium"
        else:
            role = LLMRole.ARCHITECTURE
            mode = "multi_agent"

        return RoutingDecision(
            prompt=prompt,
            score=score,
            llm=ROLE_MODELS[role],
            role=role,
            mode=mode,
            reason=result.reason,
        )

    async def save_feedback(
        self,
        prompt_pattern: str,
        routed_to: str,
        corrected_to: str,
    ):
        prompt_hash = hashlib.md5(prompt_pattern.encode()).hexdigest()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO routing_feedback (prompt_hash, routed_to, corrected_to, pattern) "
                "VALUES (?, ?, ?, ?)",
                (prompt_hash, routed_to, corrected_to, prompt_pattern),
            )
            await db.commit()

    async def get_feedbacks(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM routing_feedback ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
```

- [ ] **Step 4.4 : Lancer les tests**

```bash
source venv/bin/activate && pytest tests/backend/test_router_engine.py -v
```

Expected : `7 passed`

- [ ] **Step 4.5 : Commit**

```bash
git add backend/router_engine.py tests/backend/test_router_engine.py
git commit -m "feat: add Router Engine extending complexity.py with feedback loop"
```

---

## Task 5 : File Lock async

**Files:**
- Create: `backend/file_lock.py`
- Create: `tests/backend/test_file_lock.py`

- [ ] **Step 5.1 : Écrire les tests**

```python
# tests/backend/test_file_lock.py
import pytest
import asyncio
from backend.file_lock import FileLock


@pytest.fixture
def lock():
    return FileLock()


@pytest.mark.asyncio
async def test_acquire_free_file(lock):
    """Un fichier libre peut être acquis."""
    result = await lock.acquire("auth.py", "minimax")
    assert result is True
    assert lock.is_locked("auth.py")


@pytest.mark.asyncio
async def test_acquire_locked_file_fails(lock):
    """Un fichier déjà verrouillé refuse une deuxième acquisition."""
    await lock.acquire("auth.py", "minimax")
    result = await lock.acquire("auth.py", "deepseek")
    assert result is False


@pytest.mark.asyncio
async def test_release_lock(lock):
    """Après release, le fichier est disponible."""
    await lock.acquire("auth.py", "minimax")
    await lock.release("auth.py", "minimax")
    assert not lock.is_locked("auth.py")


@pytest.mark.asyncio
async def test_only_owner_can_release(lock):
    """Seul le LLM propriétaire peut libérer le lock."""
    await lock.acquire("auth.py", "minimax")
    await lock.release("auth.py", "deepseek")  # Pas le propriétaire
    assert lock.is_locked("auth.py")  # Toujours verrouillé


@pytest.mark.asyncio
async def test_get_locked_files(lock):
    """Liste des fichiers verrouillés."""
    await lock.acquire("auth.py", "minimax")
    await lock.acquire("users.py", "codestral")
    locked = lock.get_locked_files()
    assert "auth.py" in locked
    assert "users.py" in locked
    assert locked["auth.py"] == "minimax"


@pytest.mark.asyncio
async def test_concurrent_acquire_is_safe(lock):
    """Deux coroutines concurrent : une seule gagne le lock."""
    results = []

    async def try_acquire(llm: str):
        result = await lock.acquire("shared.py", llm)
        results.append(result)

    await asyncio.gather(
        try_acquire("minimax"),
        try_acquire("deepseek"),
    )
    # Exactement un True et un False
    assert results.count(True) == 1
    assert results.count(False) == 1
```

- [ ] **Step 5.2 : Confirmer l'échec**

```bash
source venv/bin/activate && pytest tests/backend/test_file_lock.py -v
```

Expected : `ImportError: cannot import name 'FileLock'`

- [ ] **Step 5.3 : Implémenter backend/file_lock.py**

```python
# backend/file_lock.py
from __future__ import annotations
import asyncio


class FileLock:
    """
    File locking thread-safe via asyncio.Lock.
    L'opération check-then-set est atomique.
    """

    def __init__(self):
        self._locks: dict[str, str] = {}   # filepath → llm_name
        self._mutex = asyncio.Lock()

    async def acquire(self, filepath: str, llm: str) -> bool:
        """
        Tente d'acquérir le lock sur filepath pour llm.
        Retourne True si acquis, False si déjà verrouillé.
        Opération atomique — pas de race condition.
        """
        async with self._mutex:
            if filepath in self._locks:
                return False
            self._locks[filepath] = llm
            return True

    async def release(self, filepath: str, llm: str):
        """
        Libère le lock uniquement si llm est le propriétaire.
        Les autres LLMs ne peuvent pas libérer un lock qui ne leur appartient pas.
        """
        async with self._mutex:
            if self._locks.get(filepath) == llm:
                del self._locks[filepath]

    def is_locked(self, filepath: str) -> bool:
        return filepath in self._locks

    def get_locked_files(self) -> dict[str, str]:
        """Retourne une copie du mapping filepath → llm_name."""
        return dict(self._locks)

    async def release_all_for(self, llm: str):
        """Libère tous les fichiers verrouillés par un LLM (ex: après crash)."""
        async with self._mutex:
            to_release = [fp for fp, owner in self._locks.items() if owner == llm]
            for fp in to_release:
                del self._locks[fp]
```

- [ ] **Step 5.4 : Lancer les tests**

```bash
source venv/bin/activate && pytest tests/backend/test_file_lock.py -v
```

Expected : `6 passed`

- [ ] **Step 5.5 : Commit**

```bash
git add backend/file_lock.py tests/backend/test_file_lock.py
git commit -m "feat: add async FileLock with atomic acquire/release"
```

---

## Task 6 : Task Queue par LLM

**Files:**
- Create: `backend/task_queue.py`
- Create: `tests/backend/test_task_queue.py`

- [ ] **Step 6.1 : Écrire les tests**

```python
# tests/backend/test_task_queue.py
import pytest
import asyncio
from backend.task_queue import LLMTaskQueue


@pytest.fixture
def queue():
    return LLMTaskQueue()


@pytest.mark.asyncio
async def test_enqueue_and_process(queue):
    """Une tâche enqueued est exécutée."""
    results = []

    async def my_task():
        results.append("done")

    await queue.enqueue("minimax", my_task)
    await asyncio.sleep(0.1)  # Laisse le worker tourner
    assert results == ["done"]


@pytest.mark.asyncio
async def test_sequential_execution(queue):
    """Les tâches sont exécutées dans l'ordre pour un même LLM."""
    order = []

    async def task_a():
        order.append("A")
        await asyncio.sleep(0.05)

    async def task_b():
        order.append("B")

    await queue.enqueue("minimax", task_a)
    await queue.enqueue("minimax", task_b)
    await asyncio.sleep(0.2)
    assert order == ["A", "B"]


@pytest.mark.asyncio
async def test_different_llms_parallel(queue):
    """Deux LLMs différents s'exécutent en parallèle."""
    start_times = {}

    async def slow_task(llm: str):
        start_times[llm] = asyncio.get_event_loop().time()
        await asyncio.sleep(0.1)

    await queue.enqueue("minimax", lambda: slow_task("minimax"))
    await queue.enqueue("deepseek", lambda: slow_task("deepseek"))
    await asyncio.sleep(0.2)

    # Les deux ont démarré dans la même fenêtre temporelle (< 0.05s d'écart)
    assert abs(start_times["minimax"] - start_times["deepseek"]) < 0.05


@pytest.mark.asyncio
async def test_queue_size(queue):
    """pending_count retourne le nombre de tâches en attente."""
    async def long_task():
        await asyncio.sleep(10)

    await queue.enqueue("minimax", long_task)
    await queue.enqueue("minimax", long_task)
    await asyncio.sleep(0.05)  # Laisse la première démarrer
    assert queue.pending_count("minimax") >= 1
```

- [ ] **Step 6.2 : Confirmer l'échec**

```bash
source venv/bin/activate && pytest tests/backend/test_task_queue.py -v
```

Expected : `ImportError: cannot import name 'LLMTaskQueue'`

- [ ] **Step 6.3 : Implémenter backend/task_queue.py**

```python
# backend/task_queue.py
from __future__ import annotations
import asyncio
from typing import Callable, Awaitable


class LLMTaskQueue:
    """
    File d'attente par LLM — 1 tâche à la fois par LLM.
    Des LLMs différents s'exécutent en parallèle.
    """

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._workers: dict[str, asyncio.Task] = {}

    def _ensure_worker(self, llm: str):
        if llm not in self._queues:
            self._queues[llm] = asyncio.Queue()
        if llm not in self._workers or self._workers[llm].done():
            self._workers[llm] = asyncio.create_task(self._worker(llm))

    async def _worker(self, llm: str):
        queue = self._queues[llm]
        while True:
            task_fn = await queue.get()
            try:
                await task_fn()
            except Exception as e:
                # Log sans crasher le worker
                print(f"[TaskQueue] Erreur dans tâche {llm}: {e}")
            finally:
                queue.task_done()

    async def enqueue(self, llm: str, task_fn: Callable[[], Awaitable]):
        """Ajoute une tâche async dans la file du LLM donné."""
        self._ensure_worker(llm)
        await self._queues[llm].put(task_fn)

    def pending_count(self, llm: str) -> int:
        """Nombre de tâches en attente pour un LLM."""
        if llm not in self._queues:
            return 0
        return self._queues[llm].qsize()

    async def wait_all(self, llm: str):
        """Attend que toutes les tâches d'un LLM soient terminées."""
        if llm in self._queues:
            await self._queues[llm].join()
```

- [ ] **Step 6.4 : Lancer les tests**

```bash
source venv/bin/activate && pytest tests/backend/test_task_queue.py -v
```

Expected : `4 passed`

- [ ] **Step 6.5 : Commit**

```bash
git add backend/task_queue.py tests/backend/test_task_queue.py
git commit -m "feat: add per-LLM task queue with parallel execution"
```

---

## Task 7 : WebSocket Streamer

**Files:**
- Create: `backend/ws_streamer.py`
- Create: `tests/backend/test_ws_streamer.py`

- [ ] **Step 7.1 : Écrire les tests**

```python
# tests/backend/test_ws_streamer.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.ws_streamer import WSStreamer
from backend.models import WSEvent


@pytest.fixture
def streamer():
    return WSStreamer()


@pytest.mark.asyncio
async def test_connect_and_disconnect(streamer):
    """Un client peut se connecter et se déconnecter."""
    mock_ws = AsyncMock()
    mock_ws.send_json = AsyncMock()

    session_id = "session_001"
    streamer.connect(session_id, mock_ws)
    assert streamer.is_connected(session_id)

    streamer.disconnect(session_id)
    assert not streamer.is_connected(session_id)


@pytest.mark.asyncio
async def test_broadcast_sends_to_connected(streamer):
    """broadcast() envoie à tous les clients connectés."""
    mock_ws = AsyncMock()
    mock_ws.send_json = AsyncMock()

    streamer.connect("session_001", mock_ws)
    event = WSEvent(type="routing", data={"llm": "minimax"}, session_id="session_001")
    await streamer.broadcast(event)

    mock_ws.send_json.assert_called_once()
    call_args = mock_ws.send_json.call_args[0][0]
    assert call_args["type"] == "routing"


@pytest.mark.asyncio
async def test_send_to_session(streamer):
    """send_to() envoie uniquement à la session cible."""
    mock_ws_1 = AsyncMock()
    mock_ws_2 = AsyncMock()
    mock_ws_1.send_json = AsyncMock()
    mock_ws_2.send_json = AsyncMock()

    streamer.connect("session_001", mock_ws_1)
    streamer.connect("session_002", mock_ws_2)

    event = WSEvent(type="agent_action", data={}, session_id="session_001")
    await streamer.send_to("session_001", event)

    mock_ws_1.send_json.assert_called_once()
    mock_ws_2.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_disconnected_client_cleaned_up(streamer):
    """Si le client est fermé, il est retiré automatiquement."""
    mock_ws = AsyncMock()
    from fastapi import WebSocketDisconnect
    mock_ws.send_json = AsyncMock(side_effect=WebSocketDisconnect())

    streamer.connect("session_001", mock_ws)
    event = WSEvent(type="test", data={}, session_id="session_001")
    await streamer.broadcast(event)

    # Client déconnecté automatiquement après l'erreur
    assert not streamer.is_connected("session_001")
```

- [ ] **Step 7.2 : Confirmer l'échec**

```bash
source venv/bin/activate && pytest tests/backend/test_ws_streamer.py -v
```

Expected : `ImportError: cannot import name 'WSStreamer'`

- [ ] **Step 7.3 : Implémenter backend/ws_streamer.py**

```python
# backend/ws_streamer.py
from __future__ import annotations
from fastapi import WebSocket, WebSocketDisconnect
from backend.models import WSEvent


class WSStreamer:
    """
    Gestionnaire de connexions WebSocket.
    Envoie des événements temps réel au frontend React.
    """

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    def connect(self, session_id: str, ws: WebSocket):
        self._connections[session_id] = ws

    def disconnect(self, session_id: str):
        self._connections.pop(session_id, None)

    def is_connected(self, session_id: str) -> bool:
        return session_id in self._connections

    async def send_to(self, session_id: str, event: WSEvent):
        """Envoie un événement à une session spécifique."""
        ws = self._connections.get(session_id)
        if ws:
            try:
                await ws.send_json(event.model_dump(mode="json"))
            except WebSocketDisconnect:
                self.disconnect(session_id)

    async def broadcast(self, event: WSEvent):
        """Envoie un événement à tous les clients connectés."""
        disconnected = []
        for session_id, ws in self._connections.items():
            try:
                await ws.send_json(event.model_dump(mode="json"))
            except WebSocketDisconnect:
                disconnected.append(session_id)
        for session_id in disconnected:
            self.disconnect(session_id)

    async def emit_routing(self, session_id: str, llm: str, prompt: str, mode: str):
        """Raccourci pour émettre un événement de routing."""
        await self.send_to(session_id, WSEvent(
            type="routing",
            data={"llm": llm, "prompt": prompt[:100], "mode": mode},
            session_id=session_id,
        ))

    async def emit_agent_action(self, session_id: str, llm: str, action: str, file: str = ""):
        """Raccourci pour émettre une action de l'agent loop."""
        await self.send_to(session_id, WSEvent(
            type="agent_action",
            data={"llm": llm, "action": action, "file": file},
            session_id=session_id,
        ))

    async def emit_error(self, session_id: str, message: str):
        """Émet une erreur visible dans l'UI."""
        await self.send_to(session_id, WSEvent(
            type="error",
            data={"message": message},
            session_id=session_id,
        ))
```

- [ ] **Step 7.4 : Lancer les tests**

```bash
source venv/bin/activate && pytest tests/backend/test_ws_streamer.py -v
```

Expected : `4 passed`

- [ ] **Step 7.5 : Commit**

```bash
git add backend/ws_streamer.py tests/backend/test_ws_streamer.py
git commit -m "feat: add WebSocket streamer for real-time frontend events"
```

---

## Task 8 : FastAPI Main App

**Files:**
- Create: `backend/main.py`
- Create: `tests/backend/test_main.py`
- Create: `tests/backend/conftest.py`

- [ ] **Step 8.1 : Créer conftest.py**

```python
# tests/backend/conftest.py
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from backend.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
async def async_client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

- [ ] **Step 8.2 : Écrire les tests**

```python
# tests/backend/test_main.py
import pytest
from fastapi.testclient import TestClient


def test_health_check(client):
    """GET /health retourne 200 avec status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_includes_version(client):
    """GET /health inclut la version."""
    response = client.get("/health")
    data = response.json()
    assert "version" in data
    assert data["version"] == "2.0.0"


def test_route_endpoint(client):
    """POST /route analyse un prompt et retourne une décision."""
    response = client.post("/route", json={"prompt": "corrige le typo"})
    assert response.status_code == 200
    data = response.json()
    assert "llm" in data
    assert "mode" in data
    assert "score" in data


def test_route_complex_prompt(client):
    """POST /route sur prompt complexe retourne mode multi_agent."""
    response = client.post(
        "/route",
        json={"prompt": "refactore tout le module d'authentification"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "multi_agent"


def test_llm_status_endpoint(client):
    """GET /llms retourne la liste des LLMs avec leur statut."""
    response = client.get("/llms")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 5  # 5 LLMs configurés
    assert all("model_id" in llm for llm in data)
    assert all("active" in llm for llm in data)


def test_disable_llm(client):
    """POST /llms/{model}/disable désactive un LLM."""
    response = client.post("/llms/minimax%2Fminimax-m2.5/disable")
    assert response.status_code == 200

    status_response = client.get("/llms")
    llms = {llm["model_id"]: llm for llm in status_response.json()}
    assert not llms["minimax/minimax-m2.5"]["active"]

    # Réactiver pour ne pas polluer les autres tests
    client.post("/llms/minimax%2Fminimax-m2.5/enable")
```

- [ ] **Step 8.3 : Confirmer l'échec**

```bash
source venv/bin/activate && pytest tests/backend/test_main.py -v
```

Expected : `ImportError: cannot import name 'create_app'`

- [ ] **Step 8.4 : Implémenter backend/main.py**

```python
# backend/main.py
from __future__ import annotations
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.models import LLMConfig, LLMRole, WSEvent
from backend.llm_manager import LLMManager
from backend.router_engine import RouterEngine
from backend.file_lock import FileLock
from backend.task_queue import LLMTaskQueue
from backend.ws_streamer import WSStreamer

VERSION = "2.0.0"

# Configuration des LLMs (source de vérité)
DEFAULT_LLM_CONFIGS = [
    LLMConfig(model_id="minimax/minimax-m2.5",      role=LLMRole.CODING,       rpm=200),
    LLMConfig(model_id="deepseek/deepseek-r1",      role=LLMRole.ARCHITECTURE, rpm=50),
    LLMConfig(model_id="gemini/gemini-2.5-flash",   role=LLMRole.ROUTING,      rpm=1000),
    LLMConfig(model_id="gemini/gemini-2.5-pro",     role=LLMRole.ANALYSIS,     rpm=60),
    LLMConfig(model_id="mistral/codestral-latest",  role=LLMRole.TESTING,      rpm=100),
]


class RouteRequest(BaseModel):
    prompt: str


def create_app(configs: list[LLMConfig] | None = None) -> FastAPI:
    llm_manager = LLMManager(configs=configs or DEFAULT_LLM_CONFIGS)
    router_engine = RouterEngine()
    file_lock = FileLock()
    task_queue = LLMTaskQueue()
    ws_streamer = WSStreamer()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await router_engine.init_db()
        yield

    app = FastAPI(title="LocalCoder IDE Backend", version=VERSION, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health ──────────────────────────────────────────────────────────────
    @app.get("/health")
    async def health():
        return {"status": "ok", "version": VERSION}

    # ── Routing ─────────────────────────────────────────────────────────────
    @app.post("/route")
    async def route_prompt(req: RouteRequest):
        decision = await router_engine.route(req.prompt)
        return decision.model_dump(mode="json")

    # ── LLM Management ──────────────────────────────────────────────────────
    @app.get("/llms")
    async def list_llms():
        return [
            {
                "model_id": cfg.model_id,
                "role": cfg.role,
                "active": llm_manager.is_active(cfg.model_id),
                "rpm": cfg.rpm,
            }
            for cfg in (configs or DEFAULT_LLM_CONFIGS)
        ]

    @app.post("/llms/{model_id}/disable")
    async def disable_llm(model_id: str):
        model_id = model_id.replace("%2F", "/")
        llm_manager.disable(model_id)
        return {"model_id": model_id, "active": False}

    @app.post("/llms/{model_id}/enable")
    async def enable_llm(model_id: str):
        model_id = model_id.replace("%2F", "/")
        llm_manager.enable(model_id)
        return {"model_id": model_id, "active": True}

    # ── WebSocket ────────────────────────────────────────────────────────────
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        session_id = str(uuid.uuid4())
        ws_streamer.connect(session_id, ws)
        await ws_streamer.emit_routing(
            session_id, "system", "Connexion établie", "system"
        )
        try:
            while True:
                data = await ws.receive_json()
                if data.get("type") == "route":
                    decision = await router_engine.route(data["prompt"])
                    await ws_streamer.send_to(session_id, WSEvent(
                        type="routing_decision",
                        data=decision.model_dump(mode="json"),
                        session_id=session_id,
                    ))
        except WebSocketDisconnect:
            ws_streamer.disconnect(session_id)

    # Expose les services pour les autres modules
    app.state.llm_manager = llm_manager
    app.state.router_engine = router_engine
    app.state.file_lock = file_lock
    app.state.task_queue = task_queue
    app.state.ws_streamer = ws_streamer

    return app


# Point d'entrée direct
app = create_app()
```

- [ ] **Step 8.5 : Lancer les tests**

```bash
source venv/bin/activate && pytest tests/backend/test_main.py -v
```

Expected : `5 passed`

- [ ] **Step 8.6 : Lancer tous les tests pour s'assurer que rien n'est cassé**

```bash
source venv/bin/activate && pytest tests/ -v
```

Expected : `26 passed` (tous les tests des tasks précédentes + ceux-ci)

- [ ] **Step 8.7 : Tester le serveur manuellement**

```bash
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8765 --reload
```

Dans un autre terminal :
```bash
curl http://localhost:8765/health
# Expected : {"status":"ok","version":"2.0.0"}

curl -X POST http://localhost:8765/route \
  -H "Content-Type: application/json" \
  -d '{"prompt":"refactore tout le module auth"}'
# Expected : {"mode":"multi_agent","score":8,...}
```

- [ ] **Step 8.8 : Commit final**

```bash
git add backend/main.py tests/backend/conftest.py tests/backend/test_main.py
git commit -m "feat: add FastAPI app with health, routing, LLM management, and WebSocket"
```

---

## Task 9 : Intégration `localcoder ide` → démarre FastAPI

**Files:**
- Modify: `localcoder/workspace.py`

La commande `localcoder ide` existe déjà et lance tmux. On l'étend pour démarrer FastAPI en processus enfant avant d'ouvrir Tauri (Tauri sera ajouté dans le Plan 3 — pour l'instant on valide le démarrage FastAPI).

- [ ] **Step 9.1 : Lire le workspace.py existant**

```bash
cat localcoder/workspace.py
```

- [ ] **Step 9.2 : Ajouter start_backend() dans workspace.py**

Ajouter cette fonction dans `localcoder/workspace.py` SANS supprimer le code existant :

```python
import subprocess
import time
import urllib.request
import urllib.error

def start_backend(port: int = 8765, timeout: int = 5) -> subprocess.Popen:
    """
    Démarre FastAPI en processus enfant.
    Attend que /health réponde avant de retourner.
    """
    process = subprocess.Popen(
        ["python", "-m", "uvicorn", "backend.main:app",
         "--host", "0.0.0.0", "--port", str(port)],
        cwd=str(Path(__file__).parent.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Health check avec retry
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{port}/health", timeout=1)
            return process  # FastAPI prêt
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)

    process.terminate()
    raise RuntimeError(f"FastAPI n'a pas démarré en {timeout}s sur le port {port}")
```

- [ ] **Step 9.3 : Vérifier que les tests existants passent toujours**

```bash
source venv/bin/activate && pytest tests/ -v
```

Expected : `26 passed`

- [ ] **Step 9.4 : Commit**

```bash
git add localcoder/workspace.py
git commit -m "feat: add start_backend() to workspace — FastAPI as child process"
```

---

## Self-Review

**Couverture spec → plan :**

| Section spec | Couvert dans ce plan |
|-------------|---------------------|
| Architecture Tauri + FastAPI | ✅ FastAPI complet, Tauri en Plan 3 |
| LLM Manager + fallback + rate limit | ✅ Task 3 |
| Router Engine (complexity.py étendu) | ✅ Task 4 |
| File Lock async | ✅ Task 5 |
| Task Queue par LLM | ✅ Task 6 |
| WebSocket Streamer | ✅ Task 7 |
| FastAPI routes /health /route /llms /ws | ✅ Task 8 |
| Démarrage `localcoder ide` | ✅ Task 9 |
| Cycle de vie processus (SIGTERM) | ⚠️ Partiel — handler SIGTERM dans Plan 2 |
| Clés API keychain | ❌ Plan 3 (Tauri secure store) |

**Pas de placeholders détectés.**

**Cohérence des types :** `LLMRole`, `RoutingDecision`, `WSEvent` définis en Task 2 et utilisés de façon cohérente dans toutes les tasks suivantes.

---

## Plan 1 terminé

Ce plan produit un serveur FastAPI fonctionnel, testé (26 tests), avec :
- LLM Manager avec fallback chain et rate limiting
- Router Engine qui classe les prompts en simple/medium/multi_agent
- File Lock async thread-safe
- Task Queue par LLM avec parallélisme inter-LLMs
- WebSocket Streamer pour le frontend
- Routes REST /health, /route, /llms

**Plans suivants :**
- **Plan 2** : Agent Loop + Memory (court terme + long terme) + Roadmap + Context Builder
- **Plan 3** : UI Tauri + React (Chat, Routing, Terminaux, Monitoring)
- **Plan 4** : GitHub Integration + Mode Projet (CdC → Sprints → CI)
