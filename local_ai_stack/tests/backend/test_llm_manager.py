import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.llm_manager import (
    LLMManager, RateLimiter, FALLBACK_CHAINS, _load_system_prompt
)
from backend.models import LLMRole


def test_rate_limiter_allows_under_limit():
    rl = RateLimiter(rpm=60)
    for _ in range(5):
        assert rl.try_acquire() is True


def test_rate_limiter_blocks_over_limit():
    rl = RateLimiter(rpm=5)
    for _ in range(5):
        rl.try_acquire()
    # 6e appel devrait être bloqué (dépassement)
    assert rl.try_acquire() is False


def test_fallback_chains_defined_for_all_roles():
    """Chaque LLMRole doit avoir une fallback chain définie."""
    assert LLMRole.CODING in FALLBACK_CHAINS
    assert LLMRole.ARCHITECTURE in FALLBACK_CHAINS
    assert LLMRole.ANALYSIS in FALLBACK_CHAINS
    assert LLMRole.TESTING in FALLBACK_CHAINS
    assert LLMRole.ROUTING in FALLBACK_CHAINS
    # MiniMax est le LLM coding principal
    assert FALLBACK_CHAINS[LLMRole.CODING][0] == "minimax/minimax-m2.5"
    # Codestral-2 pour testing (ID unifié)
    assert FALLBACK_CHAINS[LLMRole.TESTING][0] == "mistral/codestral-2"


def test_load_system_prompt_returns_empty_if_missing(tmp_path, monkeypatch):
    """_load_system_prompt retourne '' si fichier absent."""
    # Simuler un dossier prompts vide
    fake_prompts = tmp_path / "prompts"
    fake_prompts.mkdir()
    monkeypatch.setattr("backend.llm_manager.PROMPTS_DIR", fake_prompts)
    assert _load_system_prompt(LLMRole.CODING) == ""


def test_load_system_prompt_returns_content_if_exists(tmp_path, monkeypatch):
    fake_prompts = tmp_path / "prompts"
    fake_prompts.mkdir()
    (fake_prompts / "system_minimax.md").write_text("# Règles MiniMax")
    monkeypatch.setattr("backend.llm_manager.PROMPTS_DIR", fake_prompts)
    content = _load_system_prompt(LLMRole.CODING)
    assert "Règles MiniMax" in content


@pytest.mark.asyncio
async def test_llm_manager_call_with_fallback_success():
    """call_with_fallback retourne le contenu du premier LLM qui répond."""
    manager = LLMManager()

    # Mock litellm.acompletion
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="Hello"))]
    fake_response.usage = MagicMock(total_tokens=50)

    with patch("backend.llm_manager.acompletion", new=AsyncMock(return_value=fake_response)):
        result = await manager.call_with_fallback(
            role=LLMRole.CODING,
            messages=[{"role": "user", "content": "Say hi"}],
        )
    assert result == "Hello"


@pytest.mark.asyncio
async def test_llm_manager_fallback_on_first_failure():
    """Si le 1er LLM échoue, le 2e de la chain est appelé."""
    manager = LLMManager()

    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="Fallback response"))]
    fake_response.usage = MagicMock(total_tokens=30)

    # Premier appel lève exception, deuxième réussit
    call_count = [0]
    async def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("Provider down")
        return fake_response

    with patch("backend.llm_manager.acompletion", side_effect=side_effect):
        result = await manager.call_with_fallback(
            role=LLMRole.CODING,
            messages=[{"role": "user", "content": "Test"}],
        )
    assert result == "Fallback response"
    assert call_count[0] == 2  # Premier a échoué, deuxième a répondu


@pytest.mark.asyncio
async def test_llm_manager_disable_llm():
    """Un LLM désactivé ne devrait pas être appelé."""
    manager = LLMManager()
    manager.disable("minimax/minimax-m2.5")
    assert manager.is_disabled("minimax/minimax-m2.5") is True
    manager.enable("minimax/minimax-m2.5")
    assert manager.is_disabled("minimax/minimax-m2.5") is False


@pytest.mark.asyncio
async def test_llm_manager_injects_system_prompt_when_available(tmp_path, monkeypatch):
    """Si un system prompt MD existe pour le rôle, il est injecté comme premier message."""
    fake_prompts = tmp_path / "prompts"
    fake_prompts.mkdir()
    (fake_prompts / "system_minimax.md").write_text("TU ES MINIMAX")
    monkeypatch.setattr("backend.llm_manager.PROMPTS_DIR", fake_prompts)

    manager = LLMManager()

    captured_messages = []
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="OK"))]
    fake_response.usage = MagicMock(total_tokens=10)

    async def capture(*args, **kwargs):
        captured_messages.append(kwargs.get("messages", []))
        return fake_response

    with patch("backend.llm_manager.acompletion", side_effect=capture):
        await manager.call_with_fallback(
            role=LLMRole.CODING,
            messages=[{"role": "user", "content": "hi"}],
        )

    assert len(captured_messages[0]) == 2  # system + user
    assert captured_messages[0][0]["role"] == "system"
    assert "MINIMAX" in captured_messages[0][0]["content"]
