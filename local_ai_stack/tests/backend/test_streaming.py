"""Tests pour backend/streaming.py + LLMManager.call_with_fallback_streaming
(Plan 5B Task 4).

`stream_llm_response(llm_id, messages, on_token, ...)` :
- Appelle ``acompletion(model, messages, stream=True)``.
- Itère sur les chunks via ``async for``.
- Pour chaque chunk dont ``choices[0].delta.content`` est non vide, appelle
  ``await on_token(content)``.
- Retourne ``{"content": str (concaténé), "tokens": int}``.

`LLMManager.call_with_fallback_streaming(role, messages, on_token, ...)` :
- Wrappe `stream_llm_response` avec la fallback chain (si le 1er LLM lève
  une exception au début du stream, on bascule au suivant).
- Mêmes garanties que `call_with_fallback` (rate-limit, désactivation).
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.llm_manager import LLMManager, LLMManagerError
from backend.models import LLMRole
from backend.streaming import stream_llm_response


def _chunk(content: str) -> SimpleNamespace:
    """Construit un chunk litellm avec ``choices[0].delta.content``."""
    delta = SimpleNamespace(content=content)
    choice = SimpleNamespace(delta=delta)
    return SimpleNamespace(choices=[choice])


async def _make_async_iterable(items: list):
    """Helper : transforme une liste en async iterable."""
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_stream_llm_response_calls_on_token_per_chunk():
    chunks = [_chunk("Hel"), _chunk("lo "), _chunk("world")]

    async def fake_acompletion(**kwargs):
        assert kwargs.get("stream") is True
        return _make_async_iterable(chunks)

    received = []

    async def on_token(t: str) -> None:
        received.append(t)

    with patch("backend.streaming.acompletion", side_effect=fake_acompletion):
        result = await stream_llm_response(
            llm_id="minimax/minimax-m2.5",
            messages=[{"role": "user", "content": "hi"}],
            on_token=on_token,
        )

    assert received == ["Hel", "lo ", "world"]
    assert result["content"] == "Hello world"
    assert result["tokens"] >= 1


@pytest.mark.asyncio
async def test_stream_llm_response_skips_empty_chunks():
    chunks = [_chunk(""), _chunk("ok"), _chunk(None)]

    async def fake_acompletion(**kwargs):
        return _make_async_iterable(chunks)

    received = []

    async def on_token(t: str) -> None:
        received.append(t)

    with patch("backend.streaming.acompletion", side_effect=fake_acompletion):
        result = await stream_llm_response(
            llm_id="minimax/minimax-m2.5",
            messages=[{"role": "user", "content": "hi"}],
            on_token=on_token,
        )

    assert received == ["ok"]
    assert result["content"] == "ok"


@pytest.mark.asyncio
async def test_stream_llm_response_propagates_exception():
    async def fake_acompletion(**kwargs):
        raise RuntimeError("network down")

    async def on_token(t: str) -> None:  # pragma: no cover (not called)
        pass

    with patch("backend.streaming.acompletion", side_effect=fake_acompletion):
        with pytest.raises(RuntimeError, match="network down"):
            await stream_llm_response(
                llm_id="minimax/minimax-m2.5",
                messages=[{"role": "user", "content": "hi"}],
                on_token=on_token,
            )


@pytest.mark.asyncio
async def test_llm_manager_streaming_uses_fallback_chain_on_first_failure():
    """Si le 1er LLM lève, on bascule au suivant via fallback chain."""
    received = []

    async def on_token(t: str) -> None:
        received.append(t)

    call_count = {"n": 0}

    async def fake_stream(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("first llm down")
        # 2e appel : succès
        await on_token("hi")
        return {"content": "hi", "tokens": 1}

    manager = LLMManager()

    with patch(
        "backend.llm_manager.stream_llm_response",
        side_effect=fake_stream,
    ):
        result = await manager.call_with_fallback_streaming(
            role=LLMRole.CODING,
            messages=[{"role": "user", "content": "hi"}],
            on_token=on_token,
        )

    assert result["content"] == "hi"
    assert call_count["n"] == 2  # 1er a échoué, 2e a réussi


@pytest.mark.asyncio
async def test_llm_manager_streaming_raises_when_all_fail():
    async def on_token(t: str) -> None:
        pass

    async def fake_stream(**kwargs):
        raise RuntimeError("boom")

    manager = LLMManager()

    with patch(
        "backend.llm_manager.stream_llm_response",
        side_effect=fake_stream,
    ):
        with pytest.raises(LLMManagerError):
            await manager.call_with_fallback_streaming(
                role=LLMRole.CODING,
                messages=[{"role": "user", "content": "hi"}],
                on_token=on_token,
            )


@pytest.mark.asyncio
async def test_llm_manager_streaming_skips_disabled_llm():
    """Un LLM disable() ne doit jamais être tenté."""
    received_models = []

    async def fake_stream(*, llm_id, **kwargs):
        received_models.append(llm_id)
        return {"content": "ok", "tokens": 1}

    manager = LLMManager()
    manager.disable("minimax/minimax-m2.5")

    async def on_token(t):
        pass

    with patch(
        "backend.llm_manager.stream_llm_response",
        side_effect=fake_stream,
    ):
        await manager.call_with_fallback_streaming(
            role=LLMRole.CODING,
            messages=[{"role": "user", "content": "hi"}],
            on_token=on_token,
        )

    assert "minimax/minimax-m2.5" not in received_models
