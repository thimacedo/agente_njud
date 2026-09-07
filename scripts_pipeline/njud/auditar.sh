#!/bin/bash
# ============================================================
# NJUD — Auditoria de integridade dos jornais montados
# Verifica: cortes (_CABECA/_CORPO), duração, contexto.
#
# Uso:
#   bash scripts_pipeline/njud/auditar.sh
# ============================================================

set -euo pipefail

BASE_DIR="E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR"
SCRIPTS_DIR="$BASE_DIR/scripts_pipeline"
PYTHON="${PYTHON:-python}"

cd "$BASE_DIR"

echo "========================================"
echo "NJUD — AUDITORIA DE INTEGRIDADE"
echo "========================================"

# Executa auditoria v2 (etapa3_auditoria_montagem.py)
"$PYTHON" "$SCRIPTS_DIR/etapa3_auditoria_montagem.py"

# Se houver problemas, sugere reprocessamento
echo ""
echo "========================================"
echo "AUDITORIA CONCLUÍDA"
echo "========================================"

# Verifica se há NJUDs para refazer
if grep -q "NECESSITA REFAZER" "$BASE_DIR/logs/auditoria_v2.log" 2>/dev/null; then
    echo ""
    echo "⚠ NJUDs com problemas detectados!"
    echo "  Para refazer a montagem, execute:"
    echo "    bash scripts_pipeline/njud/divide.sh montar"
else
    echo ""
    echo "✓ Todos os NJUDs auditados com sucesso."
fi
