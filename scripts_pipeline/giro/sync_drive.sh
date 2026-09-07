#!/bin/bash
# ============================================================
# GIRO nas Comarcas — Sincronização com Drive H:
# Copia programas montados para a pasta de produção do Drive.
#
# Uso:
#   bash scripts_pipeline/giro/sync_drive.sh
# ============================================================

set -euo pipefail

BASE_DIR="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
SRC_DIR="$BASE_DIR/src"
PYTHON="${PYTHON:-python}"

cd "$BASE_DIR"

echo "========================================"
echo "GIRO — SINCRONIZAÇÃO COM DRIVE H:"
echo "========================================"

# Executa sincronização via módulo giro
"$PYTHON" -m giro.sync_drive

echo ""
echo "========================================"
echo "SINCRONIZAÇÃO CONCLUÍDA"
echo "========================================"
