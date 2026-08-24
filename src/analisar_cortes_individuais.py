#!/usr/bin/env python3
"""
Auditoria de Cortes Individuais — CABEÇA/CORPO
=================================================

Diferente de analisar_integridade_arquivo() (que transcreve o JORNAL
MONTADO inteiro e só olha a primeira/última palavra do arquivo — que
são sempre da vinheta de abertura/encerramento, nunca de um boletim),
este script transcreve CADA _CABECA.mp3 e _CORPO.mp3 individualmente,
na pasta gerada pela etapa de divisão (antes da montagem). É o único
jeito de detectar corte de manchete/corpo no meio da fala, porque
essas bordas ficam "escondidas" no meio do jornal final.

Também filtra dois padrões de falso-positivo que já vimos em
produção:
  - Alucinação conhecida do Whisper em trechos quase silenciosos
    (ex: "Amara.org", "obrigado por assistir", "se inscreva no canal")
    — não indica corte real, indica silêncio real sendo mal-transcrito.
  - Falta de pontuação final isolada, sem outro sinal de corte — Whisper
    frequentemente omite o ponto final mesmo em frases completas; só
    conta como suspeito quando combinado com outro sinal.

Uso
----
    python analisar_cortes_individuais.py <pasta_JORNAIS_DIVIDIDOS> relatorio.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

from faster_whisper import WhisperModel
from pydub import AudioSegment
from pydub.silence import detect_leading_silence

# Frases/palavras conhecidas como alucinação do Whisper em silêncio — não contam como corte.
PADROES_ALUCINACAO = {
    "amara.org",
    "amara",
    "legendas pela comunidade amara.org",
    "obrigado por assistir",
    "se inscreva no canal",
    "like e se inscreva",
    "www.youtube.com",
    "subtitles by",
    "transcrito por",
}

LIMIAR_SILENCIO_BORDA_MS = 1500

# --- MEDIÇÃO FÍSICA DE ENERGIA (migração 2026-08-24, DECISOES.md item 6) ---
# O Whisper ancora timestamps das primeiras/últimas palavras em 0.00s em
# cortes curtos MESMO havendo silêncio físico real (limitação 2 do P.P.;
# confirmado em produção: 8/8 cortes íntegros reprovados como CORTADO).
# A borda agora é julgada por ENERGIA (RMS), não por timestamp:
#   - janela física de 50ms junto à borda;
#   - piso de fala = percentil 10 do RMS global (o vale mais baixo real);
#   - borda cortada SOMENTE se energia da janela >= PISO_ENERGIA_DB + 12dB
#     acima do piso (fala de verdade colada na borda).
JANELA_BORDA_MS = 50
PISO_ENERGIA_DB = -45.0   # abaixo disso é silêncio digital, nunca é corte
LIMIAR_CORTE_DB_ACIMA_PISO = 12.0


def _rms_db_janela(audio: AudioSegment, inicio_ms: int, fim_ms: int) -> float:
    """RMS em dBFS de uma janela [inicio_ms, fim_ms). Janela vazia → -inf."""
    if fim_ms <= inicio_ms:
        return -120.0
    trecho = audio[inicio_ms:fim_ms]
    if len(trecho) == 0:
        return -120.0
    return trecho.dBFS if trecho.dBFS > -120 else -120.0


def _piso_fala_db(audio: AudioSegment) -> float:
    """Percentil 10 dos RMS de janelas de 50ms — o 'vale' real do arquivo."""
    passo = JANELA_BORDA_MS
    valores = [
        audio[i:i + passo].dBFS
        for i in range(0, max(1, len(audio) - passo), passo)
    ]
    valores = [v for v in valores if v > -120]
    if not valores:
        return -120.0
    valores.sort()
    return valores[max(0, int(len(valores) * 0.10))]


def _borda_com_fala(
    audio: AudioSegment,
    lado: str,           # 'inicio' | 'fim'
    piso_db: float,
) -> tuple[bool, float]:
    """True se há energia de FALA (>= piso+limiar, e >= PISO_ENERGIA_DB)
    na janela física encostada na borda indicada. Retorna (suspeito, db)."""
    dur = len(audio)
    if lado == "inicio":
        janela = _rms_db_janela(audio, 0, JANELA_BORDA_MS)
    else:
        janela = _rms_db_janela(audio, max(0, dur - JANELA_BORDA_MS), dur)
    limiar = max(piso_db + LIMIAR_CORTE_DB_ACIMA_PISO, PISO_ENERGIA_DB + LIMIAR_CORTE_DB_ACIMA_PISO)
    return (janela >= limiar), janela


# ===========================================================================
# VALIDADOR CRUZADO COM FFMPEG SILENCEDETECT (item 1 da lista)
# ===========================================================================
# Motivo: o pydub usa detecção simples de RMS; ffmpeg tem filtro mais
# robusto e com parâmetros distintos. Usamos como segunda opinião antes
# de classificar como ESGOTADO ou CORTADO. ffmpeg indisponível não
# bloqueia: o resultado simplesmente não é usado.
# ===========================================================================

def _ffmpeg_silence_ms(caminho: Path, lado: str) -> int:
    """Retorna ms de silêncio no início/fim detectados pelo ffmpeg.
    lado: 'inicio' ou 'fim'. Retorna -1 se ffmpeg falhar."""
    if not shutil.which("ffmpeg"):
        return -1
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(caminho),
                "-af",
                "silencedetect=noise=-30dB:d=0.12",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        saida = proc.stderr + proc.stdout
        linhas = [l.strip() for l in saida.splitlines() if "silence_start:" in l or "silence_end:" in l]
        duracoes = []
        inicio_atual = None
        for l in linhas:
            if "silence_start:" in l:
                try:
                    inicio_atual = float(l.split("silence_start:")[-1].strip())
                except ValueError:
                    inicio_atual = None
            elif "silence_end:" in l and inicio_atual is not None:
                try:
                    fim = float(l.split("silence_end:")[-1].strip())
                    duracoes.append(fim - inicio_atual)
                    inicio_atual = None
                except ValueError:
                    pass
        if not duracoes:
            return 0
        if lado == "inicio":
            return int(duracoes[0] * 1000)
        sil_fim = duracoes[-1] * 1000 if duracoes else 0
        return int(sil_fim)
    except Exception:
        return -1


CONECTIVOS_CURTOS = {
    "a",
    "o",
    "e",
    "de",
    "do",
    "da",
    "em",
    "um",
    "uma",
    "os",
    "as",
    "no",
    "na",
    "que",
    "com",
    "por",
    "para",
    "ao",
    "aos",
    "às",
    "à",
}


def carregar_modelo() -> WhisperModel:
    # Mantido alinhado com o resto do pipeline: CPU + int8 + 2 threads.
    return WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=2)


def eh_alucinacao(texto: str) -> bool:
    t = texto.lower().strip(".,!?; ")
    return any(padrao in t for padrao in PADROES_ALUCINACAO)


def analisar_arquivo(caminho: Path, tipo: str, modelo: WhisperModel) -> dict:
    """
    tipo: 'CABECA' ou 'CORPO' — muda a expectativa de cada borda:
      - CABECA: início deve ser limpo; fim NÃO precisa de pontuação.
      - CORPO: fim DEVE ter pontuação; ausência isolada é sinal fraco.
    """
    resultado: dict = {
        "arquivo": caminho.name,
        "tipo": tipo,
        "duracao_s": None,
        "primeira_palavra": "",
        "ultima_palavra": "",
        "classificacao": "OK",
        "motivo": [],
        "erro": "",
    }

    try:
        segments, info = modelo.transcribe(
            str(caminho),
            beam_size=5,
            language="pt",
            word_timestamps=True,
        )
        segments = list(segments)
        resultado["duracao_s"] = round(info.duration, 2)

        palavras = []
        for seg in segments:
            for w in (seg.words or []):
                palavras.append({"start": w.start, "end": w.end, "word": w.word.strip()})

        texto_completo = " ".join(s.text.strip() for s in segments)

        if not palavras:
            resultado["classificacao"] = "SEM_FALA"
            resultado["motivo"].append("nenhuma palavra transcrita")
            return resultado

        if eh_alucinacao(texto_completo):
            resultado["classificacao"] = "POSSIVEL_ALUCINACAO_WHISPER"
            resultado["motivo"].append(
                f"texto bate com padrão de alucinação: '{texto_completo[:80]}'"
            )
            resultado["primeira_palavra"] = palavras[0]["word"]
            resultado["ultima_palavra"] = palavras[-1]["word"]
            return resultado

        primeira, ultima = palavras[0], palavras[-1]
        resultado["primeira_palavra"] = primeira["word"]
        resultado["ultima_palavra"] = ultima["word"]

        # --- BORDAS POR ENERGIA FÍSICA (não por timestamp do Whisper) ---
        audio = AudioSegment.from_file(str(caminho))
        piso_db = _piso_fala_db(audio)
        suspeito_inicio, db_ini = _borda_com_fala(audio, "inicio", piso_db)
        suspeito_fim, db_fim = _borda_com_fala(audio, "fim", piso_db)
        if suspeito_inicio:
            resultado["motivo"].append(
                f"energia de fala na borda inicial ({db_ini:.1f} dBFS, piso {piso_db:.1f})"
            )
        if suspeito_fim:
            resultado["motivo"].append(
                f"energia de fala na borda final ({db_fim:.1f} dBFS, piso {piso_db:.1f})"
            )
        resultado["energia_borda_ini_db"] = round(db_ini, 1)
        resultado["energia_borda_fim_db"] = round(db_fim, 1)

        p_lower = primeira["word"].lower().strip(".,!?")
        u_lower = ultima["word"].lower().strip(".,!?")
        # Conectivo isolado SÓ é suspeito se o arquivo não tiver fala real
        # além dele: artigos ("A plataforma...", "O quinto...") iniciam
        # frases naturais legítimas. Critério físico: arquivo >= 3s e
        # bordas SEM energia de fala = há frase completa; conectivo inicial
        # nesses casos é começo natural de frase, não resíduo.
        tem_fala_real = (
            info.duration >= 3.0
            and not suspeito_inicio
            and not suspeito_fim
        )
        if p_lower in CONECTIVOS_CURTOS and not tem_fala_real:
            suspeito_inicio = True
            resultado["motivo"].append(f"inicia com conectivo isolado: '{primeira['word']}'")
        if u_lower in CONECTIVOS_CURTOS and not tem_fala_real:
            suspeito_fim = True
            resultado["motivo"].append(f"termina com conectivo isolado: '{ultima['word']}'")

        if tipo == "CORPO" and texto_completo and not texto_completo.rstrip().endswith(
            (".", "!", "?")
        ):
            if suspeito_fim:
                resultado["motivo"].append(
                    "CORPO sem pontuação final E outro sinal de corte"
                )
            else:
                resultado["motivo"].append(
                    "CORPO sem pontuação final (fraco, isolado — checar manualmente)"
                )

        if tipo == "CABECA" and info.duration < 2.5:
            suspeito_fim = True
            resultado["motivo"].append(
                f"CABEÇA muito curta ({info.duration:.1f}s) — provável corte no início da manchete"
            )

        sil_inicio = detect_leading_silence(audio, silence_threshold=-40)
        sil_fim = detect_leading_silence(audio.reverse(), silence_threshold=-40)

        ffmpeg_sil_inicio_ms = _ffmpeg_silence_ms(caminho, "inicio")
        ffmpeg_sil_fim_ms = _ffmpeg_silence_ms(caminho, "fim")
        resultado["ffmpeg_sil_inicio_ms"] = ffmpeg_sil_inicio_ms
        resultado["ffmpeg_sil_fim_ms"] = ffmpeg_sil_fim_ms
        resultado["ffmpeg_status"] = "ok" if ffmpeg_sil_inicio_ms >= 0 and ffmpeg_sil_fim_ms >= 0 else "ignored"

        if ffmpeg_sil_inicio_ms == -1 and ffmpeg_sil_fim_ms == -1:
            resultado["ffmpeg_status"] = "ffmpeg_indisponivel"

        if sil_inicio > LIMIAR_SILENCIO_BORDA_MS:
            resultado["motivo"].append(
                f"silêncio de {sil_inicio}ms no início (possível resíduo)"
            )
        if sil_fim > LIMIAR_SILENCIO_BORDA_MS:
            resultado["motivo"].append(
                f"silêncio de {sil_fim}ms no fim (possível resíduo)"
            )

        # Validação cruzada: ffmpeg confirma resíduo mesmo quando pydub
        # não vê silêncio suficiente. Se ffmpeg diz >1200ms de silêncio
        # inicial, marca explicitamente.
        if ffmpeg_sil_inicio_ms >= 1200:
            resultado["motivo"].append(
                f"ffmpeg detectou {ffmpeg_sil_inicio_ms}ms de silêncio inicial"
            )
        if ffmpeg_sil_fim_ms >= 1200:
            resultado["motivo"].append(
                f"ffmpeg detectou {ffmpeg_sil_fim_ms}ms de silêncio final"
            )

        if suspeito_inicio or suspeito_fim:
            resultado["classificacao"] = "CORTADO"
        elif sil_inicio > LIMIAR_SILENCIO_BORDA_MS or sil_fim > LIMIAR_SILENCIO_BORDA_MS:
            resultado["classificacao"] = "RESIDUO_SILENCIO"

    except Exception as e:
        resultado["erro"] = f"{type(e).__name__}: {e}"
        resultado["classificacao"] = "ERRO_ANALISE"

    return resultado


def analisar_par(
    caminho_cabeca: str | Path,
    caminho_corpo: str | Path,
    modelo: WhisperModel,
) -> tuple[str, list[str]]:
    """
    Analisa CABEÇA+CORPO de UM boletim como unidade única e devolve
    (status, motivos) no formato consumido pelo ciclo_arquivo() de
    processo_unico.py: status é "OK" só se ambos os arquivos passarem;
    motivos concatena os motivos de ambos (prefixados por CABECA:/CORPO:
    para rastreabilidade) e é o insumo de classificar_motivo() para
    decidir a próxima estratégia de reprocessamento.

    Isto substitui o padrão anterior de rodar a auditoria em lote (todos
    os arquivos de uma pasta, gerando um CSV no final) por uma chamada
    pontual reutilizável pelo processo único e pelo dispatcher paralelo,
    sem duplicar a lógica de classificação em analisar_arquivo().
    """
    r_cabeca = analisar_arquivo(Path(caminho_cabeca), "CABECA", modelo)
    r_corpo = analisar_arquivo(Path(caminho_corpo), "CORPO", modelo)

    classificacoes_ok = {"OK"}
    status_cabeca_ok = r_cabeca["classificacao"] in classificacoes_ok
    status_corpo_ok = r_corpo["classificacao"] in classificacoes_ok

    motivos: list[str] = []
    motivos += [f"CABECA: {m}" for m in r_cabeca["motivo"]]
    motivos += [f"CORPO: {m}" for m in r_corpo["motivo"]]
    if r_cabeca["classificacao"] != "OK":
        motivos.append(f"CABECA classificada como {r_cabeca['classificacao']}")
    if r_corpo["classificacao"] != "OK":
        motivos.append(f"CORPO classificado como {r_corpo['classificacao']}")

    if status_cabeca_ok and status_corpo_ok:
        return "OK", []

    # Erros de análise não são "corte ruim" — são falha de processamento
    # e devem ser tratados separadamente (não adianta trocar estratégia
    # de corte se o Whisper não conseguiu nem transcrever).
    if r_cabeca["classificacao"] == "ERRO_ANALISE" or r_corpo["classificacao"] == "ERRO_ANALISE":
        return "ERRO", motivos

    return "CORTADO", motivos


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audita cada _CABECA.mp3/_CORPO.mp3 individualmente (não o jornal montado)."
    )
    parser.add_argument(
        "pasta_jornais_divididos",
        help="Pasta com os cortes (ex: F:/Projetos/DIVISOR/data/processed/JORNAIS_DIVIDIDOS)",
    )
    parser.add_argument("relatorio_csv", help="Caminho de saída do relatório CSV")
    args = parser.parse_args()

    pasta = Path(args.pasta_jornais_divididos)
    if not pasta.is_dir():
        print(f"✖ Pasta não encontrada: {pasta}", file=sys.stderr)
        sys.exit(1)

    cabecas = sorted(pasta.rglob("*_CABECA.mp3"))
    corpos = sorted(pasta.rglob("*_CORPO.mp3"))
    arquivos = [(c, "CABECA") for c in cabecas] + [(c, "CORPO") for c in corpos]

    print(f"{len(cabecas)} CABEÇA(s) + {len(corpos)} CORPO(s) = {len(arquivos)} arquivo(s) a analisar.")

    modelo = carregar_modelo()
    resultados: list[dict] = []

    # Escrita incremental: abre CSV no início, escreve header, flush a cada linha
    campos = [
        "arquivo",
        "tipo",
        "classificacao",
        "duracao_s",
        "primeira_palavra",
        "ultima_palavra",
        "motivo",
        "erro",
        "energia_borda_ini_db",
        "energia_borda_fim_db",
        "ffmpeg_sil_inicio_ms",
        "ffmpeg_sil_fim_ms",
        "ffmpeg_status",
    ]
    with open(args.relatorio_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        f.flush()

        for i, (arq, tipo) in enumerate(arquivos, start=1):
            print(f"[{i}/{len(arquivos)}] {arq.name} ({tipo})...", end=" ")
            r = analisar_arquivo(arq, tipo, modelo)
            resultados.append(r)
            print(r["classificacao"])

            # Grava linha imediatamente
            linha = dict(r)
            linha["motivo"] = "; ".join(r["motivo"])
            writer.writerow(linha)
            f.flush()  # Força escrita no disco

    contagem: dict[tuple[str, str], int] = {}
    for r in resultados:
        chave = (r["tipo"], r["classificacao"])
        contagem[chave] = contagem.get(chave, 0) + 1

    print(f"\nRelatório salvo em: {args.relatorio_csv}")
    print("\nResumo por tipo:")
    for (tipo, classe), qtd in sorted(contagem.items()):
        print(f"  {tipo:8s} {classe:30s} {qtd}")

    cortados = [r for r in resultados if r["classificacao"] == "CORTADO"]
    if cortados:
        print(f"\n{len(cortados)} arquivo(s) CORTADO(s) — priorize a audição manual destes:")
        for r in cortados[:30]:
            print(f"  {r['arquivo']} ({r['tipo']}): {r['motivo']}")
        if len(cortados) > 30:
            print(f"  ... e mais {len(cortados) - 30}")


if __name__ == "__main__":
    main()
