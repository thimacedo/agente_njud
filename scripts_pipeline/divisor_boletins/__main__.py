from __future__ import annotations

"""CLI entry point para: python -m divisor_boletins dividir <entrada> <saida> [--apply]

Esta é a interface que o scripts_pipeline/njud/njud_dividir.sh espera.

No mínimo, o subcomando 'dividir' deve:
    1. Ler os MP3s de entrada (pasta ou arquivos).
    2. Invocar processar_arquivo() para cada um.
    3. Salvar as saídas (CABEÇA/CORPO ou metadados) em pasta_saida.
    4. Retornar código de sucesso/falha.

Implementação mínima: transcreve cada MP3, gera metadados de calibração,
corta em CABEÇA/CORPO e salva os arquivos mp3 resultantes + JSON de
metadados por arquivo. O corte usa a função cortar_audio() do audio.py.
"""
import argparse
import json
import sys
from pathlib import Path

from .audio import (
    carregar_modelo,
    processar_arquivo,
    cortar_audio,
)
from .log import LogPipeline

# Campos do resultado que são serializáveis para JSON (primários)
_CAMPOS_SERIALIZAVEIS = frozenset({
    "status",
    "transcricao",
    "calibracao",
    "ancora",
    "caminho_saida",
    "caminho_entrada",
    "erro",
})


def _serializavel(resultado: dict) -> dict:
    """Retorna uma cópia do resultado contendo apenas campos JSON-serializáveis."""
    return {k: v for k, v in resultado.items() if k in _CAMPOS_SERIALIZAVEIS}


def _salvar_cortado(
    audio: object,
    resultado: dict,
    pasta_boletim: Path,
   nome_base: str,
) -> dict:
    """Corta o áudio em CABEÇA/CORPO e salva os MP3s.

    Args:
        audio: AudioSegment do áudio original.
        resultado: dict retornado por processar_arquivo().
        pasta_boletim: pasta onde salvar (ex.: .../B1_saida/).
        nome_base: nome base sem extensão (ex.: 'B1').

    Returns:
        dict com 'cabeca_path' e 'corpo_path' ou None em caso de falha.
    """
    calibracao = resultado.get("calibracao", {})
    ancora = resultado.get("ancora", {})

    tempo_cabeca_fim_s = calibracao.get("tempo_inicio_s", 0.0)
    # Se a calibração reportar um tempo de início, usa como fim da cabeça;
    # senão usa 30% do áudio como fallback.
    if tempo_cabeca_fim_s <= 0:
        try:
            duracao_total_s = len(audio) / 1000.0
            tempo_cabeca_fim_s = duracao_total_s * 0.30
        except Exception:
            tempo_cabeca_fim_s = 0.0

    tempo_pos_vinheta_s = calibracao.get("duracao_vinheta_s", 0.0)
    tempo_assinatura_s = ancora.get("tempo_ancora_s", None)

    try:
        cabeca, corpo = cortar_audio(
            audio,
            tempo_cabeca_fim_s=tempo_cabeca_fim_s,
            tempo_pos_vinheta_s=tempo_pos_vinheta_s,
            tempo_assinatura_inicio_s=tempo_assinatura_s,
        )
    except Exception as e:
        return {"erro_corte": str(e)}

    pasta_boletim.mkdir(parents=True, exist_ok=True)

    cabeca_path = pasta_boletim / f"{nome_base}_CABECA.mp3"
    corpo_path = pasta_boletim / f"{nome_base}_CORPO.mp3"

    try:
        cabeca.export(str(cabeca_path), format="mp3", bitrate="192k")
    except Exception as e:
        return {"erro_cabeca": str(e)}
    try:
        corpo.export(str(corpo_path), format="mp3", bitrate="192k")
    except Exception as e:
        return {"erro_corpo": str(e)}

    return {
        "cabeca_path": str(cabeca_path),
        "corpo_path": str(corpo_path),
        "cabeca_duration_s": round(len(cabeca) / 1000.0, 2),
        "corpo_duration_s": round(len(corpo) / 1000.0, 2),
    }


