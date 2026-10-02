#!/usr/bin/env python3
"""Compatibilidade: o montador auxiliar antigo foi retirado por duplicar boletins.

Preparar com njud.controle_producao e usar montagem_jornais.py.
"""

def montar_jornal(boletins_paths, output_dir, nome_jornal=None, normalizar=True, target_lufs=-16.0):
    raise RuntimeError("Montador auxiliar desativado: repetia boletins inteiros. Preparar com njud.controle_producao e montar com montagem_jornais.py.")

if __name__ == "__main__":
    raise SystemExit("Use njud.controle_producao para preparar e montagem_jornais.py para montar.")
