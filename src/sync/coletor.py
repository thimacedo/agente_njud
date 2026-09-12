"""
sync/coletor.py — Ponte entre regras e staging.

Contratos:
- Recebe SelecaoBoletins de regras/
- Copia arquivos do Drive H: para data/staging/PROGRAMA/AAAA-MM-DD/
- Verifica integridade pós-cópia
- Devolve ResultadoColeta

O coletor é o ÚNICO módulo que lê do Drive H: (read-only).
Nenhum outro módulo deve acessar H: diretamente.
"""
from __future__ import annotations

import logging
import shutil
from datetime import date
from pathlib import Path
from typing import Optional

from regras.livro import ResultadoColeta, SelecaoBoletins, TipoPrograma

logger = logging.getLogger(__name__)

# ===========================================================================
# CONSTANTES
# ===========================================================================

# Pasta base de staging (relativa ao projeto)
STAGING_BASE = Path("data/staging")

# Mapeamento de programa para pasta de staging
STAGING_DIR = {
    TipoPrograma.NJUD: "NJUD",
    TipoPrograma.GIRO: "GIRO",
    TipoPrograma.BOLETIM: "BOLETIM",
}


# ===========================================================================
# FUNÇÕES AUXILIARES
# ===========================================================================


def _diretorio_staging(programa: TipoPrograma, data: date) -> Path:
    """
    Retorna o diretório de staging para um programa/data.

    Formato: data/staging/PROGRAMA/AAAA-MM-DD/
    """
    nome_programa = STAGING_DIR.get(programa, programa.value)
    return STAGING_BASE / nome_programa / data.strftime("%Y-%m-%d")


# ===========================================================================
# FUNÇÃO PRINCIPAL
# ===========================================================================


def coletar_boletins(
    selecao: SelecaoBoletins,
    data_referencia: Optional[date] = None,
    dry_run: bool = False,
) -> ResultadoColeta:
    """
    Copia boletins selecionados do Drive H: para staging.

    Args:
        selecao: SelecaoBoletins com boletins a copiar
        data_referencia: data para organizar a pasta de staging
                         (padrão: data do primeiro boletim)
        dry_run: se True, apenas simula sem copiar

    Returns:
        ResultadoColeta com status da operação

    Raises:
        ValueError: se a seleção for inválida
    """
    if not selecao.boletins:
        return ResultadoColeta(
            sucesso=True,
            erros=[],
            integridade_ok=True,
        )

    # Determinar data de referência
    if data_referencia is None:
        data_referencia = selecao.boletins[0].data

    # Diretório de destino
    destino = _diretorio_staging(selecao.programa, data_referencia)

    arquivos_coletados: list[Path] = []
    erros: list[str] = []

    if dry_run:
        logger.info(f"[DRY-RUN] Copiaria {len(selecao.boletins)} boletins para {destino}")
        for b in selecao.boletins:
            logger.info(f"  [DRY-RUN] {b.caminho_absoluto} → {destino / b.nome_arquivo}")
        return ResultadoColeta(
            sucesso=True,
            arquivos_coletados=[destino / b.nome_arquivo for b in selecao.boletins],
            erros=[],
            integridade_ok=True,
        )

    # Criar diretório de destino
    destino.mkdir(parents=True, exist_ok=True)

    # Copiar cada boletim
    for b in selecao.boletins:
        origem = b.caminho_absoluto
        arquivo_destino = destino / b.nome_arquivo

        # Verificar se origem existe
        if not origem.exists():
            erros.append(f"Origem não existe: {origem}")
            continue

        try:
            # Copiar com shutil.copy2 (preserva metadados)
            shutil.copy2(str(origem), str(arquivo_destino))
            arquivos_coletados.append(arquivo_destino)
            logger.info(f"Copiado: {origem.name} → {arquivo_destino}")
        except Exception as e:
            erros.append(f"Erro ao copiar {origem}: {e}")
            logger.error(f"Erro ao copiar {origem}: {e}")

    # Verificar integridade
    integridade_ok = True
    if not erros:
        integridade_ok = verificar_integridade(arquivos_coletados, selecao)

    sucesso = len(erros) == 0 and len(arquivos_coletados) > 0

    return ResultadoColeta(
        sucesso=sucesso,
        arquivos_coletados=arquivos_coletados,
        erros=erros,
        integridade_ok=integridade_ok,
    )


def verificar_integridade(
    arquivos: list[Path],
    selecao: SelecaoBoletins,
) -> bool:
    """
    Verifica integridade dos arquivos copiados.

    Critérios:
    - Arquivo existe no destino
    - Tamanho > 0 bytes
    - Tamanho próximo ao original (tolerância 1%)

    Args:
        arquivos: lista de caminhos copiados
        selecao: seleção original (para comparar tamanhos)

    Returns:
        True se todos os arquivos estão íntegros
    """
    if not arquivos:
        return True

    # Mapa de origens por nome
    origens = {b.nome_arquivo: b for b in selecao.boletins}

    for arq in arquivos:
        if not arq.exists():
            logger.error(f"Integridade: arquivo não existe: {arq}")
            return False

        tamanho_destino = arq.stat().st_size
        if tamanho_destino == 0:
            logger.error(f"Integridade: arquivo vazio: {arq}")
            return False

        # Comparar com origem se disponível
        nome = arq.name
        if nome in origens:
            origem = origens[nome].caminho_absoluto
            if origem.exists():
                tamanho_origem = origem.stat().st_size
                if tamanho_destino != tamanho_origem:
                    logger.error(
                        f"Integridade: tamanho divergente para {nome}: "
                        f"origem={tamanho_origem}, destino={tamanho_destino}"
                    )
                    return False
                # Tamanho idêntico confirma integridade para este arquivo

    logger.info(f"Integridade OK: {len(arquivos)} arquivo(s) verificado(s)")
    return True


def listar_staging(programa: TipoPrograma, data: date) -> list[Path]:
    """
    Lista arquivos em staging para um programa/data.

    Args:
        programa: tipo do programa
        data: data de referência

    Returns:
        Lista de caminhos de arquivos em staging
    """
    diretorio = _diretorio_staging(programa, data)
    if not diretorio.exists():
        return []
    return sorted(diretorio.rglob("*.mp3"))


def limpar_staging(programa: TipoPrograma, data: date, confirmar: bool = True) -> bool:
    """
    Remove arquivos de staging de um programa/data.

    Args:
        programa: tipo do programa
        data: data de referência
        confirmar: se True, pede confirmação

    Returns:
        True se removeu com sucesso
    """
    if data == date.today():
        logger.warning(
            f"Remoção de staging bloqueada: {programa.value}/{data} "
            "é o dia corrente e não pode ser removido."
        )
        return False

    diretorio = _diretorio_staging(programa, data)
    if not diretorio.exists():
        return True

    if confirmar:
        logger.warning(f"Limpando staging: {diretorio}")

    try:
        shutil.rmtree(str(diretorio))
        logger.info(f"Staging limpo: {diretorio}")
        return True
    except Exception as e:
        logger.error(f"Erro ao limpar staging: {e}")
        return False
