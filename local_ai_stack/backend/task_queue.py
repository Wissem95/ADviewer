# backend/task_queue.py
"""Task queue par LLM — 1 tâche à la fois par LLM, parallèle entre LLMs.

Correction C14 : méthode submit(llm, coro) qui retourne le résultat
directement via Future.
"""
import asyncio
from typing import Any, Coroutine


class LLMTaskQueue:
    """File d'attente par LLM.

    Pour chaque LLM, une asyncio.Queue garantit qu'une seule tâche tourne
    à la fois. Des LLMs différents peuvent tourner en parallèle.
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}
        self._workers: dict[str, asyncio.Task] = {}
        self._mutex = asyncio.Lock()

    def _get_queue(self, llm: str) -> asyncio.Queue:
        if llm not in self._queues:
            self._queues[llm] = asyncio.Queue()
        return self._queues[llm]

    async def _ensure_worker(self, llm: str) -> None:
        """Démarre un worker pour ce LLM s'il n'existe pas encore."""
        async with self._mutex:
            worker = self._workers.get(llm)
            if worker is None or worker.done():
                self._workers[llm] = asyncio.create_task(self._run_worker(llm))

    async def _run_worker(self, llm: str) -> None:
        """Worker — consomme la queue du LLM séquentiellement."""
        queue = self._get_queue(llm)
        while True:
            try:
                item = await queue.get()
            except asyncio.CancelledError:
                return
            coro, future = item
            try:
                result = await coro
                if not future.done():
                    future.set_result(result)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
            finally:
                queue.task_done()

    async def submit(self, llm: str, coro: Coroutine) -> Any:
        """Soumet une coroutine à la queue du LLM et attend son résultat.

        Correction C14 : retourne directement le résultat ou lève l'exception.
        """
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        queue = self._get_queue(llm)
        await queue.put((coro, future))
        await self._ensure_worker(llm)
        return await future

    def pending_count(self, llm: str) -> int:
        """Retourne le nombre de tâches en attente dans la queue du LLM."""
        if llm not in self._queues:
            return 0
        return self._queues[llm].qsize()
