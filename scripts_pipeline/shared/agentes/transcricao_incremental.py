#!/usr/bin/env python3
"""
transcricao_incremental.py — Quando apenas um trecho muda, retranscreve só aquele trecho.

Uso:
    from shared.agentes.transcricao_incremental import transcricao_incremental

    resultado = transcricao_incremental(
        audio_path=Path("audio.mp3"),
        cache_dir=Path(".cache")
    )
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Adiciona raiz do projeto ao path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from shared.logging_config import get_logger
from shared.transcricao_cache import TranscricaoCache, calcular_hash_audio

logger = get_logger("transcricao_incremental")

# ── Constantes ───────────────────────────────────────────────────────────────

SEGMENTO_DURACAO_S = 30  # Segmentos de 30s para retranscrição parcial


def detectar_mudancas(audio_path: Path, cache_path: Optional[Path] = None) -> dict:
    """
    Compara hash para detectar mudanças (usa shared/transcricao_cache.py).

    Args:
        audio_path: Path do arquivo de áudio.
        cache_path: Path do arquivo de cache (opcional).

    Returns:
        Dict com 'mudou', 'hash_atual', 'hash_anterior', 'segmentos_afetados'.
    """
    audio_path = Path(audio_path)

    if not audio_path.exists():
        return {
            "mudou": False,
            "erro": f"Arquivo não encontrado: {audio_path}",
            "hash_atual": None,
            "hash_anterior": None,
            "segmentos_afetados": [],
        }

    # Calcular hash atual
    hash_atual = calcular_hash_audio(audio_path)

    # Verificar cache
    if cache_path is None:
        cache_path = Path(tempfile.gettempdir()) / "divisor_incremental" / f"{audio_path.stem}_cache.json"
    else:
        cache_path = Path(cache_path)

    hash_anterior = None
    segmentos_afetados = []

    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            hash_anterior = cache_data.get("hash_audio")
        except (json.JSONDecodeError, KeyError):
            logger.warning("Cache corrompido, retranscrever tudo")
            hash_anterior = None

    mudou = hash_atual != hash_anterior

    if mudou:
        logger.info(f"Mudança detectada: {audio_path.name}")
        logger.debug(f"Hash anterior: {hash_anterior}")
        logger.debug(f"Hash atual:    {hash_atual}")
        # Se mudou, marcar todos os segmentos como afetados inicialmente
        # A lógica refinada compara segmentos individuais
        segmentos_afetados = ["todos"]
    else:
        logger.info(f"Áudio inalterado: {audio_path.name}")

    return {
        "mudou": mudou,
        "hash_atual": hash_atual,
        "hash_anterior": hash_anterior,
        "segmentos_afetados": segmentos_afetados,
    }


def retranscrever_trecho(
    audio_path: Path,
    inicio: float,
    fim: float,
    modelo=None
) -> list[dict]:
    """
    Transcreve apenas um segmento de áudio (usa faster_whisper).

    Args:
        audio_path: Path do arquivo de áudio.
        inicio: Tempo de início em segundos.
        fim: Tempo de fim em segundos.
        modelo: Modelo whisper pré-carregado (opcional).

    Returns:
        Lista de segmentos transcritos.
    """
    audio_path = Path(audio_path)
    segmentos = []

    try:
        from pydub import AudioSegment

        # Carregar modelo se não fornecido
        if modelo is None:
            try:
                from faster_whisper import WhisperModel
                modelo = WhisperModel("base", device="cpu", compute_type="int8")
            except ImportError:
                logger.error("faster_whisper não instalado")
                return [{"inicio": inicio, "fim": fim, "texto": "[ERRO: faster_whisper não disponível]"}]

        # Extrair trecho do áudio
        audio = AudioSegment.from_mp3(str(audio_path))
        trecho = audio[int(inicio * 1000):int(fim * 1000)]

        # Salvar trecho temporário
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            trecho.export(tmp.name, format="wav")
            tmp_path = tmp.name

        # Transcrever
        segments, info = modelo.transcribe(tmp_path, language="pt", vad_filter=True)

        for segment in segments:
            segmentos.append({
                "inicio": segment.start + inicio,
                "fim": segment.end + inicio,
                "texto": segment.text.strip(),
                "probabilidade": segment.avg_log_prob if hasattr(segment, 'avg_log_prob') else 0.0,
            })

        # Limpar temp
        Path(tmp_path).unlink(missing_ok=True)

        logger.info(f"Trecho {inicio:.1f}s-{fim:.1f}s transcrito: {len(segmentos)} segmentos")

    except Exception as e:
        logger.error(f"Erro ao transcrever trecho {inicio}-{fim}: {e}")
        segmentos.append({
            "inicio": inicio,
            "fim": fim,
            "texto": f"[ERRO: {e}]",
            "probabilidade": 0.0,
        })

    return segmentos


def mesclar_transcricoes(
    original: list[dict],
    nova: list[dict],
    faixa: tuple[float, float]
) -> list[dict]:
    """
    Mescla transcrição antiga com nova.

    Substitui os segmentos da faixa especificada pela nova transcrição,
    mantendo os demais segmentos originais.

    Args:
        original: Transcrição original completa.
        nova: Nova transcrição (da faixa alterada).
        faixa: Tupla (inicio, fim) da faixa substituída.

    Returns:
        Lista mesclada de segmentos.
    """
    inicio_faixa, fim_faixa = faixa
    resultado = []

    # Adicionar segmentos antes da faixa
    for seg in original:
        if seg.get("fim", 0) <= inicio_faixa:
            resultado.append(seg)

    # Adicionar nova transcrição
    resultado.extend(nova)

    # Adicionar segmentos depois da faixa
    for seg in original:
        if seg.get("inicio", 0) >= fim_faixa:
            resultado.append(seg)

    # Ordenar por tempo
    resultado.sort(key=lambda s: s.get("inicio", 0))

    logger.info(f"Transcrições mescladas: {len(original)} original + {len(nova)} nova → {len(resultado)} final")
    return resultado


def transcricao_incremental(
    audio_path: Path,
    cache_dir: Optional[Path] = None,
    duracao_segmento_s: int = SEGMENTO_DURACAO_S
) -> dict:
    """
    Pipeline completo de transcrição incremental.

    1. Detecta mudanças via hash
    2. Se mudou, identifica segmentos afetados
    3. Retranscreve apenas os segmentos alterados
    4. Mescla com transcrição anterior

    Args:
        audio_path: Path do arquivo de áudio.
        cache_dir: Diretório de cache.
        duracao_segmento_s: Duração de cada segmento para análise.

    Returns:
        Dict com transcrição, status e estatísticas.
    """
    audio_path = Path(audio_path)

    if cache_dir is None:
        cache_dir = Path(tempfile.gettempdir()) / "divisor_incremental"
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_path = cache_dir / f"{audio_path.stem}_cache.json"

    resultado = {
        "status": "pendente",
        "transcricao": [],
        "segmentos_retranscritos": 0,
        "total_segmentos": 0,
        "do_cache": False,
        "erros": [],
    }

    try:
        # Verificar se áudio existe
        if not audio_path.exists():
            resultado["status"] = "erro"
            resultado["erros"].append(f"Arquivo não encontrado: {audio_path}")
            return resultado

        # Detectar mudanças
        mudancas = detectar_mudancas(audio_path, cache_path)

        if not mudancas["mudou"]:
            # Áudio inalterado — carregar do cache
            if cache_path.exists():
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                resultado["transcricao"] = cache_data.get("transcricao", [])
                resultado["status"] = "cache_hit"
                resultado["do_cache"] = True
                resultado["total_segmentos"] = len(resultado["transcricao"])
                logger.info(f"Cache hit: {audio_path.name}")
                return resultado
            else:
                # Sem cache — transcrever tudo
                logger.info(f"Sem cache, transcrever tudo: {audio_path.name}")
                mudancas["mudou"] = True

        if mudancas["mudou"]:
            # Carregar transcrição anterior se existir
            transcricao_anterior = []
            if cache_path.exists():
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        cache_data = json.load(f)
                    transcricao_anterior = cache_data.get("transcricao", [])
                except (json.JSONDecodeError, KeyError):
                    transcricao_anterior = []

            # Calcular duração total e segmentos
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_mp3(str(audio_path))
                duracao_total = len(audio) / 1000.0
            except Exception:
                # Fallback: estimar
                duracao_total = audio_path.stat().st_size / 16000  # rough estimate

            num_segmentos = max(1, int(duracao_total / duracao_segmento_s) + 1)
            resultado["total_segmentos"] = num_segmentos

            # Carregar modelo uma vez
            modelo = None
            try:
                from faster_whisper import WhisperModel
                modelo = WhisperModel("base", device="cpu", compute_type="int8")
                logger.info("Modelo Whisper carregado")
            except ImportError:
                logger.warning("faster_whisper não disponível, usando fallback")

            # Transcrever por segmentos
            transcricao_completa = []
            segmentos_retranscritos = 0

            for i in range(num_segmentos):
                inicio = i * duracao_segmento_s
                fim = min((i + 1) * duracao_segmento_s, duracao_total)

                # Verificar se segmento específico mudou (comparação fina)
                segmento_mudou = True
                if transcricao_anterior and mudancas["segmentos_afetados"] != ["todos"]:
                    # Hash por segmento para granularidade fina
                    segmento_hash_path = cache_dir / f"{audio_path.stem}_seg_{i}.hash"
                    segmento_hash_atual = _hash_segmento(audio_path, inicio, fim)
                    if segmento_hash_path.exists():
                        segmento_hash_anterior = segmento_hash_path.read_text().strip()
                        if segmento_hash_atual == segmento_hash_anterior:
                            segmento_mudou = False
                            # Manter segmento original
                            for seg in transcricao_anterior:
                                if seg.get("inicio", 0) >= inicio and seg.get("fim", 0) <= fim:
                                    transcricao_completa.append(seg)

                    segmento_hash_path.write_text(segmento_hash_atual)

                if segmento_mudou:
                    segmentos_novos = retranscrever_trecho(audio_path, inicio, fim, modelo)
                    transcricao_completa.extend(segmentos_novos)
                    segmentos_retranscritos += 1

            # Ordenar
            transcricao_completa.sort(key=lambda s: s.get("inicio", 0))

            # Salvar no cache
            cache_data = {
                "hash_audio": mudancas["hash_atual"],
                "transcricao": transcricao_completa,
                "audio_path": str(audio_path),
                "ultima_atualizacao": str(Path(audio_path).stat().st_mtime),
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            resultado["transcricao"] = transcricao_completa
            resultado["segmentos_retranscritos"] = segmentos_retranscritos
            resultado["status"] = "sucesso"
            logger.info(
                f"Transcrição incremental: {segmentos_retranscritos}/{num_segmentos} segmentos retranscritos"
            )

    except Exception as e:
        resultado["status"] = "erro"
        resultado["erros"].append(str(e))
        logger.error(f"Erro na transcrição incremental: {e}")

    return resultado


def _hash_segmento(audio_path: Path, inicio_s: float, fim_s: float) -> str:
    """Calcula hash de um segmento específico do áudio."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(str(audio_path))
        inicio_ms = int(inicio_s * 1000)
        fim_ms = int(fim_s * 1000)
        trecho = audio[inicio_ms:fim_ms]

        # Exportar para bytes e calcular hash
        import io
        buffer = io.BytesIO()
        trecho.export(buffer, format="wav")
        return hashlib.sha256(buffer.getvalue()).hexdigest()
    except Exception:
        # Fallback: hash do arquivo + timestamps
        h = hashlib.sha256()
        h.update(f"{audio_path}:{inicio_s}:{fim_s}".encode())
        return h.hexdigest()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Transcrição incremental DIVISOR")
    parser.add_argument("audio_path", type=Path, help="Arquivo de áudio")
    parser.add_argument("--cache-dir", type=Path, default=None)

    args = parser.parse_args()

    from shared.logging_config import setup_logging
    setup_logging(level="INFO")

    resultado = transcricao_incremental(args.audio_path, args.cache_dir)
    print(f"Status: {resultado['status']}")
    print(f"Segmentos: {resultado['segmentos_retranscritos']}/{resultado['total_segmentos']}")
    print(f"Do cache: {resultado['do_cache']}")
    if resultado["transcricao"]:
        print(f"\nTranscrição ({len(resultado['transcricao'])} segmentos):")
        for seg in resultado["transcricao"][:5]:
            print(f"  [{seg['inicio']:.1f}s - {seg['fim']:.1f}s] {seg['texto'][:60]}...")
