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
})

# Cidades/comarcas do RN que são OBJETIVO do Giro (aceitamos notícias
# sobre elas — são o que queremos).
# A lista é informativa para o filtro: se uma nota menciona cidade do RN
# que não é Natal, provavelmente é do RN mesmo.
RN_CIDADES = frozenset({
    "acari", "afonso bezerra", "água nova", "alexandria", "almino afonso",
    "alto do rodrigues", "angicos", "antônio martins", "apodi",
    "areia branca", "arês", "assu", "baraúna",
    "barcelona", "baía formosa", "bento fernandes", "boa saúde",
    "bodó", "bom jesus", "brejinho", "caicó",
    "caiçara do norte", "caiçara do rio do vento", "campo grande", "campo redondo",
    "canguaretama", "caraúbas", "carnaubais", "carnaúba dos dantas",
    "ceará-mirim", "cerro corá", "coronel ezequiel", "coronel joão pessoa",
    "cruzeta", "currais novos", "doutor severiano", "encanto",
    "equador", "espírito santo", "extremoz", "felipe guerra",
    "fernando pedroza", "florânia", "francisco dantas", "frutuoso gomes",
    "galinhos", "goianinha", "governador dix-sept rosado", "grossos",
    "guamaré", "ielmo marinho", "ipanguaçu", "ipueira",
    "itajá", "itaú", "jaçanã", "jandaíra",
    "janduís", "japi", "jardim de angicos", "jardim de piranhas",
    "jardim do seridó", "joão câmara", "joão dias", "josé da penha",
    "jucurutu", "jundiá", "lagoa d'anta", "lagoa de pedras",
    "lagoa de velhos", "lagoa nova", "lagoa salgada", "lajes",
    "lajes pintadas", "lucrécia", "luís gomes", "macaíba",
    "macau", "major sales", "marcelino vieira", "martins",
    "maxaranguape", "messias targino", "monte alegre", "monte das gameleiras",
    "montanhas", "mossoró", "natal", "nísia floresta",
    "nova cruz", "olho-d'água do borges", "ouro branco", "paraná",
    "paraú", "parazinho", "parelhas", "parnamirim",
    "passa e fica", "passagem", "patu", "pau dos ferros",
    "pedra grande", "pedra preta", "pedro avelino", "pedro velho",
    "pendências", "pilões", "poço branco", "portalegre",
    "porto do mangue", "pureza", "rafael fernandes", "rafael godeiro",
    "riacho da cruz", "riacho de santana", "riachuelo", "rio do fogo",
    "rodolfo fernandes", "ruy barbosa", "santa cruz", "santa maria",
    "santana do matos", "santana do seridó", "santo antônio", "senador elói de souza",
    "senador georgino avelino", "serra caiada", "serra de são bento", "serra do mel",
    "serra negra do norte", "serrinha", "serrinha dos pintos", "severiano melo",
    "sítio novo", "são bento do norte", "são bento do trairi", "são fernando",
    "são francisco do oeste", "são gonçalo do amarante", "são joão do sabugi", "são josé de mipibu",
    "são josé do campestre", "são josé do seridó", "são miguel", "são miguel do gostoso",
    "são paulo do potengi", "são pedro", "são rafael", "são tomé",
    "são vicente", "taboleiro grande", "taipu", "tangará",
    "tenente ananias", "tenente laurentino cruz", "tibau", "tibau do sul",
    "timbaúba dos batistas", "touros", "triunfo potiguar", "umarizal",
    "upanema", "venha-ver", "vera cruz", "viçosa",
    "vila flor", "várzea",
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
