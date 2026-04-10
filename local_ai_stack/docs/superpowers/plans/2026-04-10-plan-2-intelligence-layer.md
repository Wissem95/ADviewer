# LocalCoder IDE v2 — Plan 2 : Intelligence Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire la couche intelligence : mémoire courte/longue (SQLite), ProjectRoadmap, Context Builder, Agent Loop 5 étapes avec retry, Orchestrateur central, et les 5 system prompts MD par LLM.

**Architecture:** L'Orchestrateur est le seul point d'entrée pour toute tâche — les LLMs ne se parlent jamais directement. L'Agent Loop exécute les 5 étapes (PLAN→VERIFY→EXECUTE→CHECK→CONFIRM) avec 3 retries max sur erreur lint. La mémoire courte (RAM, session) et longue (SQLite, persistant) tracent toutes les décisions et le feedback de routage.

**Tech Stack:** Python 3.12, aiosqlite, dataclasses, asyncio, ruff (lint), Plan 1 requis (backend/models.py, llm_manager.py, file_lock.py, task_queue.py, ws_streamer.py, router_engine.py)

**Spec de référence:** `docs/superpowers/specs/2026-04-10-localcoder-ide-v2-design.md` §4 et §5

---

## Fichiers créés ou modifiés

```
backend/
├── memory.py              # CRÉÉ — ShortTermMemory (RAM) + LongTermMemory (SQLite)
├── roadmap.py             # CRÉÉ — ProjectRoadmap + Task + SubTask + Decision
├── context_builder.py     # CRÉÉ — build_context_for() ciblé ~2-3K tokens
├── agent_loop.py          # CRÉÉ — AgentLoop 5 étapes + AgentLoopError + retry
├── orchestrator.py        # CRÉÉ — Orchestrateur central, point d'entrée unique
└── prompts/
    ├── system_minimax.md       # CRÉÉ — system prompt MiniMax M2.5 (coding)
    ├── system_deepseek_r1.md   # CRÉÉ — system prompt DeepSeek R1 (architecture)
    ├── system_codestral.md     # CRÉÉ — system prompt Codestral 2 (tests)
    ├── system_gemini_pro.md    # CRÉÉ — system prompt Gemini 2.5 Pro (analyse)
    └── system_gemini_flash.md  # CRÉÉ — system prompt Gemini 2.5 Flash (routing)

tests/backend/
├── test_memory.py         # CRÉÉ — 8 tests
├── test_roadmap.py        # CRÉÉ — 7 tests
├── test_context_builder.py# CRÉÉ — 4 tests
├── test_agent_loop.py     # CRÉÉ — 5 tests
└── test_orchestrator.py   # CRÉÉ — 4 tests
```

**Dépend de Plan 1 :** `backend/models.py`, `backend/llm_manager.py`, `backend/file_lock.py`, `backend/task_queue.py`, `backend/ws_streamer.py`, `backend/router_engine.py`

---

## Task 1 : Mémoire courte et longue (memory.py)

**Files:**
- Create: `backend/memory.py`
- Create: `tests/backend/test_memory.py`

- [ ] **Step 1.1 : Écrire les tests memory**

```python
# tests/backend/test_memory.py
import pytest
import asyncio
import aiosqlite
from pathlib import Path
from backend.memory import ShortTermMemory, LongTermMemory


# --- ShortTermMemory ---

def test_short_memory_initial_state():
    mem = ShortTermMemory()
    assert mem.active_task == ""
    assert mem.actions == []
    assert mem.consultation_rounds == 0
    assert len(mem.session_id) > 0


def test_short_memory_record_action():
    mem = ShortTermMemory()
    mem.record_action(llm="minimax", action="write", detail="auth.py")
    assert len(mem.actions) == 1
    assert mem.actions[0]["llm"] == "minimax"
    assert mem.actions[0]["action"] == "write"
    assert "ts" in mem.actions[0]


def test_short_memory_add_message_increments_rounds():
    mem = ShortTermMemory()
    mem.add_message("minimax", "deepseek", "question", "Comment splitter auth.py ?")
    assert mem.consultation_rounds == 1
    assert len(mem.messages) == 1


def test_short_memory_max_rounds_raises():
    mem = ShortTermMemory()
    for i in range(5):
        mem.add_message("minimax", "deepseek", "question", f"Q{i}")
    with pytest.raises(RuntimeError, match="Max consultation rounds"):
        mem.add_message("minimax", "deepseek", "question", "Q6")


def test_short_memory_reset():
    mem = ShortTermMemory()
    mem.active_task = "T-003"
    mem.record_action("minimax", "write", "auth.py")
    mem.reset()
    assert mem.active_task == ""
    assert mem.actions == []
    assert mem.consultation_rounds == 0


# --- LongTermMemory ---

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_memory.db")


@pytest.mark.asyncio
async def test_long_memory_init_creates_tables(db_path):
    mem = LongTermMemory(db_path)
    await mem.init()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in await cursor.fetchall()}
    assert "decisions" in tables
    assert "llm_messages" in tables
    assert "roadmap_history" in tables
    assert "routing_feedback" in tables


@pytest.mark.asyncio
async def test_long_memory_save_and_get_decision(db_path):
    mem = LongTermMemory(db_path)
    await mem.init()
    rowid = await mem.save_decision(
        session_id="sess-1",
        llm="deepseek/deepseek-r1",
        dtype="architecture",
        content="auth.py splitté en 3 fichiers",
        rationale="SRP",
    )
    assert rowid == 1
    decisions = await mem.get_recent_decisions()
    assert len(decisions) == 1
    assert decisions[0]["content"] == "auth.py splitté en 3 fichiers"
    assert decisions[0]["llm"] == "deepseek/deepseek-r1"


@pytest.mark.asyncio
async def test_long_memory_routing_feedback_roundtrip(db_path):
    mem = LongTermMemory(db_path)
    await mem.init()
    await mem.save_routing_feedback(
        prompt="Refactore tout le module auth",
        routed_to="minimax/minimax-m2.5",
        corrected_to="deepseek/deepseek-r1",
        pattern="refactor.*module",
    )
    corrected = await mem.get_feedback_for("Refactore tout le module auth")
    assert corrected == "deepseek/deepseek-r1"


@pytest.mark.asyncio
async def test_long_memory_feedback_unknown_prompt_returns_none(db_path):
    mem = LongTermMemory(db_path)
    await mem.init()
    result = await mem.get_feedback_for("Corrige un typo dans le bouton")
    assert result is None
```

- [ ] **Step 1.2 : Vérifier que les tests échouent**

```bash
source venv/bin/activate && pytest tests/backend/test_memory.py -v 2>&1 | head -20
```

Expected : `FAILED` ou `ImportError: cannot import name 'ShortTermMemory'`

- [ ] **Step 1.3 : Implémenter backend/memory.py**

