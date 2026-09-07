# coding: utf-8
"""
Configurações do módulo GIRO nas Comarcas.

Âncoras de texto, thresholds, padrões de nomenclatura e regras
específicas deste programa — sem misturar com NJUD.

Caminhos namespaced: assets/vinhetas/giro/ (separado do NJUD).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Garantir que src/ está no path para importar config.giro
_src_dir = Path(__file__).resolve().parents[1]
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from config.giro import settings as _settings

# ===========================================================================
# THRESHOLDS
# ===========================================================================
LIMIAR_ANCORA_GIRO = _settings.LIMIAR_ANCORA_GIRO
LIMIAR_FIM_PASSAGEM_GIRO = _settings.LIMIAR_FIM_PASSAGEM_GIRO
LIMIAR_INICIO_FALA_GIRO = _settings.LIMIAR_INICIO_FALA_GIRO

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
BASE_DIR = _settings.BASE_DIR
DIR_PROCESSED = _settings.DIR_PROCESSED
DIR_OUTPUT = _settings.DIR_OUTPUT
DIR_PLANOS = _settings.DIR_PLANOS
DIR_ASSETS_VINHETAS = _settings.VINHETAS_DIR

VHT_ABERTURA_GIRO_NOME = _settings.VHT_ABERTURA_GIRO_NOME
VHT_PASSAGEM_GIRO_NOME = _settings.VHT_PASSAGEM_GIRO_NOME
VHT_ENCERRAMENTO_GIRO_NOME = _settings.VHT_ENCERRAMENTO_GIRO_NOME

# ===========================================================================
# Whisper (herdado de BaseSettings via SettingsGiro)
# ===========================================================================
MODELO_WHISPER = _settings.MODELO_WHISPER
COMPUTE_TYPE = _settings.COMPUTE_TYPE
CACHE_TRANSCRICOES = _settings.CACHE_TRANSCRICOES
LOGS_DIR_GIRO = _settings.LOGS_DIR_GIRO
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
    # Fonte: API IBGE (servicodados.ibge.gov.br) — UF 24 (RN), 167 municípios.
    # Atualizado em 2026-07-07. NÃO EDITAR MANUALMENTE — use o script
    # scripts/atualizar_cidades_rn.py para regenerar a partir do IBGE.
    "acari", "afonso bezerra", "alexandria", "almino afonso", "alto do rodrigues",
    "angicos", "antônio martins", "apodi", "areia branca", "arez", "assú",
    "baraúna", "barcelona", "baía formosa", "bento fernandes", "bodó",
    "bom jesus", "brejinho", "caicó", "caiçara do norte", "caiçara do rio do vento",
    "campo grande", "campo redondo", "canguaretama", "caraúbas", "carnaubais",
    "carnaúba dos dantas", "ceará-mirim", "cerro corá", "coronel ezequiel",
    "coronel joão pessoa", "cruzeta", "currais novos", "doutor severiano",
    "encanto", "equador", "espírito santo", "extremoz", "felipe guerra",
    "fernando pedroza", "florânia", "francisco dantas", "frutuoso gomes",
    "galinhos", "goianinha", "governador dix-sept rosado", "grossos", "guamaré",
    "ielmo marinho", "ipanguaçu", "ipueira", "itajá", "itaú", "jandaíra",
    "janduís", "januário cicco", "japi", "jardim de angicos", "jardim de piranhas",
    "jardim do seridó", "jaçanã", "josé da penha", "joão câmara", "joão dias",
    "jucurutu", "jundiá", "lagoa d'anta", "lagoa de pedras", "lagoa de velhos",
    "lagoa nova", "lagoa salgada", "lajes", "lajes pintadas", "lucrécia",
    "luís gomes", "macau", "macaíba", "major sales", "marcelino vieira",
    "martins", "maxaranguape", "messias targino", "montanhas", "monte alegre",
    "monte das gameleiras", "mossoró", "natal", "nova cruz", "nísia floresta",
    "olho d'água do borges", "ouro branco", "paraná", "parazinho", "paraú",
    "parelhas", "parnamirim", "passa e fica", "passagem", "patu",
    "pau dos ferros", "pedra grande", "pedra preta", "pedro avelino", "pedro velho",
    "pendências", "pilões", "portalegre", "porto do mangue", "poço branco",
    "pureza", "rafael fernandes", "rafael godeiro", "riacho da cruz",
    "riacho de santana", "riachuelo", "rio do fogo", "rodolfo fernandes",
    "ruy barbosa", "santa cruz", "santa maria", "santana do matos",
    "santana do seridó", "santo antônio", "senador elói de souza",
    "senador georgino avelino", "serra caiada", "serra de são bento", "serra do mel",
    "serra negra do norte", "serrinha", "serrinha dos pintos", "severiano melo",
    "são bento do norte", "são bento do trairí", "são fernando",
    "são francisco do oeste", "são gonçalo do amarante", "são josé de mipibu",
    "são josé do campestre", "são josé do seridó", "são joão do sabugi",
    "são miguel", "são miguel do gostoso", "são paulo do potengi", "são pedro",
    "são rafael", "são tomé", "são vicente", "sítio novo", "taboleiro grande",
    "taipu", "tangará", "tenente ananias", "tenente laurentino cruz", "tibau",
    "tibau do sul", "timbaúba dos batistas", "touros", "triunfo potiguar",
    "umarizal", "upanema", "venha-ver", "vera cruz", "vila flor", "viçosa",
    "várzea", "água nova",
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
    "MODELO_WHISPER",
    "COMPUTE_TYPE",
    "CACHE_TRANSCRICOES",
    "LOGS_DIR_GIRO",
    "_PADRAO_ASSINATURA_GIRO",
]
