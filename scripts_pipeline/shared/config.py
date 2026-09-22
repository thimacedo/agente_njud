#!/usr/bin/env python3
"""
config.py — Config centralizada do pipeline DIVISOR.

Elimina a dependencia circular de thresholds:
- Antes: supervisor.py escrevia .supervisor_env, pipeline nao lia automaticamente
- Agora: DivisorConfig.carregar() le env vars, .aplicar() seta env vars

Uso:
    from shared.config import DivisorConfig
    config = DivisorConfig.carregar()
    config.cobertura_min = 0.65
    config.aplicar()  # Atualiza env vars para todos os modulos
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DivisorConfig:
    """
    Config centralizada do pipeline.
    Prioridade: env vars > defaults
    """
    cobertura_min: float = 0.60
    threshold_similaridade: float = 0.75
    whisper_model: str = "base"
    loudness_lufs: float = -16.0
    loudness_tp: float = -1.5
    loudness_lra: float = 11.0
    use_vad: bool = False
    log_level: str = "INFO"

    def __post_init__(self):
        """Validacao basica de ranges."""
        if not (0.0 <= self.cobertura_min <= 1.0):
            raise ValueError(f"cobertura_min deve ser 0..1, got {self.cobertura_min}")
        if not (0.0 <= self.threshold_similaridade <= 1.0):
            raise ValueError(f"threshold_similaridade deve ser 0..1, got {self.threshold_similaridade}")

    def aplicar(self):
        """Seta env vars para compatibilidade com codigo legado."""
        os.environ["DIVISOR_COBERTURA_MIN"] = str(self.cobertura_min)
        os.environ["DIVISOR_THRESHOLD_SIMILARIDADE"] = str(self.threshold_similaridade)
        os.environ["DIVISOR_WHISPER_MODEL"] = self.whisper_model
        os.environ["DIVISOR_LOUDNESS_LUFS"] = str(self.loudness_lufs)
        os.environ["DIVISOR_LOUDNESS_TP"] = str(self.loudness_tp)
        os.environ["DIVISOR_LOUDNESS_LRA"] = str(self.loudness_lra)
        os.environ["DIVISOR_USE_VAD"] = str(self.use_vad).lower()
        os.environ["DIVISOR_LOG_LEVEL"] = self.log_level
        return self

    @classmethod
    def carregar(cls) -> "DivisorConfig":
        """Carrega de env vars com fallback para defaults."""
        return cls(
            cobertura_min=float(os.environ.get("DIVISOR_COBERTURA_MIN", "0.6")),
            threshold_similaridade=float(os.environ.get("DIVISOR_THRESHOLD_SIMILARIDADE", "0.75")),
            whisper_model=os.environ.get("DIVISOR_WHISPER_MODEL", "base"),
            loudness_lufs=float(os.environ.get("DIVISOR_LOUDNESS_LUFS", "-16.0")),
            loudness_tp=float(os.environ.get("DIVISOR_LOUDNESS_TP", "-1.5")),
            loudness_lra=float(os.environ.get("DIVISOR_LOUDNESS_LRA", "11.0")),
            use_vad=os.environ.get("DIVISOR_USE_VAD", "false").lower() == "true",
            log_level=os.environ.get("DIVISOR_LOG_LEVEL", "INFO"),
        )


# Singleton global para compatibilidade
_config: Optional[DivisorConfig] = None


def get_config() -> DivisorConfig:
    """Retorna a config global (lazy load)."""
    global _config
    if _config is None:
        _config = DivisorConfig.carregar()
    return _config


def set_config(config: DivisorConfig):
    """Define a config global e aplica env vars."""
    global _config
    _config = config
    config.aplicar()
