"""Ponto de entrada canônico GIRO; não executa planos legados sem manifesto."""
import sys
sys.dont_write_bytecode = True
from giro.processo import main

if __name__ == '__main__':
    raise SystemExit(main())
