"""
regras/livro.py — Tipos de dados e regras universais do DIVISOR.

Contratos:
- Todos os programas (NJUD, GIRO, BOLETIM) usam os tipos definidos aqui.
- Regras universais são imutáveis e aplicáveis a qualquer programa.
- Este módulo NÃO importa regras específicas de nenhum programa.

Tipos definidos:
- TipoPrograma: enum区分 NJUD / GIRO / BOLETIM
- OrigemBoletim: identifica um boletim no Drive H:
- SelecaoBoletins: resultado da seleção de boletins para um programa
- ResultadoColeta: resultado da cópia para staging
- JanelaColeta: período de tempo para coleta de boletins
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional


# ===========================================================================
# TIPOS FUNDAMENTAIS
# ===========================================================================


class TipoPrograma(Enum):
    """Tipos de programa suportados pelo DIVISOR."""
    NJUD = "NJUD"
    GIRO = "GIRO"
    BOLETIM = "BOLETIM"


@dataclass(frozen=True)
class OrigemBoletim:
    """
    Identifica unicamente um boletim no Drive H:.

    Attributes:
        caminho_absoluto: caminho completo no Drive H:
        nome_arquivo: nome do arquivo (imutável, nunca renomear)
        id_boletim: identificador único extraído do nome (ex: B1, B2)
        data: data extraída do nome do arquivo
    """
    caminho_absoluto: Path
    nome_arquivo: str
    id_boletim: str
    data: date

    def __post_init__(self) -> None:
        # Validação: nomenclatura imutável
        if not re.match(r"^BOLETIM_RADIO_TJRN_\d{2}_\d{2}_\d{4}_B\d+_", self.nome_arquivo):
            raise ValueError(
                f"Nome de boletim inválido (nomenclatura imutável): {self.nome_arquivo}"
            )


@dataclass
class JanelaColeta:
    """
    Janela de tempo para coleta de boletins.

    Attributes:
        data_inicio: primeira data da janela (inclusive)
        data_fim: última data da janela (inclusive)
    """
    data_inicio: date
    data_fim: date

    def __post_init__(self) -> None:
        if self.data_inicio > self.data_fim:
            raise ValueError(
                f"data_inicio ({self.data_inicio}) > data_fim ({self.data_fim})"
            )

    def dias(self) -> list[date]:
        """Retorna todas as datas na janela."""
        resultado = []
        atual = self.data_inicio
        while atual <= self.data_fim:
            resultado.append(atual)
            atual += timedelta(days=1)
        return resultado

    def __contains__(self, d: date) -> bool:
        return self.data_inicio <= d <= self.data_fim


@dataclass
class SelecaoBoletins:
    """
    Resultado da seleção de boletins para um programa.

    Attributes:
        programa: tipo do programa
        janela: janela de coleta usada
        boletins: lista de boletins selecionados (cada um com id único)
        metadados: informações adicionais da seleção
    """
    programa: TipoPrograma
    janela: JanelaColeta
    boletins: list[OrigemBoletim] = field(default_factory=list)
    metadados: dict = field(default_factory=dict)

    @property
    def quantidade(self) -> int:
        """Número único de boletins (por id_boletim, não por arquivo)."""
        return len({b.id_boletim for b in self.boletins})


@dataclass
class ResultadoColeta:
    """
    Resultado da cópia de boletins para staging.

    Attributes:
        sucesso: se a coleta foi bem-sucedida
        arquivos_coletados: lista de caminhos copiados para staging
        erros: lista de erros encontrados
        integridade_ok: verificação de integridade pós-cópia
    """
    sucesso: bool
    arquivos_coletados: list[Path] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    integridade_ok: bool = False


# ===========================================================================
# REGRAS UNIVERSAIS
# ===========================================================================

# Padrão de nomenclatura: BOLETIM_RADIO_TJRN_DD_MM_AAAA_BX_*
PADRAO_NOME_BOLETIM = re.compile(
    r"^BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_(B\d+)_(.+)$"
)

# Separadores entre programas — nunca misturar
PROGRAMAS_VALIDOS = {TipoPrograma.NJUD, TipoPrograma.GIRO, TipoPrograma.BOLETIM}


def extrair_id_boletim(nome_arquivo: str) -> str:
    """
    Extrai o id único do boletim do nome do arquivo.

    O ID inclui o número E o sufixo (título) para distinguir boletins
    diferentes com o mesmo número (ex: B5_CNJ_CONCILIAR vs B5_NOVAS_PARCERIAS).

    Ex: BOLETIM_RADIO_TJRN_11_09_2026_B1_something_CABECA.mp3 → "B1_something"

    Raises:
        ValueError: se o nome não segue o padrão.
    """
    import re
    # Extrai BX_titulo (tudo entre BX e _CABECA/_CORPO)
    m = re.search(r'B(\d+)_(.+?)_(CABECA|CORPO)', nome_arquivo)
    if not m:
        raise ValueError(f"Nome inválido: {nome_arquivo}")
    return f"B{m.group(1)}_{m.group(2)}"


def extrair_data_boletim(nome_arquivo: str) -> date:
    """
    Extrai a data do boletim do nome do arquivo.

    Ex: BOLETIM_RADIO_TJRN_11_09_2026_B1_something.mp3 → date(2026, 9, 11)

    Raises:
        ValueError: se o nome não segue o padrão.
    """
    m = PADRAO_NOME_BOLETIM.match(nome_arquivo)
    if not m:
        raise ValueError(f"Nome inválido: {nome_arquivo}")
    dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return date(ano, mes, dia)


def normalizar_nome(nome: str) -> str:
    """Normaliza nome para comparação: minúsculas, sem acento."""
    t = nome.lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.strip()


def validar_selecao(selecao: SelecaoBoletins) -> list[str]:
    """
    Valida uma seleção de boletins conforme regras universais.

    Retorna lista de erros (vazia = OK).
    """
    erros = []

    # Regra: programa válido
    if selecao.programa not in PROGRAMAS_VALIDOS:
        erros.append(f"Programa inválido: {selecao.programa}")

    # Regra: sem boletins duplicados por id (CABECA/CORPO são pares, não duplicatas)
    ids_vistos = set()
    for b in selecao.boletins:
        # Usa id_boletim + tipo (CABECA/CORPO) como chave única
        chave = f"{b.id_boletim}_{b.nome_arquivo.split('_')[-1]}"
        if chave in ids_vistos:
            erros.append(f"Arquivo duplicado: {b.nome_arquivo}")
        ids_vistos.add(chave)

    # Regra: todos os boletins na janela
    for b in selecao.boletins:
        if b.data not in selecao.janela:
            erros.append(
                f"Boletim {b.id_boletim} ({b.data}) fora da janela "
                f"[{selecao.janela.data_inicio} – {selecao.janela.data_fim}]"
            )

    # Regra: nomenclatura imutável
    for b in selecao.boletins:
        if not PADRAO_NOME_BOLETIM.match(b.nome_arquivo):
            erros.append(f"Nome fora do padrão: {b.nome_arquivo}")

    return erros


def calcular_janela_semana_anterior(data_programa: date, dias: int = 6) -> JanelaColeta:
    """
    Calcula a janela de coleta: semana anterior ao programa.

    Para um programa na data X, a janela é [X-dias, X-1].
    Padrão: 6 dias anteriores (semana completa de trabalho).

    Args:
        data_programa: data de exibição do programa
        dias: número de dias anteriores (padrão 6)

    Returns:
        JanelaColeta com data_inicio e data_fim
    """
    data_fim = data_programa - timedelta(days=1)
    data_inicio = data_fim - timedelta(days=dias - 1)
    return JanelaColeta(data_inicio=data_inicio, data_fim=data_fim)
