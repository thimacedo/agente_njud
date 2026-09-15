"""
core/processamento/estado_arquivo.py — Estado persistido de um arquivo no pipeline.

Este módulo foi extraído de processar_boletim.py para resolver o import
`from core.processamento.estado_arquivo import EstadoArquivo`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class EstadoArquivo:
    """Estado persistido de um arquivo no pipeline unificado."""
    arquivo: str
    programa: str
    njud: str = ""
    status: str = "PENDENTE"
    estrategia_atual: str = "calibracao_correlacao"
    tentativas: list = field(default_factory=list)
    erro: str = ""
    arquivo_cabeca: Optional[str] = None
    arquivo_corpo: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "arquivo": self.arquivo,
            "programa": self.programa,
            "njud": self.njud,
            "status": self.status,
            "estrategia_atual": self.estrategia_atual,
            "tentativas": self.tentativas,
            "erro": self.erro,
            "arquivo_cabeca": self.arquivo_cabeca,
            "arquivo_corpo": self.arquivo_corpo,
        }

    @classmethod
    def from_dict(cls, dados: dict) -> "EstadoArquivo":
        return cls(
            arquivo=dados.get("arquivo", ""),
            programa=dados.get("programa", ""),
            njud=dados.get("njud", ""),
            status=dados.get("status", "PENDENTE"),
            estrategia_atual=dados.get("estrategia_atual", "calibracao_correlacao"),
            tentativas=dados.get("tentativas", []),
            erro=dados.get("erro", ""),
            arquivo_cabeca=dados.get("arquivo_cabeca"),
            arquivo_corpo=dados.get("arquivo_corpo"),
        )


def carregar_estado(arquivo: str, programa: str, njud: str, pasta_estado: Path) -> EstadoArquivo:
    """Carrega ou cria estado persistido por arquivo."""
    caminho = pasta_estado / f"{Path(arquivo).stem}.json"
    if caminho.exists():
        try:
            import json
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            return EstadoArquivo.from_dict(dados)
        except Exception:
            pass
    return EstadoArquivo(arquivo=arquivo, programa=programa, njud=njud)


def salvar_estado(estado: EstadoArquivo, pasta_estado: Path) -> None:
    """Persiste estado no disco."""
    import json
    caminho = pasta_estado / f"{Path(estado.arquivo).stem}.json"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(estado.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
