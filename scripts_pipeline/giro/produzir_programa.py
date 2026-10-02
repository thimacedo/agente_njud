"""Entrada legada de produção GIRO substituída por ações explícitas."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from giro.processo import main
if __name__ == '__main__':
    raise SystemExit(main())
