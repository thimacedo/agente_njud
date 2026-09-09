#!/bin/bash
# ====================================================================
# rodar_tudo_giro.sh — Executa todos os programas GIRO (janeiro a agosto)
# ====================================================================
# Regras inegociáveis:
#   - Drive H: é fonte (somente-leitura), nunca alterado
#   - Saída: local (data/processed/PRODUCAO_2026/)
#   - Sincronização apenas quando programa estiver pronto
# ====================================================================

set -euo pipefail

SCRIPT_DIR="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/scripts_pipeline"
PROJETO="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
FONTE_H="H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO"
SAIDA="$PROJETO/data/processed/PRODUCAO_2026"
PLANOS="$PROJETO/config/planejamento_2026"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== INICIANDO PRODUÇÃO GIRO (janeiro → agosto) ==="
log "Fonte (H:): $FONTE_H"
log "Saída:      $SAIDA"
log "Planos:     $PLANOS"
log ""

log "Verificando plano de executação..."

total=0
sucesso=0
falha=0

for json in "$PLANOS"/giro_*.json; do
    codigo=$(basename "$json" .json)
    total=$((total + 1))
    
    log "----------------------------------------"
    log "[$total/34] Executando $codigo ..."
    
    # Converter caminho POSIX (MSYS) para nativo Windows
    json_win=$(cygpath -w "$json" 2>/dev/null || echo "$json")
    
    if timeout 900 python "$SCRIPT_DIR/executar_programa.py" \
        "$json_win" \
        --boletins "$FONTE_H" \
        --saida "$SAIDA" \
        2>&1 | tee "$SAIDA/_logs/${codigo}.log"; then
        log "[$codigo] ✅ Concluído com sucesso"
        sucesso=$((sucesso + 1))
    else
        log "[$codigo] ❌ Falhou (ver log: $SAIDA/_logs/${codigo}.log)"
        falha=$((falha + 1))
    fi
    
    log ""
done

log "========================================="
log "=== RESUMO FINAL ==="
log "Total:   $total"
log "Sucesso: $sucesso"
log "Falha:   $falha"
log "========================================="

if [ "$falha" -gt 0 ]; then
    log "⚠️  $falha programa(s) com falha — verificar logs em $SAIDA/_logs/"
    exit 1
fi

log "✅ Todos os programas executados com sucesso."
exit 0
