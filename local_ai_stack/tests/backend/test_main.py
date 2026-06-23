import asyncio
import json

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from backend.main import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(db_path=str(tmp_path / "test.db"))


@pytest_asyncio.fixture
async def client(app):
    """Client HTTP asynchrone avec lifespan FastAPI activé (init_db inclus)."""
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "llms" in data


@pytest.mark.asyncio
async def test_route_endpoint(app):
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/route", json={"prompt": "Corrige un typo"})
    assert resp.status_code == 200
    data = resp.json()
    # Typo = simple → minimax
    assert data["llm"] == "minimax/minimax-m2.5"
    assert data["mode"] == "simple"
    assert data["role"] == "coding"
    assert data["score"] <= 4


@pytest.mark.asyncio
async def test_llms_list_endpoint(client):
    resp = await client.get("/llms")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 5  # 5 LLMs configurés


@pytest.mark.asyncio
async def test_llms_health_endpoint(app):
    """GET /llms/health retourne le health_check des 5 LLMs en parallèle."""
    # Mock health_check sur l'instance LLMManager utilisée par l'app
    async def fake_health(llm_id: str) -> dict:
        return {"ok": True, "latency_ms": 42, "error": None}

    async with app.router.lifespan_context(app):
        app.state.llm_manager.health_check = fake_health
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/llms/health")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    # Les 5 LLMs configurés sont tous présents dans la réponse
    assert "minimax/minimax-m2.5" in data
    assert "gemini/gemini-2.5-pro" in data
    assert "gemini/gemini-2.5-flash" in data
    assert "deepseek/deepseek-r1" in data
    assert "mistral/codestral-2" in data
    for llm_id, result in data.items():
        assert result["ok"] is True
        assert result["latency_ms"] == 42
        assert result["error"] is None


@pytest.mark.asyncio
async def test_disable_enable_llm(client):
    # Disable
    resp = await client.post("/llms/minimax/minimax-m2.5/disable")
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"

    # Enable
    resp = await client.post("/llms/minimax/minimax-m2.5/enable")
    assert resp.status_code == 200
    assert resp.json()["status"] == "enabled"


@pytest.mark.asyncio
async def test_route_with_mention(client):
    resp = await client.post("/route", json={
        "prompt": "Corrige un typo",
        "mention": "deepseek"
    })
    data = resp.json()
    assert "deepseek" in data["llm"]


@pytest.mark.asyncio
async def test_chat_endpoint(app):
    """POST /chat passe par l'orchestrateur et retourne le contenu."""
    transport = ASGITransport(app=app)

    # Helper qui consomme proprement la coroutine passée à submit
    fake_result = MagicMock(content="Voici la réponse", tokens=42, files_modified=[], attempts=1)

    async def _fake_submit(llm, coro):
        coro.close()  # Fermer la coroutine non utilisée pour éviter RuntimeWarning
        return fake_result

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch.object(app.state.orchestrator.task_queue, "submit", new=AsyncMock(side_effect=_fake_submit)):
                resp = await client.post("/chat", json={"prompt": "Corrige un typo"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "Voici la réponse"
    assert data["tokens"] == 42
    assert "minimax" in data["llm"]


@pytest.mark.asyncio
async def test_project_status_inactive(app):
    """GET /project/status retourne active=False par défaut."""
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/project/status")
    assert resp.status_code == 200
    assert resp.json()["active"] is False


@pytest.mark.asyncio
async def test_project_feedback_saved(app):
    """POST /project/feedback persiste la correction."""
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/project/feedback", json={
                "prompt": "Refacto module auth",
                "routed_to": "minimax/minimax-m2.5",
                "corrected_to": "deepseek/deepseek-r1",
            })
    assert resp.status_code == 200
    assert resp.json()["saved"] is True


