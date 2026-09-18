#!/bin/bash
# ============================================================
# prepare.sh — Copia boletins necessários do H: para workspace
# Fluxo inegociável: arquivos no H: NÃO são modificados
# ============================================================
set -euo pipefail

BASE_H="H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026"
SRC_H="${BASE_H}/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO"
E_WS="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
TMP="${E_WS}/tmp_boletins"
LOG_DIR="${E_WS}/logs"

mkdir -p "$TMP"
mkdir -p "$LOG_DIR"

DATA=$(date +%Y%m%d_%H%M%S)
LOG="${LOG_DIR}/prepare_${DATA}.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== INÍCIO PREPARAÇÃO $(date) ==="
log "Fonte H:  ${SRC_H}"
log "Destino:  ${TMP}"

# Copiar boletins de JULHO e AGOSTO para tmp organizados por mes
for MES_COD in "07 - JUL - 26" "08 - AGO - 26"; do
    SRC_MES="${SRC_H}/${MES_COD}"
    if [ -d "$SRC_MES" ]; then
        log "📂 Copiando ${MES_COD}..."
        # Copiar todos os mp3s mantendo estrutura
        find "$SRC_MES" -type f \( -iname "*.mp3" -o -iname "*.wav" -o -iname "*.m4a" -o -iname "*.ogg" \) | while read -r ARQ; do
            REL="${ARQ#$SRC_MES/}"
            DST="${TMP}/${MES_COD}/${REL}"
            mkdir -p "$(dirname "$DST")"
            cp -v "$ARQ" "$DST" 2>&1 | tee -a "$LOG"
        done
        log "✅ ${MES_COD} copiado"
    else
        log "❌ PASTA NÃO ENCONTRADA: ${SRC_MES}"
    fi
done

log "=== PREPARAÇÃO CONCLUÍDA $(date) ==="
log "Log salvo: ${LOG}"
echo " Prepare concluído. Log: ${LOG}"
