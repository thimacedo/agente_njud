#!/bin/bash
# run_pipeline.sh - Executor isolado do pipeline DIVISOR
# Uso: bash scripts_pipeline/run_pipeline.sh <arquivo.mp3> [--roteiros <pasta>]
#
# Isola o Python do Hermes para evitar conflito de memória.
# Usa .venv_pipeline com modelo tiny (economiza RAM).

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv_pipeline/Scripts/python.exe"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERRO: .venv_pipeline não encontrado. Crie com:"
    echo "  python3.11 -m venv .venv_pipeline"
    echo "  .venv_pipeline/Scripts/pip install faster-whisper pydub"
    exit 1
fi

# Limpar PATH: remover TODOS os paths do Hermes
export PATH=$(echo "$PATH" | tr ':' '\n' | grep -vi "hermes" | tr '\n' ':' | sed 's/:$//; s/^://')

# Isolar PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT/scripts_pipeline"

# Desabilitar site packages do usuário (evita imports do Hermes)
export PYTHONNOUSERSITE=1

# Usar modelo tiny para economizar RAM (base falha com mkl_malloc)
export DIVISOR_WHISPER_MODEL=tiny

# Executar - usar caminhos Windows nativos para evitar conversão MSYS
WIN_PROJECT=$(cd "$PROJECT_ROOT" && cygpath -w . 2>/dev/null || echo "$PROJECT_ROOT")
exec "$VENV_PYTHON" "${WIN_PROJECT}\\scripts_pipeline\\boletim\\processar_boletim_canonico.py" "$@"