def test_websocket_chat_handler(tmp_path):
    """WebSocket /ws dispatche type='chat' vers orchestrator et émet chat_response (correction I8)."""
    from fastapi.testclient import TestClient

    app = create_app(db_path=str(tmp_path / "ws.db"))

    # Précharger l'orchestrateur via startup events
    with TestClient(app) as client:
        # Mock task_queue.submit pour ne pas lancer un vrai LLM
        fake_result = MagicMock(
            content="Voici la réponse",
            tokens=42,
            files_modified=[],
            attempts=1,
        )

        async def _fake_submit(llm, coro):
            coro.close()
            return fake_result

        with patch.object(
            client.app.state.orchestrator.task_queue,
            "submit",
            new=AsyncMock(side_effect=_fake_submit),
        ):
            with client.websocket_connect("/ws") as ws:
                # Envoyer un chat
                ws.send_json({"type": "chat", "data": {"prompt": "Corrige un typo"}})
                # Recevoir possiblement plusieurs events (routing_decision, agent_step*, chat_response)
                # On cherche le chat_response
                chat_response = None
                for _ in range(20):  # max 20 messages avant timeout
                    msg = ws.receive_json()
                    if msg.get("type") == "chat_response":
                        chat_response = msg
                        break

                assert chat_response is not None
                assert chat_response["data"]["content"] == "Voici la réponse"
                assert chat_response["data"]["tokens"] == 42
                assert "minimax" in chat_response["data"]["llm"]


def test_websocket_chat_pipeline_path(tmp_path):
    """WS chat avec usePipeline=true → exécute le Pipeline et émet pipeline_done.

    Le Pipeline réel est patché (couvert E2E par test_chat_runner) ; ici on
    valide le câblage handler : task créée, run_chat_pipeline appelé, event
    final relayé au bon client.
    """
    from fastapi.testclient import TestClient
    from backend.pipeline.types import PipelineResult

    app = create_app(db_path=str(tmp_path / "ws_pipe.db"))

    class _FakePipeline:
        async def run(self, ctx):
            return PipelineResult(
                success=True,
                files_modified=["hello.py"],
                total_cost_usd=0.002,
            )

    with TestClient(app) as client:
        with patch("backend.main.make_pipeline", return_value=_FakePipeline()):
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "chat", "data": {
                    "prompt": "Crée hello.py",
                    "usePipeline": True,
                    "mode": "simple",
                    "workspace_root": str(tmp_path),
                }})
                done = None
                for _ in range(20):
                    msg = ws.receive_json()
                    if msg.get("type") == "pipeline_done":
                        done = msg
                        break
                assert done is not None
                assert done["data"]["success"] is True
                assert done["data"]["mode"] == "simple"
                assert "hello.py" in done["data"]["filesModified"]


def test_websocket_chat_pipeline_requires_workspace(tmp_path):
    """usePipeline=true sans workspace_root → event error, pas de crash."""
    from fastapi.testclient import TestClient

    app = create_app(db_path=str(tmp_path / "ws_pipe2.db"))
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "chat", "data": {
                "prompt": "x", "usePipeline": True, "mode": "simple",
            }})
            err = None
            for _ in range(10):
                msg = ws.receive_json()
                if msg.get("type") == "error":
                    err = msg
                    break
            assert err is not None
            assert "workspace_root" in err["data"]["message"]


@pytest.mark.asyncio
async def test_project_start_endpoint_wires_orchestrator(app):
    """POST /project/start appelle orch.run_project_mode et renvoie la roadmap."""
    from backend.roadmap import ProjectRoadmap, Task

    async with app.router.lifespan_context(app):
        mock_roadmap = ProjectRoadmap(project="demo")
        mock_roadmap.tasks.append(
            Task(
                id="T-001",
                title="Login",
                status="pending",
                assigned_to="",
                sprint="Sprint 1",
                github_issue=42,
            )
        )
        app.state.orchestrator.run_project_mode = AsyncMock(return_value=mock_roadmap)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/project/start",
                json={
                    "description": "app todo",
                    "github_token": "gh-token",
                    "repo_name": "u/r",
                },
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project"] == "demo"
    assert data["tasks_count"] == 1
    assert data["tasks"][0]["github_issue"] == 42


@pytest.mark.asyncio
async def test_ci_webhook_emits_ci_status_success(app, monkeypatch):
    """POST /ci-webhook avec conclusion=success broadcast un WSEvent ci_status."""
    # #CRIT4 : pas de secret → il faut l'override explicite en dev local.
    monkeypatch.setenv("LOCALCODER_ALLOW_UNSIGNED_WEBHOOK", "1")
    async with app.router.lifespan_context(app):
        broadcasts: list = []

        async def capture(event):
            broadcasts.append(event)

        app.state.ws_streamer.broadcast = capture

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/ci-webhook",
                headers={"X-GitHub-Event": "check_run"},
                json={
                    "check_run": {
                        "conclusion": "success",
                        "html_url": "https://github.com/u/r/pulls/42",
                        "pull_requests": [{"number": 42}],
                    }
                },
            )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert any(
        e.type == "ci_status" and e.data["ticketId"] == "PR-42"
        and e.data["status"] == "success"
        for e in broadcasts
    )


