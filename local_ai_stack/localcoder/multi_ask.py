"""Multi-Ask — pose une question aux 3 modeles (Gemini, DeepSeek, Local) en parallele.

Utile pour :
- Decisions d'architecture importantes (comparer 3 avis)
- Debug difficile (3 angles differents)
- Review de code (3 perspectives)

N'ecrit AUCUN fichier — lecture seule, juste pour reflechir.
Utilise litellm (deja installe avec Aider).
"""

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModelResponse:
    model: str
    mode: str              # local, gemini, deepseek
    content: str = ""
    error: str = ""
    duration: float = 0.0
    tokens: int = 0


def _call_model(
    model: str,
    prompt: str,
    system_prompt: str = "",
    timeout: int = 90,
) -> ModelResponse:
    """Appelle un modele via litellm."""
    start = time.time()
    response = ModelResponse(model=model, mode="unknown")

    if "ollama" in model:
        response.mode = "local"
    elif "gemini" in model:
        response.mode = "gemini"
    elif "deepseek" in model:
        response.mode = "deepseek"

    try:
        from litellm import completion

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        result = completion(
            model=model,
            messages=messages,
            timeout=timeout,
            temperature=0.2,
        )

        response.content = result.choices[0].message.content
        if hasattr(result, "usage") and result.usage:
            response.tokens = result.usage.total_tokens or 0

    except Exception as e:
        response.error = str(e)[:300]

    response.duration = time.time() - start
    return response


def ask_all_models(
    prompt: str,
    context_files: list[Path] | None = None,
    system_prompt: str = "",
) -> list[ModelResponse]:
    """Pose la meme question aux 3 modeles en parallele.

    Args:
        prompt: La question.
        context_files: Fichiers a inclure dans le contexte.
        system_prompt: Prompt systeme a appliquer aux 3.

    Returns:
        Liste des 3 reponses (local, gemini, deepseek).
    """
    # Enrichir le prompt avec le contenu des fichiers si fourni
    if context_files:
        context_parts = []
        for f in context_files:
            if f.exists() and f.is_file():
                try:
                    content = f.read_text(errors="ignore")
                    context_parts.append(f"### Fichier: {f.name}\n```\n{content}\n```")
                except (PermissionError, OSError):
                    pass
        if context_parts:
            prompt = "\n\n".join(context_parts) + "\n\n---\n\nQuestion: " + prompt

    # System prompt par defaut
    if not system_prompt:
        system_prompt = (
            "Tu es un developpeur senior expert. Reponds en francais. "
            "Sois direct, concis et pragmatique. Si tu n'es pas sur, dis-le. "
            "Ne jamais inventer une API ou fonction qui n'existe pas."
        )

    # Determiner les modeles disponibles
    models_to_call = []
    models_to_call.append("ollama_chat/qwen2.5-coder:14b")
    if os.environ.get("GEMINI_API_KEY"):
        models_to_call.append("gemini/gemini-2.5-flash")
    if os.environ.get("DEEPSEEK_API_KEY"):
        models_to_call.append("deepseek/deepseek-reasoner")

    # Appels en parallele via threads
    responses: list[ModelResponse | None] = [None] * len(models_to_call)
    threads = []

    def worker(idx: int, model: str):
        responses[idx] = _call_model(model, prompt, system_prompt)

    for i, model in enumerate(models_to_call):
        t = threading.Thread(target=worker, args=(i, model))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    return [r for r in responses if r is not None]


def format_responses(responses: list[ModelResponse]) -> str:
    """Formate les reponses cote a cote."""
    lines = []
    for r in responses:
        lines.append("=" * 80)
        lines.append(f"MODELE : {r.model} ({r.mode.upper()})")
        lines.append(f"Duree  : {r.duration:.1f}s | Tokens : {r.tokens}")
        lines.append("=" * 80)
        if r.error:
            lines.append(f"ERREUR : {r.error}")
        else:
            lines.append(r.content)
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Dis bonjour en une phrase."
    print(f"Question: {prompt}\n")
    print("Appel en parallele aux 3 modeles...\n")
    responses = ask_all_models(prompt)
    print(format_responses(responses))
