# coding: utf-8
"""
Módulo GIRO nas Comarcas — pacote principal.

Processamento semanal de notícias do TJRN (Rio Grande do Norte),
com filtro geográfico (exceto Natal / inegociável: fora RN) e
montagem com vinhetas próprias (VHT_ABERTURA_GIRO, PASSAGEM_GIRO,
ENCERRAMENTO_GIRO).

Estrutura:
    src/giro/
        __init__.py    ← este arquivo
        __main__.py    ← entry point (python -m giro ...)
        cli.py         ← argparse CLI
        config.py      ← configurações, âncoras, thresholds
        montagem.py    ← montador do programa
        plano.py       ← gerador de plano mmss
        filtro.py      ← filtro geográfico
        log.py         ← logger do GIRO
        utils.py       ← utilitários (mmss, data, texto)
"""

from __future__ import annotations

import warnings

warnings.warn(
    "src/giro/* (cli.py, transcricao.py, filtro.py, montagem.py, plano.py, "
    "sync_drive.py) documentado em AGENTE_GIRO.md como se fosse o pipeline "
    "real, mas NAO e importado pela cadeia de producao confirmada. O GIRO em "
    "producao usa scripts_pipeline/executar_programa.py -> "
    "core.processamento.processar_boletim -> divisor_boletins/audio.py "
    "(mesmo nucleo do NJUD). Confirmado em ARQUITETURA_REAL.md. Se a intencao "
    "e migrar para esta arquitetura, e uma decisao de projeto separada, nao "
    "uma correcao de bug.",
    DeprecationWarning,
    stacklevel=2,
)

__version__ = "0.1.0"
__project__ = "GIRO nas Comarcas"
__descripcion__ = (
    "Processamento semanal de notícias do TJRN para o programa "
    "GIRO nas Comarcas (Rádio TJRN)."
)

# Nomes de arquivos de saída
from .utils import nome_programa, nome_corte_nota

# Submódulos (importados sob demanda para evitar circular import)
# from . import cli  # FLAKE8
# from . import config  # FLAKE8
# from . import filtro  # FLAKE8
# from . import log  # FLAKE8
# from . import montagem  # FLAKE8
# from . import plano  # FLAKE8
from . import utils  # Circular-safe: utils não importa nada de giro
from . import transcricao  # Módulo de transcrição e corte

# Importação tardia (embutida em funções, não aqui)
_cli = None
_config = None
_filtro = None
_log = None
_montagem = None
_plano = None


def __getattr__(name: str):
    """Importação lazy para evitar circular import."""
    import importlib

    mapeamento = {
        "cli": "cli",
        "config": "config",
        "filtro": "filtro",
        "log": "log",
        "montagem": "montagem",
        "plano": "plano",
    }
    if name in mapeamento:
        modulo = importlib.import_module(f".{mapeamento[name]}", __name__)
        globals()[f"_{name}"] = modulo
        return modulo
    raise AttributeError(f"módulo {__name__!r} não possui atributo {name!r}")


__all__ = [
    "cli",
    "config",
    "filtro",
    "log",
    "montagem",
    "plano",
    "transcricao",
    "utils",
    "nome_programa",
    "nome_corte_nota",
]
