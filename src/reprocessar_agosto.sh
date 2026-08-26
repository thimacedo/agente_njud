#!/bin/bash
# Reprocessa AGOSTO com código calibrado (LIMIAR_ANCORA=0.55, margens 300ms)
set -e
cd "F:/Projetos/DIVISOR/src"

echo "=== [1/4] Parando processos ativos ==="
ps -W | grep -iE 'python.*(run_pipeline|monitor_paralelo)' | awk '{print $1}' | while read pid; do
    echo "Matando PID $pid"
    taskkill //F //PID "$pid" 2>/dev/null || true
done
sleep 2

echo ""
echo "=== [2/4] Limpando divisão e auditoria de AGOSTO ==="
rm -rf "data/processed/JORNAIS_DIVIDIDOS"
rm -f "data/output/relatorio_auditoria.csv"
mkdir -p "data/processed/JORNAIS_DIVIDIDOS"

echo ""
echo "=== [3/4] Dry-run ==="
python run_pipeline_safe_v2.py --dry-run --batch 2026-08

echo ""
echo "=== [4/4] Apply ==="
python run_pipeline_safe_v2.py --apply --batch 2026-08

echo ""
echo "=== REPROCESSAMENTO CONCLUÍDO ==="
