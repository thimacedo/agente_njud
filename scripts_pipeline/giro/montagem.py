"""Montagem GIRO exige manifesto editorial; não seleciona arquivos de uma pasta."""
from __future__ import annotations
from pathlib import Path
import sys
sys.dont_write_bytecode = True

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from giro.controle_producao import montar_manifesto_giro


def montar_programa(codigo, notas, output_dir, data_str, assets_dir=None):
    raise ValueError('Montagem por lista/pasta desativada. Use manifesto com giro.processo montar.')


def main(argv=None):
    from giro.processo import main as processo_main
    return processo_main(['montar', *(sys.argv[1:] if argv is None else argv)])


if __name__ == '__main__':
    raise SystemExit(main())
