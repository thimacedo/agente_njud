"""
Sistema de log dual (TXT + JSONL) para o pipeline.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EventoLog:
    timestamp: str
    nivel: str
    etapa: str
    mensagem: str
    dados: dict = field(default_factory=dict)


def _serializar_dados(dados: dict | None) -> dict:
    if dados is None:
        return {}
    resultado = {}
    for k, v in dados.items():
        if isinstance(v, Path):
            resultado[k] = str(v)
        elif isinstance(v, dict):
            resultado[k] = _serializar_dados(v)
        elif isinstance(v, (list, tuple)):
            resultado[k] = [
                _serializar_dados({i: x})[i] if isinstance(x, Path) else x
                for i, x in enumerate(v)
            ]
        else:
            resultado[k] = v
    return resultado


class LogPipeline:
    NIVEIS = {"INFO", "AVISO", "ERRO"}

    def __init__(self, log_dir: str | Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._txt_path = self.log_dir / "divisor_log.txt"
        self._jsonl_path = self.log_dir / "divisor_log.jsonl"

    def _escrever(
        self, nivel: str, etapa: str, mensagem: str, dados: dict | None = None
    ):
        if nivel not in self.NIVEIS:
            nivel = "INFO"
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        dados = dados or {}

        marker = ""
        if nivel == "AVISO":
            marker = "⚠ "
        elif nivel == "ERRO":
            marker = "✖ "
        linha_txt = f"[{ts}] [{nivel}] {marker}{etapa}: {mensagem}"
        if dados:
            dados_str = {k: str(v) for k, v in dados.items()}
            linha_txt += f" | {dados_str}"
        linha_txt += "\n"

        dados_serializaveis = _serializar_dados(dados)
        evento = EventoLog(
            timestamp=ts,
            nivel=nivel,
            etapa=etapa,
            mensagem=mensagem,
            dados=dados_serializaveis,
        )

        try:
            with open(self._txt_path, "a", encoding="utf-8") as f:
                f.write(linha_txt)
            with open(self._jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(evento.__dict__, ensure_ascii=False) + "\n")
        except (OSError, TypeError):
            pass

    def info(self, etapa: str, mensagem: str, **dados):
        self._escrever("INFO", etapa, mensagem, dados)

    def aviso(self, etapa: str, mensagem: str, **dados):
        self._escrever("AVISO", etapa, mensagem, dados)

    def erro(self, etapa: str, mensagem: str, **dados):
        self._escrever("ERRO", etapa, mensagem, dados)
