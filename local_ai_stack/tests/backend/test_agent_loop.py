import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.agent_loop import AgentLoop, AgentLoopError, AgentResult, PlanStep
from backend.models import LLMRole, RoutingDecision
from backend.file_lock import FileLock


def _make_decision(llm: str = "minimax/minimax-m2.5") -> RoutingDecision:
    return RoutingDecision(
        prompt="Fix typo",
        score=2,
        llm=llm,
        role=LLMRole.CODING,
        mode="simple",
        reason="Fix simple",
    )


def _make_loop() -> AgentLoop:
    llm_manager = AsyncMock()
    llm_manager.call_with_fallback = AsyncMock(return_value="Default response")
    file_lock = FileLock()
    ws = AsyncMock()
    ws.emit_step = AsyncMock()
    ws.emit_routing = AsyncMock()
    return AgentLoop(
        llm_manager=llm_manager,
        file_lock=file_lock,
        ws_streamer=ws,
        decision=_make_decision(),
        context="# Contexte minimal",
    )


@pytest.mark.asyncio
async def test_agent_loop_success_no_lint_errors():
    """Run complet sans erreur → AgentResult retourné au 1er essai."""
    loop = _make_loop()
    loop.llm.call_with_fallback.side_effect = [
        '{"steps": [{"description": "Fix typo", "files": [], "action": "write"}]}',
        "# Code corrigé\nprint('hi')",
    ]
    with patch.object(loop, "_step_check", return_value=[]):
        result = await loop.run("Corrige le typo")
    assert isinstance(result, AgentResult)
    assert result.attempts == 1
    assert "Code corrigé" in result.content


@pytest.mark.asyncio
async def test_agent_loop_retry_on_lint_error():
    """Erreur lint à l'essai 1 → retry → succès à l'essai 2."""
    loop = _make_loop()
    # Plan, execute_try1, execute_try2 (retry)
    loop.llm.call_with_fallback.side_effect = [
        '{"steps": [{"description": "Fix", "files": ["auth.py"], "action": "write"}]}',
        "Code buggy",
        "Code corrigé",
    ]
    # Check : erreur puis OK
    check_results = [["ruff: E501 line too long"], []]
    with patch.object(loop, "_step_check", side_effect=check_results):
        result = await loop.run("Fix typo")
    assert result.attempts == 2
    assert "Code corrigé" in result.content


@pytest.mark.asyncio
async def test_agent_loop_raises_after_3_retries():
    """3 erreurs lint consécutives → AgentLoopError levée."""
    loop = _make_loop()
    loop.llm.call_with_fallback.side_effect = [
        '{"steps": [{"description": "Fix", "files": ["auth.py"], "action": "write"}]}',
        "Code buggy 1",
        "Code buggy 2",
        "Code buggy 3",
    ]
    with patch.object(loop, "_step_check", return_value=["ruff: E501"]):
        with pytest.raises(AgentLoopError) as exc_info:
            await loop.run("Fix typo")
    assert exc_info.value.step == "CHECK"
    assert exc_info.value.attempts == 3


@pytest.mark.asyncio
async def test_agent_loop_verify_raises_on_locked_file():
    """Fichier verrouillé par un autre LLM → AgentLoopError en VERIFY."""
    loop = _make_loop()
    # Verrouiller le fichier par un autre LLM
    await loop.file_lock.acquire("auth.py", "deepseek/deepseek-r1")
    loop.llm.call_with_fallback.return_value = (
        '{"steps": [{"description": "Edit", "files": ["auth.py"], "action": "write"}]}'
    )
    with pytest.raises(AgentLoopError) as exc_info:
        await loop.run("Modifie auth.py")
    assert exc_info.value.step == "VERIFY"
    assert "auth.py" in str(exc_info.value)


@pytest.mark.asyncio
async def test_agent_loop_releases_locks_before_retry():
    """Correction C6 : les locks sont libérés avant un retry pour ré-acquérir proprement."""
    loop = _make_loop()
    loop.llm.call_with_fallback.side_effect = [
        '{"steps": [{"description": "Fix", "files": ["auth.py"], "action": "write"}]}',
        "Code try 1",
        "Code try 2",
    ]
    # 1er check échoue, 2e OK
    with patch.object(loop, "_step_check", side_effect=[["ruff E501"], []]):
        result = await loop.run("Fix typo")
    # Après run, le lock doit être libéré (release all locks à la fin)
    assert loop.file_lock.who_has("auth.py") is None
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_agent_loop_emits_all_5_steps():
    """emit_step appelé pour PLAN, VERIFY, EXECUTE, CHECK, CONFIRM."""
    loop = _make_loop()
    loop.llm.call_with_fallback.side_effect = [
        '{"steps": []}',
        "Code OK",
    ]
    with patch.object(loop, "_step_check", return_value=[]):
        await loop.run("Corrige typo")
    # Au moins 5 appels (PLAN, VERIFY, EXECUTE, CHECK, CONFIRM)
    emitted_steps = [call.args[0] for call in loop.ws.emit_step.call_args_list]
    assert "PLAN" in emitted_steps
    assert "VERIFY" in emitted_steps
    assert "EXECUTE" in emitted_steps
    assert "CHECK" in emitted_steps
    assert "CONFIRM" in emitted_steps


@pytest.mark.asyncio
async def test_agent_loop_releases_locks_on_error():
    """Si AgentLoopError levée, les locks acquis sont libérés."""
    loop = _make_loop()
    loop.llm.call_with_fallback.side_effect = [
        '{"steps": [{"description": "X", "files": ["f.py"], "action": "write"}]}',
        "buggy 1", "buggy 2", "buggy 3",
    ]
    with patch.object(loop, "_step_check", return_value=["err"]):
        with pytest.raises(AgentLoopError):
            await loop.run("task")
    # Locks libérés même en cas d'erreur
    assert loop.file_lock.who_has("f.py") is None


def test_plan_step_dataclass():
    """PlanStep peut être créé avec les 3 champs."""
    step = PlanStep(description="Edit auth", files=["auth.py"], action="write")
    assert step.action == "write"
    assert step.files == ["auth.py"]
