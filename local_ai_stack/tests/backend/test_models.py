import pytest
from backend.models import (
    LLMRole, MessageType, LLMMessage, RoutingDecision,
    AgentAction, TaskStatus, LLMConfig, WSEvent
)


def test_llm_role_values():
    assert LLMRole.CODING.value == "coding"
    assert LLMRole.ARCHITECTURE.value == "architecture"
    assert LLMRole.ANALYSIS.value == "analysis"
    assert LLMRole.TESTING.value == "testing"
    assert LLMRole.ROUTING.value == "routing"


def test_message_type_values():
    assert MessageType.DECISION.value == "decision"
    assert MessageType.QUESTION.value == "question"
    assert MessageType.RESULT.value == "result"
    assert MessageType.WARNING.value == "warning"
    assert MessageType.CONTEXT.value == "context"


def test_task_status_values():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.IN_PROGRESS.value == "in_progress"
    assert TaskStatus.DONE.value == "done"
    assert TaskStatus.FAILED.value == "failed"
    assert TaskStatus.BLOCKED.value == "blocked"


def test_llm_config_defaults():
    config = LLMConfig(id="minimax/minimax-m2.5", name="MiniMax M2.5", role=LLMRole.CODING)
    assert config.enabled is True
    assert config.rpm == 60


def test_llm_message_creation():
    msg = LLMMessage(
        session_id="sess-1",
        from_llm="minimax",
        to_llm="deepseek",
        type=MessageType.QUESTION,
        content="Comment splitter auth.py ?",
    )
    assert msg.from_llm == "minimax"
    assert msg.replied is False


def test_routing_decision_creation():
    decision = RoutingDecision(
        prompt="Corrige le typo",
        score=2,
        llm="minimax/minimax-m2.5",
        role=LLMRole.CODING,
        mode="simple",
        reason="Fix simple",
    )
    assert decision.score == 2
    assert decision.mode == "simple"


def test_agent_action_creation():
    action = AgentAction(
        llm="minimax",
        step="PLAN",
        detail="Lister les fichiers à modifier",
    )
    assert action.llm == "minimax"
    assert action.step == "PLAN"


def test_ws_event_serialization():
    event = WSEvent(
        type="routing_decision",
        data={"llm": "minimax", "score": 5},
        session_id="sess-1",
    )
    dumped = event.model_dump(mode="json")
    assert dumped["type"] == "routing_decision"
    assert dumped["data"]["llm"] == "minimax"


def test_ws_event_empty_session():
    """WSEvent avec session_id='system' pour les broadcasts globaux."""
    event = WSEvent(type="sys_stats", data={"cpu": 50}, session_id="system")
    assert event.session_id == "system"
