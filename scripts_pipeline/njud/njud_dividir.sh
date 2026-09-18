#!/bin/bash
# ============================================================
# NJUD — Divisão e montagem (Fase 2 do pipeline)
# 1. Divide boletins em _CABECA/_CORPO
# 2. Monta jornais completos (4 boletins por jornal)
#
# Uso:
#   bash scripts_pipeline/njud/divide.sh <pasta_boletins>
#   bash scripts_pipeline/njud/montar.sh
# ============================================================

set -euo pipefail

BASE_DIR="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
SRC_DIR="$BASE_DIR/src"
SCRIPTS_DIR="$BASE_DIR/scripts_pipeline"
PYTHON="${PYTHON:-python}"

cd "$BASE_DIR"

# ============================================================
# DIVISÃO
# ============================================================
divider() {
    local pasta_entrada="${1:?Uso: divide.sh <pasta_boletins>}"
    local pasta_saida="${2:-data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS}"

    echo "========================================"
    echo "NJUD — DIVISÃO DE BOLETINS"
    echo "========================================"
    echo "Entrada : $pasta_entrada"
    echo "Saída   : $pasta_saida"
    echo ""

    "$PYTHON" -m divisor_boletins dividir "$pasta_entrada" "$pasta_saida" --apply

    echo ""
    echo "========================================"
    echo "DIVISÃO CONCLUÍDA"
    echo "========================================"
}

# ============================================================
# MONTAGEM
# ============================================================
montador() {
    local pasta_entrada="${1:-data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS}"
    local pasta_saida="${2:-data/output/JORNAIS_FINAL}"

    echo "========================================"
    echo "NJUD — MONTAGEM DE JORNais"
    echo "========================================"
    echo "Entrada : $pasta_entrada"
    echo "Saída   : $pasta_saida"
    echo ""

    "$PYTHON" "$SCRIPTS_DIR/montagem_jornais.py"

    echo ""
    echo "========================================"
    echo "MONTAGEM CONCLUÍDA"
    echo "========================================"
}

# Dispatcher por argumento
case "${1:-}" in
    divide)
        divider "${2:-}" "${3:-}"
        ;;
    montar)
        montador "${2:-}" "${3:-}"
        ;;
    *)
        echo "Uso:"
        echo "  bash scripts_pipeline/njud/divide.sh divide <pasta_boletins> [pasta_saida]"
        echo "  bash scripts_pipeline/njud/divide.sh montar [pasta_entrada] [pasta_saida]"
        exit 1
        ;;
esac
