# coding: utf-8
"""
Configurações do módulo GIRO nas Comarcas.

Âncoras de texto, thresholds, padrões de nomenclatura e regras
específicas deste programa — sem misturar com NJUD.
"""

from __future__ import annotations

import re
from pathlib import Path

# ===========================================================================
# NÚMERO DO PROGRAMA (mmss)
# ===========================================================================
# mm = mês (01..12)
# ss = semana dentro do mês, contando a partir da 1ª terça do ano
#     que cai na semana ISO em que o mês começa.
#     A terça sempre cai no dia ISO 2 (seg=1, ter=2, ..., dom=7).
#
# Regra derivada:
#   data_terça(mm, ss) = primeira terça do ano + ( (mm-1)*4 + (ss-1) ) semanas
# Isso funciona porque 4 programas/mês e a terça é sempre dia 2 ISO.
# ===========================================================================

# ===========================================================================
# THRESHOLDS
# ===========================================================================

# Limiar de confiança para âncora de abertura/encerramento (texto)
LIMIAR_ANCORA_GIRO = 0.55

# Distância mínima (s) entre passagem e próxima nota para considerar
# que a passagem terminou e a nota começou
LIMIAR_FIM_PASSAGEM_GIRO = 0.8

# Margem de silêncio antes do início da fala (s)
LIMIAR_INICIO_FALA_GIRO = 0.3

# ===========================================================================
# ÂNCORAS DE TEXTO (vinhetas GIRO transcritas) — NORMALIZADAS
# ===========================================================================

# VHT_ABERTURA_GIRO.mp3 — transcrição Whisper (normalizada):
#   "é o giro pelas comarcas do rio grande do norte"
#
# VHT_ENCERRAMENTO_GIRO.mp3 — transcrição Whisper (normalizada):
#   "voce acabou de ouvir o giro pelas comarcas do rio grande do norte"
#
# VHT_PASSAGEM_GIRO.mp3 — música instrumental, sem texto útil para ancora.

ANCORAS_ABERTURA_GIRO = [
    "giro pelas comarcas do rio grande do norte",
    "giro pelas comarcas",
    "comarcas do rio grande do norte",
]

ANCORAS_ENCERRAMENTO_GIRO = [
    "voce acabou de ouvir o giro",
    "giro pelas comarcas do rio grande do norte",
    "acabou de ouvir",
]

# ===========================================================================
# ASSINATURA DE NOTA (LOC + OFF) — padrão de início de cada notícia
# ===========================================================================
# No NJUD a assinatura localize o começo da cabeça.
# No GIRO, cada nota é uma unidade self-contained (manchete+corpo),
# mas o início da nota pode ser detectado pelo padrão "LOC:"/"OFF:" no
# texto transcrito, ou pela âncora de locução/assinatura semelhante.
#
# Padrão: "tribunal de justica do rio grande do norte" + nome do locutor
# (quando presente) — mesma base do NJUD.
#
# Como o GIRO traz manchete+corpo juntos, não temos mais separação
# CABEÇA/CORPO. A "nota" começa no início do bloco LOC e termina no fim
# do bloco OFF.
# ===========================================================================

_PADRAO_ASSINATURA_GIRO = re.compile(
    r"tribunal de justica do rio grande do norte"
    r"(?:\s+para a\s+radio justi[çc]a)?"
    r"[\s,]+[A-Za-z]+(?:\s+[A-Za-z]+)*\s*$",
    flags=re.IGNORECASE,
)

# ===========================================================================
# Caminhos do projeto GIRO
# ===========================================================================

def _base_dir() -> Path:
    """Raiz do projeto (pai de src/)."""
    import os
    from pathlib import Path
    return Path(os.getenv("BASE_DIR", str(Path(__file__).resolve().parents[2])))


BASE_DIR = _base_dir()
DIR_PROCESSED = BASE_DIR / "data" / "processed" / "GIRO_COMARCAS"
DIR_OUTPUT = BASE_DIR / "data" / "output" / "GIRO_COMARCAS"
DIR_PLANOS = BASE_DIR / "data"
DIR_ASSETS_VINHETAS = BASE_DIR / "assets" / "vinhetas"

VHT_ABERTURA_GIRO_NOME = "VHT_ABERTURA_GIRO.mp3"
VHT_PASSAGEM_GIRO_NOME = "VHT_PASSAGEM_GIRO.mp3"
VHT_ENCERRAMENTO_GIRO_NOME = "VHT_ENCERRAMENTO_GIRO.mp3"

