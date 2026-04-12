import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from backend.ws_streamer import WSStreamer
from backend.models import WSEvent, RoutingDecision, LLMRole


def _fake_websocket() -> AsyncMock:
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    ws.accept = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_ws_streamer_connect_returns_session_id():
    streamer = WSStreamer()
    ws = _fake_websocket()
    session_id = await streamer.connect(ws)
    assert isinstance(session_id, str)
    assert len(session_id) > 0
    ws.accept.assert_called_once()


@pytest.mark.asyncio
async def test_ws_streamer_disconnect_removes_session():
    streamer = WSStreamer()
    ws = _fake_websocket()
    session_id = await streamer.connect(ws)
    streamer.disconnect(session_id)
    assert session_id not in streamer._connections


@pytest.mark.asyncio
async def test_ws_streamer_broadcast_sends_to_all():
    streamer = WSStreamer()
    ws1 = _fake_websocket()
    ws2 = _fake_websocket()
    await streamer.connect(ws1)
    await streamer.connect(ws2)

    event = WSEvent(type="test", data={"foo": "bar"}, session_id="system")
    await streamer.broadcast(event)

    ws1.send_text.assert_called_once()
    ws2.send_text.assert_called_once()
    # Vérifier que le JSON envoyé est bien l'event
    sent = json.loads(ws1.send_text.call_args[0][0])
    assert sent["type"] == "test"
    assert sent["data"]["foo"] == "bar"


@pytest.mark.asyncio
async def test_ws_streamer_send_to_specific_session():
    streamer = WSStreamer()
    ws1 = _fake_websocket()
    ws2 = _fake_websocket()
    s1 = await streamer.connect(ws1)
    s2 = await streamer.connect(ws2)

    event = WSEvent(type="private", data={"x": 1}, session_id=s1)
    await streamer.send_to(s1, event)

    ws1.send_text.assert_called_once()
    ws2.send_text.assert_not_called()


@pytest.mark.asyncio
async def test_ws_streamer_emit_step():
    """emit_step envoie un event 'agent_step' avec step, llm, attempt."""
    streamer = WSStreamer()
    ws = _fake_websocket()
    await streamer.connect(ws)

    await streamer.emit_step("PLAN", "minimax/minimax-m2.5", attempt=1)

    ws.send_text.assert_called_once()
    sent = json.loads(ws.send_text.call_args[0][0])
    assert sent["type"] == "agent_step"
    assert sent["data"]["step"] == "PLAN"
    assert sent["data"]["llm"] == "minimax/minimax-m2.5"
    assert sent["data"]["attempt"] == 1


@pytest.mark.asyncio
async def test_ws_streamer_emit_routing_with_decision():
    """emit_routing prend un RoutingDecision et émet 'routing_decision'."""
    streamer = WSStreamer()
    ws = _fake_websocket()
    await streamer.connect(ws)

    decision = RoutingDecision(
        prompt="Fix typo",
        score=2,
        llm="minimax/minimax-m2.5",
        role=LLMRole.CODING,
        mode="simple",
        reason="Fix simple",
    )
    await streamer.emit_routing(decision)

    ws.send_text.assert_called_once()
    sent = json.loads(ws.send_text.call_args[0][0])
    assert sent["type"] == "routing_decision"
    assert sent["data"]["llm"] == "minimax/minimax-m2.5"
    assert sent["data"]["mode"] == "simple"
    assert sent["data"]["reason"] == "Fix simple"


@pytest.mark.asyncio
async def test_ws_streamer_handles_disconnected_client():
    """Si send_text lève WebSocketDisconnect, l'event est simplement ignoré."""
    streamer = WSStreamer()
    ws = _fake_websocket()
    ws.send_text = AsyncMock(side_effect=Exception("disconnected"))
    await streamer.connect(ws)

    event = WSEvent(type="test", data={}, session_id="system")
    # Ne devrait pas lever d'exception
    await streamer.broadcast(event)
