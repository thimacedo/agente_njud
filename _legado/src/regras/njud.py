"""
regras/njud.py — Regras específicas do NJUD.

Contratos:
- 4 boletins por jornal
- Janela: dia anterior ao programa
  - Segunda → usa Sexta (3 dias atrás)
  - Terça a Sexta → usa dia anterior
- Sem filtro geográfico
- Saída: NJUD_XXXX_DD-MM-YYYY.mp3

Regra de janela:
  Domingo não tem programa.
   Segunda usa boletins da sexta (3 dias)
   Terça usa boletins da segunda (1 dia)
   Quarta usa boletins da terça (1 dia)
   Quinta usa boletins da quarta (1 dia)
   Sexta usa boletins da quinta (1 dia)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from .livro import (
    JanelaColeta,
    OrigemBoletim,
    SelecaoBoletins,
    TipoPrograma,
    extrair_data_boletim,
    extrair_id_boletim,
    validar_selecao,
)

logger = logging.getLogger(__name__)

# ===========================================================================
# CONSTANTES NJUD
# ===========================================================================

BOLETINS_POR_JORNAL = 4
MINIMO_BOLETINS = 4  # Gate: abaixo disso, programa inválido


# ===========================================================================
# TIPOS ESPECÍFICOS
# ===========================================================================


@dataclass
class PlanejamentoNJUD:
    """
    Planejamento de um NJUD específico.
    """
    njud_id: int
    data_exibicao: date
    janela: JanelaColeta
    boletins: list[OrigemBoletim] = field(default_factory=list)

    @property
    def quantidade(self) -> int:
        return len(self.boletins)

    @property
    def valido(self) -> bool:
        return self.quantidade >= MINIMO_BOLETINS


# ===========================================================================
# FUNÇÕES DE REGRA
# ===========================================================================


def calcular_janela_njud(data_exibicao: date) -> JanelaColeta:
    """
    Calcula a janela de coleta para o NJUD.

    Regra:
      - Segunda (weekday=0): usa sexta anterior (3 dias atrás)
      - Terça a Sexta (weekday=1-4): usa dia anterior
      - Sábado/Domingo: não tem programa (janela vazia)
    """
    weekday = data_exibicao.weekday()  # 0=Seg, 1=Ter, ..., 6=Dom

    if weekday == 0:  # Segunda → Sexta anterior
        inicio = data_exibicao - timedelta(days=3)
    elif weekday in (1, 2, 3, 4):  # Terça a Sexta → dia anterior
        inicio = data_exibicao - timedelta(days=1)
    else:  # Sábado/Domingo → sem programa
        return JanelaColeta(data_inicio=data_exibicao, data_fim=data_exibicao - timedelta(days=1))

    return JanelaColeta(data_inicio=inicio, data_fim=inicio)


def selecionar_boletins_njud(
    data_exibicao: date,
    boletins_disponiveis: list[Path],
    njud_id: Optional[int] = None,
) -> SelecaoBoletins:
    """
    Seleciona 4 boletins para um NJUD.

    Regras:
    - Janela: dia anterior (sexta→segunda usa sexta)
    - Sem filtro geográfico
    - 4 boletins por jornal (gate mínimo)
    - Seleciona B1, B2, B3, B4 do dia (ordem numérica)
    """
    janela = calcular_janela_njud(data_exibicao)

    if janela.data_inicio > janela.data_fim:
        raise ValueError(f"NJUD {njud_id}: data {data_exibicao} é fim de semana, sem programa")

    # Filtrar boletins na janela (apenas dia específico)
    boletins_na_janela: list[OrigemBoletim] = []
    for caminho in boletins_disponiveis:
        nome = caminho.name
        try:
            data_boletim = extrair_data_boletim(nome)
            id_boletim = extrair_id_boletim(nome)
        except ValueError:
            continue

        # Apenas boletins do dia exato da janela
        if data_boletim == janela.data_inicio:
            boletins_na_janela.append(
                OrigemBoletim(
                    caminho_absoluto=caminho,
                    nome_arquivo=nome,
                    id_boletim=id_boletim,
                    data=data_boletim,
                )
            )

    # Agrupar por boletim único (id_boletim inclui título = único)
    # Inclui apenas versões principais (CABEÇA + CORPO), ignora v2/RESTORED/etc.
    from collections import defaultdict
    boletins_por_id: dict[str, list[OrigemBoletim]] = defaultdict(list)
    for b in boletins_na_janela:
        nome = b.nome_arquivo
        if "_v2" in nome or "_RESTORED" in nome or "__" in nome:
            continue
        boletins_por_id[b.id_boletim].append(b)

    # Ordenar por número de boletim
    def num_boletim(chave: str) -> int:
        import re
        m = re.search(r'B(\d+)', chave)
        return int(m.group(1)) if m else 999

    ids_ordenados = sorted(boletins_por_id.keys(), key=num_boletim)

    # Selecionar até BOLETINS_POR_JORNAL boletins (cada boletim = CABEÇA + CORPO = 2 arquivos)
    selecionados: list[OrigemBoletim] = []
    for bid in ids_ordenados:
        if len(selecionados) // 2 >= BOLETINS_POR_JORNAL:
            break
        selecionados.extend(boletins_por_id[bid])

    selecao = SelecaoBoletins(
        programa=TipoPrograma.NJUD,
        janela=janela,
        boletins=selecionados,
        metadados={"njud_id": njud_id, "data_exibicao": data_exibicao.isoformat()},
    )

    # Validação
    erros = validar_selecao(selecao)
    if erros:
        logger.warning(f"Validação NJUD com avisos: {erros}")

    if selecao.quantidade < MINIMO_BOLETINS:
        raise ValueError(
            f"NJUD {njud_id}: apenas {selecao.quantidade} boletins na janela "
            f"[{janela.data_inicio} – {janela.data_fim}], mínimo é {MINIMO_BOLETINS}"
        )

    return selecao


def gerar_nome_saida_njud(njud_id: int, data_exibicao: date) -> str:
    """Gera o nome do arquivo de saída: NJUD_XXXX_DD-MM-YYYY.mp3"""
    data_str = data_exibicao.strftime("%d-%m-%Y")
    return f"NJUD_{njud_id:04d}_{data_str}.mp3"


def criar_planejamento_njud(
    njud_id: int,
    data_exibicao: date,
    boletins_disponiveis: list[Path],
) -> PlanejamentoNJUD:
    """Cria um planejamento completo de NJUD."""
    selecao = selecionar_boletins_njud(data_exibicao, boletins_disponiveis, njud_id)
    return PlanejamentoNJUD(
        njud_id=njud_id,
        data_exibicao=data_exibicao,
        janela=selecao.janela,
        boletins=selecao.boletins,
    )
