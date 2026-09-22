#!/usr/bin/env python3
"""
logging_config.py — Config de logging do pipeline DIVISOR.

Uso:
    from shared.logging_config import setup_logging, get_logger
    
    setup_logging(level="INFO", log_file=Path("divisor.log"))
    logger = get_logger("pipeline")
    logger.info("Processando boletim", extra={"boletim": 5})
"""
import logging
import sys
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    formato: str = "simples"
) -> logging.Logger:
    """
    Configura logging do pipeline.
    
    Args:
        level: DEBUG, INFO, WARNING, ERROR
        log_file: Path para arquivo de log (None = só console)
        formato: "simples" (só mensagem) ou "detalhado" (timestamp + nível)
    """
    logger = logging.getLogger("divisor")
    logger.setLevel(getattr(logging, level.upper()))
    logger.handlers.clear()
    
    if formato == "detalhado":
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        fmt = logging.Formatter("%(message)s")
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)
    
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "") -> logging.Logger:
    """Retorna um logger filho para um módulo específico."""
    full_name = f"divisor.{name}" if name else "divisor"
    return logging.getLogger(full_name)
