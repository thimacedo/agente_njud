#!/bin/bash
# ============================================================
# NJUD — Etapa de preparação (Fase 1 do pipeline)
# Valida boletins, gera plano de alocação, copia para
# boletins_brutos/ com estrutura mês/NJUD.
#
# Uso:
#   bash scripts_pipeline/njud/prepare.sh
#   bash scripts_pipeline/njud/prepare.sh --apply
# ============================================================

set -euo pipefail

BASE_DIR="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
SRC_DIR="$BASE_DIR/src"
SCRIPTS_DIR="$BASE_DIR/scripts_pipeline"
PYTHON="${PYTHON:-python}"

cd "$BASE_DIR"

echo "========================================"
echo "NJUD — PREPARAÇÃO DE BOLETINS"
echo "========================================"

# 1. Validar integridade do plano de alocação (dry-run)
echo ""
echo "[1/3] Validando plano de alocação..."
"$PYTHON" "$SRC_DIR/sync/copy.py" --dry-run

# 2. Copiar boletins para estrutura namespaced
echo ""
echo "[2/3] Copiando boletins para boletins_brutos/..."
"$PYTHON" "$SRC_DIR/sync/copy.py" --apply

# 3. Gerar relatório
echo ""
echo "[3/3] Gerando relatório de alocação..."
if [ -f "$BASE_DIR/data/alocacao_boletins.csv" ]; then
    echo "  Relatório: $BASE_DIR/data/alocacao_boletins.csv"
    wc -l < "$BASE_DIR/data/alocacao_boletins.csv" | xargs echo "  Linhas: "
fi

echo ""
echo "========================================"
echo "NJUD PREPARADO — pronto para divisão"
echo "========================================"
