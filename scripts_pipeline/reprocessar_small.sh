#!/bin/bash
# reprocessar_small.sh — Reprocessa todos os dias não-SAM com modelo small
set -e
cd "E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"

export PATH=$(echo "$PATH" | tr ':' '\n' | grep -vi hermes | tr '\n' ':' | sed 's/:$//; s/^://')
export PYTHONPATH=scripts_pipeline
export PYTHONNOUSERSITE=1
export PYTHONIOENCODING=utf-8
export DIVISOR_WHISPER_MODEL=small

AUDIOS=(
  "11 SET B6-B10.mp3"
  "15 SET B6-B10.mp3"
  "16 SET B1B5.mp3"
  "18 SET B6-B10.mp3"
  "21 SET B1-B4.mp3"
  "21 SET B5-B10.mp3"
  "22 SET B1-B5.mp3"
  "22 SET B6-B10.mp3"
)

for arq in "${AUDIOS[@]}"; do
  echo ""
  echo "=========================================="
  echo "🔄 Reprocessando: $arq"
  echo "=========================================="
  .venv_pipeline/Scripts/python.exe scripts_pipeline/boletim/processar_boletim_canonico.py "setembro/$arq" --roteiros setembro/ 2>&1 | tail -5
  echo "✅ Concluído: $arq"
done

echo ""
echo "=========================================="
echo "🎉 TODOS REPROCESSADOS"
echo "=========================================="
