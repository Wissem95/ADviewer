#!/bin/bash
# ============================================
# LOCALCODER — Mode API (taches complexes)
# Lance Aider avec DeepSeek API
# ============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Verification cle API
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo -e "${RED}DEEPSEEK_API_KEY non definie.${NC}"
    echo -e "${YELLOW}Pour la definir :${NC}"
    echo -e "  export DEEPSEEK_API_KEY='sk-...' "
    echo -e ""
    echo -e "${YELLOW}Ou ajoute dans ~/.zshrc :${NC}"
    echo -e "  echo 'export DEEPSEEK_API_KEY=sk-...' >> ~/.zshrc"
    echo -e ""
    echo -e "Inscription : https://platform.deepseek.com/"
    exit 1
fi

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  LOCALCODER — Mode API (DeepSeek)${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""
echo -e "  Modele    : ${GREEN}DeepSeek Coder (API)${NC}"
echo -e "  Cout      : ${YELLOW}~0.003\$ par requete${NC}"
echo -e "  Contexte  : ${GREEN}128K tokens${NC}"
echo -e "  Architecte: ${GREEN}ON${NC}"
echo -e "  Cache     : ${GREEN}ON (economie tokens)${NC}"
echo ""
echo -e "${CYAN}============================================${NC}"
echo ""

# Copier CONVENTIONS.md si absent
if [ ! -f "CONVENTIONS.md" ] && [ -f "$SCRIPT_DIR/CONVENTIONS.md" ]; then
    cp "$SCRIPT_DIR/CONVENTIONS.md" .
fi

aider --config "$SCRIPT_DIR/.aider.conf.api.yml" "$@"
