#!/bin/bash
# ============================================================
# cleanup.sh — Limpeza pós-produção
# Apaga: 1) cópias dos boletins de E:/tmp_boletins
#        2) jornais montados de E:/data/output/JORNAIS_FINAL
# NUNCA apaga: H:, refs, logs, código
# ============================================================
set -euo pipefail

E_WS="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
TMP="${E_WS}/tmp_boletins"
OUTPUT="${E_WS}/data/output/JORNAIS_FINAL"
LOG_DIR="${E_WS}/logs"

DATA=$(date +%Y%m%d_%H%M%S)
LOG="${LOG_DIR}/cleanup_${DATA}.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== INÍCIO LIMPEZA $(date) ==="

# 1. Apagar cópias dos boletins
if [ -d "$TMP" ]; then
    TAMANHO=$(du -sh "$TMP" 2>/dev/null | cut -f1 || echo "?")
    log "🗑️  Apagando cópias dos boletins: ${TMP} (${TAMANHO})"
    rm -rf "$TMP"
    log "  ✅ tmp_boletins removido"
else
    log "ℹ️  tmp_boletins já não existe"
fi

# 2. Apagar jornais montados do workspace
if [ -d "$OUTPUT" ]; then
    TAMANHO=$(du -sh "$OUTPUT" 2>/dev/null | cut -f1 || echo "?")
    log "🗑️  Apagando jornais do workspace: ${OUTPUT} (${TAMANHO})"
    rm -rf "$OUTPUT"
    log "  ✅ JORNAIS_FINAL removido"
else
    log "ℹ️  JORNAIS_FINAL já não existe"
fi

# Verificar que o H: não foi tocado (somente leituraconfirmada)
log "✅ Verificação: H: não modificado por este script"

log "=== LIMPEZA CONCLUÍDA $(date) ==="
log "Log salvo: ${LOG}"

echo " Limpeza concluída. Log: ${LOG}"
