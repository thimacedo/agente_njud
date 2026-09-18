#!/bin/bash
# ============================================================
# run_pipeline.sh — Processa boletins: corte + transcrição
# Usa dispatcher paralelo com estado por arquivo
# ============================================================
set -euo pipefail

E_WS="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
TMP="${E_WS}/tmp_boletins"
DATA_DIR="${E_WS}/data"
PROCESSED="${DATA_DIR}/processed/JORNAIS_DIVIDIDOS"
LOG_DIR="${E_WS}/logs"

mkdir -p "$PROCESSED"
mkdir -p "$LOG_DIR"

DATA=$(date +%Y%m%d_%H%M%S)
LOG="${LOG_DIR}/pipeline_${DATA}.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# Detectar Python (venv ou sistema)
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
log "Python: ${PYTHON} (${$PYTHON} --version 2>&1 || true)"

log "=== INÍCIO PIPELINE $(date) ==="
log "Entrada:  ${TMP}"
log "Saída:    ${PROCESSED}"
log "Python:   ${PYTHON}"

# Verificar quem já está processado (estado por arquivo)
# O dispatcher pula arquivos que já têm JSON de estado OK/ESGOTADO_ACEITO

log "Iniciando dispatcher..."

# Rodar o pipeline de processamento
# NOTA: ajustar args conforme API real do dispatcher.py
$PYTHON "${E_WS}/src/iniciar_ciclo.py" \
    "${TMP}" \
    "${PROCESSED}" \
    --max-workers 2 \
    2>&1 | tee -a "$LOG" || {
    log "⚠️  Pipeline encontrou erros. Ver log para detalhes."
    log "    Arquivos já processados são preservados."
}

log "=== PIPELINE CONCLUÍDO $(date) ==="
log "Log salvo: ${LOG}"

# Resumo
if [ -d "$PROCESSED" ]; then
    NJUDS=$(find "$PROCESSED" -type d -name "NJUD*" | wc -l)
    log "NJUDs criados: ${NJUDS}"
fi

echo " Pipeline concluído. Log: ${LOG}"
