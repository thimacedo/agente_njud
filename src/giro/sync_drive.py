# coding: utf-8
"""
Sincronização do GIRO nas Comarcas com o Drive H:.

Copia os programas montados (data/output/GIRO_COMARCAS/*.mp3)
para a pasta de produção do Drive, seguindo a mesma convenção
de nomenclatura do NJUD.

Regra: H: é somente leitura exceto esta etapa de sincronização.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

# ===========================================================================
# CONFIGURAÇÃO DO CAMINHO NO DRIVE
# ===========================================================================

# Substitua pelo caminho real no Drive H:
# Exemplo:
#   H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\02_JORNAIS_GIRO\03_AUDIOS_RADIO
#
# Este valor pode vir de variável de ambiente GNC_DRIVE_SYNC ou,
# por padrão, aponta para uma pasta não-existente (obriga o usuário
# a configurar antes de usar).
# ===========================================================================

import os

_GNC_DRIVE_SYNC = os.getenv(
    "GNC_DRIVE_SYNC",
    r"H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\02_JORNAIS_GIRO\03_AUDIOS_RADIO",
)

_GNC_DRIVE_SYNC_PATH = Path(_GNC_DRIVE_SYNC)

# ===========================================================================
# FUNÇÕES DE SINCRONIZAÇÃO
# ===========================================================================


def sincronizar_programa(
    caminho_programa: Path,
    pasta_destino: Optional[Path] = None,
    logger=None,
) -> Optional[Path]:
    """Sincroniza UM programa montado para o Drive.

    Args:
        caminho_programa: Path do arquivo GNC_mmss_DD-MM-AA.mp3
        pasta_destino: pasta de destino no Drive (default: GNC_DRIVE_SYNC)
        logger: logger opcional

    Returns:
        Path do arquivo copiado no Drive, ou None se falhar
    """
    if pasta_destino is None:
        pasta_destino = _GNC_DRIVE_SYNC_PATH

    if logger is None:
        from .log import get_logger
        logger = get_logger()

    pasta_destino.mkdir(parents=True, exist_ok=True)

    # Valida nome do arquivo
    if not re.match(r"GNC_\d{4}_\d{2}-\d{2}-\d{4}\.mp3", caminho_programa.name):
        logger.error(
            "sincronizacao",
            f"Nome de arquivo inválido: {caminho_programa.name}",
        )
        return None

    destino = pasta_destino / caminho_programa.name

    try:
        shutil.copy2(caminho_programa, destino)
        logger.info(
            "sincronizacao",
            f"Programa sincronizado: {caminho_programa.name} → {destino}",
            tamanho_mb=round(caminho_programa.stat().st_size / 1_048_576, 2),
        )
        return destino
    except Exception as e:
        logger.error(
            "sincronizacao",
            f"Falha ao sincronizar {caminho_programa.name}: {e}",
        )
        return None


def sincronizar_todos(
    pasta_origem: Optional[Path] = None,
    pasta_destino: Optional[Path] = None,
    mmss_list: Optional[list[str]] = None,
    logger=None,
) -> list[Path]:
    """Sincroniza todos os programas de uma pasta para o Drive.

    Args:
        pasta_origem: pasta com os programas montados (default: DIR_OUTPUT)
        pasta_destino: pasta de destino no Drive
        mmss_list: lista opcional de mmss para sincronizar (senão, todos)
        logger: logger opcional

    Returns:
        Lista de Paths dos arquivos no Drive
    """
    from .config import DIR_OUTPUT

    if pasta_origem is None:
        pasta_origem = DIR_OUTPUT
    if pasta_destino is None:
        pasta_destino = _GNC_DRIVE_SYNC_PATH
    if logger is None:
        from .log import get_logger
        logger = get_logger()

    pasta_origem = Path(pasta_origem)
    if not pasta_origem.exists():
        logger.error(
            "sincronizacao",
            f"Pasta de origem não existe: {pasta_origem}",
        )
        return []

    # Encontrar todos os programas GNC_ no diretório
    programas = sorted(
        p for p in pasta_origem.glob("GNC_*.mp3")
        if re.match(r"GNC_\d{4}_\d{2}-\d{2}-\d{4}\.mp3", p.name)
    )

    if not programas:
        logger.warning(
            "sincronizacao",
            f"Nenhum programa GNC encontrado em {pasta_origem}",
        )
        return []

    if mmss_list is not None:
        mmss_set = set(mmss_list)
        total_antes_filtro = len(programas)
        programas = [p for p in programas if p.name[4:8] in mmss_set]
        logger.info(
            "sincronizacao",
            f"Filtro mmss aplicado: {len(programas)} de {total_antes_filtro} originais",
        )

    logger.info(
        "sincronizacao",
        f"Iniciando sincronização de {len(programas)} programas",
    )

    resultados = []
    for prog in programas:
        destino = sincronizar_programa(prog, pasta_destino, logger)
        if destino:
            resultados.append(destino)

    logger.info(
        "sincronizacao",
        f"Sincronização concluída: {len(resultados)}/{len(programas)} programas",
    )
    return resultados


# ===========================================================================
# STATUS DO DRIVE
# ===========================================================================


def status_drive(pasta_destino: Optional[Path] = None) -> dict:
    """Retorna status da pasta de sincronização no Drive.

    Args:
        pasta_destino: pasta de destino no Drive

    Returns:
        dict com estatísticas da pasta
    """
    if pasta_destino is None:
        pasta_destino = _GNC_DRIVE_SYNC_PATH

    pasta_destino = Path(pasta_destino)
    if not pasta_destino.exists():
        return {
            "exists": False,
            "total_programas": 0,
            "total_bytes": 0,
            "mmss_list": [],
        }

    programas = list(pasta_destino.glob("GNC_*.mp3"))
    total_bytes = sum(p.stat().st_size for p in programas)
    mmss_set = set()
    for p in programas:
        m = re.match(r"GNC_(\d{4})_", p.name)
        if m:
            mmss_set.add(m.group(1))

    return {
        "exists": True,
        "total_programas": len(programas),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / 1_048_576, 2),
        "mmss_list": sorted(mmss_set),
        "last_sync": datetime.now().isoformat(),
    }


# ===========================================================================
# MAIN
# ===========================================================================

if __name__ == "__main__":
    import sys

    print("=== Sincronização GNC ===")
    print(f"Caminho no Drive: {_GNC_DRIVE_SYNC_PATH}")
    print()

    status = status_drive()
    if not status["exists"]:
        print("Pasta de destino não existe no Drive.")
        print("Configure GNC_DRIVE_SYNC ou crie a pasta manualmente.")
        sys.exit(1)

    print(f"Programas no Drive: {status['total_programas']}")
    print(f"Tamanho total: {status['total_mb']} MB")
    if status["mmss_list"]:
        print(f"Programas (mmss): {', '.join(status['mmss_list'])}")
    else:
        print("Nenhum programa ainda sincronizado.")
