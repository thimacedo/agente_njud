# coding: utf-8
"""
Log do pipeline GIRO nas Comarcas.

Logger estruturado para o processamento de notícias do Giro,
com saída para arquivo + stdout. Logs namespaced: logs/giro/.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Garantir que src/ está no path para importar config.giro
_src_dir = Path(__file__).resolve().parents[1]
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from config.giro import settings

# ===========================================================================
# Logger dedicado do GIRO
# ===========================================================================

_logger: Optional[logging.Logger] = None
_handler: Optional[logging.Handler] = None


def configurar_logger(
    logger_name: str = "giro",
    nivel: int = logging.INFO,
    arquivo: Optional[Path] = None,
    stdout: bool = True,
) -> logging.Logger:
    """Configura (ou reconfigura) o logger do GIRO.

    Args:
        logger_name: nome do logger (default: "giro")
        nivel: nível mínimo (default: INFO)
        arquivo: caminho opcional para log em arquivo
        stdout: se True, também loga no stdout
    """
    global _logger, _handler

    logger = logging.getLogger(logger_name)
    logger.setLevel(nivel)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if stdout:
        _handler = logging.StreamHandler(sys.stdout)
        _handler.setFormatter(formatter)
        _handler.setLevel(nivel)
        logger.addHandler(_handler)

    if arquivo:
        _handler = logging.FileHandler(arquivo, encoding="utf-8")
        _handler.setFormatter(formatter)
        _handler.setLevel(nivel)
        logger.addHandler(_handler)

    _logger = logger
    return logger


class LogPipeline:
    """Adaptador compatível com API do log do NJUD (LogPipeline)."""

    def __init__(self, logger_name: str = "giro_pipeline", nivel: int = logging.INFO):
        self._logger = configurar_logger(logger_name, nivel=nivel, stdout=True)

    def info(self, etapa: str, mensagem: str, **kwargs) -> None:
        log_info(etapa, mensagem, **kwargs)

    def aviso(self, etapa: str, mensagem: str, **kwargs) -> None:
        log_aviso(etapa, mensagem, **kwargs)

    def erro(self, etapa: str, mensagem: str, **kwargs) -> None:
        log_erro(etapa, mensagem, **kwargs)

    def debug(self, etapa: str, mensagem: str, **kwargs) -> None:
        log_debug(etapa, mensagem, **kwargs)


def get_logger() -> logging.Logger:
    """Retorna o logger configurado, ou cria um padrão."""
    global _logger
    if _logger is None:
        _logger = configurar_logger()
    return _logger


# ===========================================================================
# Helpers de log estruturado (estilo pipeline)
# ===========================================================================


def log_info(etapa: str, mensagem: str, **kwargs) -> None:
    """Log INFO com etapa e metadados opcionais."""
    logger = get_logger()
    extra = " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    logger.info(f"[{etapa}] {mensagem}{extra}")


def log_aviso(etapa: str, mensagem: str, **kwargs) -> None:
    """Log AVISO com etapa e metadados opcionais."""
    logger = get_logger()
    extra = " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    logger.warning(f"[{etapa}] {mensagem}{extra}")


def log_erro(etapa: str, mensagem: str, **kwargs) -> None:
    """Log ERRO com etapa e metadados opcionais."""
    logger = get_logger()
    extra = " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    logger.error(f"[{etapa}] {mensagem}{extra}")


def log_debug(etapa: str, mensagem: str, **kwargs) -> None:
    """Log DEBUG com etapa e metadados opcionais."""
    logger = get_logger()
    extra = " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    logger.debug(f"[{etapa}] {mensagem}{extra}")


# ===========================================================================
# Status do processamento
# ===========================================================================


def registrar_estado(
    mmss: str,
    idx_nota: int,
    status: str,
    motivos: Optional[list[str]] = None,
    pasta_estado: Optional[Path] = None,
) -> Path:
    """Persiste o estado de uma nota processada em JSON.

    Args:
        mmss: código do programa
        idx_nota: índice da nota (1..N)
        status: PENDENTE | OK | ESGOTADO | ESGOTADO_ACEITO | ERRO
        motivos: lista de motivos da reprovação (quando aplicável)
        pasta_estado: pasta onde salvar o JSON (default: DIR_PROCESSED/estado/)
    """
    if pasta_estado is None:
        pasta_estado = settings.ESTADO_DIR
    pasta_estado.mkdir(parents=True, exist_ok=True)

    nome_arquivo = f"GNC_{mmss}_N{idx_nota:02d}_estado.json"
    caminho = pasta_estado / nome_arquivo

    import json
    from datetime import datetime, timezone

    dados = {
        "mmss": mmss,
        "idx_nota": idx_nota,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "motivos": motivos or [],
    }

    caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    return caminho


def ler_estado(mmss: str, idx_nota: int, pasta_estado: Optional[Path] = None) -> dict:
    """Lê o estado persistido de uma nota."""
    if pasta_estado is None:
        pasta_estado = settings.ESTADO_DIR

    nome_arquivo = f"GNC_{mmss}_N{idx_nota:02d}_estado.json"
    caminho = pasta_estado / nome_arquivo

    import json
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return {"status": "PENDENTE", "motivos": []}


# ===========================================================================
# Resumo final (log de conclusão do programa)
# ===========================================================================


def log_programa_concluido(
    mmss: str,
    n_notas: int,
    notas_ok: int,
    notas_esgotadas: int,
    duracao_total: float,
    saida: Optional[Path] = None,
) -> None:
    """Log de conclusão de um programa GIRO."""
    logger = get_logger()
    logger.info("=" * 70)
    logger.info(f"PROGRAMA GNC_{mmss} CONCLUÍDO")
    logger.info(f"  Notas processadas: {n_notas}")
    logger.info(f"  Notas OK:          {notas_ok}")
    logger.info(f"  Notas ESGOTADO:    {notas_esgotadas}")
    logger.info(f"  Duração total:     {duracao_total:.1f}s")
    if saida:
        logger.info(f"  Saída:             {saida}")
    logger.info("=" * 70)
