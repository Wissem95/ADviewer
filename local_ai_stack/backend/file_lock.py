# backend/file_lock.py
"""File lock atomique pour empêcher deux LLMs d'écrire le même fichier.

Utilise asyncio.Lock pour garantir que l'opération acquire est atomique
(pas de race condition check-then-set).
"""
import asyncio
from typing import Optional


class FileLock:
    """Lock thread-safe par fichier.

    Correction C7 : import Optional explicite.
    """

    def __init__(self) -> None:
        self._locks: dict[str, str] = {}           # filepath → llm
        self._mutex: asyncio.Lock = asyncio.Lock()  # atomicité

    async def acquire(self, filepath: str, llm: str) -> bool:
        """Acquiert le lock. Retourne True si succès, False si déjà pris par un autre LLM.

        Idempotent : si le même LLM ré-appelle acquire, retourne True.
        """
        async with self._mutex:
            holder = self._locks.get(filepath)
            if holder is None:
                self._locks[filepath] = llm
                return True
            if holder == llm:
                return True  # Idempotent
            return False

    async def release(self, filepath: str, llm: str) -> None:
        """Libère le lock si ce LLM en est le détenteur."""
        async with self._mutex:
            if self._locks.get(filepath) == llm:
                del self._locks[filepath]

    def who_has(self, filepath: str) -> Optional[str]:
        """Retourne le LLM qui détient le lock, ou None."""
        return self._locks.get(filepath)
