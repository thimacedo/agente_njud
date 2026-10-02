#!/bin/bash
# Ação e edição explícitas; nenhum lote executado implicitamente.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python}" "$SCRIPT_DIR/../executar_programa.py" "$@"
