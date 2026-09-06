#!/bin/bash
# ============================================================
# run_all.sh — Orquestra pipeline completo de produção NJUDs
# Fluxo: prepara → pipeline → monta → audita → sync → cleanup
# Com suporte para CONTINUAR a partir do ponto de falha
# ============================================================
set -euo pipefail

E_WS="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
SCRIPTS="${E_WS}/scripts_pipeline"
LOG_DIR="${E_WS}/logs"

# Criar log dir
mkdir -p "$LOG_DIR"

DATA=$(date +%Y%m%d_%H%M%S)
LOG="${LOG_DIR}/run_all_${DATA}.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# Estado da execução (para continuar a partir do ponto de falha)
ESTADO_FILE="${LOG_DIR}/.run_all_estado_${DATA}"

reset_estado() {
    echo "pendente" > "$ESTADO_FILE"
}

mark_feito() {
    echo "$1" > "$ESTADO_FILE"
}

le_estado() {
    if [ -f "$ESTADO_FILE" ]; then
        cat "$ESTADO_FILE"
    else
        echo "pendente"
    fi
}

log "============================================================"
log "  ORQUESTRAÇÃO COMPLETA — PRODUÇÃO NJUDs JUL/AGO 2026"
log "  Iniciado: $(date)"
log "  Workspace: ${E_WS}"
log "  Scripts:   ${SCRIPTS}"
log "============================================================"
log ""

ESTADO_ATUAL=$(le_estado)
log "Estado atual da execução: ${ESTADO_ATUAL}"
log ""

# Verificar pré-requisitos
log "🔍 Verificando pré-requisitos..."

if [ ! -d "$SCRIPTS" ]; then
    log "❌ Scripts não encontrados em ${SCRIPTS}"
    exit 1
fi

if ! command -v bash &>/dev/null; then
    log "❌ Bash não encontrado"
    exit 1
fi

# Detectar Python
if [ -x "${E_WS}/.venv/Scripts/python.exe" ]; then
    PYTHON="${E_WS}/.venv/Scripts/python.exe"
elif command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    log "❌ Python não encontrado"
    exit 1
fi
log "✅ Python: ${PYTHON}"

if [ ! -d "${E_WS}/src" ]; then
    log "❌ Código fonte não encontrado em ${E_WS}/src"
    exit 1
fi
log "✅ Código fonte: ${E_WS}/src"

log "✅ Pré-requisitos OK"
log ""

# Executar etapas com suporte a continuação
executar_etapa() {
    local NOME="$1"
    local SCRIPT="$2"
    
    log ""
    log "╔══════════════════════════════════════════╗"
    log "║  ETAPA: ${NOME}"
    log "╚══════════════════════════════════════════╝"
    
    if [ ! -f "$SCRIPT" ]; then
        log "❌ Script não encontrado: ${SCRIPT}"
        return 1
    fi
    
    log "Executando: ${SCRIPT}"
    
    if bash "$SCRIPT" 2>&1 | tee -a "$LOG"; then
        log "✅ Etapa '${NOME}' CONCLUÍDA COM SUCESSO"
        mark_feito "$NOME"
        return 0
    else
        log "❌ Etapa '${NOME}' FALHOU"
        mark_feito "falhou:${NOME}"
        return 1
    fi
}

# Se estado indica falha anterior, perguntar se quer continuar ou recomeçar
if [[ "$ESTADO_ATUAL" == falhou:* ]]; then
    ETAPA_FALHA="${ESTADO_ATUAL#falhou:}"
    log ""
    log "⚠️  Execução anterior falhou na etapa: ${ETAPA_FALHA}"
    log "  Para continuar a partir da etapa seguinte, re-executar este script."
    log "  Para recomeçar do início, apague: ${ESTADO_FILE}"
    log ""
fi

# ETAPA 1: Preparação (copiar boletins)
if [ "$ESTADO_ATUAL" = "preparacao" ] || [ "$ESTADO_ATUAL" = "pendente" ]; then
    executar_etapa "1_preparacao" "${SCRIPTS}/prepare.sh" || exit 1
fi

