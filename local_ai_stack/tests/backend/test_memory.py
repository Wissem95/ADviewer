import pytest
import aiosqlite
from backend.memory import ShortTermMemory, LongTermMemory


# ── ShortTermMemory ───────────────────────────────────────────────────────────

def test_short_memory_initial_state():
    mem = ShortTermMemory()
    assert mem.active_task == ""
    assert mem.actions == []
    assert mem.file_locks == {}
    assert mem.messages == []
    assert mem.consultation_rounds == 0
    assert len(mem.session_id) > 0


def test_short_memory_record_action():
    mem = ShortTermMemory()
    mem.record_action(llm="minimax", action="write", detail="auth.py")
    assert len(mem.actions) == 1
    assert mem.actions[0]["llm"] == "minimax"
    assert mem.actions[0]["action"] == "write"
    assert mem.actions[0]["detail"] == "auth.py"
    assert "ts" in mem.actions[0]


def test_short_memory_add_message_increments_rounds():
    mem = ShortTermMemory()
    mem.add_message("minimax", "deepseek", "question", "Comment splitter auth.py ?")
    assert mem.consultation_rounds == 1
    assert len(mem.messages) == 1
    assert mem.messages[0]["from"] == "minimax"
    assert mem.messages[0]["to"] == "deepseek"
    assert mem.messages[0]["type"] == "question"


def test_short_memory_max_rounds_raises():
    """6e message lève RuntimeError (max 5 rounds)."""
    mem = ShortTermMemory()
    for i in range(5):
        mem.add_message("minimax", "deepseek", "question", f"Q{i}")
    with pytest.raises(RuntimeError, match="Max consultation rounds"):
        mem.add_message("minimax", "deepseek", "question", "Q6")


def test_short_memory_reset_keeps_session_id():
    mem = ShortTermMemory()
    original_id = mem.session_id
    mem.active_task = "T-003"
    mem.record_action("minimax", "write", "auth.py")
    mem.add_message("minimax", "deepseek", "question", "Q")
    mem.reset()
    assert mem.active_task == ""
    assert mem.actions == []
    assert mem.messages == []
    assert mem.consultation_rounds == 0
    assert mem.session_id == original_id  # Préservé


# ── LongTermMemory ────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_memory.db")


@pytest.mark.asyncio
async def test_long_memory_init_creates_all_4_tables(db_path):
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
        files=["auth.py", "auth_core.py"],
    )
    assert rowid >= 1
    decisions = await mem.get_recent_decisions(limit=10)
    assert len(decisions) == 1
    assert decisions[0]["content"] == "auth.py splitté en 3 fichiers"
    assert decisions[0]["llm"] == "deepseek/deepseek-r1"
    assert decisions[0]["rationale"] == "SRP"


@pytest.mark.asyncio
async def test_long_memory_save_feedback_and_retrieve(db_path):
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
    assert await mem.get_feedback_for("Prompt jamais vu") is None


@pytest.mark.asyncio
async def test_long_memory_save_roadmap_history(db_path):
    mem = LongTermMemory(db_path)
    await mem.init()
    await mem.save_roadmap_history(
        project="my-app",
        ticket_id="T-003",
        action="created",
        by="orchestrator",
        detail="Ticket endpoint login",
    )
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM roadmap_history WHERE ticket_id=?", ("T-003",))
        row = await cursor.fetchone()
    assert row["project"] == "my-app"
    assert row["action"] == "created"


@pytest.mark.asyncio
async def test_long_memory_save_llm_message(db_path):
    """llm_messages table : persister les messages inter-LLMs."""
    mem = LongTermMemory(db_path)
    await mem.init()
    await mem.save_llm_message(
        session_id="sess-1",
        from_llm="minimax",
        to_llm="deepseek",
        mtype="question",
        content="Comment splitter auth.py ?",
    )
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM llm_messages WHERE from_llm=?", ("minimax",))
        row = await cursor.fetchone()
    assert row["to_llm"] == "deepseek"
    assert row["type"] == "question"