```python
# backend/memory.py
"""
Mémoire courte (RAM, session) et longue (SQLite persistant).
ShortTermMemory : effacée à la fermeture. Max 5 rounds de consultation.
LongTermMemory  : SQLite avec 4 tables : decisions, llm_messages,
                  roadmap_history, routing_feedback.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import aiosqlite


# ─── Mémoire courte ──────────────────────────────────────────────────────────

@dataclass
class ShortTermMemory:
    """Mémoire de session — effacée à la fermeture de Tauri."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    active_task: str = ""
    actions: list[dict] = field(default_factory=list)
    file_locks: dict[str, str] = field(default_factory=dict)
    messages: list[dict] = field(default_factory=list)
    consultation_rounds: int = 0
    MAX_ROUNDS: int = 5

    def record_action(self, llm: str, action: str, detail: str = "") -> None:
        self.actions.append({
            "llm": llm,
            "action": action,
            "detail": detail,
            "ts": datetime.now().isoformat(),
        })

    def add_message(self, from_llm: str, to_llm: str, mtype: str, content: str) -> None:
        if self.consultation_rounds >= self.MAX_ROUNDS:
            raise RuntimeError(
                f"Max consultation rounds ({self.MAX_ROUNDS}) atteint — "
                "trop de va-et-vient entre LLMs"
            )
        self.messages.append({
            "from": from_llm,
            "to": to_llm,
            "type": mtype,
            "content": content,
            "ts": datetime.now().isoformat(),
        })
        self.consultation_rounds += 1

    def reset(self) -> None:
        """Réinitialise sans changer le session_id."""
        self.active_task = ""
        self.actions.clear()
        self.file_locks.clear()
        self.messages.clear()
        self.consultation_rounds = 0


# ─── Mémoire longue ──────────────────────────────────────────────────────────

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    llm         TEXT    NOT NULL,
    type        TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    rationale   TEXT    DEFAULT '',
    files       TEXT    DEFAULT '[]',
    valid       BOOLEAN DEFAULT 1,
    valid_until DATE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS llm_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    from_llm    TEXT    NOT NULL,
    to_llm      TEXT    NOT NULL,
    type        TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    replied     BOOLEAN DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS roadmap_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project     TEXT    NOT NULL,
    ticket_id   TEXT    NOT NULL,
    action      TEXT    NOT NULL,
    by          TEXT    NOT NULL,
    detail      TEXT    DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS routing_feedback (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_hash  TEXT    NOT NULL,
    routed_to    TEXT    NOT NULL,
    corrected_to TEXT    NOT NULL,
    pattern      TEXT    DEFAULT '',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class LongTermMemory:
    """Persistance SQLite. Survivant aux redémarrages."""

    def __init__(self, db_path: str = "localcoder.db"):
        self.db_path = db_path

    async def init(self) -> None:
        """Crée les tables si elles n'existent pas."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_CREATE_TABLES)
            await db.commit()

    async def save_decision(
        self,
        session_id: str,
        llm: str,
        dtype: str,
        content: str,
        rationale: str = "",
        files: list[str] | None = None,
    ) -> int:
        import json
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO decisions
                   (session_id, llm, type, content, rationale, files)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, llm, dtype, content, rationale, json.dumps(files or [])),
            )
            await db.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    async def get_recent_decisions(self, limit: int = 20) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM decisions WHERE valid=1 ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def save_routing_feedback(
        self,
        prompt: str,
        routed_to: str,
        corrected_to: str,
        pattern: str = "",
    ) -> None:
        import hashlib
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO routing_feedback
                   (prompt_hash, routed_to, corrected_to, pattern)
                   VALUES (?, ?, ?, ?)""",
                (prompt_hash, routed_to, corrected_to, pattern),
            )
            await db.commit()

    async def get_feedback_for(self, prompt: str) -> Optional[str]:
        """Retrouve le LLM corrigé pour un prompt similaire (hash exact)."""
        import hashlib
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT corrected_to FROM routing_feedback
                   WHERE prompt_hash = ? ORDER BY created_at DESC LIMIT 1""",
                (prompt_hash,),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def save_roadmap_history(
        self,
        project: str,
        ticket_id: str,
        action: str,
        by: str,
        detail: str = "",
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO roadmap_history
                   (project, ticket_id, action, by, detail)
                   VALUES (?, ?, ?, ?, ?)""",
                (project, ticket_id, action, by, detail),
            )
            await db.commit()
```

- [ ] **Step 1.4 : Vérifier que les tests passent**

```bash
source venv/bin/activate && pytest tests/backend/test_memory.py -v
```

Expected :
```
PASSED tests/backend/test_memory.py::test_short_memory_initial_state
PASSED tests/backend/test_memory.py::test_short_memory_record_action
PASSED tests/backend/test_memory.py::test_short_memory_add_message_increments_rounds
PASSED tests/backend/test_memory.py::test_short_memory_max_rounds_raises
PASSED tests/backend/test_memory.py::test_short_memory_reset
PASSED tests/backend/test_memory.py::test_long_memory_init_creates_tables
PASSED tests/backend/test_memory.py::test_long_memory_save_and_get_decision
PASSED tests/backend/test_memory.py::test_long_memory_routing_feedback_roundtrip
PASSED tests/backend/test_memory.py::test_long_memory_feedback_unknown_prompt_returns_none
9 passed
```

- [ ] **Step 1.5 : Commit**

```bash
git add backend/memory.py tests/backend/test_memory.py
git commit -m "feat: add ShortTermMemory and LongTermMemory with SQLite"
```

---

## Task 2 : ProjectRoadmap (roadmap.py)

**Files:**
- Create: `backend/roadmap.py`
- Create: `tests/backend/test_roadmap.py`

- [ ] **Step 2.1 : Écrire les tests roadmap**

```python
# tests/backend/test_roadmap.py
import pytest
import json
from pathlib import Path
from backend.roadmap import ProjectRoadmap, Task, SubTask, Decision


def _make_roadmap() -> ProjectRoadmap:
    rm = ProjectRoadmap(project="test-project")
    rm.tasks = [
        Task(
            id="T-001",
            title="Setup base",
            status="done",
            assigned_to="minimax",
        ),
        Task(
            id="T-002",
            title="Endpoint login JWT",
            status="in_progress",
            assigned_to="minimax",
            subtasks=[
                SubTask(id="T-002-1", text="User model", done=True),
                SubTask(id="T-002-2", text="POST /auth/login", done=False),
            ],
            github_issue=42,
        ),
    ]
    rm.do_not_touch = ["_validate_scope()", "Redis config dans settings.py"]
    rm.decisions = [Decision(by="deepseek_r1", content="auth.py splitté en 3")]
    return rm


def test_roadmap_get_done_summary():
    rm = _make_roadmap()
    summary = rm.get_done_summary()
    assert "T-001" in summary
    assert "Setup base" in summary


def test_roadmap_get_do_not_touch():
    rm = _make_roadmap()
    txt = rm.get_do_not_touch()
    assert "_validate_scope()" in txt
    assert "Redis config" in txt


def test_roadmap_get_locked_files_empty():
    rm = _make_roadmap()
    txt = rm.get_locked_files()
    assert "Aucun" in txt


def test_roadmap_lock_and_unlock_file():
    rm = _make_roadmap()
    rm.lock_file("auth.py", "minimax")
    txt = rm.get_locked_files()
    assert "auth.py" in txt
    rm.unlock_file("auth.py")
    txt2 = rm.get_locked_files()
    assert "Aucun" in txt2


def test_roadmap_update_task_status():
    rm = _make_roadmap()
    rm.update_task_status("T-002", "done")
    task = next(t for t in rm.tasks if t.id == "T-002")
    assert task.status == "done"


def test_roadmap_json_roundtrip():
    rm = _make_roadmap()
    serialized = rm.to_json()
    restored = ProjectRoadmap.from_json(serialized)
    assert restored.project == "test-project"
    assert len(restored.tasks) == 2
    assert restored.tasks[1].subtasks[0].done is True
    assert restored.decisions[0].content == "auth.py splitté en 3"


def test_roadmap_save_and_load(tmp_path):
    rm = _make_roadmap()
    path = tmp_path / "roadmap.json"
    rm.save(path)
    loaded = ProjectRoadmap.load(path)
    assert loaded.project == "test-project"
    assert loaded.do_not_touch == ["_validate_scope()", "Redis config dans settings.py"]
```

