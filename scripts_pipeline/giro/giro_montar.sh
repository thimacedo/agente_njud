#!/bin/bash
# ============================================================
# GIRO nas Comarcas — Montagem de programas
# Monta programas a partir de notas já processadas
# (arquivos GNC_mmss_N01_*.mp3 em data/processed/GIRO_COMARCAS/)
#
# Uso:
#   bash scripts_pipeline/giro/montar.sh
#   bash scripts_pipeline/giro/montar.sh --mmss 0101
# ============================================================

set -euo pipefail

BASE_DIR="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
SRC_DIR="$BASE_DIR/src"
PYTHON="${PYTHON:-python}"

cd "$BASE_DIR"

echo "========================================"
echo "GIRO — MONTAGEM DE PROGRAMAS"
echo "========================================"

PASTA_NOTAS="${1:-data/processed/GIRO_COMARCAS}"
SAIDA_DIR="${2:-data/output/GIRO_COMARCAS}"

echo "Pasta de notas    : $PASTA_NOTAS"
echo "Saída             : $SAIDA_DIR"
echo ""

# Executa montagem via CLI do módulo giro
"$PYTHON" -m giro --montar "$PASTA_NOTAS" --saida "$SAIDA_DIR"

echo ""
echo "========================================"
echo "MONTAGEM CONCLUÍDA"
echo "========================================"
