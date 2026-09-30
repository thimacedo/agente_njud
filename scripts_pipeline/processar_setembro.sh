#!/bin/bash
# processar_setembro.sh - Processa todos os áudios de setembro em ordem cronológica
# Pula arquivos já editados por SAM
# Usa .venv_pipeline isolada com PYTHONNOUSERSITE=1

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv_pipeline/Scripts/python.exe"
PIPELINE="$PROJECT_ROOT/scripts_pipeline/boletim/processar_boletim_canonico.py"
AUDIOS_DIR="$PROJECT_ROOT/setembro"
ROTEIROS_DIR="$PROJECT_ROOT/setembro"
LOGS_DIR="$PROJECT_ROOT/setembro"
PROGRESS_FILE="$PROJECT_ROOT/setembro/progresso.json"

# Verificar venv
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERRO: .venv_pipeline não encontrado."
    exit 1
fi

# Limpar PATH: remover TODOS os paths do Hermes
export PATH=$(echo "$PATH" | tr ':' '\n' | grep -vi "hermes" | tr '\n' ':' | sed 's/:$//; s/^://')
export PYTHONPATH="$PROJECT_ROOT/scripts_pipeline"
export PYTHONNOUSERSITE=1

# Lista de áudios para processar (ordem cronológica, não-SAM)
# Formato: "arquivo.mp3|dia"
AUDIOS=(
    "01 SET B1-B5.mp3|01"
    "01 SET B6-B10.mp3|01"
    "02 SET B1-B5.mp3|02"
    "02 SET B6-B10.mp3|02"
    "03 SET B1-B5.mp3|03"
    "03 SET B6-B10.mp3|03"
    "04 SET B1-B5.mp3|04"
    "04 SET B6-B10.mp3|04"
    "05 SET B1-B5.mp3|05"
    "05 SET B6-B10.mp3|05"
    "06 SET B1-B5.mp3|06"
    "06 SET B6-B10.mp3|06"
    "07 SET B1-B5.mp3|07"
    "07 SET B6-B10.mp3|07"
    "08 SET B1-B5.mp3|08"
    "08 SET B6-B10.mp3|08"
    "09 SET B1-B5.mp3|09"
    "09 SET B6-B10.mp3|09"
    "10 SET B1-B5.mp3|10"
    "10 SET B6-B10.mp3|10"
    "11 SET B1-B5.mp3|11"
    "11 SET B6-B10.mp3|11"
    "12 SET B1-B5.mp3|12"
    "12 SET B6-B10.mp3|12"
    "13 SET B1-B5.mp3|13"
    "13 SET B6-B10.mp3|13"
    "14 SET B1-B5.mp3|14"
    "14 SET B6-B10.mp3|14"
    "15 SET B1-B5.mp3|15"
    "15 SET B6-B10.mp3|15"
    "16 SET B1-B5.mp3|16"
    "16 SET B6-B10.mp3|16"
    "17 SET B1-B5.mp3|17"
    "17 SET B6-B10.mp3|17"
    "18 SET B1-B5.mp3|18"
    "18 SET B6-B10.mp3|18"
    "19 SET B1-B5.mp3|19"
    "19 SET B6-B10.mp3|19"
    "20 SET B1-B5.mp3|20"
    "20 SET B6-B10.mp3|20"
    "21 SET B1-B5.mp3|21"
    "21 SET B6-B10.mp3|21"
    "22 SET B1-B5.mp3|22"
    "22 SET B6-B10.mp3|22"
    "23 SET B1-B5.mp3|23"
    "23 SET B6-B10.mp3|23"
)

# Arquivos já editados por SAM (pular)
SAM_FILES=(
    "01 SET B1-B5"
    "01 SET B6-B10"
    "02 SET B1-B5"
    "02 SET B6-B10"
    "03 SET B1-B5"
    "03 SET B6-B10"
    "04 SET B1-B5"
    "04 SET B6-B10"
    "05 SET B1-B5"
    "05 SET B6-B10"
    "06 SET B1-B5"
    "06 SET B6-B10"
    "07 SET B1-B5"
    "07 SET B6-B10"
    "08 SET B1-B5"
    "08 SET B6-B10"
    "09 SET B1-B5"
    "09 SET B6-B10"
    "10 SET B1-B5"
    "10 SET B6-B10"
)

TOTAL=${#AUDIOS[@]}
PROCESSADOS=0
PULADOS=0
FALHAS=0

echo "========================================"
echo "PROCESSAMENTO DE SETEMBRO - PIPELINE DIVISOR"
echo "Total de áudios: $TOTAL"
echo "========================================"

for ENTRY in "${AUDIOS[@]}"; do
    IFS='|' read -r ARQUIVO DIA <<< "$ENTRY"
    CAMINHO="$AUDIOS_DIR/$ARQUIVO"
    
    # Verificar se arquivo existe
    if [ ! -f "$CAMINHO" ]; then
        echo "⚠️  [$DIA/09] $ARQUIVO - NÃO ENCONTRADO, pulando"
        continue
    fi
    
    # Verificar se é SAM (pular)
    BASE_NAME="${ARQUIVO%.mp3}"
    IS_SAM=0
    for SAM in "${SAM_FILES[@]}"; do
        if [ "$BASE_NAME" = "$SAM" ]; then
            IS_SAM=1
            break
        fi
    done
    
    if [ $IS_SAM -eq 1 ]; then
        echo "⏭️  [$DIA/09] $ARQUIVO - SAM, pulando"
        PULADOS=$((PULADOS + 1))
        continue
    fi
    
    # Verificar se já foi processado (pasta de saída existe)
    SAIDA_DIR="$AUDIOS_DIR/${BASE_NAME}_saida"
    if [ -d "$SAIDA_DIR" ] && [ "$(ls -A "$SAIDA_DIR" 2>/dev/null)" ]; then
        echo "✅ [$DIA/09] $ARQUIVO - JÁ PROCESSADO, pulando"
        PROCESSADOS=$((PROCESSADOS + 1))
        continue
    fi
    
    echo ""
    echo "🔄 [$DIA/09] Processando: $ARQUIVO"
    echo "   Início: $(date '+%H:%M:%S')"
    
    LOG_FILE="$LOGS_DIR/log_${BASE_NAME}.txt"
    
    if "$VENV_PYTHON" "$PIPELINE" "$CAMINHO" --roteiros "$ROTEIROS_DIR/" > "$LOG_FILE" 2>&1; then
        BOLETINS=$(grep -c "montado →" "$LOG_FILE" 2>/dev/null || echo 0)
        echo "   ✅ Sucesso! $BOLETINS boletins gerados"
        PROCESSADOS=$((PROCESSADOS + 1))
    else
        echo "   ❌ Falha! Ver: $LOG_FILE"
        FALHAS=$((FALHAS + 1))
        # Mostrar última linha do log
        tail -3 "$LOG_FILE" | sed 's/^/      /'
    fi
    
    echo "   Fim: $(date '+%H:%M:%S')"
done

echo ""
echo "========================================"
echo "RESUMO: $PROCESSADOS processados, $PULADOS pulados (SAM), $FALHAS falhas"
echo "========================================"