- [ ] **Step 2.2 : Vérifier que les tests échouent**

```bash
source venv/bin/activate && pytest tests/backend/test_roadmap.py -v 2>&1 | head -10
```

Expected : `ImportError: cannot import name 'ProjectRoadmap'`

- [ ] **Step 2.3 : Implémenter backend/roadmap.py**

```python
# backend/roadmap.py
"""
ProjectRoadmap — état actuel du projet en JSON.
Règle absolue : seul l'orchestrateur appelle les méthodes d'écriture.
Les LLMs lisent via le tool roadmap_read (lecture seule).
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class SubTask:
    id: str
    text: str
    done: bool = False


@dataclass
class Task:
    id: str
    title: str
    status: str  # "pending" | "in_progress" | "done" | "failed" | "blocked"
    assigned_to: str = ""
    subtasks: list[SubTask] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    github_issue: Optional[int] = None
    sprint: str = ""
    estimated_complexity: int = 5
    tests_required: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)


@dataclass
class Decision:
    by: str
    content: str
    valid: bool = True


@dataclass
class ProjectRoadmap:
    """
    Roadmap du projet. Écrite uniquement par l'orchestrateur.
    Les LLMs appellent get_*() en lecture seule.
    """
    project: str
    session_id: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d-%Hh%M")
    )
    tasks: list[Task] = field(default_factory=list)
    files_state: dict[str, dict] = field(default_factory=dict)
    decisions: list[Decision] = field(default_factory=list)
    do_not_touch: list[str] = field(default_factory=list)
    done_this_session: list[str] = field(default_factory=list)

    # ── Lecture (pour les LLMs via tool roadmap_read) ──────────────────────

    def get_done_summary(self) -> str:
        """~300 tokens max — ce qui est terminé."""
        done = [t for t in self.tasks if t.status == "done"]
        lines = [f"## Terminé ({len(done)} tâches)"]
        for t in done[-10:]:
            lines.append(f"- [{t.id}] {t.title}")
        for s in self.done_this_session[-5:]:
            lines.append(f"  • {s}")
        return "\n".join(lines)

    def get_do_not_touch(self) -> str:
        """~200 tokens max — zones intouchables."""
        if not self.do_not_touch:
            return "## Do Not Touch\n(aucune restriction)"
        return "## Do Not Touch\n" + "\n".join(f"- {x}" for x in self.do_not_touch)

    def get_locked_files(self) -> str:
        """~100 tokens max — fichiers actuellement verrouillés."""
        locked = {f: s for f, s in self.files_state.items() if s.get("locked")}
        if not locked:
            return "## Fichiers verrouillés\nAucun"
        lines = ["## Fichiers verrouillés"]
        for f, s in locked.items():
            lines.append(f"- {f} (par {s.get('by', '?')})")
        return "\n".join(lines)

    def get_relevant_decisions(self, task: str) -> str:
        """~500 tokens max — décisions pertinentes (toutes si < 15)."""
        valid = [d for d in self.decisions if d.valid][-15:]
        if not valid:
            return "## Décisions architecturales\nAucune décision enregistrée."
        lines = ["## Décisions architecturales"]
        for d in valid:
            lines.append(f"- [{d.by}] {d.content}")
        return "\n".join(lines)

    def get_known_patterns(self) -> str:
        """~300 tokens max — fichiers modifiés cette session."""
        modified = {
            f: s for f, s in self.files_state.items()
            if s.get("status") == "modified"
        }
        if not modified:
            return "## Fichiers modifiés cette session\nAucun"
        lines = ["## Fichiers modifiés cette session"]
        for f, s in list(modified.items())[:20]:
            lines.append(f"- {f} (par {s.get('by', '?')})")
        return "\n".join(lines)

    # ── Écriture (orchestrateur uniquement) ────────────────────────────────

    def update_task_status(self, task_id: str, status: str) -> None:
        for t in self.tasks:
            if t.id == task_id:
                t.status = status
                return

    def mark_subtask_done(self, task_id: str, subtask_id: str) -> None:
        for t in self.tasks:
            if t.id == task_id:
                for st in t.subtasks:
                    if st.id == subtask_id:
                        st.done = True
                        return

    def lock_file(self, filepath: str, llm: str) -> None:
        self.files_state[filepath] = {"status": "modified", "by": llm, "locked": True}

    def unlock_file(self, filepath: str) -> None:
        if filepath in self.files_state:
            self.files_state[filepath]["locked"] = False

    def add_decision(self, by: str, content: str) -> None:
        self.decisions.append(Decision(by=by, content=content))

    def add_done(self, summary: str) -> None:
        self.done_this_session.append(summary)

    def get_next_pending_task(self) -> Optional[Task]:
        """Retourne la prochaine tâche pending sans dépendances bloquantes."""
        done_ids = {t.id for t in self.tasks if t.status == "done"}
        for t in self.tasks:
            if t.status == "pending" and all(dep in done_ids for dep in t.blocked_by):
                return t
        return None

    # ── Sérialisation ──────────────────────────────────────────────────────

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    @classmethod
    def from_json(cls, data: str) -> "ProjectRoadmap":
        d = json.loads(data)
        raw_tasks = d.pop("tasks", [])
        raw_decisions = d.pop("decisions", [])
        tasks = []
        for t in raw_tasks:
            raw_sub = t.pop("subtasks", [])
            tasks.append(Task(**t, subtasks=[SubTask(**s) for s in raw_sub]))
        decisions = [Decision(**dec) for dec in raw_decisions]
        return cls(**d, tasks=tasks, decisions=decisions)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path) -> "ProjectRoadmap":
        return cls.from_json(path.read_text())
```

- [ ] **Step 2.4 : Vérifier que les tests passent**

```bash
source venv/bin/activate && pytest tests/backend/test_roadmap.py -v
```

Expected :
```
PASSED tests/backend/test_roadmap.py::test_roadmap_get_done_summary
PASSED tests/backend/test_roadmap.py::test_roadmap_get_do_not_touch
PASSED tests/backend/test_roadmap.py::test_roadmap_get_locked_files_empty
PASSED tests/backend/test_roadmap.py::test_roadmap_lock_and_unlock_file
PASSED tests/backend/test_roadmap.py::test_roadmap_update_task_status
PASSED tests/backend/test_roadmap.py::test_roadmap_json_roundtrip
PASSED tests/backend/test_roadmap.py::test_roadmap_save_and_load
7 passed
```

- [ ] **Step 2.5 : Commit**

```bash
git add backend/roadmap.py tests/backend/test_roadmap.py
git commit -m "feat: add ProjectRoadmap with Task, SubTask, Decision and JSON serialization"
```

---

## Task 3 : Context Builder (context_builder.py)

