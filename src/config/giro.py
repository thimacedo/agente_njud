"""Configurações específicas do módulo GIRO nas Comarcas.

Herda de BaseSettings e adiciona propriedades exclusivas
do pipeline de processamento de notícias do GIRO nas Comarcas.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import BaseSettings


class SettingsGiro(BaseSettings):
    """Configurações do pipeline GIRO nas Comarcas."""

    def __init__(self, env_file: str | None = None) -> None:
        super().__init__(env_file)

        # --- Diretórios de dados ---
        self.DIR_PROCESSED = self.DATA_DIR / "processed" / "GIRO_COMARCAS"
        self.DIR_OUTPUT = self.DATA_DIR / "output" / "GIRO_COMARCAS"
        self.DIR_PLANOS = self.DATA_DIR
        self.ESTADO_DIR = self.DIR_PROCESSED / "estado"

        # --- Drive ---
        self.DRIVE_SYNC_GIRO = os.getenv(
            "GNC_DRIVE_SYNC",
            r"H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\02_JORNAIS_GIRO\03_AUDIOS_RADIO",
        )
        self.DIR_DRIVE_GIRO = Path(os.getenv(
            "DIR_DRIVE_GIRO",
            self.DRIVE_SYNC_GIRO,
        ))

        # --- Logs (namespaced por módulo) ---
        self.LOGS_DIR_GIRO = self.LOGS_DIR / "giro"

        # --- Cache (namespaced por módulo) ---
        self.CACHE_TRANSCRICOES = self.CACHE_DIR / "giro" / "transcricoes"

        # --- Vinhetas (subpasta do módulo) ---
        self.VINHETAS_DIR = self.BASE_DIR / "assets" / "vinhetas" / "giro"

        # --- Thresholds do GIRO ---
        self.LIMIAR_ANCORA_GIRO = float(os.getenv("LIMIAR_ANCORA_GIRO", "0.55"))
        self.LIMIAR_FIM_PASSAGEM_GIRO = float(os.getenv("LIMIAR_FIM_PASSAGEM_GIRO", "0.8"))
        self.LIMIAR_INICIO_FALA_GIRO = float(os.getenv("LIMIAR_INICIO_FALA_GIRO", "0.3"))

        # --- Nomes de vinhetas ---
        self.VHT_ABERTURA_GIRO_NOME = "VHT_ABERTURA_GIRO.mp3"
        self.VHT_PASSAGEM_GIRO_NOME = "VHT_PASSAGEM_GIRO.mp3"
        self.VHT_ENCERRAMENTO_GIRO_NOME = "VHT_ENCERRAMENTO_GIRO.mp3"

        # --- Nomenclatura ---
        self.ANO_PADRAO = int(os.getenv("ANO_PADRAO", "2026"))

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "DIR_PROCESSED": str(self.DIR_PROCESSED),
            "DIR_OUTPUT": str(self.DIR_OUTPUT),
            "DIR_PLANOS": str(self.DIR_PLANOS),
            "DRIVE_SYNC_GIRO": self.DRIVE_SYNC_GIRO,
            "LOGS_DIR_GIRO": str(self.LOGS_DIR_GIRO),
            "CACHE_TRANSCRICOES": str(self.CACHE_TRANSCRICOES),
            "VINHETAS_DIR": str(self.VINHETAS_DIR),
            "LIMIAR_ANCORA_GIRO": self.LIMIAR_ANCORA_GIRO,
            "LIMIAR_FIM_PASSAGEM_GIRO": self.LIMIAR_FIM_PASSAGEM_GIRO,
            "LIMIAR_INICIO_FALA_GIRO": self.LIMIAR_INICIO_FALA_GIRO,
            "ANO_PADRAO": self.ANO_PADRAO,
        })
        return base


# Instância global
settings = SettingsGiro()
