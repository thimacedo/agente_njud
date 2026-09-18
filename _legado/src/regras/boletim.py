"""
regras/boletim.py — Regras específicas do BOLETIM.

Contratos:
- Processa o que existe (não seleciona)
- Saída: CABECA.wav, CORPO.wav
- Unidade = boletim (vinheta abertura → cabeça → vinheta passagem → corpo → vinheta encerramento)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from .livro import (
    JanelaColeta,
    OrigemBoletim,
    SelecaoBoletins,
    TipoPrograma,
    extrair_data_boletim,
    extrair_id_boletim,
)

logger = logging.getLogger(__name__)

# ===========================================================================
# CONSTANTES BOLETIM
# ===========================================================================

# O BOLETIM processa o que existe — sem gate mínimo de quantidade
MINIMO_BOLETINS = 0  # Não há mínimo; processa o que tem


# ===========================================================================
# TIPOS ESPECÍFICOS
# ===========================================================================


@dataclass
class PlanejamentoBoletim:
    """
    Planejamento de processamento de boletins.

    O BOLETIM não seleciona — processa o que existe na pasta.

    Attributes:
        data: data de referência
        boletins: boletins encontrados para processar
    """
    data: Optional[date] = None
    boletins: list[OrigemBoletim] = field(default_factory=list)

    @property
    def quantidade(self) -> int:
        return len(self.boletins)

    @property
    def valido(self) -> bool:
        # Sempre válido — processa o que existe
        return True


# ===========================================================================
# FUNÇÕES DE REGRA
# ===========================================================================


def listar_boletins_para_processar(
    pasta_origem: Path,
    data_referencia: Optional[date] = None,
) -> SelecaoBoletins:
    """
    Lista boletins disponíveis para processamento.

    O BOLETIM não seleciona — processa o que existe.
    Filtra apenas por data se especificado.

    Args:
        pasta_origem: pasta onde procurar boletins
        data_referencia: se especificado, filtra apenas boletins desta data

    Returns:
        SelecaoBoletins com todos os boletins encontrados
    """
    boletins: list[OrigemBoletim] = []

    if not pasta_origem.exists():
        logger.warning(f"Pasta de origem não existe: {pasta_origem}")
        return SelecaoBoletins(
            programa=TipoPrograma.BOLETIM,
            janela=JanelaColeta(
                data_inicio=date.min,
                data_fim=date.max,
            ),
            boletins=[],
        )

    # Buscar arquivos mp3 na pasta
    for caminho in sorted(pasta_origem.rglob("*.mp3")):
        nome = caminho.name
        try:
            data_boletim = extrair_data_boletim(nome)
            id_boletim = extrair_id_boletim(nome)
        except ValueError:
            logger.debug(f"Ignorando arquivo fora do padrão: {nome}")
            continue

        # Filtrar por data se especificado
        if data_referencia and data_boletim != data_referencia:
            continue

        boletins.append(
            OrigemBoletim(
                caminho_absoluto=caminho,
                nome_arquivo=nome,
                id_boletim=id_boletim,
                data=data_boletim,
            )
        )

    # Ordenar por data e id
    boletins.sort(key=lambda b: (b.data, b.id_boletim))

    # Janela baseada nos boletins encontrados
    if boletins:
        datas = [b.data for b in boletins]
        janela = JanelaColeta(
            data_inicio=min(datas),
            data_fim=max(datas),
        )
    else:
        janela = JanelaColeta(
            data_inicio=date.today(),
            data_fim=date.today(),
        )

    return SelecaoBoletins(
        programa=TipoPrograma.BOLETIM,
        janela=janela,
        boletins=boletins,
        metadados={"data_referencia": str(data_referencia) if data_referencia else None},
    )


def gerar_nomes_saida_boletim(nome_boletim: str) -> tuple[str, str]:
    """
    Gera os nomes dos arquivos de saída do boletim.

    Formato: CABECA.wav, CORPO.wav
    O prefixo é derivado do nome do boletim.

    Args:
        nome_boletim: stem do arquivo de boletim

    Returns:
        Tupla (nome_cabeca, nome_corpo)
    """
    return (f"{nome_boletim}_CABECA.wav", f"{nome_boletim}_CORPO.wav")


def criar_planejamento_boletim(
    pasta_origem: Path,
    data_referencia: Optional[date] = None,
) -> PlanejamentoBoletim:
    """
    Cria um planejamento de processamento de boletins.

    Args:
        pasta_origem: pasta onde procurar boletins
        data_referencia: se especificado, filtra apenas esta data

    Returns:
        PlanejamentoBoletim com boletins encontrados
    """
    selecao = listar_boletins_para_processar(pasta_origem, data_referencia)
    return PlanejamentoBoletim(
        data=data_referencia,
        boletins=selecao.boletins,
    )
