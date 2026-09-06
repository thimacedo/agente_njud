#!/bin/bash
# ============================================================
# montar.sh — Monta jornais a partir dos cortes processados
# Gate: só monta NJUDs com todos os 4 boletins OK ou ESGOTADO_ACEITO
# ============================================================
set -euo pipefail

E_WS="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
DATA_DIR="${E_WS}/data"
PROCESSED="${DATA_DIR}/processed/JORNAIS_DIVIDIDOS"
OUTPUT="${DATA_DIR}/output/JORNAIS_FINAL"
LOG_DIR="${E_WS}/logs"

mkdir -p "$OUTPUT"
mkdir -p "$LOG_DIR"

DATA=$(date +%Y%m%d_%H%M%S)
LOG="${LOG_DIR}/montagem_${DATA}.log"

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

log "=== INÍCIO MONTAGEM $(date) ==="
log "Cortes:  ${PROCESSED}"
log "Saída:   ${OUTPUT}"

log "Iniciando montagem..."

$PYTHON -m divisor_boletins.montagem \
    "${PROCESSED}" \
    "${OUTPUT}" \
    --log-dir "${LOG_DIR}/montagem_logs" \
    2>&1 | tee -a "$LOG" || {
    log "⚠️  Montagem encontrou erros. Ver log para detalhes."
}

log "=== MONTAGEM CONCLUÍDA $(date) ==="

# Relatório de NJUDs montados
if [ -d "$OUTPUT" ]; then
    NJUDS=$(find "$OUTPUT" -type f -name "NJUD_*.mp3" | wc -l)
    log "Jornais montados: ${NJUDS}"
    log "Arquivos: $(find "$OUTPUT" -type f -name "*.mp3" | head -20)"
fi

echo " Montagem concluída. Log: ${LOG}"