@pytest.mark.asyncio
async def test_ci_webhook_rejects_bad_signature_returns_401(app, monkeypatch):
    """#CRIT3 : signature invalide → 401 (non-2xx pour que GitHub remonte l'erreur)."""
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s3cr3t")
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/ci-webhook",
                headers={
                    "X-GitHub-Event": "check_run",
                    "X-Hub-Signature-256": "sha256=badsig",
                },
                json={"check_run": {"conclusion": "success", "pull_requests": []}},
            )
    assert resp.status_code == 401
    assert resp.json()["ok"] is False


@pytest.mark.asyncio
async def test_ci_webhook_refuses_unsigned_by_default(app, monkeypatch):
    """#CRIT4 fail-secure : sans secret ni override, on refuse avec 401."""
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("LOCALCODER_ALLOW_UNSIGNED_WEBHOOK", raising=False)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/ci-webhook",
                headers={"X-GitHub-Event": "check_run"},
                json={"check_run": {"conclusion": "success", "pull_requests": []}},
            )
    assert resp.status_code == 401
    assert "webhook unsigned" in resp.json()["error"]


@pytest.mark.asyncio
async def test_ci_webhook_logs_inbound_events(app, monkeypatch, caplog):
    """Logs : webhook valide doit tracer event + conclusion pour debug."""
    import logging

    monkeypatch.setenv("LOCALCODER_ALLOW_UNSIGNED_WEBHOOK", "1")
    caplog.set_level(logging.INFO, logger="backend.main")
    async with app.router.lifespan_context(app):
        app.state.ws_streamer.broadcast = AsyncMock()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/ci-webhook",
                headers={"X-GitHub-Event": "check_run"},
                json={
                    "check_run": {
                        "conclusion": "success",
                        "pull_requests": [{"number": 42}],
                    }
                },
            )
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "check_run" in text
    assert "success" in text
    assert "42" in text


@pytest.mark.asyncio
async def test_ci_webhook_logs_rejected_signature(app, monkeypatch, caplog):
    """Signature invalide → warning loggé avec contexte."""
    import logging

    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s3cr3t")
    caplog.set_level(logging.WARNING, logger="backend.main")
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/ci-webhook",
                headers={
                    "X-GitHub-Event": "check_run",
                    "X-Hub-Signature-256": "sha256=bad",
                },
                json={"check_run": {"conclusion": "success", "pull_requests": []}},
            )
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "signature" in text.lower()


@pytest.mark.asyncio
async def test_ci_webhook_valid_signature_accepted(app, monkeypatch):
    """#CRIT3 miroir : signature correcte → 200."""
    import hashlib
    import hmac as hmac_mod

    secret = "topsecret"
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)

    async with app.router.lifespan_context(app):
        app.state.ws_streamer.broadcast = AsyncMock()
        payload = {"check_run": {"conclusion": "success", "pull_requests": [{"number": 1}]}}
        body = json.dumps(payload).encode()
        sig = "sha256=" + hmac_mod.new(secret.encode(), body, hashlib.sha256).hexdigest()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/ci-webhook",
                headers={
                    "X-GitHub-Event": "check_run",
                    "X-Hub-Signature-256": sig,
                    "Content-Type": "application/json",
                },
                content=body,
            )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_broadcast_sys_stats_emits_cpu_ram():
    """_broadcast_sys_stats émet un event sys_stats puis est annulé proprement."""
    from backend.main import _broadcast_sys_stats
    from backend.ws_streamer import WSStreamer

    streamer = MagicMock(spec=WSStreamer)
    streamer.broadcast = AsyncMock()

    call_count = {"n": 0}

    async def fake_sleep(_seconds):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            # Laisse 1 itération complète, puis annule à la 2e sleep.
            raise asyncio.CancelledError()

    with patch("backend.main.asyncio.sleep", side_effect=fake_sleep):
        task = asyncio.create_task(_broadcast_sys_stats(streamer))
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert streamer.broadcast.await_count >= 1
    event = streamer.broadcast.await_args_list[0][0][0]
    assert event.type == "sys_stats"
    assert "cpuPercent" in event.data
    assert "ramMB" in event.data
