"""Tools package — outils exposés aux LLMs via tool-calling.

- ``file_ops`` : read/edit/patch/create/delete/list (lecture et écriture).
- ``search`` : grep_codebase (lecture seule).
- ``registry`` : TOOLS_SCHEMA_READ / TOOLS_SCHEMA_WRITE + dispatcher.
- ``exceptions`` : ToolError + PathOutsideWorkspace.
"""
