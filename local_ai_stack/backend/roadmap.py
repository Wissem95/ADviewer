# backend/roadmap.py
"""ProjectRoadmap — état actuel du projet en mémoire + persistance JSON.

Règle absolue : seul l'orchestrateur appelle les méthodes de modification
(update_task_status, lock_file, add_decision, etc.).
Les LLMs lisent via get_*() en lecture seule (exposé via tool roadmap_read).
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── Entités ──────────────────────────────────────────────────────────────────

@dataclass
class SubTask:
    id: str
    text: str
    done: bool = False


@dataclass
class Task:
    id: str
    title: str
    status: str = "pending"  # "pending" | "in_progress" | "done" | "failed" | "blocked"
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


# ── Roadmap ──────────────────────────────────────────────────────────────────

@dataclass
class ProjectRoadmap:
    """État du projet. Lecture libre, écriture réservée à l'orchestrateur.

    Budget tokens : ~2-3K quand sérialisée pour injection dans un LLM.
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

    # ── Lecture (pour les LLMs via tool roadmap_read) ────────────────────────

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
        """~500 tokens max — décisions pertinentes pour la tâche."""
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

    def get_next_pending_task(self) -> Optional[Task]:
        """Retourne la prochaine tâche pending dont les dépendances sont done."""
        done_ids = {t.id for t in self.tasks if t.status == "done"}
        for t in self.tasks:
            if t.status == "pending" and all(dep in done_ids for dep in t.blocked_by):
                return t
        return None

    # ── Écriture (orchestrateur uniquement) ──────────────────────────────────

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
        self.files_state[filepath] = {
            "status": "modified",
            "by": llm,
            "locked": True,
        }

    def unlock_file(self, filepath: str) -> None:
        if filepath in self.files_state:
            self.files_state[filepath]["locked"] = False

    def add_decision(self, by: str, content: str) -> None:
        self.decisions.append(Decision(by=by, content=content))

    def add_done(self, summary: str) -> None:
        self.done_this_session.append(summary)

    # ── Sérialisation ────────────────────────────────────────────────────────

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
