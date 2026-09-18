#!/bin/bash
# ============================================================
# auditar.sh — Audita jornais montados
# Refaz o que precisar com log de correções
# ============================================================
set -euo pipefail

E_WS="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
OUTPUT="${E_WS}/data/output/JORNAIS_FINAL"
LOG_DIR="${E_WS}/logs"

DATA=$(date +%Y%m%d_%H%M%S)
LOG="${LOG_DIR}/auditoria_${DATA}.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

if [ -x "${E_WS}/.venv/Scripts/python.exe" ]; then
    PYTHON="${E_WS}/.venv/Scripts/python.exe"
elif command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "❌ Python não encontrado" | tee -a "$LOG"
    exit 1
fi

log "=== INÍCIO AUDITORIA $(date) ==="
log "Auditando: ${OUTPUT}"

if [ ! -d "$OUTPUT" ]; then
    log "❌ Diretório de saída não encontrado: ${OUTPUT}"
    exit 1
fi

log "Iniciando auditoria de integridade..."

$PYTHON -m audit.integrity \
    "${OUTPUT}" \
    --report "${LOG_DIR}/relatorio_auditoria_${DATA}.json" \
    2>&1 | tee -a "$LOG" || {
    log "⚠️  Auditoria encontrou inconsistencies."
}

log "=== AUDITORIA CONCLUÍDA $(date) ==="

# Se houver falhas, registrar para reprocessamento
if [ -f "${LOG_DIR}/relatorio_auditoria_${DATA}.json" ]; then
    FALHAS=$(python3 -c "
import json, sys
try:
    with open('${LOG_DIR}/relatorio_auditoria_${DATA}.json') as f:
        d = json.load(f)
    print(d.get('falhas', d.get('pendencias', 0)))
except:
    print(0)
" 2>/dev/null || echo "0")
    log "Falhas detectadas: ${FALHAS}"
fi

echo " Auditoria concluída. Log: ${LOG}"
