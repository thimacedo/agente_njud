#!/bin/bash
# Reprocessa apenas os boletins que falharam (código 143/3221225794 do Demucs)
# Executa um por um para evitar pressão de memória

set -euo pipefail

LOG_DIR="data/processed/PRODUCAO_2026/_logs"
OUTPUT_BASE="data/processed/PRODUCAO_2026"

# Recuperar lista de arquivos falhados a partir dos logs
echo "=== Recuperando lista de boletins falhados ===" >&2

FAILED_LIST=$(mktemp)
for log in "$LOG_DIR"/giro_*.log; do
    grep "Demucs falhou" "$log" 2>/dev/null | sed 's/.*para //' | sort -u
done | sort -u > "$FAILED_LIST"

TOTAL=$(wc -l < "$FAILED_LIST")
echo "Encontrados $TOTAL boletins falhados" >&2

if [ "$TOTAL" -eq 0 ]; then
    echo "Nenhum boletim falhado encontrado. Nada a reprocessar."
    rm -f "$FAILED_LIST"
    exit 0
fi

echo "" >&2
echo "=== Iniciando reprocessamento ($(date '+%H:%M:%S')) ===" >&2
echo "" >&2

CONTEXTO="reprocessar_falhos"
SUCESSO=0
FALHA=0

while IFS= read -r nome_arquivo; do
    [ -z "$nome_arquivo" ] && continue
    
    # Extrair data do nome (ex: BOLETIM_RADIO_TJRN_08_01_2026_B1_... → 08_01_2026)
    data_seg=$(echo "$nome_arquivo" | grep -oP '\d{2}_\d{2}_\d{4}' | head -1)
    if [ -z "$data_seg" ]; then
        echo "⚠ Não consegue extrair data de: $nome_arquivo"
        FALHA=$((FALHA + 1))
        continue
    fi
    
    # Converter data para formato Diretório (ex: 08_01_2026 → 08 - JAN - 26)
    mes_num=$(echo "$data_seg" | cut -d'_' -f1)
    ano=$(echo "$data_seg" | cut -d'_' -f3)
    mes_nome=$(case $mes_num in
        01) echo "JAN";;
        02) echo "FEV";;
        03) echo "MAR";;
        04) echo "ABR";;
        05) echo "MAI";;
        06) echo "JUN";;
        07) echo "JUL";;
        08) echo "AGO";;
        09) echo "SET";;
        10) echo "OUT";;
        11) echo "NOV";;
        12) echo "DEZ";;
    esac)
    pasta_fonte="H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO/${mes_num} - ${mes_nome} - ${ano}"
    
    arq_origem="$pasta_fonte/$nome_arquivo"
    
    if [ ! -f "$arq_origem" ]; then
        echo "⚠ Arquivo não encontrado: $arq_origem"
        FALHA=$((FALHA + 1))
        continue
    fi
    
    echo "[$(date '+%H:%M:%S')] Processando: $nome_arquivo"
    
    # Executar executar_programa.py diretamente para este arquivo
    python -u scripts_pipeline/executar_programa.py \
        --boletins "$pasta_fonte" \
        --planejamento "config/planejamento_2026/giro_$(echo $data_seg | tr '_' '').json" \
        --saida "$OUTPUT_BASE" \
        2>&1 | tee -a "$LOG_DIR/reprocessar_falhos.log" || {
            echo " Falhou: $nome_arquivo"
            FALHA=$((FALHA + 1))
        }
    
    echo "" >&2
done < "$FAILED_LIST"

rm -f "$FAILED_LIST"

echo "" >&2
echo "=== RESUMO DO REPROCESSAMENTO ===" >&2
echo "Total: $TOTAL" >&2
echo "Sucesso: $SUCESSO" >&2
echo "Falha: $FALHA" >&2
echo "" >&2

if [ "$FALHA" -gt 0 ]; then
    echo "⚠ $FALHA boletin(s) ainda com falha — ver log: $LOG_DIR/reprocessar_falhos.log" >&2
    exit 1
else
    echo "✅ Todos reprocessados com sucesso." >&2
    exit 0
fi
