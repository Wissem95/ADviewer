"""Mémoire courte (RAM, session) et longue (SQLite persistant).

ShortTermMemory : effacée à la fermeture de Tauri. Max 5 rounds de consultation.
LongTermMemory  : SQLite avec 4 tables — decisions, llm_messages,
                  roadmap_history, routing_feedback.
"""
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import aiosqlite


# ── Mémoire courte ──────────────────────────────────────────────────────────

@dataclass
class ShortTermMemory:
    """Mémoire de session — effacée à la fermeture.

    Max 5 rounds de consultation inter-LLMs pour éviter les boucles infinies.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    active_task: str = ""
    actions: list[dict] = field(default_factory=list)
    file_locks: dict[str, str] = field(default_factory=dict)  # filepath → llm
    messages: list[dict] = field(default_factory=list)
    consultation_rounds: int = 0
    MAX_ROUNDS: int = 5

    def record_action(self, llm: str, action: str, detail: str = "") -> None:
        """Enregistre une action dans le journal temps réel."""
        self.actions.append({
            "llm": llm,
            "action": action,
            "detail": detail,
            "ts": datetime.now().isoformat(),
        })

    def add_message(self, from_llm: str, to_llm: str, mtype: str, content: str) -> None:
        """Ajoute un message inter-LLM. Lève RuntimeError si max rounds atteint."""
        if self.consultation_rounds >= self.MAX_ROUNDS:
            raise RuntimeError(
                f"Max consultation rounds ({self.MAX_ROUNDS}) atteint — "
                "trop de va-et-vient entre LLMs, blocage préventif."
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
        """Réinitialise sans changer le session_id (nouvelle tâche)."""
        self.active_task = ""
        self.actions.clear()
        self.file_locks.clear()
        self.messages.clear()
        self.consultation_rounds = 0


# ── Mémoire longue (SQLite) ──────────────────────────────────────────────────

_CREATE_TABLES_SQL = """
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


def _hash_prompt(prompt: str) -> str:
    """Hash court et déterministe pour indexer les feedbacks."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


class LongTermMemory:
    """Persistance SQLite — survit aux redémarrages.

    Stocke les décisions architecturales, messages inter-LLMs, historique
    roadmap, et feedback de routage pour apprentissage.
    """

    def __init__(self, db_path: str = "localcoder.db"):
        self.db_path = db_path

    async def init(self) -> None:
        """Crée les 4 tables si elles n'existent pas."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_CREATE_TABLES_SQL)
            await db.commit()

    # ── Decisions ────────────────────────────────────────────────────────────

    async def save_decision(
        self,
        session_id: str,
        llm: str,
        dtype: str,
        content: str,
        rationale: str = "",
        files: Optional[list[str]] = None,
    ) -> int:
        """Enregistre une décision architecturale ou de routage."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO decisions
                   (session_id, llm, type, content, rationale, files)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, llm, dtype, content, rationale, json.dumps(files or [])),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def get_recent_decisions(self, limit: int = 20) -> list[dict]:
        """Retourne les décisions valides les plus récentes."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM decisions WHERE valid=1 ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ── Routing feedback ─────────────────────────────────────────────────────

    async def save_routing_feedback(
        self,
        prompt: str,
        routed_to: str,
        corrected_to: str,
        pattern: str = "",
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO routing_feedback
                   (prompt_hash, routed_to, corrected_to, pattern)
                   VALUES (?, ?, ?, ?)""",
                (_hash_prompt(prompt), routed_to, corrected_to, pattern),
            )
            await db.commit()

    async def get_feedback_for(self, prompt: str) -> Optional[str]:
        """Retrouve le LLM corrigé pour un prompt similaire (hash exact)."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT corrected_to FROM routing_feedback
                   WHERE prompt_hash = ? ORDER BY created_at DESC LIMIT 1""",
                (_hash_prompt(prompt),),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    # ── Roadmap history ──────────────────────────────────────────────────────

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

    # ── LLM messages ─────────────────────────────────────────────────────────

    async def save_llm_message(
        self,
        session_id: str,
        from_llm: str,
        to_llm: str,
        mtype: str,
        content: str,
    ) -> None:
        """Persiste un message inter-LLM (pour audit et apprentissage)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO llm_messages
                   (session_id, from_llm, to_llm, type, content)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, from_llm, to_llm, mtype, content),
            )
            await db.commit()
