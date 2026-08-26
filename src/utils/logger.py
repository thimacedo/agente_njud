"""
Logger estruturado para o pipeline DIVISOR
Substitui prints por logging com níveis, rotação e contexto
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logger(
    name: str,
    log_dir: str = "./logs",
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Configura logger estruturado com saída em console e arquivo com rotação.
    
    Args:
        name: Nome do logger (geralmente __name__)
        log_dir: Diretório para armazenar logs
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Tamanho máximo do arquivo antes da rotação
        backup_count: Número de arquivos de backup a manter
    
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Evita duplicação de handlers
    if logger.handlers:
        return logger
    
    # Formato estruturado com timestamp, nível, módulo e mensagem
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler para arquivo com rotação
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    log_file = log_path / f"{name.replace('.', '_')}_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Retorna logger existente ou cria novo com configurações padrão."""
    return setup_logger(name)
