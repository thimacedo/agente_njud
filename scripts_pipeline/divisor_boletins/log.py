from __future__ import annotations

"""Log Pipeline — mínimo compatível com o que o processar_boletim.py espera.

O LogPipeline original (divisor_boletins.log.LogPipeline) era usado por
processar_boletim.py e pelo safe_runner.py. Este mínimo replica a interface
que o código legado chama: construtor aceita pasta_log (Path ou str), e
expõe métodos de log básicos."""

import logging
from pathlib import Path

loggers: dict[str, logging.Logger] = {}


def _get_logger(name: str, pasta_log: Path | None = None) -> logging.Logger:
    if name in loggers:
        return loggers[name]
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    if pasta_log is not None:
        pasta_log = Path(pasta_log)
        pasta_log.mkdir(parents=True, exist_ok=True)
        try:
            fh = logging.FileHandler(pasta_log / f"{name}.log", encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(fh)
        except OSError:
            pass
    loggers[name] = logger
    return logger


class LogPipeline:
    """Logger mínimo compatível com o que o código legado espera.

    Uso:
        logger = LogPipeline(pasta_log)
        logger.info("mensagem")
        logger.error("erro")
    """

    def __init__(self, pasta_log: Path | str | None = None) -> None:
        self._pasta_log = Path(pasta_log) if pasta_log else None
        nome = "divisor_boletins"
        self._logger = _get_logger(nome, self._pasta_log)

    def info(self, msg: str, *args) -> None:
        self._logger.info(msg, *args)

    def warning(self, msg: str, *args) -> None:
        self._logger.warning(msg, *args)

    def error(self, msg: str, *args) -> None:
        self._logger.error(msg, *args)

    def debug(self, msg: str, *args) -> None:
        self._logger.debug(msg, *args)

    def exception(self, msg: str, *args) -> None:
        self._logger.exception(msg, *args)
