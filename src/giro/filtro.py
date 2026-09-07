"""
Filtro geográfico do GIRO nas Comarcas.

Regras:
- INEGOCIÁVEL: excluir notícias de outros estados (fora RN)
- AJUSTÁVEL: evitar notícias sobre Natal (pode ser relaxado quando
  há poucas notícias de outras cidades no período)

DETECÇÃO POR PALAVRA (word boundary), não substring genérica.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .config import NATAL_PALAVRAS, OUTROS_ESTADOS_PALAVRAS, RN_CIDADES


# ===========================================================================
# CLASSIFICAÇÃO DA NOTA
# ===========================================================================


class ClassificacaoGiro(Enum):
    """Classificação geográfica de uma nota para o GIRO."""

    ACEITA = "ACEITA"
    FILTRADA_NATAL = "FILTRADA_NATAL"
    FILTRADA_OUTRO_ESTADO = "FILTRADA_OUTRO_ESTADO"
    AMBIGUA = "AMBIGUA"


@dataclass
class ResultadoFiltro:
    classificacao: ClassificacaoGiro
    texto_origem: str = ""
    cidades_rn_mencionadas: list[str] = field(default_factory=list)
    motivo: str = ""
    aceita: bool = False


# ===========================================================================
# UTILITÁRIO: normalizar texto
# ===========================================================================


def _norm(texto: str) -> str:
    """Normaliza: minúsculas, sem acento, espaço único entre palavras."""
    t = texto.lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ===========================================================================
# PALAVRAS-CHAVE QUE INDICAM QUE A NOTÍCIA É DO RN
# ===========================================================================

# "Rio Grande do Norte" é o nome do estado — notícias que o menciona
# explicitamente são provavelmente do RN (a menos que também mencione
# Natal ou outro estado).
#
# "TJRN" é a abreviatura oficial do Tribunal de Justiça do RN.
# Notícias que usam TJRN estão necessariamente vinculadas ao RN.

_RN_INDICADORES = frozenset({
    _norm("rio grande do norte"),
    _norm("tjrn"),
    _norm("tribunal de justica do rio grande do norte"),
    _norm("tribunal de justiça do rio grande do norte"),
})

# ===========================================================================
# DETECÇÃO DE OUTRO ESTADO (INEGOCIÁVEL)
# ===========================================================================


def _norm_estado(p: str) -> str:
    """Normaliza estado para busca (minúsculas, sem acento, sem combining)."""
    t = p.lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z]", "", t)
    return t


_OUTROS_ESTADOS_PALAVRAS_NORM = frozenset({
    _norm_estado(p)
    for p in OUTROS_ESTADOS_PALAVRAS
    if len(p) >= 3 and p.lower() not in {"rio", "norte", "sul"}
})

# Bigramas e trigramas que identificam outros estados (busca direta)
_BIGRAMAS_OUTROS_ESTADOS = frozenset({
    _norm("rio grande do sul"),
    _norm("santa catarina"),
    _norm("parana"),
    _norm("mato grosso"),
    _norm("mato grosso do sul"),
    _norm("rio de janeiro"),
    _norm("sao paulo"),
    _norm("espirito santo"),
    _norm("minas gerais"),
    _norm("para"),
    _norm("tocantins"),
    _norm("amazonas"),
    _norm("roraima"),
    _norm("acre"),
    _norm("amapa"),
    _norm("alagoas"),
    _norm("sergipe"),
    _norm("paraiba"),
    _norm("bahia"),
    _norm("pernambuco"),
    _norm("piaui"),
    _norm("goias"),
    _norm("ceara"),
    # Capitais
    _norm("salvador"),
    _norm("fortaleza"),
    _norm("recife"),
    _norm("joao pessoa"),
    _norm("maceio"),
    _norm("aracaju"),
    _norm("vitoria"),
    _norm("belo horizonte"),
    _norm("curitiba"),
    _norm("florianopolis"),
    _norm("porto alegre"),
    _norm("cuiaba"),
    _norm("campo grande"),
    _norm("goiania"),
    _norm("palmas"),
    _norm("manaus"),
    _norm("boa vista"),
    _norm("rio branco"),
    _norm("belem"),
})


def _contem_outro_estado(texto_norm: str) -> bool:
    """Detecta menção a outro estado (INEGOCIÁVEL)."""
    palavras = texto_norm.split()
    for p in _OUTROS_ESTADOS_PALAVRAS_NORM:
        if p in palavras:
            return True
    for bg in _BIGRAMAS_OUTROS_ESTADOS:
        if bg in texto_norm:
            return True
    return False


# ===========================================================================
# DETECÇÃO DE NATAL (AJUSTÁVEL) — sem false-positive de "norte"
# ===========================================================================

_NATAL_WORD_RE = re.compile(r"\bnatal\b", re.IGNORECASE)
_NATAL_CONTEXTO_RE = re.compile(
    r"(?:comarca|vara|juiz|juizado|tribunal)\s+de\s+natal",
    re.IGNORECASE,
)


def _contem_natal(texto: str) -> bool:
    """Detecta menção geográfica específica à cidade Natal."""
    if not _NATAL_WORD_RE.search(texto):
        return False
    if _NATAL_CONTEXTO_RE.search(texto):
        return True
    # Palavra "natal" isolada pode ser cidade ou adjetivo
    if re.search(r"(?:rf\.?|comarca|vara|juizado|tribunal|município|cidade)", texto, re.IGNORECASE):
        return True
    if re.search(r"(?:tribunal|justiça|juiz|processo|julgamento|jurisdição)", texto, re.IGNORECASE):
        return True
    return False


# ===========================================================================
# CIDADES DO RN (aceitas)
# ===========================================================================

def _cidades_rn_list() -> list[str]:
    """Retorna lista de nomes de cidades do RN."""
    return sorted(set(RN_CIDADES))


def _detectar_cidades_rn(texto_norm: str) -> list[str]:
    """Detecta cidades do RN mencionadas no texto (normalizado)."""
    cidades_norm = _cidades_rn_list()
    encontradas = []
    for cid in cidades_norm:
        cid_norm = _norm(cid)
        if cid_norm in texto_norm:
            encontradas.append(cid)
    return list(dict.fromkeys(encontradas))


# ===========================================================================
# INDICADORES DE QUE A NOTÍCIA É DO RN
# ===========================================================================
#
# As notícias do GIro nas Comarcas vêm do Boletim TJRN diário.
# Podem ser:
#   a) Notícias com cidade mencionada → usar cidade para aceitar
#   b) Notícias institucionais do próprio TJRN, sem cidade →
#      detectar pelo nome "Tribunal de Justiça do Rio Grande do Norte"
#      ou abreviatura "TJRN"
#   c) Notícias de outra repartição do RN sem cidade (ex: "Secretaria de
#      Estado de...", "Governador...", "Assembleia Legislativa...") →
#      também são do RN


# Frases que identificam notícia do RN sem necessidade de cidade
_INDICADORES_RN = frozenset({
    _norm("rio grande do norte"),
    _norm("tjrn"),
    _norm("tribunal de justica do rio grande do norte"),
    _norm("tribunal de justiça do rio grande do norte"),
    _norm("justiça do rio grande do norte"),
})


def _eh_do_rn(texto_norm: str) -> bool:
    """Verifica se o texto é (provavelmente) uma notícia do RN.

    Critérios:
    - Menciona "Rio Grande do Norte" ou "TJRN" explicitamente
    - Menciona "Tribunal de Justiça do Rio Grande do Norte"
    - Menciona algum órgão conhecido do RN (ex: "Secretaria de Estado
      de Comunicação do RN", "Governador do RN", etc.)
    """
    return any(ind in texto_norm for ind in _INDICADORES_RN)


# ===========================================================================
# FILTRO PRINCIPAL
# ===========================================================================


def filtrar_nota(
    texto: str,
    evitar_natal: bool = True,
    logger: Optional[object] = None,
) -> ResultadoFiltro:
    """Aplica o filtro geográfico a uma nota transcrita."""
    t_norm = _norm(texto)

    # ---- PASSO 1: outro estado (INEGOCIÁVEL) ----
    if _contem_outro_estado(t_norm):
        return ResultadoFiltro(
            classificacao=ClassificacaoGiro.FILTRADA_OUTRO_ESTADO,
            texto_origem=texto,
            motivo="Outro estado detectado — INEGOCIÁVEL",
        )

    # ---- PASSO 2: Natal (AJUSTÁVEL) ----
    if _contem_natal(texto) and evitar_natal:
        return ResultadoFiltro(
            classificacao=ClassificacaoGiro.FILTRADA_NATAL,
            texto_origem=texto,
            motivo="Menciona Natal — filtrada (evitar_natal=True)",
        )

    # ---- PASSO 3: cidades do RN (ACEITA) ----
    cidades_rn = _detectar_cidades_rn(t_norm)
    if cidades_rn:
        return ResultadoFiltro(
            classificacao=ClassificacaoGiro.ACEITA,
            texto_origem=texto,
            cidades_rn_mencionadas=cidades_rn,
            motivo=f"Notícia do RN — cidades: {', '.join(cidades_rn)}",
            aceita=True,
        )

    # ---- PASSO 4: detectar indicadores gerais do RN (TJRN, "Rio Grande do Norte") ----
    if _eh_do_rn(t_norm):
        return ResultadoFiltro(
            classificacao=ClassificacaoGiro.ACEITA,
            texto_origem=texto,
            motivo="Notícia do RN — menciona Tribunal de Justiça do RN / RJN diretamente",
            aceita=True,
        )

    # ---- PASSO 5: ambígua ----
    motivo = "Sem menção geográfica clara — mantida para revisão"
    if logger:
        logger.warning(f"[filtro] {motivo} | texto={texto[:200]}")

    return ResultadoFiltro(
        classificacao=ClassificacaoGiro.AMBIGUA,
        texto_origem=texto,
        motivo=motivo,
    )


# ===========================================================================
# FILTRO DE LOTE
# ===========================================================================


def filtrar_lote(
    notas: list[tuple[int, str]],
    evitar_natal: bool = True,
    logger: Optional[object] = None,
) -> list[ResultadoFiltro]:
    """Aplica filtro a todas as notas de uma semana."""
    return [filtrar_nota(texto, evitar_natal, logger) for _, texto in notas]


# ===========================================================================
# RESUMO
# ===========================================================================


def resumo_filtro(resultados: list[ResultadoFiltro]) -> dict:
    total = len(resultados)
    return {
        "total": total,
        "aceitas": sum(1 for r in resultados if r.classificacao == ClassificacaoGiro.ACEITA),
        "filtradas_natal": sum(1 for r in resultados if r.classificacao == ClassificacaoGiro.FILTRADA_NATAL),
        "filtradas_outro_estado": sum(1 for r in resultados if r.classificacao == ClassificacaoGiro.FILTRADA_OUTRO_ESTADO),
        "ambiguas": sum(1 for r in resultados if r.classificacao == ClassificacaoGiro.AMBIGUA),
    }


# ===========================================================================
# MAIN — teste rápido
# ===========================================================================


if __name__ == "__main__":
    from .log import configurar_logger
    logger = configurar_logger(stdout=True)

    testes = [
        ("Nota sobre Mossoró", "O juiz de direito de Mossoró declarou na tarde desta quinta-feira..."),
        ("Nota sobre Natal", "A Vara de Família de Natal determinou o afastamento do juiz..."),
        ("Nota sobre outro estado", "O tribunal de Justiça do Ceará anunciou a abertura de processo..."),
        ("Nota institucional TJRN", "O Tribunal de Justiça do Rio Grande do Norte publicou novo ato administrativo..."),
        ("Nota sobre TJRN (Conbrascom)", "O Tribunal de Justiça do Rio Grande do Norte é finalista em três categorias..."),
    ]

    print("=== Teste do filtro geográfico ===")
    for nome, texto in testes:
        rf = filtrar_nota(texto, evitar_natal=True, logger=logger)
        print(f"\n[{nome}]")
        print(f"  Classificação: {rf.classificacao.value}")
        print(f"  Motivo:        {rf.motivo}")
        print(f"  Aceita:        {rf.aceita}")
        if rf.cidades_rn_mencionadas:
            print(f"  Cidades RN:    {rf.cidades_rn_mencionadas}")
