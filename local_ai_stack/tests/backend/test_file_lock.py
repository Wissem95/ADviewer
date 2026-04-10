import pytest
import asyncio
from backend.file_lock import FileLock


@pytest.mark.asyncio
async def test_file_lock_acquire_success():
    lock = FileLock()
    acquired = await lock.acquire("auth.py", "minimax")
    assert acquired is True
    assert lock.who_has("auth.py") == "minimax"


@pytest.mark.asyncio
async def test_file_lock_acquire_blocks_other_llm():
    lock = FileLock()
    await lock.acquire("auth.py", "minimax")
    refused = await lock.acquire("auth.py", "deepseek")
    assert refused is False
    assert lock.who_has("auth.py") == "minimax"


@pytest.mark.asyncio
async def test_file_lock_same_llm_reacquire():
    """Même LLM peut ré-acquérir son propre lock (idempotent)."""
    lock = FileLock()
    assert await lock.acquire("auth.py", "minimax") is True
    assert await lock.acquire("auth.py", "minimax") is True


@pytest.mark.asyncio
async def test_file_lock_release():
    lock = FileLock()
    await lock.acquire("auth.py", "minimax")
    await lock.release("auth.py", "minimax")
    assert lock.who_has("auth.py") is None


@pytest.mark.asyncio
async def test_file_lock_release_wrong_llm_noop():
    """Release par un autre LLM ne libère pas."""
    lock = FileLock()
    await lock.acquire("auth.py", "minimax")
    await lock.release("auth.py", "deepseek")
    assert lock.who_has("auth.py") == "minimax"


@pytest.mark.asyncio
async def test_file_lock_atomic_concurrent_acquire():
    """Deux acquires simultanés sur le même fichier → un seul réussit."""
    lock = FileLock()
    results = await asyncio.gather(
        lock.acquire("file.py", "minimax"),
        lock.acquire("file.py", "deepseek"),
    )
    # Exactement un True et un False
    assert results.count(True) == 1
    assert results.count(False) == 1
