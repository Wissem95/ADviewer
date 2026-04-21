"""Exceptions exposées par le package ``backend.tools``."""


class ToolError(Exception):
    """Erreur remontée au LLM sous forme de result.error dans la tool_call_result.

    L'orchestrator ne doit PAS crasher sur ces erreurs : il doit les renvoyer
    au LLM pour qu'il puisse corriger son approche dans la prochaine itération
    tool-calling (Stage3Ground, Stage5Execute).
    """

    def __init__(self, message: str, *, stage: str | None = None):
        super().__init__(message)
        self.stage = stage


class PathOutsideWorkspace(ToolError):
    """Refus de sécurité : le path résolu sort du workspace_root.

    Levée par ``file_ops._resolve`` quand le LLM tente un ``../../etc/passwd``
    ou un path absolu hors du projet. Empêche toute exfiltration ou écriture
    hors zone.
    """
