#!/bin/bash
# Processar todos os áudios não-SAM em ordem cronológica

PROCESSADOS=0
ERROS=0
PULADOS=0

processar() {
    local arquivo="$1"
    local nome=$(basename "$arquivo" .mp3)
    
    echo ""
    echo "============================================================"
    echo "🎵 PROCESSANDO: $nome"
    echo "   Início: $(date '+%H:%M:%S')"
    echo "============================================================"
    
    INICIO=$(date +%s)
    
    PYTHONPATH=scripts_pipeline python scripts_pipeline/boletim/processar_boletim_canonico.py "$arquivo" --roteiros setembro/ 2>&1 | tee "setembro/log_${nome}.txt"
    
    FIM=$(date +%s)
    DURACAO=$((FIM - INICIO))
    
    if [ $? -eq 0 ]; then
        echo "   ✅ CONCLUÍDO em ${DURACAO}s"
        PROCESSADOS=$((PROCESSADOS + 1))
    else
        echo "   ❌ ERRO após ${DURACAO}s"
        ERROS=$((ERROS + 1))
    fi
}

# Limpar progresso anterior
rm -f setembro/progresso_processamento.json

# Processar em ordem (mais antigo primeiro, pulando SAM)
echo "🎙️  INICIANDO PROCESSAMENTO - SETEMBRO 2026"
echo "   $(date)"

# Dia 11 - apenas B6-B10 (B1-B5 é SAM)
processar "setembro/11 SET B6-B10.mp3"

# Dia 15 - apenas B6-B10 (B1-B5 é SAM)
processar "setembro/15 SET B6-B10.mp3"

# Dia 17 - B1-B5 (sem SAM)
processar "setembro/17 SET B1-B5.mp3"

# Dia 18 - B6-B10 (sem SAM)
processar "setembro/18 SET B6-B10.mp3"

# Dia 21 - B1-B4 e B5-B10 (sem SAM)
processar "setembro/21 SET B1-B4.mp3"
processar "setembro/21 SET B5-B10.mp3"

# Dia 22 - B1-B5 e B6-B10 (sem SAM)
processar "setembro/22 SET B1-B5.mp3"
processar "setembro/22 SET B6-B10.mp3"

echo ""
echo "============================================================"
echo "📊 RESUMO FINAL"
echo "   ✅ Sucesso: $PROCESSADOS"
echo "   ❌ Erros: $ERROS"
echo "   ⏭️ Pulados (SAM): 17"
echo "   Término: $(date)"
echo "============================================================"
