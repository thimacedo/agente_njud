"""
Registro canónico dos programas de rádio do TJRN.

Fonte única de verdade (single source of truth) sobre qual pipeline,
orquestrador e paths pertencem a cada programa. Qualquer script novo —
ou qualquer agente de IA editando este repositório — deve IMPORTAR
daqui em vez de recriar essas strings/paths manualmente.

Ver também: GLOSSARIO_PROGRAMAS.md (versão legível para humanos).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path


# ===========================================================================
# CONSTANTES GLOBAIS
# ===========================================================================

ROOT = Path(__file__).resolve().parent.parent

# Pastas staging por programa
STAGING_DIR = ROOT / "data" / "staging"

# Pastas de output por programa
OUTPUT_DIR = ROOT / "data" / "output"

# Pastas de boletins por programa
PROGRAMAS_DIR = ROOT  # GIRO/, NJUD/, BOLETIM/


# ===========================================================================
# TIPOS
# ===========================================================================


class TipoPrograma(Enum):
    """Tipos de programa suportados pelo DIVISOR."""
    NJUD = "NJUD"
    GIRO = "GIRO"
    BOLETIM = "BOLETIM"


@dataclass(frozen=True)
class Programa:
    """
    Configuração canónica de um programa.
    
    Attributes:
        id: identificador único (njud, giro, boletim)
        nome_completo: nome legível do programa
        pasta_raiz: pasta raiz do programa no repositório (GIRO/, NJUD/, BOLETIM/)
        pasta_staging: pasta de staging isolada
        pasta_output: pasta de saída isolada
        orquestrador: módulo orquestrador principal
        scripts_entrada: scripts de entrada válidos
        worker_pool: worker pool específico (se houver)
        notas: notas adicionais
    """
    id: str
    nome_completo: str
    pasta_raiz: Path
    pasta_staging: Path
    pasta_output: Path
    orquestrador: str
    scripts_entrada: tuple[str, ...] = field(default_factory=tuple)
    worker_pool: str | None = None
    notas: str = ""

    @property
    def nome_pasta(self) -> str:
        """Retorna o nome da pasta raiz (ex: 'GIRO', 'NJUD', 'BOLETIM')."""
        return self.pasta_raiz.name


@dataclass(frozen=True)
class ConfiguracaoPrograma:
    """
    Configuração de execução de um programa.
    
    Agrupa todas as configurações necessárias para isolar a execução
    de um programa, garantindo que não haja mistura com outros.
    """
    programa: TipoPrograma
    codigo: str  # ex: "0101", "2026-09-15"
    data_exibicao: date | None
    janela_inicio: date | None
    janela_fim: date | None
    
    @property
    def pasta_staging_programa(self) -> Path:
        """Pasta de staging específica para este programa/código."""
        return STAGING_DIR / self.programa.value / self.codigo
    
    @property
    def pasta_output_programa(self) -> Path:
        """Pasta de saída específica para este programa/código."""
        return OUTPUT_DIR / self.programa.value / self.codigo
    
    @property
    def pasta_estado_programa(self) -> Path:
        """Pasta de estado específica para este programa/código."""
        return self.pasta_output_programa / "estado"
    
    @property
    def pasta_logs_programa(self) -> Path:
        """Pasta de logs específica para este programa/código."""
        return self.pasta_output_programa / "logs"


# ===========================================================================
# REGISTRO CANÓNICO
# ===========================================================================


PROGRAMA_NJUD = Programa(
    id="njud",
    nome_completo="Jornal Noticioso do Judiciário",
    pasta_raiz=PROGRAMAS_DIR / "NJUD",
    pasta_staging=STAGING_DIR / "NJUD",
    pasta_output=OUTPUT_DIR / "NJUD",
    orquestrador="src.orchestration.safe_runner",
    scripts_entrada=(
        "run_pipeline_safe_v2.py",
        "iniciar_ciclo.py",
        "reprocessar_agosto.sh",
    ),
    worker_pool="src.pipeline.dispatcher",
    notas=(
        "Trilha de fundo TRILHA_ESCALADA_NJUD.mp3 (overlay fixo 20% ou "
        "bgm_mixer.py com ducking, opt-in) em src/divisor_boletins/montagem.py"
    ),
)

PROGRAMA_GIRO = Programa(
    id="giro",
    nome_completo="GIRO nas Comarcas",
    pasta_raiz=PROGRAMAS_DIR / "GIRO",
    pasta_staging=STAGING_DIR / "GIRO",
    pasta_output=OUTPUT_DIR / "GIRO",
    orquestrador="scripts_pipeline.executar_programa",
    scripts_entrada=("rodar_tudo_giro.sh",),
    notas=(
        "Pipeline ativo: scripts_pipeline/executar_programa.py → "
        "src/core/processamento/processar_boletim.py"
    ),
)

PROGRAMA_BOLETIM = Programa(
    id="boletim",
    nome_completo="Boletim",
    pasta_raiz=PROGRAMAS_DIR / "BOLETIM",
    pasta_staging=STAGING_DIR / "BOLETIM",
    pasta_output=OUTPUT_DIR / "BOLETIM",
    orquestrador="src.gravador_inteligente.montagem_boletins",
    notas=(
        "Mesmo repositório do NJUD, pipeline distinto. Função de "
        "auditoria: auditar_boletim() (LUFS, duração, existência) em "
        "src/gravador_inteligente/montagem_boletins.py"
    ),
)


# ===========================================================================
# MAPEAMENTO
# ===========================================================================


PROGRAMAS_POR_ID: dict[str, Programa] = {
    PROGRAMA_NJUD.id: PROGRAMA_NJUD,
    PROGRAMA_GIRO.id: PROGRAMA_GIRO,
    PROGRAMA_BOLETIM.id: PROGRAMA_BOLETIM,
}


PROGRAMAS: tuple[Programa, ...] = (
    PROGRAMA_NJUD,
    PROGRAMA_GIRO,
    PROGRAMA_BOLETIM,
)


# ===========================================================================
# FUNÇÕES AUXILIARES
# ===========================================================================


def obter_programa(id_programa: str) -> Programa:
    """
    Retorna o Programa pelo id ('njud', 'giro', 'boletim').
    
    Levanta KeyError com mensagem explícita se o id não existir —
    propositalmente falha alto, para não permitir que um agente
    "invente" um quarto programa por engano.
    """
    try:
        return PROGRAMAS_POR_ID[id_programa.lower()]
    except KeyError:
        validos = ", ".join(sorted(PROGRAMAS_POR_ID.keys()))
        raise KeyError(
            f"Programa desconhecido: {id_programa!r}. "
            f"Programas válidos: {validos}. "
            f"Ver GLOSSARIO_PROGRAMAS.md antes de prosseguir."
        )


def obter_programa_por_valor(valor: str) -> Programa | None:
    """
    Tenta identificar o programa por valor (pode ser id, nome, ou TipoPrograma).
    
    Returns:
        Programa se encontrado, None caso contrário.
    """
    valor_lower = valor.lower()
    
    # Tentativa 1: id direto
    if valor_lower in PROGRAMAS_POR_ID:
        return PROGRAMAS_POR_ID[valor_lower]
    
    # Tentativa 2: nome do TipoPrograma (NJUD, GIRO, BOLETIM)
    for prog in PROGRAMAS:
        if prog.id.upper() == valor_upper or prog.nome_pasta.upper() == valor_upper:
            return prog
    
    return None


def listar_programas() -> list[Programa]:
    """Retorna lista de todos os programas válidos."""
    return list(PROGRAMAS)


# ===========================================================================
# VALIDAÇÃO DE ISOLAMENTO
# ===========================================================================


def validar_isolamento(programa_id: str) -> list[str]:
    """
    Valida que o ambiente de um programa está isolado.
    
    Returns:
        Lista de erros (vazia = OK).
    """
    erros = []
    programa = obter_programa(programa_id)
    
    # Verificar que pasta raiz existe
    if not programa.pasta_raiz.exists():
        erros.append(f"Pasta raiz não existe: {programa.pasta_raiz}")
    
    # Verificar que staging está isolado
    if not programa.pasta_staging.exists():
        erros.append(f"Pasta staging não existe: {programa.pasta_staging}")
    
    # Verificar que output está isolado
    if not programa.pasta_output.exists():
        erros.append(f"Pasta output não existe: {programa.pasta_output}")
    
    return erros


if __name__ == "__main__":
    print("=" * 60)
    print("PROGRAMAS VÁLIDOS")
    print("=" * 60)
    for p in PROGRAMAS:
        print(f"\n[{p.id}] {p.nome_completo}")
        print(f"  pasta_raiz: {p.pasta_raiz}")
        print(f"  pasta_staging: {p.pasta_staging}")
        print(f"  pasta_output: {p.pasta_output}")
        print(f"  orquestrador: {p.orquestrador}")
        if p.worker_pool:
            print(f"  worker pool: {p.worker_pool}")
        if p.scripts_entrada:
            print(f"  scripts_entrada: {', '.join(p.scripts_entrada)}")
        if p.notas:
            print(f"  notas: {p.notas}")