# ===========================================================================
# Filtro geográfico
# ===========================================================================
# INEGOCIÁVEL: excluir notícias de outros estados (fora RN)
# AJUSTÁVEL: evitar notas sobre Natal (pode ser relaxado quando poucas
#            notícias de outras cidades no boletim)

# Palavras-chave que identificam "outros estados" (INEGOCIÁVEL)
# Serão usadas para DETECÇÃO — se o texto transcrito contiver referência
# a outro estado, a nota será rejeitada.
OUTROS_ESTADOS_PALAVRAS = frozenset({
    # Estado literal mencionado (sem acento para normalização)
    "bahia", "ceara", "pernambuco", "paraiba", "piaui",
    "alagoas", "sergipe", "paraiba", "espirito santo",
    "minas gerais", "rio de janeiro", "sao paulo",
    "parana", "santa catarina", "rio grande do sul",
    "mato grosso", "mato grosso do sul", "goias",
    "tocantins", "amazonas", "roraima", "acre",
    "amapa", "para", "fernando pedroso",
    # Capitais
    "salvador", "fortaleza", "recife", "joao pessoa",
    "maceio", "aracaju", "vitoria", "belo horizonte",
    "rio de janeiro", "sao paulo", "curitiba", "florianopolis",
    "porto alegre", "cuiaba", "campo grande", "goiania",
    "palmas", "manaus", "boa vista", "rio branco", "belem",
})

# Palavras-chave que identificam "Natal" (AJUSTÁVEL — não é veto, mas
# preferencialmente evitado). Se a opção de evitar Natal estiver ativa,
# qualquer menção a "Natal" (com contexto de notícia local) será filtrada.
NATAL_PALAVRAS = frozenset({
    "natal", "rn", "rio grande do norte",
    # Comunas de Natal
    "parnamirim", "macau", "serra de sa", "gracas",
    " impeding",  # parque industrial? não, evitar falso positivo
})

# Cidades/comarcas do RN que são OBJETIVO do Giro (aceitamos notícias
# sobre elas — são o que queremos).
# A lista é informativa para o filtro: se uma nota menciona cidade do RN
# que não é Natal, provavelmente é do RN mesmo.
RN_CIDADES = frozenset({
    "mossoró", "caicó", "parnamirim", "exouía", "joão camps",
    "augusto petrillo", "anjos lício de madureira", "baía nova",
    "billings", "bento fernandes", "boa vista do burmester",
    "bom conselho", "brejo saint", "camalaú",
    "campo grande do jequitinhonha", "caraúbas", "carnaúba dos dantas",
    "ceará-mirim", "crato", "cuitegi", "dom pedro",
    "encanto", "égla", "espírito santo do agosto",
    "florânia", "foz do iguaru", "goro", "goianinha",
    "gr maçônica", "guamaré", "ibógum", "importância",
    "ipanguaçu", "ippo", "ivisen", "jardim de piranhas",
    "juru", "lagoinha", "lagoa de pedras", "lagoa seca",
    "loures", "madeiro", "malha", "maurilândia",
    "maxaranguape", "medeiros", "mutualinho", "nanú",
    "natal", "nísia flore", "nova racha", "olho d'água do borges",
    "oliveira", "pau dos ferros", "pedra do ingaí",
    "pedras de fogo", "penninca", "picuí", "pindoretama",
    "pitimbu", "poço branco", "ponta do tubarão", "porto do mangue",
    "praia", "recanto das emas", "rocha", "sale", "santa cruz",
    "santa lima", "são gonçalo do amaral", "são josé de mimoso",
    "são pedro", "são tome", "seridó", "triunfo",
    "umpa", "upanema", "valentim", "venus", "vereda",
})

# ===========================================================================
# MENSAGEM DE AJUDA
# ===========================================================================
__all__ = [
    "LIMIAR_ANCORA_GIRO",
    "LIMIAR_FIM_PASSAGEM_GIRO",
    "LIMIAR_INICIO_FALA_GIRO",
    "ANCORAS_ABERTURA_GIRO",
    "ANCORAS_ENCERRAMENTO_GIRO",
    "OUTROS_ESTADOS_PALAVRAS",
    "NATAL_PALAVRAS",
    "RN_CIDADES",
    "BASE_DIR",
    "DIR_PROCESSED",
    "DIR_OUTPUT",
    "DIR_PLANOS",
    "DIR_ASSETS_VINHETAS",
    "VHT_ABERTURA_GIRO_NOME",
    "VHT_PASSAGEM_GIRO_NOME",
    "VHT_ENCERRAMENTO_GIRO_NOME",
]
