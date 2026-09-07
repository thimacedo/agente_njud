"""Configurações específicas do módulo NJUD.

Herda de BaseSettings e adiciona propriedades e thresholds
exclusivos do pipeline de divisão e montagem de jornais.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import BaseSettings


class SettingsNJUD(BaseSettings):
    """Configurações do pipeline NJUD (Jornal Noticioso)."""

    def __init__(self, env_file: str | None = None) -> None:
        super().__init__(env_file)

        # --- Diretórios de dados ---
        self.BOLETINS_BRUTOS = os.getenv(
            "BOLETINS_BRUTOS",
            str(self.BASE_DIR / "boletins_brutos"),
        )
        self.BOLETINS_CORTADOS = os.getenv(
            "BOLETINS_CORTADOS",
            str(self.DATA_DIR / "processed" / "PRODUCAO_2026" / "JORNAIS_DIVIDIDOS"),
        )
        self.DIR_OUTPUT = Path(os.getenv(
            "DIR_OUTPUT",
            str(self.DATA_DIR / "output"),
        ))
        self.JORNAIS_MONTADOS = os.getenv(
            "JORNAIS_MONTADOS",
            str(self.DIR_OUTPUT / "JORNAIS_FINAL"),
        )
        self.ESTADO_DIR = self.DATA_DIR / "processed" / "PRODUCAO_2026" / "estado_por_arquivo"

        # --- Drive ---
        self.DRIVE_SYNC = os.getenv(
            "DRIVE_SYNC",
            r"H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\02_JORNAIS_NJUD\03_AUDIOS_RADIO",
        )
        self.DIR_DRIVE_JORNAIS = Path(os.getenv(
            "DIR_DRIVE_JORNAIS",
            self.DRIVE_SYNC,
        ))

        # --- Logs (namespaced por módulo) ---
        self.LOGS_DIR_NJUD = self.LOGS_DIR / "njud"

        # --- Cache (namespaced por módulo) ---
        self.CACHE_TRANSCRICOES = self.CACHE_DIR / "njud" / "transcricoes"
        self.CACHE_VAD = self.CACHE_DIR / "njud" / "vad"

        # --- Vinhetas (subpasta do módulo) ---
        self.VINHETAS_DIR = self.BASE_DIR / "assets" / "vinhetas" / "njud"

        # --- Parâmetros de qualidade de áudio ---
        self.DURACAO_MINIMA_BOLETIM = float(os.getenv("DURACAO_MINIMA_BOLETIM", "2.0"))
        self.DURACAO_MINIMA_JORNAL = float(os.getenv("DURACAO_MINIMA_JORNAL", "60.0"))
        self.TAMANHO_MINIMO_ARQUIVO = int(os.getenv("TAMANHO_MINIMO_ARQUIVO", "102400"))  # 100KB
        self.LIMIAR_SILENCIO = float(os.getenv("LIMIAR_SILENCIO", "-50.0"))  # dB

        # --- Parâmetros de retry ---
        self.MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
        self.RETRY_DELAY = float(os.getenv("RETRY_DELAY", "1.0"))
        self.RETRY_BACKOFF = float(os.getenv("RETRY_BACKOFF", "2.0"))

        # --- Configurações de NJUD ---
        self.BOLETINS_POR_JORNAL = int(os.getenv("BOLETINS_POR_JORNAL", "4"))
        self.INTERCALAR_VOCES = os.getenv("INTERCALAR_VOCES", "true").lower() == "true"
        self.BLOCO_INTERCALACAO = int(os.getenv("BLOCO_INTERCALACAO", "5"))

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "BOLETINS_BRUTOS": self.BOLETINS_BRUTOS,
            "BOLETINS_CORTADOS": self.BOLETINS_CORTADOS,
            "JORNAIS_MONTADOS": self.JORNAIS_MONTADOS,
            "DRIVE_SYNC": self.DRIVE_SYNC,
            "LOGS_DIR_NJUD": str(self.LOGS_DIR_NJUD),
            "CACHE_TRANSCRICOES": str(self.CACHE_TRANSCRICOES),
            "CACHE_VAD": str(self.CACHE_VAD),
            "VINHETAS_DIR": str(self.VINHETAS_DIR),
            "BOLETINS_POR_JORNAL": self.BOLETINS_POR_JORNAL,
            "INTERCALAR_VOCES": self.INTERCALAR_VOCES,
        })
        return base


# Instância global
settings = SettingsNJUD()
