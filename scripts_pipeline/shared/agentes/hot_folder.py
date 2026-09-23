#!/usr/bin/env python3
"""
hot_folder.py — Monitora pasta de entrada e processa automaticamente novos áudios .mp3.

Uso:
    from shared.agentes.hot_folder import hot_folder_start, monitorar_pasta

    # Iniciar monitoramento
    hot_folder_start(pasta_entrada="/path/entrada", pasta_roteiros="/path/roteiros")

    # Ou usar funções individualmente
    arquivos = monitorar_pasta("/path/entrada", callback=meu_callback)
"""
import re
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

# Adiciona raiz do projeto ao path para imports
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from shared.logging_config import get_logger

logger = get_logger("hot_folder")


def monitorar_pasta(pasta: Path, callback: Optional[Callable] = None) -> list[dict]:
    """
    Monitora pasta para novos .mp3 usando polling com pathlib (sem watchdog).

    Args:
        pasta: Caminho da pasta a monitorar.
        callback: Função chamada para cada novo arquivo encontrada.
                 Recebe Path do arquivo como argumento.

    Returns:
        Lista de dicts com informações dos arquivos encontrados.
    """
    pasta = Path(pasta)
    if not pasta.exists():
        logger.error(f"Pasta não encontrada: {pasta}")
        return []

    resultados = []
    arquivos_mp3 = sorted(pasta.glob("*.mp3"))

    for arquivo in arquivos_mp3:
        info = {
            "arquivo": arquivo,
            "nome": arquivo.name,
            "tamanho": arquivo.stat().st_size,
            "modificacao": datetime.fromtimestamp(arquivo.stat().st_mtime),
            "processado": False,
            "erro": None,
        }

        if callback:
            try:
                callback(arquivo)
                info["processado"] = True
            except Exception as e:
                info["erro"] = str(e)
                logger.error(f"Erro ao processar {arquivo.name}: {e}")
                logger.debug(traceback.format_exc())

        resultados.append(info)

    return resultados


def associar_roteiro(audio_path: Path, pasta_roteiros: Path) -> Optional[Path]:
    """
    Busca roteiro correspondente por data no nome do arquivo.

    Padrão: 'DD SET' no nome (ex: '04 SET' → dia 04 de setembro).
    Procura roteiros com o mesmo dia no nome.

    Args:
        audio_path: Path do arquivo de áudio.
        pasta_roteiros: Pasta onde buscar roteiros.

    Returns:
        Path do roteiro encontrado ou None.
    """
    audio_path = Path(audio_path)
    pasta_roteiros = Path(pasta_roteiros)

    if not pasta_roteiros.exists():
        logger.warning(f"Pasta de roteiros não encontrada: {pasta_roteiros}")
        return None

    # Extrair dia do nome do áudio (padrão: DD SET)
    match = re.search(r'(\d{1,2})\s*SET', audio_path.stem, re.IGNORECASE)
    if not match:
        logger.warning(f"Padrão 'DD SET' não encontrado no nome: {audio_path.name}")
        return None

    dia = match.group(1).zfill(2)
    logger.info(f"Buscando roteiro para dia {dia} (arquivo: {audio_path.name})")

    # Buscar roteiros que contenham o dia no nome
    padrao_roteiro = re.compile(rf'\b{dia}\b', re.IGNORECASE)

    for roteiro in pasta_roteiros.glob("*.txt"):
        if padrao_roteiro.search(roteiro.stem):
            logger.info(f"Roteiro encontrado: {roteiro.name}")
            return roteiro

    # Tentar com .docx
    for roteiro in pasta_roteiros.glob("*.docx"):
        if padrao_roteiro.search(roteiro.stem):
            logger.info(f"Roteiro encontrado: {roteiro.name}")
            return roteiro

    logger.warning(f"Nenhum roteiro encontrado para dia {dia}")
    return None


