#!/bin/bash
# ============================================================
# sync_drive.sh — Faz upload dos jornais prontos para H:
# ÚNICA escrita permitida no H: por este pipeline
# ============================================================
set -euo pipefail

E_WS="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
OUTPUT="${E_WS}/data/output/JORNAIS_FINAL"
BASE_H="H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026"
H_DEST="${BASE_H}/02_JORNAIS_NJUD/03_AUDIOS_RADIO"
LOG_DIR="${E_WS}/logs"

DATA=$(date +%Y%m%d_%H%M%S)
LOG="${LOG_DIR}/sync_drive_${DATA}.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== INÍCIO SINCRONIZAÇÃO COM H: $(date) ==="
log "Origem:  ${OUTPUT}"
log "Destino: ${H_DEST}"

if [ ! -d "$OUTPUT" ]; then
    log "❌ Diretório de saída não encontrado: ${OUTPUT}"
    exit 1
fi

# Descobrir quais meses existem no output
for MES_DIR in "$OUTPUT"/*/; do
    [ -d "$MES_DIR" ] || continue
    MES_NOME=$(basename "$MES_DIR")
    log "📂 Processando mês: ${MES_NOME}"
    
    H_MES_DEST="${H_DEST}/${MES_NOME}"
    
    # Criar pasta no H: se não existir (única escrita no H:)
    if [ ! -d "$H_MES_DEST" ]; then
        log "  Criando pasta no H:: ${H_MES_DEST}"
        mkdir -p "$H_MES_DEST"
    fi
    
    # Copiar jornais montados
    SUCCESS=0
    FAIL=0
    for JORNAL in "$MES_DIR"/*.mp3; do
        [ -f "$JORNAL" ] || continue
        NOME=$(basename "$JORNAL")
        DST="${H_MES_DEST}/${NOME}"
        
        if [ -f "$DST" ]; then
            log "  ⏭️  JÁ EXISTE: ${NOME} — pulando"
            continue
        fi
        
        if cp -v "$JORNAL" "$DST" 2>&1 | tee -a "$LOG"; then
            log "  ✅ ${NOME} → H:"
            SUCCESS=$((SUCCESS+1))
        else
            log "  ❌ FALHA ao copiar ${NOME}"
            FAIL=$((FAIL+1))
        fi
    done
    
    log "  Mês ${MES_NOME}: ${SUCCESS} copiados, ${FAIL} falhos"
done

log "=== SINCRONIZAÇÃO CONCLUÍDA $(date) ==="
log "Log salvo: ${LOG}"

# Relatório final
TOTAL=$(find "$OUTPUT" -type f -name "*.mp3" | wc -l)
log "Total de jornais no output: ${TOTAL}"

echo " Sincronização concluída. Log: ${LOG}"
