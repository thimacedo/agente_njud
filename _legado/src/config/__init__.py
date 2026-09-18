"""Configurações base compartilhadas entre módulos NJUD e GIRO.

Contém a classe BaseSettings com propriedades comuns a ambos os módulos.
Módulos específicos criam subclasses em njud.py e giro.py.

Este pacote fornece apenas a classe base. Para usar:
    from config.njud import settings as njud_settings
    from config.giro import settings as giro_settings
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class BaseSettings:
    """Configurações-base compartilhadas (herdadas por NJUD e GIRO)."""

    def __init__(self, env_file: Optional[str] = None) -> None:
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        raiz_padrao = Path(__file__).resolve().parents[2]
        self.BASE_DIR = Path(os.getenv("BASE_DIR", str(raiz_padrao)))
        self.ASSETS_DIR = self.BASE_DIR / "assets"
        self.VINHETAS_DIR = self.ASSETS_DIR / "vinhetas"
        self.LOGS_DIR = Path(os.getenv("LOGS_DIR", str(self.BASE_DIR / "logs")))
        self.DATA_DIR = self.BASE_DIR / "data"
        self.CACHE_DIR = self.DATA_DIR / "cache"

        # Whisper
        self.MODELO_WHISPER = os.getenv("MODELO_WHISPER", "tiny")
        self.COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "int8")

        # Metadados
        self.VERSAO_PIPELINE = os.getenv("VERSAO_PIPELINE", "2.0.0")
        self.PROJETO_NOME = os.getenv("PROJETO_NOME", "DIVISOR")

    def to_dict(self) -> dict:
        return {
            "BASE_DIR": str(self.BASE_DIR),
            "ASSETS_DIR": str(self.ASSETS_DIR),
            "VINHETAS_DIR": str(self.VINHETAS_DIR),
            "LOGS_DIR": str(self.LOGS_DIR),
            "DATA_DIR": str(self.DATA_DIR),
            "CACHE_DIR": str(self.CACHE_DIR),
            "MODELO_WHISPER": self.MODELO_WHISPER,
            "COMPUTE_TYPE": self.COMPUTE_TYPE,
            "VERSAO_PIPELINE": self.VERSAO_PIPELINE,
            "PROJETO_NOME": self.PROJETO_NOME,
        }


# Instância global — usada apenas para acesso rápido a caminhos comuns
settings = BaseSettings()
