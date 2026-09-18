#!/bin/bash
# ============================================================
# GIRO nas Comarcas — Processamento de boletins
# 1. Transcreve boletins do período
# 2. Extrai notas (LOC+OFF juntos)
# 3. Aplica filtro geográfico (exceto Natal / fora RN)
# 4. Corta áudio das notas aceitas
#
# Uso:
#   bash scripts_pipeline/giro/processar.sh
#   bash scripts_pipeline/giro/processar.sh --mmss 0101
# ============================================================

set -euo pipefail

BASE_DIR="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
SRC_DIR="$BASE_DIR/src"
PYTHON="${PYTHON:-python}"

cd "$BASE_DIR"

echo "========================================"
echo "GIRO — PROCESSAMENTO DE BOLETINS"
echo "========================================"

# Determina pasta de boletins (default: JORNAIS/)
PASTA_BOLETINS="${1:-JORNAIS}"
SAIDA_DIR="${2:-data/output/GIRO_COMARCAS}"

echo "Pasta de boletins : $PASTA_BOLETINS"
echo "Saída             : $SAIDA_DIR"
echo ""

# Executa processamento via CLI do módulo giro
"$PYTHON" -m giro "$PASTA_BOLETINS" --saida "$SAIDA_DIR"

echo ""
echo "========================================"
echo "PROCESSAMENTO CONCLUÍDO"
echo "========================================"
