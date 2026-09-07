# coding: utf-8
"""
Montador do programa GIRO nas Comarcas.

Receita de montagem:
  1. VHT_ABERTURA_GIRO
  2. Abertura do programa (locução: "Olá, hoje é terça-feira ... e esse é o Giro pelas Comarcas do Rio Grande do Norte")
  3. Para cada nota:
     a. VHT_PASSAGEM_GIRO (vinheta de passagem entre notas)
     b. Nota (manchete + corpo, sem vinheta interna)
  4. VHT_ENCERRAMENTO_GIRO

Diferente do NJUD: não há separação CABEÇA/CORPO — cada nota é uma
unidade self-contained (LOC + OFF juntos), e as vinhetas só aparecem
ENTRE notas, não cortando o interior das notas.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from pydub import AudioSegment
from pydub.effects import normalize

from .log import LogPipeline, log_debug, log_erro, log_info
from .config import (
    DIR_ASSETS_VINHETAS,
    DIR_OUTPUT,
    LIMIAR_ANCORA_GIRO,
    LIMIAR_FIM_PASSAGEM_GIRO,
    LIMIAR_INICIO_FALA_GIRO,
    VHT_ABERTURA_GIRO_NOME,
    VHT_PASSAGEM_GIRO_NOME,
    VHT_ENCERRAMENTO_GIRO_NOME,
)
from .utils import (
    normalizar_texto_giro,
    terça_do_programa,
    nome_programa,
)


# ===========================================================================
# CARREGAMENTO DE VINHETAS
# ===========================================================================


def _carregar_vinheta(nome_arquivo: str, etapa: str) -> Optional[AudioSegment]:
    """Carrega uma vinheta do diretório de assets.

    Args:
        nome_arquivo: nome do arquivo de vinheta (ex: VHT_ABERTURA_GIRO.mp3)
        etapa: nome da etapa para log

    Returns:
        AudioSegment carregado, ou None se não encontrado
    """
    caminho = DIR_ASSETS_VINHETAS / nome_arquivo
    if not caminho.exists():
        log_erro(etapa, f"Vinheta não encontrada: {caminho}")
        return None
    try:
        return AudioSegment.from_file(str(caminho))
    except Exception as e:
        log_erro(etapa, f"Erro ao carregar vinheta {caminho}: {e}")
        return None


# ===========================================================================
# MONTAGEM DO PROGRAMA
# ===========================================================================


def montar_programa(
    mmss: str,
    notas: list[Path],  # arquivos de nota já processados (manchete+corpo integrados)
    data_terça: Optional[str] = None,
    logger: Optional[LogPipeline] = None,
) -> Optional[Path]:
    """Monta um programa GIRO a partir das notas processadas.

    Receita:
        1. VHT_ABERTURA_GIRO
        2. [Não há abertura de locução separada — a abertura já está na
           VHT_ABERTURA_GIRO. O roteiro prevê LOC de abertura, mas como
           não temos áudio de abertura de locução, usamos apenas a VHT.
           Se houver áudio de abertura de locução disponível no futuro,
           adicionar como etapa 2.]
        3. Para cada nota:
           a. VHT_PASSAGEM_GIRO
           b. Nota (arquivo de nota processado)
        4. VHT_ENCERRAMENTO_GIRO

    Args:
        mmss: código do programa (ex: "0101")
        notas: lista de Path dos arquivos de nota processados
        data_terça: data da terça no formato DD-MM-ANO (ex: "11-08-26").
                    Se não informado, calcula automaticamente.
        logger: logger para auditoria

    Returns:
        Path do arquivo montado, ou None se falhar
    """
    if logger is None:
        from .log import get_logger
        logger = get_logger()

    etapa = "montagem"
    log_info(etapa, f"Iniciando montagem do programa GIRO: {mmss}")

    # Calcula data da terça se não informada
    if data_terça is None:
        data_terça = terça_do_programa(mmss).strftime("%d-%m-%Y")

    # Carrega vinhetas
    vht_abertura = _carregar_vinheta(VHT_ABERTURA_GIRO_NOME, etapa)
    if vht_abertura is None:
        return None

    vht_passagem = _carregar_vinheta(VHT_PASSAGEM_GIRO_NOME, etapa)
    if vht_passagem is None:
        return None

    vht_encerramento = _carregar_vinheta(VHT_ENCERRAMENTO_GIRO_NOME, etapa)
    if vht_encerramento is None:
        return None

    # Valida: precisa de pelo menos 1 nota
    if not notas:
        log_erro(etapa, f"Nenhuma nota para montar o programa {mmss}")
        return None

    # Ordena notas por nome (que contém índice N{n})
    notas_ordenadas = sorted(notas, key=lambda p: extrair_idx_nota(p.name))

    log_info(
    etapa,
    f"Montando {len(notas_ordenadas)} notas para GNC_{mmss}",
        notas=[p.name for p in notas_ordenadas],
    )

    # Inicia o programa com a VHT de abertura
    programa = AudioSegment.empty()
    programa += vht_abertura

    # Adiciona cada nota com a passagem antes
    for i, nota_path in enumerate(notas_ordenadas):
        log_debug(etapa, f"Adicionando nota {i+1}/{len(notas)}")

        # Vinheta de passagem (antes de cada nota, inclusive a primeira)
        # Nota: se quiser evitar passagem antes da primeira nota, comente
        # esta linha e adicione passagem apenas entre notas (i > 0).
        programa += vht_passagem

        # Nota (manchete + corpo integrados)
        try:
            nota_audio = AudioSegment.from_file(str(nota_path))
            # Normaliza a nota para consistência de volume
            nota_audio = normalize(nota_audio)
            programa += nota_audio
            log_debug(etapa, f"Nota {i+1} adicionada: {len(nota_audio)/1000:.1f}s")
        except Exception as e:
            log_erro(etapa, f"Erro ao carregar nota {nota_path}: {e}")
            return None

    # Adiciona vinheta de encerramento
    programa += vht_encerramento

    # Salva o programa montado
    pasta_saida = DIR_OUTPUT
    pasta_saida.mkdir(parents=True, exist_ok=True)

    nome_arquivo = nome_programa(mmss, data_terça)
    caminho_saida = pasta_saida / nome_arquivo

    try:
        programa.export(str(caminho_saida), format="mp3")
        log_info(
            etapa,
            f"Programa GNC_{mmss} montado com sucesso",
            duracao=len(programa)/1000,
            n_notas=len(notas_ordenadas),
            saida=str(caminho_saida),
        )
        return caminho_saida
    except Exception as e:
        log_erro(etapa, f"Erro ao salvar programa {caminho_saida}: {e}")
        return None


# ===========================================================================
# MONTAGEM DE VÁRIOS PROGRAMAS (por pasta de saída)
# ===========================================================================


def montar_todos(
    pasta_notas: Path,
    mmss_lista: Optional[list[str]] = None,
    logger: Optional[LogPipeline] = None,
) -> list[Path]:
    """Monta todos os programas a partir de notas já processadas.

    Args:
        pasta_notas: pasta contendo subpastas por mmss com as notas
        mmss_lista: lista opcional de mmss para montar (senão, todos)
        logger: logger

    Returns:
        Lista de Paths dos programas montados
    """
    if logger is None:
        from .log import get_logger
        logger = get_logger()

    etapa = "montagem_todos"
    log_info(etapa, "Iniciando montagem de todos os programas GNC")

    # Se pasta_notas contém subpastas por mmss
    if not pasta_notas.exists():
        log_erro(etapa, f"Pasta de notas não existe: {pasta_notas}")
        return []

    # Detecta mmss disponíveis
    mmss_dirs = sorted(
        d for d in pasta_notas.iterdir()
        if d.is_dir() and re.match(r"GNC_\d{4}_N\d+", d.name) or
           (d.is_dir() and d.name.startswith("GNC_"))
    )

    # Agrupa por mmss
    from collections import defaultdict
    notas_por_mmss = defaultdict(list)

    for nota_path in pasta_notas.rglob("*.mp3"):
        m = re.match(r"GNC_(\d{4})_N\d+", nota_path.name)
        if m:
            mmss = m.group(1)
            notas_por_mmss[mmss].append(nota_path)

    if not mmss_lista:
        mmss_lista = sorted(notas_por_mmss.keys())

    resultados = []
    for mmss in mmss_lista:
        notas = sorted(notas_por_mmss.get(mmss, []))
        if not notas:
            log_aviso(etapa, f"Nenhuma nota para GNC_{mmss}")
            continue
        caminho = montar_programa(mmss, notas, logger=logger)
        if caminho:
            resultados.append(caminho)

    log_info(
        etapa,
        f"Montagem concluída: {len(resultados)} programas gerados",
        total=len(resultados),
    )
    return resultados


# ===========================================================================
# UTILITÁRIOS
# ===========================================================================


def extrair_idx_nota(nome_arquivo: str) -> int:
    """Extrai o índice da nota (N{n}) do nome do arquivo.

    Ex: GNC_0101_N01_06-01-26.mp3 -> 1
    """
    m = re.search(r"N(\d+)", nome_arquivo)
    if m:
        return int(m.group(1))
    return 0


def extrair_mmss(nome_arquivo: str) -> Optional[str]:
    """Extrai o mmss do nome do arquivo.

    Ex: GNC_0101_N01_06-01-26.mp3 -> "0101"
    """
    m = re.match(r"GNC_(\d{4})", nome_arquivo)
    if m:
        return m.group(1)
    return None


# ===========================================================================
# MAIN — teste de montagem (se houver notas)
# ===========================================================================

if __name__ == "__main__":
    import sys
    from .log import configurar_logger

    logger = configurar_logger(stdout=True)

    if len(sys.argv) > 1:
        pasta = Path(sys.argv[1])
        from .montagem import montar_todos
        resultados = montar_todos(pasta, logger=logger)
        print(f"\nMontados: {len(resultados)} programas")
        for r in resultados:
            print(f"  {r}")
    else:
        print("Uso: python montagem.py <pasta_notas>")
        print("     pasta_notas contém subpastas com notas GNC_N*.mp3")
