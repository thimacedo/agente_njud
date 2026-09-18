# coding: utf-8
"""
Entry point do módulo GIRO nas Comarcas.

Uso:
    python -m giro --help
    python -m giro processar <pasta_boletins> --saida <dir>
    python -m giro --lista-plano
    python -m giro --montar <pasta_notas>
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    import sys
    sys.exit(main())
