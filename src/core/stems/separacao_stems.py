"""
core/stems/separacao_stems.py

Separação de stems (vocal / resto) via Demucs — primeira etapa do
pipeline unificado, executada ANTES da detecção de cortes.

Objetivo: remover trilha original (vinheta/música de fundo) da locução,
deixando áudio limpo para a detecção de bordas funcionar com mais
precisão. Sem isso, a vinheta confunde os algoritmos de detecção
(correlação, VAD, silêncio) e produz cortes imprecisos ou falhas
silenciosas (o caso que motivou este módulo: Giro 2026-09-07).

Uso:
    python -m core.stems.separacao_stems entrada.mp3 --saida dir/

Integração ao pipeline:
    from core.stems.separacao_stems import separar_stems, ConfigSeparacao
    resultado = separar_stems("boletim.mp3", ConfigSeparacao())
    if resultado.sucesso:
        arquivo_limpo = resultado.caminho_vocal
        # ... passa arquivo_limpo para a detecção de corte
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("separacao_stems")


@dataclass
class ConfigSeparacao:
    """Configuração da separação de stems via Demucs."""
    cache_dir: Path = Path("data/cache_stems")
    tmp_dir: Path = Path("data/tmp_stems")
    modelo: str = "htdemucs"
    device: Optional[str] = None  # None = auto (GPU se disponível)
    formato_saida: str = "wav"
    timeout_segundos: int = 600
    manter_stems_brutos: bool = False


@dataclass
class ResultadoSeparacao:
    """Resultado da separação para integração ao estado do arquivo."""
    caminho_entrada: str
    caminho_vocal: str
    modelo_usado: str
    device_usado: str
    tempo_processamento_s: float
    veio_do_cache: bool
    chave_cache: str
    sucesso: bool
    erro: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class SeparacaoStemsError(RuntimeError):
    """Falha na separação de stems (Demucs, timeout, I/O)."""


def _calcular_chave_cache(caminho: Path, modelo: str) -> str:
    """Hash SHA256 do conteúdo + modelo = chave de cache."""
    hasher = hashlib.sha256()
    hasher.update(modelo.encode())
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(bloco)
    return hasher.hexdigest()[:24]


def _caminho_cache_vocal(config: ConfigSeparacao, chave: str) -> Path:
    return config.cache_dir / chave / f"vocals.{config.formato_saida}"


def _caminho_cache_meta(config: ConfigSeparacao, chave: str) -> Path:
    return config.cache_dir / chave / "metadata.json"


def _rodar_demucs(
    entrada: Path,
    saida: Path,
    config: ConfigSeparacao,
) -> Path:
    """Executa demucs via subprocess e retorna caminho do stem vocal."""
    saida.mkdir(parents=True, exist_ok=True)

    comando = [
        sys.executable, "-m", "demucs",
        "--two-stems", "vocals",
        "-n", config.modelo,
        "-o", str(saida),
    ]
    if config.device:
        comando += ["-d", config.device]
    comando.append(str(entrada))

    logger.info("Executando: %s", " ".join(comando))
    t0 = time.time()

    try:
        result = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=config.timeout_segundos,
        )
    except subprocess.TimeoutExpired:
        raise SeparacaoStemsError(
            f"Demucs timeout ({config.timeout_segundos}s) para {entrada.name}"
        )

    duracao = time.time() - t0
    logger.info("Demucs finalizou em %.1fs (código %d)", duracao, result.returncode)

    if result.returncode != 0:
        raise SeparacaoStemsError(
            f"Demucs falhou (código {result.returncode}) para {entrada.name}\n"
            f"stderr: {result.stderr[-2000:]}"
        )

    vocal = saida / config.modelo / entrada.stem / "vocals.wav"
    if not vocal.exists():
        raise SeparacaoStemsError(
            f"Demucs terminou sem erro mas vocals.wav não encontrado em {vocal}"
        )

    return vocal


def separar_stems(
    caminho_entrada: str | Path,
    config: Optional[ConfigSeparacao] = None,
) -> ResultadoSeparacao:
    """
    Separa stem vocal do áudio. Usa cache quando disponível.

    Fluxo:
        1. Calcula chave (hash conteúdo + modelo)
        2. Se cache hit → retorna imediatamente
        3. Se não → roda demucs, move para cache, salva metadata
    """
    config = config or ConfigSeparacao()
    entrada = Path(caminho_entrada)

    if not entrada.exists():
        raise FileNotFoundError(f"Entrada não encontrada: {entrada}")

    chave = _calcular_chave_cache(entrada, config.modelo)
    vocal_cache = _caminho_cache_vocal(config, chave)
    meta_cache = _caminho_cache_meta(config, chave)

    # Cache hit
    if vocal_cache.exists() and meta_cache.exists():
        logger.info("Cache hit para %s (chave=%s)", entrada.name, chave)
        meta = json.loads(meta_cache.read_text(encoding="utf-8"))
        return ResultadoSeparacao(
            caminho_entrada=str(entrada),
            caminho_vocal=str(vocal_cache),
            modelo_usado=meta.get("modelo_usado", config.modelo),
            device_usado=meta.get("device_usado", "desconhecido"),
            tempo_processamento_s=0.0,
            veio_do_cache=True,
            chave_cache=chave,
            sucesso=True,
        )

    # Processamento
    tmp_saida = config.tmp_dir / chave
    t0 = time.time()

    try:
        vocal_bruto = _rodar_demucs(entrada, tmp_saida, config)
    except SeparacaoStemsError as exc:
        logger.error("Falha na separação: %s", exc)
        raise

    duracao = time.time() - t0

    # Move para cache definitivo
    vocal_cache.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(vocal_bruto), str(vocal_cache))

    resultado = ResultadoSeparacao(
        caminho_entrada=str(entrada),
        caminho_vocal=str(vocal_cache),
        modelo_usado=config.modelo,
        device_usado=config.device or "auto",
        tempo_processamento_s=duracao,
        veio_do_cache=False,
        chave_cache=chave,
        sucesso=True,
    )

    meta_cache.write_text(
        json.dumps(resultado.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if not config.manter_stems_brutos:
        shutil.rmtree(tmp_saida, ignore_errors=True)

    logger.info(
        "Separação concluída para %s em %.1fs → %s",
        entrada.name, duracao, vocal_cache,
    )

    return resultado


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Separa stem vocal via Demucs")
    parser.add_argument("entrada", help="Arquivo de áudio de entrada")
    parser.add_argument("--saida-dir", default="data/stems_out", help="Diretório de saída")
    parser.add_argument("--cache-dir", default="data/cache_stems")
    parser.add_argument("--tmp-dir", default="data/tmp_stems")
    parser.add_argument("--modelo", default="htdemucs")
    parser.add_argument("--device", choices=["cpu", "cuda"], default=None)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--manter-stems-brutos", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger("separacao_stems").setLevel(logging.DEBUG)

    config = ConfigSeparacao(
        cache_dir=Path(args.cache_dir),
        tmp_dir=Path(args.tmp_dir),
        modelo=args.modelo,
        device=args.device,
        timeout_segundos=args.timeout,
        manter_stems_brutos=args.manter_stems_brutos,
    )

    try:
        resultado = separar_stems(args.entrada, config)
    except SeparacaoStemsError as exc:
        logger.error("Abortado: %s", exc)
        sys.exit(1)

    print(json.dumps(resultado.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
