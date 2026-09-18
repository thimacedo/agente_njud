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
    # Pós-Demucs: resultado da verificação de vinhetas no stem vocal
    vinheta_abertura_detectada: bool = False
    vinheta_encerramento_detectada: bool = False
    texto_inicio_stem: str = ""
    texto_fim_stem: str = ""
    match_abertura: Optional[str] = None
    match_encerramento: Optional[str] = None

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

    # ------------------------------------------------------------------
    # Pós-Demucs: verificar se vinhetas de abertura/encerramento
    # ainda aparecem no stem vocal. Se sim, reportar via transcrição.
    # ------------------------------------------------------------------
    vinheta_info = _verificar_vinhetas_nos_stems(
        caminho_entrada, vocal_cache, config, t0,
    )

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
        vinheta_abertura_detectada=vinheta_info.get("vinheta_abertura_detectada", False),
        vinheta_encerramento_detectada=vinheta_info.get("vinheta_encerramento_detectada", False),
        texto_inicio_stem=vinheta_info.get("texto_inicio", ""),
        texto_fim_stem=vinheta_info.get("texto_fim", ""),
        match_abertura=vinheta_info.get("match_abertura"),
        match_encerramento=vinheta_info.get("match_encerramento"),
    )

    meta_cache.write_text(
        json.dumps(resultado.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if (vinheta_info.get("vinheta_abertura_detectada") or
            vinheta_info.get("vinheta_encerramento_detectada")):
        logger.warning(
            "Pós-Demucs: vinheta(s) ainda presente(s) no stem vocal de %s → "
            "abertura=%s encerramento=%s",
            entrada.name,
            vinheta_info.get("vinheta_abertura_detectada", False),
            vinheta_info.get("vinheta_encerramento_detectada", False),
        )

    if not config.manter_stems_brutos:
        shutil.rmtree(tmp_saida, ignore_errors=True)

    logger.info(
        "Separação concluída para %s em %.1fs → %s",
        entrada.name, duracao, vocal_cache,
    )

    return resultado


def _verificar_vinhetas_nos_stems(
    caminho_original: Path,
    caminho_vocal: Path,
    config: ConfigSeparacao,
    t0: float,
) -> dict:
    """
    Verifica se vinhetas de abertura ou encerramento ainda aparecem
    no stem vocal após a separação via Demucs.

    Como o Demucs (htdemucs, two-stems=vocals) não foi treinado para
    remover vinhetas específicas de rádio, é comum que fragmentos da
    vinheta sobrevivam no stem vocal — especialmente se a vinheta tiver
    parte falada sobreposta à música de fundo.

    A verificação é feita comparando o texto transcrito do início e do
    fim do stem vocal com os textos conhecidos das vinhetas de referência
    em assets/vinhetas/boletim/.

    Retorna um dict com:
        - 'vinheta_abertura detectada': bool
        - 'vinheta_encerramento_detectada': bool
        - 'texto_inicio': str (primeiros ~10s transcritos)
        - 'texto_fim': str (últimos ~10s transcritos)
        - 'match_abertura': str ou None (texto da vinheta que bateu)
        - 'match_encerramento': str ou None
    """
    from faster_whisper import WhisperModel
    from pathlib import Path

    assets_dir = Path(__file__).resolve().parent.parent / "assets" / "vinhetas" / "boletim"
    vinheta_abertura_path = assets_dir / "VHT_ABERTURA_BOLETIM.mp3"
    vinheta_encerramento_path = assets_dir / "VHT_ENCERRAMENTO_BOLETIM.mp3"

    resultado = {
        "vinheta_abertura_detectada": False,
        "vinheta_encerramento_detectada": False,
        "texto_inicio": "",
        "texto_fim": "",
        "match_abertura": None,
        "match_encerramento": None,
    }

    # Se não houver arquivos de referência, não faz nada
    if not vinheta_abertura_path.exists() or not vinheta_encerramento_path.exists():
        logger.debug(
            "Arquivos de vinheta não encontrados em %s — pulando verificação",
            assets_dir,
        )
        return resultado

    # Transcreve trecho inicial (primeiros 12s) e final (últimos 12s) do stem
    try:
        modelo_whisper = WhisperModel("tiny", device="cpu", compute_type="int8")
    except Exception as exc:
        logger.debug("Não foi possível carregar Whisper para verificação de vinhetas: %s", exc)
        return resultado

    try:
        import librosa  # type: ignore

        y, sr = librosa.load(str(caminho_vocal), sr=None, duration=12.0)
        duracao_real = len(y) / sr

        # Início
        segments_inicio, _ = modelo_whisper.transcribe(y=y, sr=sr)
        texto_inicio = " ".join(
            seg.text.strip() for seg in segments_inicio if seg.text.strip()
        )
        resultado["texto_inicio"] = texto_inicio

        # Fim (se o arquivo tiver mais de 24s, pega os últimos 12s)
        if duracao_real > 24.0:
            y_fim, _ = librosa.load(str(caminho_vocal), sr=None, offset=duracao_real - 12.0)
            segments_fim, _ = modelo_whisper.transcribe(y=y_fim, sr=sr)
            texto_fim = " ".join(
                seg.text.strip() for seg in segments_fim if seg.text.strip()
            )
        else:
            texto_fim = ""
        resultado["texto_fim"] = texto_fim

        # Transcreve as vinhetas de referência para comparação
        def transcrever_referencia(caminho: Path) -> str:
            y_ref, sr_ref = librosa.load(str(caminho), sr=None)
            segs, _ = modelo_whisper.transcribe(y=y_ref, sr=sr_ref)
            return " ".join(s.text.strip() for s in segs if s.text.strip())

        texto_ref_abertura = transcrever_referencia(vinheta_abertura_path)
        texto_ref_encerramento = transcrever_referencia(vinheta_encerramento_path)

        # Comparação frouxa: verifica se palavras-chave da vinheta aparecem
        # no texto do stem (ignora pontuação e case)
        def palavras_chave(texto: str) -> set[str]:
            import re
            return set(re.findall(r"[a-zA-Záàâãéèêíóôõúüç]+", texto.lower()))

        chaves_abertura = palavras_chave(texto_ref_abertura)
        chaves_encerramento = palavras_chave(texto_ref_encerramento)

        inicio_chaves = palavras_chave(texto_inicio)
        fim_chaves = palavras_chave(texto_fim)

        # Interseção: se >= 3 palavras coincidentes, considera detecção
        THRESH = 3

        if len(inicio_chaves & chaves_abertura) >= THRESH:
            resultado["vinheta_abertura_detectada"] = True
            resultado["match_abertura"] = texto_inicio[:200]

        if len(fim_chaves & chaves_encerramento) >= THRESH:
            resultado["vinheta_encerramento_detectada"] = True
            resultado["match_encerramento"] = texto_fim[:200]

        if resultado["vinheta_abertura_detectada"] or resultado["vinheta_encerramento_detectada"]:
            logger.warning(
                "Pós-Demucs: vinheta ainda presente no stem vocal de %s → "
                "abertura=%s encerramento=%s",
                caminho_original.name,
                resultado["vinheta_abertura_detectada"],
                resultado["vinheta_encerramento_detectada"],
            )

    except Exception as exc:
        logger.debug(
            "Não foi possível verificar vinhetas no stem de %s: %s",
            caminho_original.name, exc,
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
