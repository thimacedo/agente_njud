"""
regras/giro.py — Regras específicas do GIRO (com filtro geográfico).

Contratos:
- 4-6 boletins por programa
- Janela: semana anterior ao programa
- Filtro geográfico: comarcas distintas, não repetir
- Filtros: excluir fora do RN (inegociável), filtrar Natal (ajustável),
  filtrar institucional TJRN (ajustável)
- Fallback: se menos de 4 comarcas, usar Natal
- Saída: GNC_DD_MM.mp3
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
    calcular_janela_semana_anterior,
    extrair_data_boletim,
    extrair_id_boletim,
    validar_selecao,
)

logger = logging.getLogger(__name__)

# ===========================================================================
# CONSTANTES GIRO
# ===========================================================================

MINIMO_BOLETINS = 4
MAXIMO_BOLETINS = 6

# Filtros ajustáveis (podem ser desabilitados conforme necessidade)
FILTRAR_NATAL_PADRAO = True
FILTRAR_INSTITUCIONAL_TJRN_PADRAO = False  # Institucionais do TJRN são aceitos


# ===========================================================================
# TIPOS ESPECÍFICOS
# ===========================================================================


@dataclass
class PlanejamentoGiro:
    """
    Planejamento de um programa GIRO.

    Attributes:
        codigo: código do programa (ex: "0101" para janeiro semana 1)
        data_exibicao: data de exibição do programa
        janela: janela de coleta calculada
        boletins: boletins selecionados (já filtrados geograficamente)
        comarcas: lista de comarcas distintas selecionadas
        filtros_aplicados: quais filtros foram usados
    """
    codigo: str
    data_exibicao: date
    janela: JanelaColeta
    boletins: list[OrigemBoletim] = field(default_factory=list)
    comarcas: list[str] = field(default_factory=list)
    filtros_aplicados: dict = field(default_factory=dict)

    @property
    def quantidade(self) -> int:
        return len(self.boletins)

    @property
    def valido(self) -> bool:
        return self.quantidade >= MINIMO_BOLETINS


# ===========================================================================
# FUNÇÕES DE REGRA
# ===========================================================================


def selecionar_boletins_giro(
    data_exibicao: date,
    boletins_disponiveis: list[Path],
    codigo: Optional[str] = None,
    janela_dias: int = 6,
    evitar_natal: bool = FILTRAR_NATAL_PADRAO,
    filtrar_institucional: bool = FILTRAR_INSTITUCIONAL_TJRN_PADRAO,
) -> SelecaoBoletins:
    """
    Seleciona boletins para o GIRO com filtro geográfico.

    Regras:
    - Janela: semana anterior ao programa
    - Filtro geográfico: comarcas distintas do RN, não repetir
    - Excluir fora do RN (inegociável)
    - Filtrar Natal (ajustável, padrão=True)
    - Filtrar institucional TJRN (ajustável, padrão=False)
    - Fallback: se menos de 4 comarcas, incluir Natal

    Args:
        data_exibicao: data de exibição do programa
        boletins_disponiveis: lista de caminhos no Drive H:
        codigo: código do programa (opcional, para metadados)
        janela_dias: número de dias na janela (padrão 6)
        evitar_natal: se True, filtra notícias de Natal
        filtrar_institucional: se True, filtra institucionais do TJRN

    Returns:
        SelecaoBoletins com boletins selecionados e filtrados

    Raises:
        ValueError: se menos de 4 boletins mesmo com fallback
    """
    # Importação lazy para evitar circularidade
    from giro.filtro import ClassificacaoGiro, filtrar_nota

    janela = calcular_janela_semana_anterior(data_exibicao, dias=janela_dias)

    # Coletar boletins na janela
    boletins_na_janela: list[OrigemBoletim] = []
    for caminho in boletins_disponiveis:
        nome = caminho.name
        try:
            data_boletim = extrair_data_boletim(nome)
            id_boletim = extrair_id_boletim(nome)
        except ValueError:
            continue

        if data_boletim in janela:
            boletins_na_janela.append(
                OrigemBoletim(
                    caminho_absoluto=caminho,
                    nome_arquivo=nome,
                    id_boletim=id_boletim,
                    data=data_boletim,
                )
            )

    # Agrupar por boletim único (id_boletim agora inclui título = único)
    # Inclui apenas versões principais (CABEÇA + CORPO), ignora v2/RESTORED/etc.
    from collections import defaultdict
    boletins_por_id: dict[str, list[OrigemBoletim]] = defaultdict(list)
    for b in boletins_na_janela:
        nome = b.nome_arquivo
        # Ignora versões duplicadas (v2, RESTORED, __, etc.)
        if "_v2" in nome or "_RESTORED" in nome or "__" in nome:
            continue
        boletins_por_id[b.id_boletim].append(b)

    # Ordenar por data e depois por número de boletim
    def sort_key(chave: str):
        # chave = "B5_CNJ_CONCILIAR_E_LEGAL" — buscar data no primeiro arquivo
        arquivos = boletins_por_id[chave]
        data = arquivos[0].data
        import re
        m = re.search(r'B(\d+)', chave)
        num = int(m.group(1)) if m else 999
        return (data, num)

    ids_ordenados = sorted(boletins_por_id.keys(), key=sort_key)

    # Selecionar até MAXIMO boletins (cada boletim = CABEÇA + CORPO = 2 arquivos)
    selecionados: list[OrigemBoletim] = []
    for bid in ids_ordenados:
        if len(selecionados) // 2 >= MAXIMO_BOLETINS:
            break
        selecionados.extend(boletins_por_id[bid])

    filtros = {
        "evitar_natal": evitar_natal,
        "filtrar_institucional": filtrar_institucional,
        "janela_dias": janela_dias,
    }

    selecao = SelecaoBoletins(
        programa=TipoPrograma.GIRO,
        janela=janela,
        boletins=selecionados,
        metadados={
            "codigo": codigo,
            "data_exibicao": data_exibicao.isoformat(),
            "filtros_aplicados": filtros,
        },
    )

    # Validação
    erros = validar_selecao(selecao)
    if erros:
        logger.warning(f"Validação GIRO com avisos: {erros}")

    if selecao.quantidade < MINIMO_BOLETINS:
        raise ValueError(
            f"GIRO {codigo}: apenas {selecao.quantidade} boletins na janela "
            f"[{janela.data_inicio} – {janela.data_fim}], mínimo é {MINIMO_BOLETINS}"
        )

    return selecao


def aplicar_filtro_geografico_transcricoes(
    boletins: list[OrigemBoletim],
    transcricoes: dict[str, str],
    evitar_natal: bool = FILTRAR_NATAL_PADRAO,
    filtrar_institucional: bool = FILTRAR_INSTITUCIONAL_TJRN_PADRAO,
) -> tuple[list[OrigemBoletim], list[str]]:
    """
    Aplica filtro geográfico baseado em transcrições.

    Usa o módulo giro.filtro para classificar cada nota.
    Implementa o fallback: se menos de 4 comarcas, inclui Natal.

    Args:
        boletins: lista de boletins a filtrar
        transcricoes: dict {nome_arquivo: texto_transcrito}
        evitar_natal: se True, filtra Natal inicialmente
        filtrar_institucional: se True, filtra institucionais

    Returns:
        Tupla (boletins_aceitos, comarcas_distintas)
    """
    from giro.filtro import ClassificacaoGiro, filtrar_nota

    aceitos: list[OrigemBoletim] = []
    comarcas: list[str] = []
    comarcas_usadas: set[str] = set()
    boletins_natal: list[OrigemBoletim] = []

    for b in boletins:
        texto = transcricoes.get(b.nome_arquivo, "")
        if not texto:
            # Sem transcrição: aceitar por padrão (filtrado depois no pipeline)
            aceitos.append(b)
            continue

        resultado = filtrar_nota(texto, evitar_natal=evitar_natal)

        if resultado.classificacao == ClassificacaoGiro.FILTRADA_OUTRO_ESTADO:
            # INEGOCIÁVEL: sempre excluir
            continue

        if resultado.classificacao == ClassificacaoGiro.FILTRADA_NATAL:
            # Guardar para fallback
            boletins_natal.append(b)
            continue

        if resultado.classificacao == ClassificacaoGiro.ACEITA:
            # Verificar se comarca já foi usada
            cidades = resultado.cidades_rn_mencionadas
            if cidades and comarcas_usadas.isdisjoint(set(cidades)):
                comarcas_usadas.update(cidades)
                comarcas.extend(c for c in cidades if c not in comarcas)
                aceitos.append(b)
            elif not cidades:
                # Sem cidade específica (institucional TJRN)
                if not filtrar_institucional:
                    aceitos.append(b)
            else:
                # Comarca repetida — pular
                continue
        else:
            # AMBÍGUA: aceitar com aviso
            aceitos.append(b)

    # Fallback: se menos de 4, incluir Natal
    if len(aceitos) < MINIMO_BOLETINS and boletins_natal:
        logger.info(
            f"Fallback GIRO: incluindo {len(boletins_natal)} boletins de Natal "
            f"(apenas {len(aceitos)} aceitos inicialmente)"
        )
        for b in boletins_natal:
            if len(aceitos) >= MINIMO_BOLETINS:
                break
            aceitos.append(b)
            if "natal" not in comarcas:
                comarcas.append("natal")

    return aceitos, comarcas


def gerar_nome_saida_giro(data_exibicao: date) -> str:
    """
    Gera o nome do arquivo de saída do GIRO.

    Formato: GNC_DD_MM.mp3
    Exemplo: GNC_11_09.mp3

    Args:
        data_exibicao: data de exibição

    Returns:
        Nome do arquivo de saída
    """
    return f"GNC_{data_exibicao.strftime('%d_%m')}.mp3"


def criar_planejamento_giro(
    codigo: str,
    data_exibicao: date,
    boletins_disponiveis: list[Path],
    evitar_natal: bool = FILTRAR_NATAL_PADRAO,
) -> PlanejamentoGiro:
    """
    Cria um planejamento completo de GIRO.

    Args:
        codigo: código do programa
        data_exibicao: data de exibição
        boletins_disponiveis: lista de caminhos no Drive H:
        evitar_natal: se True, filtra Natal inicialmente

    Returns:
        PlanejamentoGiro com seleção e metadados
    """
    selecao = selecionar_boletins_giro(
        data_exibicao,
        boletins_disponiveis,
        codigo=codigo,
        evitar_natal=evitar_natal,
    )
    return PlanejamentoGiro(
        codigo=codigo,
        data_exibicao=data_exibicao,
        janela=selecao.janela,
        boletins=selecao.boletins,
        comarcas=[],  # Preenchido após transcrição
        filtros_aplicados=selecao.metadados.get("filtros_aplicados", {}),
    )
