#!/bin/bash
# ============================================
# LOCALCODER — Mode Gemini 2.5 Pro (GRATUIT)
# 1M tokens de contexte — parfait pour gros projets
# ============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Verification cle API
if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${RED}GEMINI_API_KEY non definie.${NC}"
    echo ""
    echo -e "${YELLOW}Pour obtenir une cle GRATUITE :${NC}"
    echo -e "  1. Va sur ${CYAN}https://aistudio.google.com/apikey${NC}"
    echo -e "  2. Clique 'Create API Key'"
    echo -e "  3. Copie la cle"
    echo ""
    echo -e "${YELLOW}Puis ajoute dans ~/.zshrc :${NC}"
    echo -e "  echo 'export GEMINI_API_KEY=ta-cle-ici' >> ~/.zshrc"
    echo -e "  source ~/.zshrc"
    echo ""
    echo -e "${GREEN}C'est 100% GRATUIT — 25 requetes/minute${NC}"
    exit 1
fi

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  LOCALCODER — Mode Gemini 2.5 Pro${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""
echo -e "  Modele    : ${GREEN}Gemini 2.5 Pro (GRATUIT)${NC}"
echo -e "  Contexte  : ${GREEN}1 000 000 tokens${NC}"
echo -e "  Cout      : ${GREEN}0\$ (free tier)${NC}"
echo -e "  Architecte: ${GREEN}ON${NC}"
echo -e "  Rate limit: ${YELLOW}25 req/min${NC}"
echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "  admin.py (4359 lignes)   : ${GREEN}RENTRE${NC}"
echo -e "  Tout huntzenjobs (~5000 fichiers) : ${GREEN}repo-map OK${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Copier CONVENTIONS.md si absent
if [ ! -f "CONVENTIONS.md" ] && [ -f "$SCRIPT_DIR/CONVENTIONS.md" ]; then
    cp "$SCRIPT_DIR/CONVENTIONS.md" .
fi

aider --config "$SCRIPT_DIR/.aider.conf.gemini.yml" "$@"