**Files:**
- Create: `backend/context_builder.py`
- Create: `tests/backend/test_context_builder.py`

- [ ] **Step 3.1 : Écrire les tests context_builder**

```python
# tests/backend/test_context_builder.py
import pytest
from pathlib import Path
from backend.context_builder import build_context_for, load_project_conventions
from backend.roadmap import ProjectRoadmap, Task, Decision


def _make_roadmap_with_data() -> ProjectRoadmap:
    rm = ProjectRoadmap(project="my-project")
    rm.tasks = [Task(id="T-001", title="Setup", status="done")]
    rm.decisions = [Decision(by="deepseek_r1", content="Use JWT")]
    rm.do_not_touch = ["legacy_auth()"]
    rm.lock_file("auth.py", "minimax")
    return rm


def test_build_context_no_roadmap_returns_conventions(tmp_path, monkeypatch):
    """Sans roadmap → conventions du projet chargées."""
    # Simuler un CONVENTIONS.md dans le répertoire courant
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CONVENTIONS.md").write_text("# Conventions\nPas de magic strings.")
    ctx = build_context_for(llm="minimax", task="Corrige un typo", roadmap=None)
    assert "Conventions" in ctx
    assert "magic strings" in ctx


def test_build_context_no_roadmap_no_conventions_file(tmp_path, monkeypatch):
    """Sans roadmap et sans fichier CONVENTIONS.md → message minimal."""
    monkeypatch.chdir(tmp_path)
    ctx = build_context_for(llm="minimax", task="Corrige un typo", roadmap=None)
    assert "Aucune convention" in ctx or "Conventions" in ctx


def test_build_context_with_roadmap_contains_all_sections():
    """Avec roadmap active → toutes les sections présentes."""
    rm = _make_roadmap_with_data()
    ctx = build_context_for(llm="minimax", task="Implémente POST /auth/login", roadmap=rm)
    assert "Terminé" in ctx          # get_done_summary
    assert "Do Not Touch" in ctx      # get_do_not_touch
    assert "legacy_auth()" in ctx     # do_not_touch item
    assert "verrouill" in ctx.lower() # get_locked_files
    assert "JWT" in ctx               # get_relevant_decisions


def test_build_context_with_roadmap_token_budget():
    """Le contexte construit ne dépasse pas ~4K chars (proxy pour 2-3K tokens)."""
    rm = _make_roadmap_with_data()
    ctx = build_context_for(llm="deepseek", task="Architecture auth", roadmap=rm)
    # 4000 chars ≈ ~3000 tokens (estimation 0.75 token/char)
    assert len(ctx) < 4000
```

- [ ] **Step 3.2 : Vérifier que les tests échouent**

```bash
source venv/bin/activate && pytest tests/backend/test_context_builder.py -v 2>&1 | head -10
```

Expected : `ImportError: cannot import name 'build_context_for'`

- [ ] **Step 3.3 : Implémenter backend/context_builder.py**

```python
# backend/context_builder.py
"""
Context Builder — construit ~2-3K tokens ciblés pour chaque appel LLM.
Jamais le contexte brut complet de la session.

Si roadmap est None  → mode conversation simple : CONVENTIONS.md + AGENT_RULES.md
Si roadmap est active → mode projet : état tâches + décisions + locks + patterns
"""
from pathlib import Path
from typing import Optional

from backend.roadmap import ProjectRoadmap


def load_project_conventions() -> str:
    """
    Charge CONVENTIONS.md et AGENT_RULES.md s'ils existent dans le CWD.
    Limite à 800 chars chacun pour rester dans le budget token.
    Retourne un message minimal si aucun fichier n'existe.
    """
    parts = []
    for filename in ("CONVENTIONS.md", "AGENT_RULES.md"):
        p = Path(filename)
        if p.exists():
            content = p.read_text(encoding="utf-8", errors="ignore")[:800]
            parts.append(f"## {filename}\n{content}")
    if not parts:
        return "## Conventions\nAucune convention définie pour ce projet."
    return "\n\n".join(parts)


def build_context_for(
    llm: str,
    task: str,
    roadmap: Optional[ProjectRoadmap],
) -> str:
    """
    Construit le contexte ciblé à injecter dans le prochain appel LLM.

    Budget cible : ~2-3K tokens (~2500 chars).
    
    Args:
        llm  : Identifiant du LLM cible (non utilisé actuellement, prévu v2)
        task : Description de la tâche en cours
        roadmap : ProjectRoadmap active, ou None si mode conversation simple
    
    Returns:
        Chaîne de contexte structurée prête à injecter dans le system prompt.
    """
    if roadmap is None:
        return load_project_conventions()

    sections = [
        roadmap.get_done_summary(),            # ~300 tokens
        roadmap.get_do_not_touch(),            # ~200 tokens
        roadmap.get_locked_files(),            # ~100 tokens
        roadmap.get_relevant_decisions(task),  # ~500 tokens
        roadmap.get_known_patterns(),          # ~300 tokens
    ]
    return "\n\n".join(sections)
```

- [ ] **Step 3.4 : Vérifier que les tests passent**

```bash
source venv/bin/activate && pytest tests/backend/test_context_builder.py -v
```

Expected :
```
PASSED tests/backend/test_context_builder.py::test_build_context_no_roadmap_returns_conventions
PASSED tests/backend/test_context_builder.py::test_build_context_no_roadmap_no_conventions_file
PASSED tests/backend/test_context_builder.py::test_build_context_with_roadmap_contains_all_sections
PASSED tests/backend/test_context_builder.py::test_build_context_with_roadmap_token_budget
4 passed
```

- [ ] **Step 3.5 : Commit**

```bash
git add backend/context_builder.py tests/backend/test_context_builder.py
git commit -m "feat: add context_builder with 2-3K token budget for LLM calls"
```

---

## Task 4 : Agent Loop (agent_loop.py)

**Files:**
- Create: `backend/agent_loop.py`
- Create: `tests/backend/test_agent_loop.py`

- [ ] **Step 4.1 : Écrire les tests agent_loop**

