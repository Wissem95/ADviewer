#!/bin/bash
# ============================================
# LOCALCODER — Script de lancement intelligent
# 3 modes : local (avion) | gemini (gratuit) | api (payant)
# Optimise pour M3 Pro 18 Go
# ============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Verification prerequis ---
check_prerequisites() {
    if ! command -v aider &> /dev/null; then
        echo -e "${RED}Aider non installe. Install: pip install aider-chat${NC}"
        exit 1
    fi
}

check_ollama() {
    if ! command -v ollama &> /dev/null; then
        return 1
    fi
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "${YELLOW}Demarrage d'Ollama...${NC}"
        ollama serve &> /dev/null &
        sleep 3
    fi
    return 0
}

# --- Detection mode ---
detect_connectivity() {
    if curl -s --max-time 3 https://google.com > /dev/null 2>&1; then
        echo "online"
    else
        echo "offline"
    fi
}

# --- Menu de selection ---
show_menu() {
    local mode=$1

    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         ${BOLD}LOCALCODER — IDE IA Local${NC}${CYAN}            ║${NC}"
    echo -e "${CYAN}║         M3 Pro 18 Go — Aider Engine         ║${NC}"
    echo -e "${CYAN}╠══════════════════════════════════════════════╣${NC}"

    if [ "$mode" = "offline" ]; then
        echo -e "${CYAN}║${NC}  Connexion : ${RED}OFFLINE (mode avion)${NC}${CYAN}            ║${NC}"
        echo -e "${CYAN}╠══════════════════════════════════════════════╣${NC}"
        echo -e "${CYAN}║${NC}                                              ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}  ${GREEN}1)${NC} Local — qwen2.5-coder:14b ${GREEN}[DISPONIBLE]${NC}   ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}     Contexte: 16K | Cout: 0E                ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}     Ideal: fix rapides, 1 fichier           ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}                                              ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}  ${RED}2)${NC} Gemini 2.5 Pro ${RED}[HORS LIGNE]${NC}              ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}  ${RED}3)${NC} DeepSeek API ${RED}[HORS LIGNE]${NC}                ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}                                              ${CYAN}║${NC}"
        echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    else
        echo -e "${CYAN}║${NC}  Connexion : ${GREEN}ONLINE${NC}${CYAN}                            ║${NC}"
        echo -e "${CYAN}╠══════════════════════════════════════════════╣${NC}"
        echo -e "${CYAN}║${NC}                                              ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}  ${GREEN}1)${NC} Local — qwen2.5-coder:14b               ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}     Contexte: 16K | Cout: 0E                ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}     Ideal: fix rapides, 1 fichier           ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}                                              ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}  ${GREEN}2)${NC} Gemini 2.5 Pro ${GREEN}[GRATUIT]${NC}               ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}     Contexte: 1M | Cout: 0E                 ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}     Ideal: multi-fichier, refacto, debug    ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}     ${YELLOW}Remplace Opus a ~85-90%${NC}                 ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}                                              ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}  ${GREEN}3)${NC} DeepSeek-R1 API ${YELLOW}[~0.005\$/req]${NC}          ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}     Contexte: 128K | Raisonnement profond   ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}     Ideal: architecture, debug complexe     ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}     ${YELLOW}Remplace Opus a ~90%${NC}                    ${CYAN}║${NC}"
        echo -e "${CYAN}║${NC}                                              ${CYAN}║${NC}"
        echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    fi
    echo ""
}

# --- Commandes utiles ---
show_commands() {
    echo -e "${CYAN}──────────────────────────────────────────────${NC}"
    echo -e "  Commandes Aider :"
    echo -e "  ${GREEN}/architect${NC}  planifier avant de coder"
    echo -e "  ${GREEN}/code${NC}       edition directe"
    echo -e "  ${GREEN}/ask${NC}        question sans modifier"
    echo -e "  ${GREEN}/test${NC}       lancer les tests"
    echo -e "  ${GREEN}/undo${NC}       annuler derniere modif"
    echo -e "  ${GREEN}/diff${NC}       voir les changements"
    echo -e "  ${GREEN}/add${NC}        ajouter un fichier au contexte"
    echo -e "  ${GREEN}/drop${NC}       retirer un fichier du contexte"
    echo -e "  ${GREEN}/run${NC}        executer une commande shell"
    echo -e "${CYAN}──────────────────────────────────────────────${NC}"
    echo ""
}

# --- Lancement ---
main() {
    check_prerequisites

    local mode
    mode=$(detect_connectivity)

    show_menu "$mode"

    # Choix utilisateur
    read -p "  Choisis ton mode [1/2/3] : " choice
    echo ""

    local config_file

    case $choice in
        1)
            if ! check_ollama; then
                echo -e "${RED}Ollama non installe ou non demarre.${NC}"
                exit 1
            fi
            config_file="$SCRIPT_DIR/.aider.conf.yml"
            echo -e "${GREEN}Mode LOCAL selectionne (qwen2.5-coder:14b)${NC}"
            ;;
        2)
            if [ "$mode" = "offline" ]; then
                echo -e "${RED}Pas de connexion internet. Utilise le mode local.${NC}"
                exit 1
            fi
            if [ -z "$GEMINI_API_KEY" ]; then
                echo -e "${RED}GEMINI_API_KEY non definie.${NC}"
                echo -e "${YELLOW}Cle GRATUITE : https://aistudio.google.com/apikey${NC}"
                echo -e "  export GEMINI_API_KEY='ta-cle'"
                exit 1
            fi
            config_file="$SCRIPT_DIR/.aider.conf.gemini.yml"
            echo -e "${GREEN}Mode GEMINI selectionne (gratuit, 1M contexte)${NC}"
            ;;
        3)
            if [ "$mode" = "offline" ]; then
                echo -e "${RED}Pas de connexion internet. Utilise le mode local.${NC}"
                exit 1
            fi
            if [ -z "$DEEPSEEK_API_KEY" ]; then
                echo -e "${RED}DEEPSEEK_API_KEY non definie.${NC}"
                echo -e "${YELLOW}Inscription : https://platform.deepseek.com/${NC}"
                echo -e "  export DEEPSEEK_API_KEY='sk-...'"
                exit 1
            fi
            config_file="$SCRIPT_DIR/.aider.conf.api.yml"
            echo -e "${GREEN}Mode DEEPSEEK selectionne (API, raisonnement profond)${NC}"
            ;;
        *)
            echo -e "${RED}Choix invalide. Utilise 1, 2 ou 3.${NC}"
            exit 1
            ;;
    esac

    echo ""
    show_commands

    # Copier CONVENTIONS.md si absent dans le repertoire courant
    if [ ! -f "CONVENTIONS.md" ] && [ -f "$SCRIPT_DIR/CONVENTIONS.md" ]; then
        cp "$SCRIPT_DIR/CONVENTIONS.md" .
        echo -e "${GREEN}CONVENTIONS.md copie dans le projet${NC}"
    fi

    # Lancement Aider
    aider --config "$config_file" "$@"
}

main "$@"
