#!/bin/bash
# ============================================================
# NJUD — Orquestrador de ciclo completo (wrapper para safe_runner.py)
#
# Coordena o ciclo completo de produção de jornais NJUD:
#   1. Preparar (validar + copiar boletins)
#   2. Dividir em _CABECA/_CORPO
#   3. Montar jornais completos
#   4. Auditar integridade
#   5. Repetir até conclusão (com delay entre ciclos)
#
# Este script é o entry point principal para produção NJUD.
# Usa o orquestrador modularizado: src/orchestration/safe_runner.py
#
# Uso:
#   bash scripts_pipeline/njud/orquestrador.sh
#   bash scripts_pipeline/njud/orquestrador.sh --njuds 1909,1910
#   bash scripts_pipeline/njud/orquestrador.sh --max-ciclos 3 --delay 60
# ============================================================

set -euo pipefail

BASE_DIR="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
SRC_DIR="$BASE_DIR/src"
PYTHON="${PYTHON:-python}"

cd "$BASE_DIR"

echo "========================================"
echo "NJUD — ORQUESTRADOR DE CICLO COMPLETO"
echo "========================================"

# Executa o safe_runner (orquestrador modularizado) com argumentos passados
exec "$PYTHON" "$SRC_DIR/orchestration/safe_runner.py" "$@"
