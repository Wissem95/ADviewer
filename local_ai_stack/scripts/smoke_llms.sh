#!/usr/bin/env bash
# LocalCoder IDE — smoke test live des 5 LLMs.
#
# Usage :
#   export DEEPSEEK_API_KEY=...
#   export MINIMAX_API_KEY=...
#   export GEMINI_API_KEY=...
#   export MISTRAL_API_KEY=...
#   ./scripts/smoke_llms.sh
#
# Lance les tests marqués ``llm_live`` de tests/backend/test_llm_manager.py.
# Chaque test est skippé automatiquement si sa clé API n'est pas définie.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d "venv" ]; then
    echo "Erreur : venv/ introuvable à la racine. Créer avec : python -m venv venv" >&2
    exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "== LocalCoder smoke LLMs =="
echo "Clés détectées :"
for var in DEEPSEEK_API_KEY MINIMAX_API_KEY GEMINI_API_KEY MISTRAL_API_KEY; do
    if [ -n "${!var:-}" ]; then
        echo "  ✓ $var (longueur=${#var} chars)"
    else
        echo "  ✗ $var (absent → tests associés skippés)"
    fi
done
echo

python -m pytest tests/backend/test_llm_manager.py -m llm_live -v --tb=short