```python
# tests/backend/test_agent_loop.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.agent_loop import AgentLoop, AgentLoopError, AgentResult
from backend.models import LLMRole, RoutingDecision
from backend.file_lock import FileLock
from backend.ws_streamer import WSStreamer


def _make_decision(llm: str = "minimax/minimax-m2.5") -> RoutingDecision:
    return RoutingDecision(
        prompt="Corrige le typo",
        score=2,
        llm=llm,
        role=LLMRole.CODING,
        mode="simple",
        reason="Fix simple",
    )


def _make_loop(llm_response: str = "Code généré") -> tuple[AgentLoop, AsyncMock]:
    llm_manager = AsyncMock()
    llm_manager.call_with_fallback = AsyncMock(return_value=llm_response)
    file_lock = FileLock()
    ws = AsyncMock()
    ws.emit_step = AsyncMock()
    ws.emit_routing = AsyncMock()
    decision = _make_decision()
    loop = AgentLoop(
        llm_manager=llm_manager,
        file_lock=file_lock,
        ws_streamer=ws,
        decision=decision,
        context="# Contexte minimal",
    )
    return loop, llm_manager


@pytest.mark.asyncio
async def test_agent_loop_run_success_no_lint_errors():
    """Run complet sans erreur lint → AgentResult retourné."""
    loop, llm = _make_loop()
    # LLM retourne un JSON plan valide puis du code
    llm.call_with_fallback.side_effect = [
        '{"steps": [{"description": "Corrige typo", "files": [], "action": "write"}]}',
        "# Code corrigé\nprint('hello')",
    ]
    with patch.object(loop, "_step_check", return_value=[]):  # Pas d'erreur lint
        result = await loop.run("Corrige le typo dans bouton.py")
    assert isinstance(result, AgentResult)
    assert result.attempts == 1
    assert result.content == "# Code corrigé\nprint('hello')"


@pytest.mark.asyncio
async def test_agent_loop_retry_on_lint_error():
    """Erreur lint à la 1ère tentative → retry → succès à la 2ème."""
    loop, llm = _make_loop()
    llm.call_with_fallback.side_effect = [
        '{"steps": []}',   # plan
        "Code buggy",       # execute tentative 1
        "Code corrigé",     # execute tentative 2 (retry)
    ]
    check_calls = [["ruff: E501 line too long"], []]  # Erreur puis OK
    with patch.object(loop, "_step_check", side_effect=check_calls):
        result = await loop.run("Fix typo")
    assert result.attempts == 2
    assert result.content == "Code corrigé"


@pytest.mark.asyncio
async def test_agent_loop_raises_after_3_retries():
    """3 erreurs lint consécutives → AgentLoopError levée."""
    loop, llm = _make_loop()
    llm.call_with_fallback.side_effect = [
        '{"steps": []}',
        "Code buggy 1",
        "Code buggy 2",
        "Code buggy 3",
    ]
    with patch.object(loop, "_step_check", return_value=["ruff: E501"]):
        with pytest.raises(AgentLoopError) as exc_info:
            await loop.run("Fix typo")
    assert exc_info.value.step == "CHECK"
    assert exc_info.value.attempts == 3


@pytest.mark.asyncio
async def test_agent_loop_verify_raises_on_locked_file():
    """Fichier verrouillé par un autre LLM → AgentLoopError en VERIFY."""
    loop, llm = _make_loop()
    # Verrouiller un fichier par un autre LLM
    await loop.file_lock.acquire("auth.py", "deepseek/deepseek-r1")
    llm.call_with_fallback.return_value = (
        '{"steps": [{"description": "write", "files": ["auth.py"], "action": "write"}]}'
    )
    with pytest.raises(AgentLoopError) as exc_info:
        await loop.run("Modifie auth.py")
    assert exc_info.value.step == "VERIFY"
    assert "auth.py" in str(exc_info.value)


@pytest.mark.asyncio
async def test_agent_loop_emits_ws_steps():
    """Chaque étape envoie un event WebSocket."""
    loop, llm = _make_loop()
    llm.call_with_fallback.side_effect = [
        '{"steps": []}',
        "Code OK",
    ]
    with patch.object(loop, "_step_check", return_value=[]):
        await loop.run("Corrige typo")
    # emit_step appelé pour PLAN, VERIFY, EXECUTE, CHECK, CONFIRM
    assert loop.ws.emit_step.call_count >= 5
```

- [ ] **Step 4.2 : Vérifier que les tests échouent**

```bash
source venv/bin/activate && pytest tests/backend/test_agent_loop.py -v 2>&1 | head -10
```

Expected : `ImportError: cannot import name 'AgentLoop'`

- [ ] **Step 4.3 : Implémenter backend/agent_loop.py**

```python
# backend/agent_loop.py
"""
Agent Loop universel — 5 étapes pour toute tâche LLM.

PLAN    → LLM liste ce qu'il va faire (pas de code encore)
VERIFY  → Orchestrateur vérifie fichiers, locks, do_not_touch
EXECUTE → Un fichier à la fois, orchestrateur écrit physiquement
CHECK   → Lint (ruff Python / eslint JS/TS) — 3 retries max
CONFIRM → Diff présenté à l'UI, roadmap mise à jour

Niveau de retry : interne uniquement (lint).
Ne pas confondre avec le retry CI GitHub (Plan 4, Niveau 2).
"""
import asyncio
import json
import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional

from backend.models import LLMRole, RoutingDecision
from backend.llm_manager import LLMManager
from backend.file_lock import FileLock
from backend.ws_streamer import WSStreamer


class AgentLoopError(Exception):
    """Erreur non récupérable après MAX_RETRIES tentatives."""

    def __init__(self, message: str, step: str, attempts: int):
        super().__init__(message)
        self.step = step
        self.attempts = attempts


@dataclass
class PlanStep:
    description: str
    files: list[str]
    action: str  # "read" | "write" | "bash" | "git_diff"


@dataclass
class AgentResult:
    content: str
    files_modified: list[str]
    tokens: int
    attempts: int  # 1, 2, ou 3


class AgentLoop:
    """
    Agent loop universel — une instance par tâche, jetée après.
    
    Usage:
        loop = AgentLoop(llm_manager, file_lock, ws_streamer, decision, context)
        result = await loop.run(task_prompt)
    """
    MAX_RETRIES = 3

    def __init__(
        self,
        llm_manager: LLMManager,
        file_lock: FileLock,
        ws_streamer: WSStreamer,
        decision: RoutingDecision,
        context: str,
    ):
        self.llm = llm_manager
        self.file_lock = file_lock
        self.ws = ws_streamer
        self.decision = decision
        self.context = context
        self._locked_files: list[str] = []

    async def run(self, task: str) -> AgentResult:
        """Exécute les 5 étapes avec retry intelligent sur erreur CHECK."""
        # Étape 1 — PLAN
        await self.ws.emit_step("PLAN", self.decision.llm)
        plan = await self._step_plan(task)

        # Étape 2 — VERIFY
        await self.ws.emit_step("VERIFY", self.decision.llm)
        self._step_verify(plan)

        # Étape 3 — EXECUTE (+ retry sur CHECK)
        await self.ws.emit_step("EXECUTE", self.decision.llm)
        content, files_modified, tokens = await self._step_execute(task, plan)

        last_attempt = 1
        for attempt in range(1, self.MAX_RETRIES + 1):
            last_attempt = attempt
            await self.ws.emit_step("CHECK", self.decision.llm, attempt=attempt)
            errors = self._step_check(files_modified)

            if not errors:
                break

            if attempt == self.MAX_RETRIES:
                self._release_all_locks()
                raise AgentLoopError(
                    message=f"Lint échoue après {self.MAX_RETRIES} tentatives : {errors[0][:200]}",
                    step="CHECK",
                    attempts=attempt,
                )

            # Retry : on injecte l'erreur dans le prompt
            retry_task = (
                f"{task}\n\n"
                f"ERREUR LINT (tentative {attempt}) — corrige ces erreurs :\n"
                + "\n".join(errors[:3])
            )
            content, files_modified, tokens = await self._step_execute(retry_task, plan)

        # Étape 5 — CONFIRM
        await self.ws.emit_step("CONFIRM", self.decision.llm)
        self._step_confirm(files_modified)
        self._release_all_locks()

        return AgentResult(
            content=content,
            files_modified=files_modified,
            tokens=tokens,
            attempts=last_attempt,
        )

    async def _step_plan(self, task: str) -> list[PlanStep]:
        """LLM liste ses intentions — pas de code."""
        prompt = (
            f"TÂCHE : {task}\n\n"
            f"CONTEXTE :\n{self.context}\n\n"
            "Liste EXACTEMENT ce que tu vas faire.\n"
            "Format JSON strict :\n"
            '{"steps": [{"description": "...", "files": [...], "action": "write|read|bash"}]}\n'
            "Ne génère PAS de code dans cette réponse."
        )
        raw = await self.llm.call_with_fallback(
            role=self.decision.role,
            messages=[{"role": "user", "content": prompt}],
        )
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return [PlanStep(**s) for s in data.get("steps", [])]
            except (json.JSONDecodeError, TypeError):
                pass
        # Fallback si JSON malformé : plan minimal
        return [PlanStep(description=task, files=[], action="write")]

    def _step_verify(self, plan: list[PlanStep]) -> None:
        """
        Vérifie que les fichiers cibles ne sont pas verrouillés par un autre LLM.
        Lève AgentLoopError si conflit.
        """
        for step in plan:
            for filepath in step.files:
                locked_by = self.file_lock.who_has(filepath)
                if locked_by and locked_by != self.decision.llm:
                    raise AgentLoopError(
                        message=f"{filepath} est verrouillé par {locked_by}",
                        step="VERIFY",
                        attempts=0,
                    )

    async def _step_execute(
        self, task: str, plan: list[PlanStep]
    ) -> tuple[str, list[str], int]:
        """
        Génère le code et verrouille les fichiers cibles.
        L'orchestrateur est responsable d'écrire physiquement les fichiers.
        """
        files_modified = []
        prompt = (
            f"TÂCHE : {task}\n\n"
            f"CONTEXTE :\n{self.context}\n\n"
            "Génère le code complet pour chaque fichier à modifier.\n"
            "Inclus le chemin du fichier en commentaire au début de chaque bloc."
        )
        response = await self.llm.call_with_fallback(
            role=self.decision.role,
            messages=[{"role": "user", "content": prompt}],
        )
        # Verrouiller les fichiers write du plan
        for step in plan:
            if step.action == "write":
                for filepath in step.files:
                    acquired = await self.file_lock.acquire(filepath, self.decision.llm)
                    if acquired and filepath not in self._locked_files:
                        self._locked_files.append(filepath)
                        files_modified.append(filepath)
        return response, files_modified, 0  # tokens = 0 (litellm n'expose pas toujours)

    def _step_check(self, files_modified: list[str]) -> list[str]:
        """
        Lint : ruff pour .py, eslint pour .ts/.tsx/.js/.jsx.
        Retourne la liste des erreurs (vide = OK).
        Timeout 30s par fichier.
        """
        errors = []
        for filepath in files_modified:
            if filepath.endswith(".py"):
                result = subprocess.run(
                    ["ruff", "check", filepath, "--output-format=text"],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    errors.append(result.stdout[:500])
            elif filepath.endswith((".ts", ".tsx", ".js", ".jsx")):
                result = subprocess.run(
                    ["npx", "eslint", filepath, "--format=compact"],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    errors.append(result.stdout[:500])
        return errors

    def _step_confirm(self, files_modified: list[str]) -> str:
        """Génère un git diff pour les fichiers modifiés (affiché dans l'UI)."""
        diffs = []
        for filepath in files_modified:
            result = subprocess.run(
                ["git", "diff", filepath],
                capture_output=True, text=True,
            )
            if result.stdout:
                diffs.append(result.stdout[:2000])
        return "\n".join(diffs)

    def _release_all_locks(self) -> None:
        """Libère tous les verrous acquis par cette instance."""
        for filepath in self._locked_files:
            asyncio.create_task(self.file_lock.release(filepath, self.decision.llm))
        self._locked_files.clear()
```