def dividir(
    pasta_entrada: Path,
    pasta_saida: Path,
    aplicar: bool = False,
    modelo_nome: str = "tiny",
) -> int:
    """Divide os boletins da pasta_entrada, escrevendo resultados em pasta_saida.

    Args:
        pasta_entrada: pasta contendo os MP3s de entrada.
        pasta_saida: pasta onde os resultados serão escritos.
        aplicar: se True, salva saídas em disco; se False, só mostra o que faria.
        modelo_nome: nome do modelo Whisper.

    Returns:
        0 se tudo OK, 1 se houver falhas.
    """
    pasta_entrada = Path(pasta_entrada)
    pasta_saida = Path(pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    log = LogPipeline(pasta_saida / "logs")
    logger = log._logger if hasattr(log, "_logger") else log

    logger.info("dividir: entrada=%s saida=%s aplicar=%s", pasta_entrada, pasta_saida, aplicar)

    if not pasta_entrada.exists():
        logger.error("pasta de entrada não existe: %s", pasta_entrada)
        return 1

    mp3s = sorted(pasta_entrada.glob("*.mp3"))
    if not mp3s:
        logger.warning("nenhum MP3 encontrado em %s", pasta_entrada)
        return 1

    modelo = carregar_modelo(modelo_nome)

    resultados = []
    erros = 0

    for mp3 in mp3s:
        logger.info("processando %s", mp3.name)
        resultado = processar_arquivo(
            mp3,
            pasta_saida / f"{mp3.stem}_saida",
            modelo=modelo,
            logger=logger,
        )
        resultados.append(resultado)

        if resultado.get("status") != "ok":
            logger.error("falha em %s: %s", mp3.name, resultado.get("erro", "desconhecido"))
            erros += 1
            continue

        # Salva JSON de resultado (apenas campos serializáveis)
        saida_json = pasta_saida / f"{mp3.stem}_resultado.json"
        saida_json.write_text(
            json.dumps(_serializavel(resultado), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("resultado salvo: %s", saida_json)

        if aplicar:
            # Salva transcrição
            txt_saida = pasta_saida / f"{mp3.stem}_transcricao.txt"
            txt_saida.write_text(resultado.get("transcricao", ""), encoding="utf-8")
            logger.info("transcricao salva: %s", txt_saida)

            # Salva corte CABEÇA/CORPO
            audio = resultado.get("audio_seg")
            if audio is not None:
                info_corte = _salvar_cortado(
                    audio,
                    resultado,
                    pasta_saida / f"{mp3.stem}_saida",
                    mp3.stem,
                )
                if "erro_corte" in info_corte:
                    logger.error("corte falhou em %s: %s", mp3.name, info_corte["erro_corte"])
                    erros += 1
                else:
                    logger.info(
                        "corte salvo: cabeca=%s (%ss) corpo=%s (%ss)",
                        info_corte.get("cabeca_path"),
                        info_corte.get("cabeca_duration_s"),
                        info_corte.get("corpo_path"),
                        info_corte.get("corpo_duration_s"),
                    )
                    # Atualiza resultado com info do corte para o JSON
                    resultado["corte"] = info_corte
                    saida_json.write_text(
                        json.dumps(_serializavel(resultado), ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

    logger.info("dividir concluido: %d ok, %d erros", len(mp3s) - erros, erros)
    return 1 if erros else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="divisor_boletins — divisão de boletins em CABEÇA/CORPO",
    )
    sub = parser.add_subparsers(dest="comando")

    p_dividir = sub.add_parser("dividir", help="Divide boletins de uma pasta")
    p_dividir.add_argument("pasta_entrada", type=Path, help="pasta com os MP3s de entrada")
    p_dividir.add_argument("pasta_saida", type=Path, help="pasta de saída")
    p_dividir.add_argument("--apply", action="store_true", help="Salva saídas em disco")
    p_dividir.add_argument("--modelo", default="tiny", help="Modelo Whisper (default: tiny)")

    args = parser.parse_args()

    if args.comando == "dividir":
        rc = dividir(args.pasta_entrada, args.pasta_saida, args.apply, args.modelo)
        sys.exit(rc)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
