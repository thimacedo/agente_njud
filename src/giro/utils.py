# coding: utf-8
"""
Utilitários do GIRO nas Comarcas.

Conversões mmss ↔ data, semanas ISO, terças do ano e utilitários de
texto para o pipeline de processamento.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# ===========================================================================
# NÚMERO DO PROGRAMA (mmss)  <->  DATA DA TERÇA
# ===========================================================================
#
# Regra:
#   - O ano começa na 1ª terça de janeiro.
#   - Cada mês tem 4 programas (ss = 01..04).
#   - A 1ª terça do mês mm com número de semana ss corresponde à semana
#     ISO que contém o dia 2 (terça) contando (ss-1) semanas após a 1ª
#     terça do ano.
#
# Formulação:
#   terça_do_ano = primeira terça de janeiro (dia 2 ISO do ano)
#   deslocamento_semanas = (mm-1)*4 + (ss-1)
#   terça_programa = terça_do_ano + deslocamento_semanas * 7 dias
#
# Exemplo: 0101 → 1ª terça de janeiro. 0102 → terça + 7 dias. etc.
# ===========================================================================


def _primeira_terca_ano(ano: int) -> date:
    """Retorna a 1ª terça-feira do ano (dia ISO 2 da 1ª semana ISO)."""
    d = date(ano, 1, 1)
    # dia da semana: 0=seg, 1=ter, 2=qua, ..., 6=sáb
    # queremos a 1ª terça (weekday=1)
    delta = (1 - d.weekday()) % 7
    if delta == 0 and d.month != 1:
        # se 01/jan é terça mas já mudamos de ano? não, 01/jan sempre janeiro
        pass
    return d + timedelta(days=delta)


# Cache: 1ª terça de cada ano (2026 em diante)
_TAR = {}


def terça_do_programa(mmss: str, ano: int = 2026) -> date:
    """Data da terça de exibição do programa mmss no ano dado."""
    if len(mmss) != 4 or not mmss.isdigit():
        raise ValueError(f"mmss inválido: {mmss!r} (formato mmss numérico esperado)")
    mm = int(mmss[:2])
    ss = int(mmss[2:])
    if mm < 1 or mm > 12:
        raise ValueError(f"mm inválido: {mm:02d}")
    if ss < 1 or ss > 4:
        raise ValueError(f"ss inválido: {ss:02d}")
    if ano not in _TAR:
        _TAR[ano] = _primeira_terca_ano(ano)
    t0 = _TAR[ano]
    offset_semanas = (mm - 1) * 4 + (ss - 1)
    return t0 + timedelta(weeks=offset_semanas)


def semana_isoa_anterior(terça: date) -> tuple[date, date]:
    """Retorna (segunda, domingo) da semana ISO anterior à terça dada."""
    # Dia ISO da terça = 2. A semana anterior inicia 7 dias antes no dia ISO 2,
    # mas queremos o segmento monday→sunday da semana anterior.
    # A semana ISO que contém a terça começa na segunda anterior.
    # Semana anterior: segunda = terça - 9 dias, domingo = terça - 3 dias.
    segunda = terça - timedelta(days=9)
    domingo = terça - timedelta(days=3)
    return segunda, domingo


def semanaisoa_das_notícias(mmss: str, ano: int = 2026) -> tuple[date, date]:
    """Faixa de datas (seg, dom) cujas notícias entram no programa mmss."""
    t = terça_do_programa(mmss, ano)
    return semana_isoa_anterior(t)


# ===========================================================================
# MÊS A PARTIR DA DATA DA TERÇA
# ===========================================================================
# Usado pelo plano para associar o programa à pasta de boletins do mês.
# Na prática, o mês do boletim é referente à semana anterior à terça,
# que pode ser no mês atual ou no mês anterior (se a terça for no dia 1-7).


def mes_dos_boletins(mmss: str, ano: int = 2026) -> int:
    """Mês (1-12) dos boletins que alimentam o programa mmss.

    A regra: o mês dos boletins é o mês da segunda-feira da semana de
    notícias. Se a segunda cair no mês anterior, usamos o mês anterior.
    """
    seg, _ = semanaisoa_das_notícias(mmss, ano)
    return seg.month


# ===========================================================================
# GERADOR DE PLANO (mmss, data_terça, faixa_notícias, mês_boletim)
# ===========================================================================


def gerar_plano(ano: int = 2026) -> list[dict]:
    """Gera a lista de programas mmss para o ano, com metadados.

    Retorna lista de dicts com:
      - mmss: código do programa
      - data_terça: data de exibição (terça)
      - seg_notícias: segunda da semana de notícias
      - dom_notícias: domingo da semana de notícias
      - mes_boletim: mês (1-12)dos boletins que alimentam
      - n_noticias_previsto: 4-6 (range)
    """
    t0 = _TAR.get(ano)
    if t0 is None:
        _TAR[ano] = _primeira_terca_ano(ano)
        t0 = _TAR[ano]
    planos = []
    for mm in range(1, 13):
        for ss in range(1, 5):
            mmss = f"{mm:02d}{ss:02d}"
            t = terça_do_programa(mmss, ano)
            seg, dom = semana_isoa_anterior(t)
            mes_b = mes_dos_boletins(mmss, ano)
            planos.append({
                "mmss": mmss,
                "data_terça": t.isoformat(),
                "seg_notícias": seg.isoformat(),
                "dom_notícias": dom.isoformat(),
                "mes_boletim": mes_b,
                "n_noticias_previsto": "4-6",
            })
    return planos


# ===========================================================================
# NOMENCLATURA DE ARQUIVOS DE SAÍDA
# ===========================================================================


def nome_programa(mmss: str, data_terça: Optional[str] = None) -> str:
    """Gera o nome do arquivo do programa montado: GNC_mmss_DD-MM-ANO.mp3.

    Ex: GNC_0804_11-08-26.mp3
    """
    if data_terça is None:
        t = terça_do_programa(mmss)
        data_terça = t.strftime("%d-%m-%y")  # ano com 2 dígitos
    return f"GNC_{mmss}_{data_terça}.mp3"


def nome_corte_nota(mmss: str, idx_nota: int, data_terça: Optional[str] = None) -> str:
    """Nome do arquivo de nota processada: GNC_mmss_N{n}_DD-MM-ANO.mp3.

    Ex: GNC_0804_N01_11-08-26.mp3
    """
    if data_terça is None:
        t = terça_do_programa(mmss)
        data_terça = t.strftime("%d-%m-%y")  # ano com 2 dígitos
    return f"GNC_{mmss}_N{idx_nota:02d}_{data_terça}.mp3"


# ===========================================================================
# UTILITÁRIOS DE TEXTO
# ===========================================================================


def normalizar_texto_giro(texto: str) -> str:
    """Normaliza texto para busca de âncoras GIRO (minúsculo, sem acento)."""
    import unicodedata
    t = texto.lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extrair_locutor(texto_segmento: str) -> Optional[str]:
    """Extrai nome do locutor a partir da assinatura, se presente."""
    m = re.search(
        r"tribunal de justica do rio grande do norte"
        r"(?:\s+para a\s+radio justi[çc]a)?"
        r"[\s,]+([A-Za-z]+(?:\s+[A-Za-z]+)?)\s*$",
        texto_segmento,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return None


# ===========================================================================
# FUNÇÕES DE APÓIO PARA O FILTRO GEOGRÁFICO
# ===========================================================================


def extrair_cidades_mencoes(texto: str) -> list[str]:
    """Extrai mencões de cidades a partir do texto transcrito.

    Retorna lista de cidades identificadas no texto (primeira menção de cada).
    """
    from .config import RN_CIDADES, NATAL_PALAVRAS, OUTROS_ESTADOS_PALAVRAS

    t_norm = normalizar_texto_giro(texto)
    palabras = set(t_norm.split())
    cidades_encontradas = set()
    for cidade in RN_CIDADES:
        if cidade in palabras:
            cidades_encontradas.add(cidade)
    return sorted(cidades_encontradas)


def eh_outro_estado(texto: str) -> bool:
    """Verifica se o texto menciona outro estado (INEGOCIÁVEL)."""
    from .config import OUTROS_ESTADOS_PALAVRAS

    t_norm = normalizar_texto_giro(texto)
    palabras = set(t_norm.split())
    for estado in OUTROS_ESTADOS_PALAVRAS:
        if estado in palabras:
            return True
    return False


def eh_natal(texto: str) -> bool:
    """Verifica se o texto é sobre Natal (ajustável)."""
    from .config import NATAL_PALAVRAS

    t_norm = normalizar_texto_giro(texto)
    palabras = set(t_norm.split())
    # Para ser Natal, precisa de contextualização: "natal" + algo que
    # indique a cidade (comarca, juizado, vara, etc.) OU o próprio nome
    # "natal" sozinho com contexto de notícia local.
    if "natal" in palabras:
        # Verifica se há contexto de cidade (comarca, juízo, vara, etc.)
        palavras_contexto = {"comarca", "vara", "juizado", "dor",
                             "tjrn", "tribunal", "justiça", "juiz",
                             "desembargador", "juizado especial",
                             "comarca de natal", "vara de natal"}
        if palavras_contexto & palabras:
            return True
        # Se "natal" aparece sozinho como sujeito da notícia, é Natal
        # (ex: "Natal faz...", "Natal é...")
        if len(palabras) <= 5:
            return True
    return False


# ===========================================================================
# MAIN — diagnóstico
# ===========================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("=== teste mmss ↔ data ===")
        for mmss in ["0101", "0102", "0103", "0104",
                     "0201", "0804", "1204"]:
            t = terça_do_programa(mmss)
            seg, dom = semana_isoa_anterior(t)
            print(f"{mmss} → terça {t} | notícias {seg} → {dom}")
        print()
        print("=== plano completo 2026 ===")
        for p in gerar_plano(2026):
            print(f"{p['mmss']} | terça={p['data_terça']} | "
                  f"notícias={p['seg_notícias']}→{p['dom_notícias']} | "
                  f"boletins-mes={p['mes_boletim']}")
