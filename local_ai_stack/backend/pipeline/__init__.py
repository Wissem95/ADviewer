"""Pipeline package — orchestration des 11 étapes du pipeline rigoureux.

Voir ``docs/superpowers/specs/2026-04-20-pipeline-rigoureux.md`` pour la
spec complète. Remplace l'ancien ``AgentLoop`` 5-étapes mono-agent.

Modules :
- ``types`` : PipelineMode, PipelineContext, StageResult, PipelineResult.
- ``base`` : classe abstraite Stage (template method pour events WS).
- ``orchestrator`` : Pipeline qui dispatche les stages selon le mode.
- ``stage_*_*.py`` : un fichier par étape.
"""
