import pytest
from backend.router_engine import RouterEngine
from backend.models import LLMRole


@pytest.fixture
def router(tmp_path):
    """RouterEngine avec DB temporaire."""
    db_path = str(tmp_path / "router.db")
    return RouterEngine(db_path=db_path)


@pytest.mark.asyncio
async def test_route_simple_task(router):
    """Tâche simple (typo) → MiniMax, mode simple, score ≤ 4."""
    await router.init_db()
    decision = await router.route("Corrige le typo dans le bouton login")
    assert decision.llm == "minimax/minimax-m2.5"
    assert decision.mode == "simple"
    assert decision.role == LLMRole.CODING


@pytest.mark.asyncio
async def test_route_medium_task(router):
    """Tâche medium (optimisation) → MiniMax, mode medium."""
    await router.init_db()
    decision = await router.route("Optimise les performances du dashboard")
    assert decision.mode == "medium"
    assert decision.role == LLMRole.CODING


@pytest.mark.asyncio
async def test_route_complex_refactor(router):
    """Refacto globale → mode multi_agent, score élevé."""
    await router.init_db()
    decision = await router.route("Refactore tout le module d'authentification")
    assert decision.mode == "multi_agent"
    assert decision.score >= 7


@pytest.mark.asyncio
async def test_route_mention_override_deepseek(router):
    """@deepseek force le routage vers DeepSeek peu importe le score."""
    await router.init_db()
    decision = await router.route("Corrige le typo", mention="deepseek")
    assert "deepseek" in decision.llm.lower()
    assert decision.role == LLMRole.ARCHITECTURE


@pytest.mark.asyncio
async def test_route_mention_override_minimax(router):
    """@minimax force le routage vers MiniMax."""
    await router.init_db()
    decision = await router.route(
        "Refactore tout le module auth", mention="minimax"
    )
    assert decision.llm == "minimax/minimax-m2.5"


@pytest.mark.asyncio
async def test_route_project_keyword_forces_multi_agent(router):
    """Mot-clé projet ('crée une app') → mode multi_agent forcé."""
    await router.init_db()
    decision = await router.route("Crée une app de gestion de tâches avec auth")
    assert decision.mode == "multi_agent"
    assert decision.score >= 8


@pytest.mark.asyncio
async def test_route_file_count_boosts_score(router):
    """file_count > 5 boost le score minimum."""
    await router.init_db()
    decision = await router.route(
        "Corrige les imports dans les fichiers", file_count=8
    )
    assert decision.score >= 6


@pytest.mark.asyncio
async def test_save_and_get_feedback(router):
    """Un feedback sauvegardé peut être retrouvé pour un prompt similaire."""
    await router.init_db()
    await router.save_feedback(
        prompt="Refacto complète auth",
        routed_to="minimax/minimax-m2.5",
        corrected_to="deepseek/deepseek-r1",
    )
    corrected = await router.get_feedback_correction("Refacto complète auth")
    assert corrected == "deepseek/deepseek-r1"


@pytest.mark.asyncio
async def test_get_feedback_correction_none_if_no_match(router):
    """Aucun feedback → retourne None."""
    await router.init_db()
    result = await router.get_feedback_correction("Prompt totalement nouveau")
    assert result is None


@pytest.mark.asyncio
async def test_route_uses_feedback_to_override(router):
    """Si feedback existe, route() l'utilise pour corriger la décision."""
    await router.init_db()
    await router.save_feedback(
        prompt="Analyse les logs du serveur",
        routed_to="minimax/minimax-m2.5",
        corrected_to="gemini/gemini-2.5-pro",
    )
    decision = await router.route("Analyse les logs du serveur")
    assert decision.llm == "gemini/gemini-2.5-pro"


@pytest.mark.asyncio
async def test_save_feedback_rejects_unknown_llm(router):
    """save_feedback lève ValueError si corrected_to n'est pas un LLM connu."""
    await router.init_db()
    with pytest.raises(ValueError, match="LLM inconnu"):
        await router.save_feedback(
            prompt="test",
            routed_to="minimax/minimax-m2.5",
            corrected_to="fake-llm/that-does-not-exist",
        )
