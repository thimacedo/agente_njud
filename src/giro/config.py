# coding: utf-8
"""
Configurações do módulo GIRO nas Comarcas.

Âncoras de texto, thresholds, padrões de nomenclatura e regras
específicas deste programa — sem misturar com NJUD.

Caminhos namespaced: assets/vinhetas/giro/ (separado do NJUD).
"""
from __future__ import annotations

import re
from pathlib import Path

# ===========================================================================
# THRESHOLDS
# ===========================================================================
LIMIAR_ANCORA_GIRO = 0.55
LIMIAR_FIM_PASSAGEM_GIRO = 0.8
LIMIAR_INICIO_FALA_GIRO = 0.3

# ===========================================================================
# ÂNCORAS DE TEXTO (vinhetas GIRO transcritas) — NORMALIZADAS
# ===========================================================================
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
# PADRÃO DE ASSINATURA DE NOTA (LOC + OFF)
# ===========================================================================
_PADRAO_ASSINATURA_GIRO = re.compile(
    r"tribunal de justica do rio grande do norte"
    r"(?:\s+para a\s+radio justi[çc]a)?"
    r"[\s,]+[A-Za-z]+(?:[\s]+[A-Za-z]+)*\s*$",
    flags=re.IGNORECASE,
)

# ===========================================================================
# Caminhos (namespaced — assets/vinhetas/giro/)
# ===========================================================================
BASE_DIR = Path(__file__).resolve().parents[2]
DIR_PROCESSED = BASE_DIR / "data" / "processed" / "GIRO_COMARCAS"
DIR_OUTPUT = BASE_DIR / "data" / "output" / "GIRO_COMARCAS"
DIR_PLANOS = BASE_DIR / "data"
DIR_ASSETS_VINHETAS = BASE_DIR / "assets" / "vinhetas" / "giro"

VHT_ABERTURA_GIRO_NOME = "VHT_ABERTURA_GIRO.mp3"
VHT_PASSAGEM_GIRO_NOME = "VHT_PASSAGEM_GIRO.mp3"
VHT_ENCERRAMENTO_GIRO_NOME = "VHT_ENCERRAMENTO_GIRO.mp3"

# ===========================================================================
# Filtro geográfico — bases de dados
# ===========================================================================
# INEGOCIÁVEL: excluir notícias de outros estados (fora RN).
# AJUSTÁVEL: evitar notas sobre Natal.
# ===========================================================================

OUTROS_ESTADOS_PALAVRAS = frozenset({
    "bahia", "ceara", "pernambuco", "paraiba", "piaui",
    "alagoas", "sergipe", "paraiba", "espirito santo",
    "minas gerais", "rio de janeiro", "sao paulo",
    "parana", "santa catarina", "rio grande do sul",
    "mato grosso", "mato grosso do sul", "goias",
    "tocantins", "amazonas", "roraima", "acre",
    "amapa", "para", "fernando pedroso",
    "salvador", "fortaleza", "recife", "joao pessoa",
    "maceio", "aracaju", "vitoria", "belo horizonte",
    "rio de janeiro", "sao paulo", "curitiba", "florianopolis",
    "porto alegre", "cuiaba", "campo grande", "goiania",
    "palmas", "manaus", "boa vista", "rio branco", "belem",
})

NATAL_PALAVRAS = frozenset({
    "natal", "rn", "rio grande do norte",
})

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
    "são francisco do oeste", "são gonçalo do amarante", "são joão do sabugi",
    "são josé de mipibu", "são josé do campestre", "são josé do seridó",
    "são miguel", "são miguel do gostoso", "são paulo do potengi",
    "são pedro", "são rafael", "são tomé",
    "são vicente", "taboleiro grande", "taipu", "tangará",
    "tenente ananias", "tenente laurentino cruz", "tibau", "tibau do sul",
    "timbaúba dos batistas", "touros", "triunfo potiguar", "umarizal",
    "upanema", "venha-ver", "vera cruz", "viçosa",
    "vila flor", "várzea",
})

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
    "_PADRAO_ASSINATURA_GIRO",
]
