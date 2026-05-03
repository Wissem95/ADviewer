"""Fixture ScriptedLLM (Plan 5A Task 14).

Permet de scripter les réponses de litellm.acompletion par stage du pipeline.
La détection se fait via le system prompt : chaque prompt commence par
``# Étape N — XYZ``, on extrait ``XYZ`` et on retourne la prochaine réponse
de la liste pour cette étape.

Usage::

    scripted = ScriptedLLM({
        "ESTIMATE": [
            ScriptedLLM.text('{"classification":"simple",...}'),
        ],
        "INTAKE": [
            ScriptedLLM.text('{"prompt_cleaned":"...","target_files_hint":[]}'),
        ],
        "GROUND": [
            ScriptedLLM.text("GROUNDED_CONTEXT\\nfiles read"),
        ],
        "EXECUTE": [
            ScriptedLLM.tool_call("c1", "create_file",
                                  '{"path":"hello.py","content":"print(1)"}'),
            ScriptedLLM.text("EXECUTE_DONE\\nhello.py créé"),
        ],
    })
    with patch("backend.pipeline.stage_X_xxx.acompletion",
               side_effect=scripted.acompletion):
        ...

Le ScriptedLLM ne touche pas au réseau.
"""
import re
from types import SimpleNamespace
from typing import Any, Optional


class ScriptedLLM:
    """Mock litellm.acompletion qui retourne des réponses pré-scriptées par stage."""

    _STAGE_RE = re.compile(r"^#\s*Étape\s*\d+\s*[—-]\s*(\w+)", re.MULTILINE)

    def __init__(self, stage_responses: dict[str, list[Any]]):
        # Clés normalisées en uppercase pour matcher la regex.
        self.stage_responses = {k.upper(): list(v) for k, v in stage_responses.items()}
        self.calls_made: list[dict] = []

    @staticmethod
    def text(content: str) -> SimpleNamespace:
        """Construit une réponse "message texte" sans tool_calls."""
        msg = SimpleNamespace(
            content=content,
            tool_calls=None,
            model_dump=lambda: {"role": "assistant", "content": content},
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    @staticmethod
    def tool_call(call_id: str, name: str, arguments_json: str) -> SimpleNamespace:
        """Construit une réponse avec un seul tool_call."""
        tc = SimpleNamespace(
            id=call_id,
            function=SimpleNamespace(name=name, arguments=arguments_json),
        )
        msg = SimpleNamespace(
            content="",
            tool_calls=[tc],
            model_dump=lambda: {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {"name": name, "arguments": arguments_json},
                    }
                ],
            },
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    def _detect_stage(self, messages: list[dict]) -> Optional[str]:
        """Récupère le nom de stage depuis le system prompt."""
        if not messages:
            return None
        system = messages[0]
        if isinstance(system, dict) and system.get("role") == "system":
            content = system.get("content", "")
            match = self._STAGE_RE.search(content)
            if match:
                return match.group(1).upper()
        return None

    async def acompletion(self, **kwargs) -> SimpleNamespace:
        """Drop-in replacement pour litellm.acompletion."""
        messages = kwargs.get("messages", [])
        stage = self._detect_stage(messages)
        self.calls_made.append({"stage": stage, "model": kwargs.get("model")})

        if stage is None or stage not in self.stage_responses:
            raise RuntimeError(
                f"ScriptedLLM: pas de réponse scriptée pour stage={stage!r}"
            )

        queue = self.stage_responses[stage]
        if not queue:
            raise RuntimeError(
                f"ScriptedLLM: file vide pour stage={stage!r} "
                f"(appels deja effectues: {len(self.calls_made)})"
            )
        return queue.pop(0)
