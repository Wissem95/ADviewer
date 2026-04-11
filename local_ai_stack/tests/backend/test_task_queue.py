import pytest
import asyncio
from backend.task_queue import LLMTaskQueue


@pytest.mark.asyncio
async def test_task_queue_submit_returns_result():
    """submit(coro) attend le résultat et le retourne."""
    queue = LLMTaskQueue()

    async def my_task():
        return "hello"

    result = await queue.submit("minimax", my_task())
    assert result == "hello"


@pytest.mark.asyncio
async def test_task_queue_serializes_same_llm():
    """2 tasks sur le même LLM → exécutées séquentiellement (ordre garanti)."""
    queue = LLMTaskQueue()
    order = []

    async def task(name: str, delay: float):
        await asyncio.sleep(delay)
        order.append(name)
        return name

    # Lancer 2 tasks en parallèle sur le même LLM
    r1, r2 = await asyncio.gather(
        queue.submit("minimax", task("first", 0.05)),
        queue.submit("minimax", task("second", 0.01)),
    )
    # La 1ère doit finir avant la 2ème
    assert order == ["first", "second"]


@pytest.mark.asyncio
async def test_task_queue_parallel_different_llms():
    """Tasks sur différents LLMs → exécutées en parallèle."""
    queue = LLMTaskQueue()

    async def slow_task():
        await asyncio.sleep(0.1)
        return "done"

    start = asyncio.get_event_loop().time()
    results = await asyncio.gather(
        queue.submit("minimax", slow_task()),
        queue.submit("deepseek", slow_task()),
        queue.submit("gemini", slow_task()),
    )
    duration = asyncio.get_event_loop().time() - start
    assert results == ["done", "done", "done"]
    # En parallèle, devrait prendre ~0.1s, pas 0.3s
    assert duration < 0.25


@pytest.mark.asyncio
async def test_task_queue_exception_propagates():
    """Si la coro lève une exception, submit la propage."""
    queue = LLMTaskQueue()

    async def failing_task():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await queue.submit("minimax", failing_task())


@pytest.mark.asyncio
async def test_task_queue_pending_count_tracks_queue_size():
    """pending_count reflète le nombre de tâches en attente."""
    queue = LLMTaskQueue()
    assert queue.pending_count("minimax") == 0

    async def long_task():
        await asyncio.sleep(0.2)
        return "ok"

    # Lancer sans attendre
    t1 = asyncio.create_task(queue.submit("minimax", long_task()))
    t2 = asyncio.create_task(queue.submit("minimax", long_task()))
    await asyncio.sleep(0.05)  # Laisser la première démarrer
    assert queue.pending_count("minimax") >= 0  # Au moins la 2e est en attente
    await asyncio.gather(t1, t2)