def processar_novo_arquivo(
    audio_path: Path,
    pasta_roteiros: Path,
    saida: Optional[Path] = None
) -> dict:
    """
    Executa pipeline completo chamando processar_boletim_canonico.processar_canonico.

    Args:
        audio_path: Path do arquivo de áudio.
        pasta_roteiros: Pasta com roteiros.
        saida: Pasta de saída (opcional).

    Returns:
        Dict com status, arquivos_processados e erros.
    """
    audio_path = Path(audio_path)
    resultado = {
        "status": "pendente",
        "arquivo": str(audio_path),
        "roteiro": None,
        "saida": None,
        "erros": [],
        "estatisticas": {},
    }

    try:
        # Verificar se áudio existe
        if not audio_path.exists():
            resultado["status"] = "erro"
            resultado["erros"].append(f"Arquivo não encontrado: {audio_path}")
            return resultado

        # Associar roteiro
        roteiro = associar_roteiro(audio_path, pasta_roteiros)
        if roteiro:
            resultado["roteiro"] = str(roteiro)

        # Importar pipeline canônico
        from boletim.processar_boletim_canonico import processar_canonico

        logger.info(f"Iniciando processamento: {audio_path.name}")

        # Executar pipeline
        stats = processar_canonico(str(audio_path), str(pasta_roteiros))

        resultado["status"] = "sucesso"
        resultado["estatisticas"] = stats or {}

        # Determinar pasta de saída
        if saida:
            resultado["saida"] = str(saida)
        else:
            resultado["saida"] = str(audio_path.parent / f"{audio_path.stem}_saida")

        logger.info(f"Processamento concluído: {audio_path.name}")

    except Exception as e:
        resultado["status"] = "erro"
        resultado["erros"].append(str(e))
        logger.error(f"Erro no processamento de {audio_path.name}: {e}")
        logger.debug(traceback.format_exc())

    return resultado


def hot_folder_start(
    pasta_entrada: Path,
    pasta_roteiros: Path,
    intervalo_s: int = 30,
    saida: Optional[Path] = None,
    max_iteracoes: Optional[int] = None
) -> dict:
    """
    Loop de monitoramento com time.sleep.

    Args:
        pasta_entrada: Pasta a monitorar.
        pasta_roteiros: Pasta com roteiros.
        intervalo_s: Intervalo entre verificações (segundos).
        saida: Pasta de saída.
        max_iteracoes: Número máximo de iterações (None = infinito).

    Returns:
        Dict com resumo da execução.
    """
    pasta_entrada = Path(pasta_entrada)
    logger.info(f"Hot folder iniciado: {pasta_entrada}")
    logger.info(f"Intervalo: {intervalo_s}s | Roteiros: {pasta_roteiros}")

    arquivos_processados = set()
    erros = []
    iteracao = 0

    try:
        while True:
            if max_iteracoes and iteracao >= max_iteracoes:
                logger.info(f"Máximo de iterações atingido ({max_iteracoes})")
                break

            iteracao += 1

            # Buscar novos .mp3
            for arquivo in pasta_entrada.glob("*.mp3"):
                arquivo_id = f"{arquivo.name}_{arquivo.stat().st_mtime}"

                if arquivo_id not in arquivos_processados:
                    logger.info(f"Novo arquivo detectado: {arquivo.name}")

                    resultado = processar_novo_arquivo(
                        arquivo, pasta_roteiros, saida
                    )

                    arquivos_processados.add(arquivo_id)

                    if resultado["status"] == "erro":
                        erros.extend(resultado["erros"])

            time.sleep(intervalo_s)

    except KeyboardInterrupt:
        logger.info("Hot folder interrompido pelo usuário")

    return {
        "status": "finalizado",
        "arquivos_processados": len(arquivos_processados),
        "erros": erros,
        "iteracoes": iteracao,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hot folder DIVISOR")
    parser.add_argument("pasta_entrada", type=Path, help="Pasta de entrada")
    parser.add_argument("pasta_roteiros", type=Path, help="Pasta de roteiros")
    parser.add_argument("--intervalo", type=int, default=30, help="Intervalo (s)")
    parser.add_argument("--saida", type=Path, default=None, help="Pasta de saída")

    args = parser.parse_args()

    setup_logging = None
    from shared.logging_config import setup_logging
    setup_logging(level="INFO")

    resultado = hot_folder_start(
        args.pasta_entrada,
        args.pasta_roteiros,
        args.intervalo,
        args.saida,
    )
    print(f"Resultado: {resultado}")
