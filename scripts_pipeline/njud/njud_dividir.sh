#!/bin/bash
# ============================================================
# NJUD — Divisão e montagem (Fase 2 do pipeline)
# 1. Divide boletins em _CABECA/_CORPO
# 2. Monta jornais completos (4 boletins por jornal)
#
# Uso:
#   bash scripts_pipeline/njud/divide.sh <pasta_boletins>
#   bash scripts_pipeline/njud/montar.sh
# ============================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_DIR="$BASE_DIR/src"
SCRIPTS_DIR="$BASE_DIR/scripts_pipeline"
PYTHON="${PYTHON:-$BASE_DIR/.venv_pipeline/Scripts/python.exe}"
if [ ! -x "$PYTHON" ]; then
    PYTHON="$BASE_DIR/.venv_pipeline/bin/python"
fi
[ -x "$PYTHON" ] || { echo "Crie .venv_pipeline antes de executar." >&2; exit 1; }
case "$PYTHON" in
    *.exe) PATH_SEP=';' ;;
    *) PATH_SEP=':' ;;
esac
export PYTHONPATH="$SCRIPTS_DIR${PYTHONPATH:+$PATH_SEP$PYTHONPATH}"

export DIVISOR_TMP="${DIVISOR_TMP:-$BASE_DIR/data/tmp}"
mkdir -p "$DIVISOR_TMP"

cd "$BASE_DIR"

# ============================================================
# DIVISÃO
# ============================================================
divider() {
    local pasta_entrada="${1:?Uso: divide.sh <pasta_boletins>}"
    local pasta_saida="${2:-data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS}"

    echo "========================================"
    echo "NJUD — DIVISÃO DE BOLETINS"
    echo "========================================"
    echo "Entrada : $pasta_entrada"
    echo "Saída   : $pasta_saida"
    echo ""

    "$PYTHON" -m divisor_boletins dividir "$pasta_entrada" "$pasta_saida" --apply

    echo ""
    echo "========================================"
    echo "DIVISÃO CONCLUÍDA"
    echo "========================================"
}

# ============================================================
# MONTAGEM
# ============================================================
montador() {
    local pasta_entrada="${1:-data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS}"
    local pasta_saida="${2:-data/output/JORNAIS_FINAL}"
    local roteiro="${3:-}"

    echo "=========================================="
    echo "NJUD — MONTAGEM DE JORNAIS"
    echo "=========================================="
    echo "Entrada : $pasta_entrada"
    echo "Saída   : $pasta_saida"
    [ -n "$roteiro" ] && echo "Roteiro : $roteiro"
    echo ""

    # montagem_jornais.py detecta sozinho o modo (cortes prontos OU MP3s
    # brutos) e aplica o BG da RECEITA_NJUD.txt em ambos os casos.
    if [ -n "$roteiro" ]; then
        "$PYTHON" "$SCRIPTS_DIR/montagem_jornais.py" "$pasta_entrada" "$pasta_saida" --roteiro "$roteiro"
    else
        "$PYTHON" "$SCRIPTS_DIR/montagem_jornais.py" "$pasta_entrada" "$pasta_saida"
    fi

    echo ""
    echo "=========================================="
    echo "MONTAGEM CONCLUÍDA"
    echo "=========================================="
}

# Dispatcher por argumento
case "${1:-}" in
    preparar)
        "$PYTHON" -m njud.controle_producao preparar "${2:?Informe o manifesto de entrada}" "${3:?Informe uma pasta nova para a versão}"
        ;;
    aprendizado)
        "$PYTHON" -m njud.controle_producao aprendizado "${2:?Informe a pasta de eventos de auditoria}"
        ;;
    divide)
        divider "${2:-}" "${3:-}"
        ;;
    montar)
        montador "${2:-}" "${3:-}"
        ;;
    *)
        echo "Uso:"
        echo "  bash scripts_pipeline/njud/njud_dividir.sh preparar <manifesto.json> <pasta_nova/NJUD_numero>"
        echo "  bash scripts_pipeline/njud/njud_dividir.sh aprendizado <pasta_eventos>"
        echo "  bash scripts_pipeline/njud/divide.sh divide <pasta_boletins> [pasta_saida]"
        echo "  bash scripts_pipeline/njud/divide.sh montar [pasta_entrada] [pasta_saida]"
        exit 1
        ;;
esac
