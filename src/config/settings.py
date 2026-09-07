"""Configurações globais do pipeline DIVISOR — DEPRECATED (compat).

A classe Settings abaixo é mantida como alias para SettingsNJUD
para compatibilidade com código herdado que faz:
    from config.settings import settings

Novo código deve usar:
    from config.njud import settings  # para NJUD
    from config.giro import settings  # para GIRO

A classe Settings aqui é uma subclasse de SettingsNJUD com o mesmo nome
histórico, garantindo que imports antigos continuem funcionando.
"""
from __future__ import annotations

from .njud import SettingsNJUD

# Alias histórico para compatibilidade regressiva
Settings = SettingsNJUD  # type: ignore[misc,assignment]

# Instância global — mantém a mesma interface antiga
settings = SettingsNJUD()