- [ ] **Step 4.4 : Ajouter `who_has()` à FileLock (Plan 1 ne l'a pas)**

```python
# Ajouter dans backend/file_lock.py après la méthode release() :

    def who_has(self, filepath: str) -> Optional[str]:
        """Retourne le LLM qui tient le verrou, ou None."""
        return self._locks.get(filepath)
```

- [ ] **Step 4.5 : Vérifier que les tests passent**

```bash
source venv/bin/activate && pytest tests/backend/test_agent_loop.py -v
```

Expected :
```
PASSED tests/backend/test_agent_loop.py::test_agent_loop_run_success_no_lint_errors
PASSED tests/backend/test_agent_loop.py::test_agent_loop_retry_on_lint_error
PASSED tests/backend/test_agent_loop.py::test_agent_loop_raises_after_3_retries
PASSED tests/backend/test_agent_loop.py::test_agent_loop_verify_raises_on_locked_file
PASSED tests/backend/test_agent_loop.py::test_agent_loop_emits_ws_steps
5 passed
```

- [ ] **Step 4.6 : Commit**

```bash
git add backend/agent_loop.py backend/file_lock.py tests/backend/test_agent_loop.py
git commit -m "feat: add AgentLoop with 5-step PLAN/VERIFY/EXECUTE/CHECK/CONFIRM and 3-retry lint"
```

---

## Task 5 : Orchestrateur central (orchestrator.py)

**Files:**
- Create: `backend/orchestrator.py`
- Create: `tests/backend/test_orchestrator.py`

- [ ] **Step 5.1 : Écrire les tests orchestrator**

```python
# tests/backend/test_orchestrator.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.orchestrator import Orchestrator, OrchestratorRequest, OrchestratorResponse
from backend.models import LLMRole
from backend.roadmap import ProjectRoadmap


def _make_orchestrator(tmp_path) -> Orchestrator:
    llm_manager = AsyncMock()
    ws_streamer = AsyncMock()
    ws_streamer.emit_routing = AsyncMock()
    ws_streamer.emit_step = AsyncMock()
    file_lock = MagicMock()
    file_lock.who_has = MagicMock(return_value=None)
    file_lock.acquire = AsyncMock(return_value=True)
    file_lock.release = AsyncMock()
    task_queue = MagicMock()
    orch = Orchestrator(
        llm_manager=llm_manager,
        ws_streamer=ws_streamer,
        file_lock=file_lock,
        task_queue=task_queue,
        db_path=str(tmp_path / "test.db"),
    )
    return orch


@pytest.mark.asyncio
async def test_orchestrator_handle_returns_response(tmp_path):
    """handle() retourne OrchestratorResponse avec le bon LLM."""
    orch = _make_orchestrator(tmp_path)
    await orch.long_memory.init()

    mock_result = MagicMock()
    mock_result.content = "Voici le code corrigé"
    mock_result.tokens = 150
    orch.task_queue.submit = AsyncMock(return_value=mock_result)

    request = OrchestratorRequest(
        user_id="user-1",
        prompt="Corrige un typo dans bouton.py",
    )
    response = await orch.handle(request)

    assert isinstance(response, OrchestratorResponse)
    assert response.content == "Voici le code corrigé"
    assert response.tokens == 150
    assert response.duration > 0


@pytest.mark.asyncio
async def test_orchestrator_emits_routing_event(tmp_path):
    """handle() appelle ws.emit_routing avec la décision de routage."""
    orch = _make_orchestrator(tmp_path)
    await orch.long_memory.init()

    mock_result = MagicMock(content="Code", tokens=50)
    orch.task_queue.submit = AsyncMock(return_value=mock_result)

    await orch.handle(OrchestratorRequest(user_id="u1", prompt="Fix typo"))

    orch.ws.emit_routing.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_mention_override(tmp_path):
    """@deepseek dans la requête → routage forcé vers deepseek."""
    orch = _make_orchestrator(tmp_path)
    await orch.long_memory.init()

    mock_result = MagicMock(content="Architecture plan", tokens=300)
    orch.task_queue.submit = AsyncMock(return_value=mock_result)

    request = OrchestratorRequest(
        user_id="u1",
        prompt="Refactore tout le module auth",
        mention="deepseek",
    )
    response = await orch.handle(request)
    assert "deepseek" in response.llm_used


@pytest.mark.asyncio
async def test_orchestrator_set_and_clear_roadmap(tmp_path):
    """set_roadmap() active le mode projet, clear_roadmap() le désactive."""
    orch = _make_orchestrator(tmp_path)
    assert orch.roadmap is None

    rm = ProjectRoadmap(project="mon-projet")
    await orch.set_roadmap(rm)
    assert orch.roadmap is not None
    assert orch.roadmap.project == "mon-projet"

    await orch.clear_roadmap()
    assert orch.roadmap is None
```

- [ ] **Step 5.2 : Vérifier que les tests échouent**

```bash
source venv/bin/activate && pytest tests/backend/test_orchestrator.py -v 2>&1 | head -10
```

Expected : `ImportError: cannot import name 'Orchestrator'`

- [ ] **Step 5.3 : Implémenter backend/orchestrator.py**

```python
# backend/orchestrator.py
"""
Orchestrateur central — seul point d'entrée pour toute tâche.

Règle fondamentale : les LLMs ne se parlent JAMAIS directement.
Ils déposent des demandes à l'orchestrateur.
L'orchestrateur dispatch, valide, écrit les fichiers et met à jour la roadmap.
"""
import time
from dataclasses import dataclass
from typing import Optional

from backend.models import LLMRole
from backend.llm_manager import LLMManager
from backend.router_engine import RouterEngine
from backend.agent_loop import AgentLoop, AgentLoopError
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
    """
    Chef d'orchestre. Une seule instance par processus FastAPI.
    
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
        """
        Point d'entrée principal pour toute requête utilisateur.
        
        1. Router choisit le LLM
        2. Émet l'event routing vers l'UI
        3. Construit le contexte ciblé
        4. Exécute via agent loop dans la task queue
        5. Sauvegarde la décision en mémoire longue
        """
        start = time.time()

        # 1. Routing
        decision = self.router.route(
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

        # 4. Agent loop dans la task queue (1 tâche à la fois par LLM)
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

        # 5. Mémoire longue
        await self.long_memory.save_decision(
            session_id=self.short_memory.session_id,
            llm=decision.llm,
            dtype="routing",
            content=result.content[:500],
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

    async def set_roadmap(self, roadmap: ProjectRoadmap) -> None:
        """Active le mode projet avec une roadmap."""
        self.roadmap = roadmap

    async def clear_roadmap(self) -> None:
        """Désactive le mode projet (retour au mode conversation)."""
        self.roadmap = None
```

- [ ] **Step 5.4 : Vérifier que les tests passent**

```bash
source venv/bin/activate && pytest tests/backend/test_orchestrator.py -v
```

Expected :
```
PASSED tests/backend/test_orchestrator.py::test_orchestrator_handle_returns_response
PASSED tests/backend/test_orchestrator.py::test_orchestrator_emits_routing_event
PASSED tests/backend/test_orchestrator.py::test_orchestrator_mention_override
PASSED tests/backend/test_orchestrator.py::test_orchestrator_set_and_clear_roadmap
4 passed
```

- [ ] **Step 5.5 : Commit**

```bash
git add backend/orchestrator.py tests/backend/test_orchestrator.py
git commit -m "feat: add Orchestrator — single entry point for all LLM tasks"
```

---

## Task 6 : System prompts MD par LLM

**Files:**
- Create: `backend/prompts/system_minimax.md`
- Create: `backend/prompts/system_deepseek_r1.md`
- Create: `backend/prompts/system_codestral.md`
- Create: `backend/prompts/system_gemini_pro.md`
- Create: `backend/prompts/system_gemini_flash.md`

Pas de tests automatisés ici — les prompts sont des fichiers texte validés à l'usage.

- [ ] **Step 6.1 : Créer le dossier prompts**

```bash
mkdir -p backend/prompts
touch backend/prompts/__init__.py
```

- [ ] **Step 6.2 : Créer system_minimax.md**

```markdown
# Règles absolues — MiniMax M2.5 (Coding principal)

## AVANT TOUTE MODIFICATION
1. Lis ENTIÈREMENT le fichier cible avant de toucher quoi que ce soit
2. Grep tous les appelants de chaque fonction que tu modifies
3. Vérifie que la dépendance n'existe pas déjà (codebase + roadmap)
4. Liste les fichiers qui seront touchés — un à la fois

## FORMAT RÉPONSE OBLIGATOIRE
- Commence par : `## Fichiers modifiés : [liste]`
- Ensuite : diff propre avec contexte minimal (±3 lignes)
- Termine par : `## Vérifications effectuées : [liste]`

## INTERDICTIONS ABSOLUES
- Créer un fichier si le code peut aller dans un existant
- Supposer qu'une fonction existe sans avoir fait grep
- Modifier plus d'un fichier par réponse sans confirmation explicite
- Ignorer les entrées du champ `do_not_touch` de la roadmap
- Réécrire un fichier entier quand seules 3 lignes changent
- Ajouter des imports inutiles

## STYLE CODE
- PEP 8 strict — ruff doit passer sans warnings
- Type hints sur toutes les fonctions publiques
- Docstring uniquement si la logique n'est pas évidente
- Pas de commentaires qui répètent le code
```

- [ ] **Step 6.3 : Créer system_deepseek_r1.md**

```markdown
# Règles absolues — DeepSeek R1 (Architecture et raisonnement)

## AVANT TOUTE ANALYSE
1. Demande le contexte complet si manquant (roadmap, décisions passées)
2. Identifie les contraintes non-négociables (performance, sécu, compatibilité)
3. Vérifie les décisions déjà prises dans la roadmap — ne pas revenir dessus
   sans raison explicite

## FORMAT RÉPONSE OBLIGATOIRE
Structure chaque réponse en 4 blocs :

### PLAN
Ce que je propose de faire, étape par étape.

### TRADE-OFFS
| Option A | Option B | Recommandation |
|----------|----------|----------------|
| ...      | ...      | **Option A — raison** |

### DÉCISION
Une seule décision claire. Pas de "ça dépend" sans suite.

### RATIONALE
Pourquoi ce choix. Quand le revisiter. Ce qu'on sacrifie.

## INTERDICTIONS ABSOLUES
- Proposer plus de 3 options (paralysie de décision)
- Laisser une question ouverte sans recommandation
- Suggérer de l'over-engineering (YAGNI)
- Modifier du code existant hors de la tâche demandée
- Ignorer les décisions architecturales déjà enregistrées
```

- [ ] **Step 6.4 : Créer system_codestral.md**

```markdown
# Règles absolues — Codestral 2 (Tests unitaires)

## AVANT D'ÉCRIRE DES TESTS
1. Lis l'implémentation complète que tu testes
2. Identifie tous les chemins : happy path, edge cases, erreurs
3. Vérifie les tests déjà écrits — pas de doublons
4. Confirme le framework de test attendu (pytest / jest / vitest)

## FORMAT RÉPONSE OBLIGATOIRE
- Commence par : `## Couverture prévue : X% (estimation)`
- Un test = une assertion principale
- Nommage strict : `test_<fonction>_<condition>_<résultat_attendu>()`
- Exemples : `test_login_with_wrong_password_returns_401()`
             `test_create_user_with_duplicate_email_raises_validation_error()`

## RÈGLES TESTS
- Coverage minimum : 80% du fichier testé
- Pas de mocks si le test peut utiliser une vraie implémentation légère
- Pas de fixtures globales qui cachent le setup du test
- Chaque test doit pouvoir tourner seul (`pytest -k test_name`)
- Pas de `time.sleep()` dans les tests — utilise des mocks pour les timeouts

## INTERDICTIONS ABSOLUES
- Tests qui testent les mocks plutôt que le code réel
- Tests sans assertion (`assert True` interdit)
- Dépendances inter-tests (ordre d'exécution ne doit pas compter)
- Tests de plus de 30 lignes (si plus long → découper)
```

- [ ] **Step 6.5 : Créer system_gemini_pro.md**

```markdown
# Règles absolues — Gemini 2.5 Pro (Analyse longue et review CdC)

## AVANT TOUTE ANALYSE
1. Utilise ta fenêtre de contexte longue (1M tokens) pour tout lire avant de répondre
2. Ne résume pas ce que l'utilisateur vient de dire — il sait ce qu'il a dit
3. Identifie les incohérences, trous, et hypothèses implicites

## FORMAT RÉPONSE OBLIGATOIRE
Structure chaque réponse :

### POINTS CRITIQUES (prioritaires)
- [CRITIQUE] Ce qui bloque ou casse le design

### POINTS IMPORTANTS (à adresser)
- [IMPORTANT] Ce qui mérite discussion

### SUGGESTIONS (optionnelles)
- [SUGGESTION] Ce qui améliorerait mais n'est pas bloquant

### LISTE EXHAUSTIVE
Checklist complète de ce qui a été vérifié.

## INTERDICTIONS ABSOLUES
- Valider un CdC avec des trous sans les signaler
- Proposer une solution sans avoir analysé l'existant
- Répéter les informations sans valeur ajoutée
- Recommander une technologie non demandée sans justification claire
```

- [ ] **Step 6.6 : Créer system_gemini_flash.md**

```markdown
# Règles absolues — Gemini 2.5 Flash (Routing et tâches rapides)

## RÔLE
Tu es le routeur rapide du système. Ton seul rôle est de classifier les
requêtes et retourner une décision de routage en JSON.

## FORMAT RÉPONSE OBLIGATOIRE — JSON UNIQUEMENT
```json
{
  "score": 3,
  "level": "simple",
  "mode": "local",
  "llm": "minimax/minimax-m2.5",
  "reason": "Fix simple — un seul fichier, pas d'impact architectural"
}
```

Scores :
- 1-4 : simple → minimax seul
- 5-7 : medium → minimax + gemini flash review
- 8-10 : complex → r1 + minimax + codestral + gemini pro

## INTERDICTIONS ABSOLUES
- Répondre autre chose que du JSON
- Générer du code
- Poser des questions
- Dépasser 200 tokens dans ta réponse
```

- [ ] **Step 6.7 : Commit**

```bash
git add backend/prompts/
git commit -m "feat: add 5 LLM system prompts (minimax, deepseek-r1, codestral, gemini-pro, gemini-flash)"
```

---

## Task 7 : Intégrer l'orchestrateur dans main.py (Plan 1)

**Files:**
- Modify: `backend/main.py`

Plan 1 a créé `main.py` avec `create_app()`. On ajoute l'orchestrateur dans le lifespan et une route `/chat`.

- [ ] **Step 7.1 : Lire le main.py existant**

```bash
cat backend/main.py
```

- [ ] **Step 7.2 : Ajouter le lifespan avec orchestrateur**

Ajouter dans `backend/main.py` après les imports existants :

```python
# Ajout des imports nécessaires
from contextlib import asynccontextmanager
from backend.orchestrator import Orchestrator, OrchestratorRequest
from backend.memory import LongTermMemory

# Remplacer la fonction create_app existante par cette version étendue :

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise et nettoie les ressources au démarrage/arrêt."""
    # Démarrage
    db_path = app.state.db_path if hasattr(app.state, "db_path") else "localcoder.db"
    mem = LongTermMemory(db_path=db_path)
    await mem.init()
    app.state.orchestrator = Orchestrator(
        llm_manager=app.state.llm_manager,
        ws_streamer=app.state.ws_streamer,
        file_lock=app.state.file_lock,
        task_queue=app.state.task_queue,
        db_path=db_path,
    )
    yield
    # Arrêt — rien à faire (SQLite se ferme proprement)


# Ajouter dans create_app() après les routes existantes :

@app.post("/chat")
async def chat(request: dict) -> dict:
    """
    Endpoint principal : reçoit un prompt, retourne la réponse LLM.
    Body: {"prompt": "...", "mention": null, "file_count": 0}
    """
    orch: Orchestrator = app.state.orchestrator
    req = OrchestratorRequest(
        user_id="default",
        prompt=request["prompt"],
        file_count=request.get("file_count", 0),
        mention=request.get("mention"),
    )
    response = await orch.handle(req)
    return {
        "content": response.content,
        "llm": response.llm_used,
        "tokens": response.tokens,
        "duration": response.duration,
        "reason": response.routing_reason,
    }
```

- [ ] **Step 7.3 : Vérifier que tous les tests passent encore**

```bash
source venv/bin/activate && pytest tests/ -v --tb=short
```

Expected : Tous les tests de Plan 1 + Plan 2 passent (pas de régression).

- [ ] **Step 7.4 : Commit**

```bash
git add backend/main.py
git commit -m "feat: wire orchestrator into FastAPI lifespan and add /chat endpoint"
```

---

## Task 8 : Vérification finale Plan 2

- [ ] **Step 8.1 : Lancer tous les tests Plan 2**

```bash
source venv/bin/activate && pytest tests/backend/ -v --tb=short 2>&1 | tail -20
```

Expected : 28+ tests passent (Plan 1 : 19 tests + Plan 2 : 29 tests min).

- [ ] **Step 8.2 : Vérifier l'arborescence des fichiers créés**

```bash
find backend/ -name "*.py" -o -name "*.md" | sort
```

Expected :
```
backend/__init__.py
backend/agent_loop.py
backend/context_builder.py
backend/file_lock.py
backend/llm_manager.py
backend/main.py
backend/memory.py
backend/models.py
backend/orchestrator.py
backend/prompts/__init__.py
backend/prompts/system_codestral.md
backend/prompts/system_deepseek_r1.md
backend/prompts/system_gemini_flash.md
backend/prompts/system_gemini_pro.md
backend/prompts/system_minimax.md
backend/roadmap.py
backend/router_engine.py
backend/task_queue.py
backend/ws_streamer.py
```

- [ ] **Step 8.3 : Commit final**

```bash
git add .
git commit -m "chore: Plan 2 complete — intelligence layer fully tested and integrated"
```

---

*Plan 2 terminé — 28 tests, Intelligence Layer complète. Passer à Plan 3 : UI Tauri + React.*
