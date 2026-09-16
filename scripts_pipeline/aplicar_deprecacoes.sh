#!/usr/bin/env bash
# aplicar_deprecacoes.sh — Itens 3 e 4 do ARQUITETURA_ALVO_2026-09-14.md
# Arquiva os originais em .trash/2026-09-14_deprecados_orquestradores/
# antes de sobrescrever (mesmo padrão do limpar_workspace.sh).

set -euo pipefail
WORKSPACE_ROOT="${WORKSPACE_ROOT:-.}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TRASH_DIR="$WORKSPACE_ROOT/.trash/$(date +%Y-%m-%d)_deprecados_orquestradores"
mkdir -p "$TRASH_DIR"

echo "== Item 3: 8 orquestradores não-canônicos de scripts_pipeline/ =="
for f in orquestrador.py orquestrador_giro_jan2026.py processar_serial.py \
         processar_njud_por_njud.py processor_v2.py processor_v3.py \
         processor_com_heartbeat.py dispatcher_wrapper.py; do
  origem="$WORKSPACE_ROOT/scripts_pipeline/$f"
  if [ -f "$origem" ]; then
    cp -v "$origem" "$TRASH_DIR/$f"
    cp -v "$PATCH_DIR/scripts_pipeline/$f" "$origem"
  else
    echo "  [aviso] não encontrado, pulando: $f"
  fi
done

echo
echo "== Item 4: avisos runtime em código morto confirmado =="
declare -A ITEM4=(
  ["src/giro/__init__.py"]="src/giro/__init__.py"
  ["src/regras/__init__.py"]="src/regras/__init__.py"
  ["src/sync/coletor.py"]="src/sync/coletor.py"
)
for rel in "${!ITEM4[@]}"; do
  origem="$WORKSPACE_ROOT/$rel"
  if [ -f "$origem" ]; then
    cp -v "$origem" "$TRASH_DIR/$(basename "$rel")_ORIGINAL"
  fi
  mkdir -p "$WORKSPACE_ROOT/$(dirname "$rel")"
  cp -v "$PATCH_DIR/$rel" "$origem"
done

echo
echo "Concluído. Originais arquivados em: $TRASH_DIR"
echo "Nada foi deletado — revise e rode a suíte de testes antes de commitar."
