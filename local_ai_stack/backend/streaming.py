"""Backend streaming LLM (Plan 5B Task 4).

Helper async qui consomme un litellm streaming et publie chaque token.

Usage typique (depuis un stage)::

    received = []
    async def on_token(t: str) -> None:
        received.append(t)
        await ws.broadcast(WSEvent(type="chat_token", data={"token": t}, ...))

    result = await stream_llm_response(
        llm_id="minimax/minimax-m2.5",
        messages=[{"role": "user", "content": "Hi"}],
        on_token=on_token,
    )
    # result == {"content": "Hello world", "tokens": 12}

Le helper ne touche pas au WebSocket directement : c'est l'appelant qui
décide quoi faire de chaque token via ``on_token``.
"""
from typing import Awaitable, Callable

from litellm import acompletion


async def stream_llm_response(
    *,
    llm_id: str,
    messages: list[dict],
    on_token: Callable[[str], Awaitable[None]],
    temperature: float = 0.2,
    timeout: int = 90,
) -> dict:
    """Stream les tokens d'un LLM et appelle ``on_token`` pour chacun.

    Retourne ``{"content": str, "tokens": int}`` à la fin du stream.

    En cas d'exception (réseau, rate-limit, parsing), elle est propagée
    telle quelle — l'appelant peut décider d'un fallback.
    """
    aiter = await acompletion(
        model=llm_id,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
        stream=True,
    )

    parts: list[str] = []
    async for chunk in aiter:
        delta = chunk.choices[0].delta if chunk.choices else None
        content = getattr(delta, "content", None) if delta is not None else None
        if not content:
            continue
        parts.append(content)
        await on_token(content)

    text = "".join(parts)
    # Heuristique tokens : ~4 chars par token (cohérent avec count_tokens fallback).
    tokens = max(1, len(text) // 4) if text else 0
    return {"content": text, "tokens": tokens}