# ETAPA 2: Pipeline de processamento
if [ "$ESTADO_ATUAL" = "preparacao" ] || [ "$ESTADO_ATUAL" = "pipeline" ] || [ "$ESTADO_ATUAL" = "pendente" ]; then
    # Só executa se preparação foi OK
    if [ "$(le_estado)" = "preparacao" ] || [ "$(le_estado)" = "pendente" ]; then
        if [ "$ESTADO_ATUAL" = "pendente" ]; then
            log "⏭️  Preparação não executada (estado pendente) — pulando para pipeline..."
        fi
        executar_etapa "2_pipeline" "${SCRIPTS}/run_pipeline.sh" || exit 1
    fi
fi

# ETAPA 3: Montagem
if [ "$(le_estado)" = "pipeline" ] || [ "$(le_estado)" = "pendente" ]; then
    if [ "$ESTADO_ATUAL" = "pendente" ]; then
        log "⏭️  Pipeline não executado — pulando para montagem (se houver cortes)..."
    fi
    executar_etapa "3_montagem" "${SCRIPTS}/montar.sh" || exit 1
fi

# ETAPA 4: Auditoria
if [ "$(le_estado)" = "montagem" ] || [ "$(le_estado)" = "pendente" ]; then
    if [ "$ESTADO_ATUAL" = "pendente" ]; then
        log "⏭️  Montagem não executada — pulando para auditoria..."
    fi
    executar_etapa "4_auditoria" "${SCRIPTS}/auditar.sh" || exit 1
fi

# ETAPA 5: Sincronização com H:
if [ "$(le_estado)" = "auditoria" ] || [ "$(le_estado)" = "pendente" ]; then
    if [ "$ESTADO_ATUAL" = "pendente" ]; then
        log "⏭️  Auditoria não executada — pulando para sincronização..."
    fi
    executar_etapa "5_sincronizacao" "${SCRIPTS}/sync_drive.sh" || exit 1
fi

# ETAPA 6: Limpeza
if [ "$(le_estado)" = "sincronizacao" ] || [ "$(le_estado)" = "pendente" ]; then
    if [ "$ESTADO_ATUAL" = "pendente" ]; then
        log "⏭️  Sincronização não executada — pulando para limpeza..."
    fi
    executar_etapa "6_limpeza" "${SCRIPTS}/cleanup.sh" || exit 1
fi

log ""
log "============================================================"
log "  ✅ TODAS AS ETAPAS CONCLUÍDAS COM SUCESSO"
log "  Finalizado: $(date)"
log "============================================================"
log ""
log "RELATÓRIO RESUMIDO:"
log "  Workspace:     ${E_WS}"
log "  Log principal: ${LOG}"
log ""
log "Etapas executadas:"
for ETAPA in preparacao pipeline montagem auditoria sincronizacao limpeza; do
    if [ "$(le_estado)" = "$ETAPA" ] || [ "$(le_estado)" = "sincronizacao" ]; then
        log "  ✅ ${ETAPA}"
    fi
done

log ""
log "└─ Próximos passos:"
log "   • Verificar logs individuais em ${LOG_DIR}/"
log "   • Confirmar jornais no H: em H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/02_JORNAIS_NJUD/03_AUDIOS_RADIO/"
log "   • Relatório completo em ${LOG}"
log ""
log "============================================================"
log "  ✅ FIM DA ORQUESTRAÇÃO"
log "============================================================"

# Limpar estado
rm -f "$ESTADO_FILE"

echo ""
echo "✅ Orquestração completa. Log principal: ${LOG}"

# Gerar relatório consolidado
REPORT="${LOG_DIR}/relatorio_run_all_${DATA}.txt"
{
    echo "============================================================"
    echo "  RELATÓRIO CONSOLIDADO — PRODUÇÃO NJUDs JUL/AGO 2026"
    echo "============================================================"
    echo "Data: $(date)"
    echo "Workspace: ${E_WS}"
    echo ""
    echo "Etapas executadas:"
    for ETAPA in preparacao pipeline montagem auditoria sincronizacao limpeza; do
        echo "  [OK] ${ETAPA}"
    done
    echo ""
    echo "Logs individuais:"
    for f in "${LOG_DIR}"/prepare_*.log "${LOG_DIR}"/pipeline_*.log "${LOG_DIR}"/montagem_*.log "${LOG_DIR}"/auditoria_*.log "${LOG_DIR}"/sync_drive_*.log "${LOG_DIR}"/cleanup_*.log; do
        [ -f "$f" ] && echo "  • $(basename "$f")"
    done
    echo ""
    echo "Status final: TODAS AS ETAPAS CONCLUÍDAS"
    echo "============================================================"
} > "$REPORT"

log "Relatório consolidado: ${REPORT}"
