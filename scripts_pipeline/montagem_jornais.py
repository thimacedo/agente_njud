# coding: utf-8
"""
Montador de jornais NJUD.

Invocado por scripts_pipeline/njud/njud_dividir.sh (subcomando "montar"),
sem argumentos por padrão. Lê os cortes CABEÇA/CORPO já gerados pelo
divisor_boletins (Fase 1 do pipeline NJUD) e monta o jornal completo.

Receita IMUTÁVEL (DECISOES.md Item 9 — não negociável):
    vinheta de abertura NJUD
    → cabeça 1 → cabeça 2 → cabeça 3 → cabeça 4
    → vinheta de passagem NJUD
    → corpo 1 → corpo 2 → corpo 3 → corpo 4
    → vinheta de encerramento NJUD

Regras derivadas que este script respeita:
    - Vinhetas de NJUD são assets distintos das vinhetas de boletim
      (VHT_ABERTURA_NJUD / EFEITO_PASSAGEM_NJUD / VHT_ENCERRAMENTO_NJUD,
      nunca as vinhetas *_BOLETIM). (Item 9, regra 1)
    - Nenhum jornal é montado com peça pendente: exige as 4 cabeças e os
      4 corpos presentes antes de montar (Item 6/6b — gate por-NJUD).
    - Pastas de jornal final contêm só NJUD_*, nunca BOLETIM_RADIO_TJRN_*
      (Item 12).
    - Nome do arquivo final: NJUD_<numero>_<DD-MM-AAAA>.mp3, com a data
      extraída do nome dos boletins de origem (padrão
      BOLETIM_RADIO_TJRN_DD_MM_AAAA_Bx...), nunca por contagem de dias
      úteis (Item 2).
    - Aceita tanto <entrada>/<NJUD>/ direto (formato gravado pelo
      dispatcher em JORNAIS_DIVIDIDOS/<NJUD>/) quanto <entrada>/<MÊS>/<NJUD>/
      (Item 6b) — detectado por regex "NJUD[_ ]?<num>" no nome da pasta.

Estrutura esperada dentro de cada pasta de NJUD (gerada pelo
divisor_boletins.__main__.dividir com --apply):
    <NJUD>/
        <boletim1>_saida/<boletim1>_CABECA.mp3
        <boletim1>_saida/<boletim1>_CORPO.mp3
        <boletim2>_saida/...
        ... (4 boletins)

Os 4 boletins de um NJUD são ordenados pelo índice B<n> no nome do
arquivo/pasta (ex.: B1, B2, B6, B7 — a ordem não precisa ser sequencial
sem lacunas, só crescente), não pela ordem alfabética de pasta.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------
# Garantir que src/ está no path para importar divisor_boletins.log
# (este script vive em scripts_pipeline/, src/ é irmão de scripts_pipeline/
# dentro de BASE_DIR — ver DECISOES.md Item 10, estrutura canônica).
# ---------------------------------------------------------------------
_BASE_DIR_PADRAO = Path(
    os.getenv("DIVISOR_BASE_DIR", str(Path(__file__).resolve().parent.parent))
)
_SRC_DIR = _BASE_DIR_PADRAO / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

try:
    from divisor_boletins.log import LogPipeline
except ImportError:
    # Fallback mínimo se divisor_boletins não for importável a partir daqui
    # (ex.: execução isolada fora da árvore do projeto) — não interrompe
    # a montagem, só perde o logging estruturado do LogPipeline.
    import logging

    class LogPipeline:  # type: ignore[no-redef]
        def __init__(self, pasta_log: Optional[Path | str] = None) -> None:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
            self._logger = logging.getLogger("montagem_jornais")

        def info(self, msg: str, *args) -> None:
            self._logger.info(msg, *args)

        def warning(self, msg: str, *args) -> None:
            self._logger.warning(msg, *args)

        def error(self, msg: str, *args) -> None:
            self._logger.error(msg, *args)


# ===========================================================================
# CONFIGURAÇÃO — caminhos via env var (DECISOES.md Item 10: nenhum caminho
# hardcoded fora de config; aqui usamos env var com default relativo ao
# BASE_DIR, mesmo padrão já aplicado em sync_drive.py/montagem_boletins.py).
# ===========================================================================

BASE_DIR = _BASE_DIR_PADRAO

DIR_JORNAIS_DIVIDIDOS = Path(
    os.getenv(
        "NJUD_JORNAIS_DIVIDIDOS_DIR",
        str(BASE_DIR / "data" / "processed" / "PRODUCAO_2026" / "JORNAIS_DIVIDIDOS"),
    )
)
DIR_JORNAIS_FINAL = Path(
    os.getenv("NJUD_JORNAIS_FINAL_DIR", str(BASE_DIR / "data" / "output" / "JORNAIS_FINAL"))
)
DIR_ASSETS_VINHETAS_NJUD = Path(
    os.getenv("NJUD_ASSETS_VINHETAS_DIR", str(BASE_DIR / "assets" / "vinhetas" / "njud"))
)

VHT_ABERTURA_NJUD_NOME = os.getenv("NJUD_VHT_ABERTURA_NOME", "VHT_ABERTURA_NJUD.mp3")
VHT_PASSAGEM_NJUD_NOME = os.getenv("NJUD_VHT_PASSAGEM_NOME", "EFEITO_PASSAGEM_NJUD.mp3")
VHT_ENCERRAMENTO_NJUD_NOME = os.getenv("NJUD_VHT_ENCERRAMENTO_NOME", "VHT_ENCERRAMENTO_NJUD.mp3")

# Quantas peças (boletins) compõem um jornal — parte da estrutura imutável
# do Item 9. Não é hardcode de instância: é a definição do formato do
# programa, igual a "um boletim tem cabeça+corpo".
N_BOLETINS_POR_JORNAL = int(os.getenv("NJUD_BOLETINS_POR_JORNAL", "4"))


# ===========================================================================
# DESCOBERTA DE PASTAS DE NJUD
# ===========================================================================

_RE_NJUD_PASTA = re.compile(r"njud[_\s]*0*(\d+)", re.IGNORECASE)
_RE_INDICE_B = re.compile(r"(?:^|[^A-Za-z0-9])B0*(\d+)(?![A-Za-z0-9])", re.IGNORECASE)
_RE_DATA_BOLETIM = re.compile(r"_(\d{2})_(\d{2})_(\d{4})_")


def _extrair_numero_njud(nome_pasta: str) -> Optional[str]:
    """Extrai o número do NJUD do nome da pasta (ex.: 'NJUD_1918' ou 'NJUD 1918' -> '1918')."""
    m = _RE_NJUD_PASTA.search(nome_pasta)
    if m:
        return m.group(1)
    return None


def _listar_pastas_njud(pasta_entrada: Path) -> list[Path]:
    """Encontra pastas de NJUD em <entrada>/<NJUD>/ ou <entrada>/<MÊS>/<NJUD>/.

    Formato aceito conforme Item 6b: detecção por regex "NJUD <num>" no
    nome da pasta, em qualquer nível de profundidade imediato (direto ou
    dentro de uma pasta de mês).
    """
    pastas: list[Path] = []
    if not pasta_entrada.exists():
        return pastas

    for item in sorted(pasta_entrada.iterdir()):
        if not item.is_dir():
            continue
        if _extrair_numero_njud(item.name):
            pastas.append(item)
        else:
            # pode ser uma pasta de mês contendo pastas de NJUD dentro
            for sub in sorted(item.iterdir()):
                if sub.is_dir() and _extrair_numero_njud(sub.name):
                    pastas.append(sub)

    return pastas


def _indice_boletim(caminho: Path) -> int:
    """Extrai o índice B<n> do nome do arquivo/pasta do boletim para ordenação.

    Não assume sequência sem lacunas (B1, B2, B6, B7 é válido) — só ordena
    numericamente.
    """
    m = _RE_INDICE_B.search(caminho.name)
    if m:
        return int(m.group(1))
    return 0


def _localizar_pares_cabeca_corpo(pasta_njud: Path) -> list[tuple[Path, Path]]:
    """Localiza os pares (CABECA, CORPO) dentro da pasta de um NJUD.

    Procura em <pasta_njud>/**/*_CABECA.mp3 e casa cada uma com o
    *_CORPO.mp3 correspondente (mesmo prefixo, trocando o sufixo).
    """
    pares: list[tuple[Path, Path]] = []
    cabecas = sorted(pasta_njud.rglob("*_CABECA.mp3"), key=_indice_boletim)

    for cabeca in cabecas:
        corpo = cabeca.with_name(cabeca.name.replace("_CABECA.mp3", "_CORPO.mp3"))
        if not corpo.exists():
            raise FileNotFoundError(
                f"CORPO ausente para {cabeca.name} (esperado: {corpo.name})"
            )
        pares.append((cabeca, corpo))

    return pares


def _extrair_data_boletim(caminhos: list[Path]) -> Optional[str]:
    """Extrai DD-MM-AAAA do nome de qualquer um dos arquivos de boletim.

    Regra do Item 2: a data do jornal SEMPRE vem do nome dos boletins de
    origem (padrão BOLETIM_RADIO_TJRN_DD_MM_AAAA_Bx...), nunca de
    contagem de dias úteis a partir de uma âncora fixa.
    """
    for caminho in caminhos:
        m = _RE_DATA_BOLETIM.search(caminho.name)
        if m:
            dd, mm, aaaa = m.groups()
            return f"{dd}-{mm}-{aaaa}"
    return None


# ===========================================================================
# MONTAGEM
# ===========================================================================


def _carregar_vinheta(nome_arquivo: str, etapa: str, logger) -> Optional[object]:
    from pydub import AudioSegment

    caminho = DIR_ASSETS_VINHETAS_NJUD / nome_arquivo
    if not caminho.exists():
        logger.error(f"[{etapa}] Vinheta NJUD não encontrada: {caminho}")
        return None
    try:
        return AudioSegment.from_file(str(caminho))
    except Exception as e:
        logger.error(f"[{etapa}] Erro ao carregar vinheta {caminho}: {e}")
        return None


def montar_jornal(pasta_njud: Path, pasta_saida: Path, logger=None) -> Optional[Path]:
    """Monta UM jornal NJUD a partir da pasta de cortes de um NJUD.

    Args:
        pasta_njud: pasta contendo as subpastas <boletim>_saida/ com os
            arquivos *_CABECA.mp3/*_CORPO.mp3 (gerados pelo divisor_boletins).
        pasta_saida: pasta onde salvar o jornal montado (NJUD_*.mp3).
        logger: logger opcional (LogPipeline).

    Returns:
        Path do jornal montado, ou None em caso de falha (peça faltando,
        vinheta ausente, etc. — NUNCA monta jornal incompleto, Item 6/6b).
    """
    from pydub import AudioSegment
    from pydub.effects import normalize

    if logger is None:
        logger = LogPipeline()

    etapa = "montagem_jornal"
    numero_njud = _extrair_numero_njud(pasta_njud.name) or pasta_njud.name
    logger.info(f"[{etapa}] Iniciando montagem do NJUD {numero_njud} ({pasta_njud})")

    try:
        pares = _localizar_pares_cabeca_corpo(pasta_njud)
    except FileNotFoundError as e:
        logger.error(f"[{etapa}] NJUD {numero_njud}: {e} — jornal NÃO será montado (peça pendente)")
        return None

    if len(pares) != N_BOLETINS_POR_JORNAL:
        logger.error(
            f"[{etapa}] NJUD {numero_njud}: esperado {N_BOLETINS_POR_JORNAL} boletins, "
            f"encontrado {len(pares)} — jornal NÃO será montado (peça pendente, Item 6/6b)"
        )
        return None

    vht_abertura = _carregar_vinheta(VHT_ABERTURA_NJUD_NOME, etapa, logger)
    vht_passagem = _carregar_vinheta(VHT_PASSAGEM_NJUD_NOME, etapa, logger)
    vht_encerramento = _carregar_vinheta(VHT_ENCERRAMENTO_NJUD_NOME, etapa, logger)
    if vht_abertura is None or vht_passagem is None or vht_encerramento is None:
        logger.error(f"[{etapa}] NJUD {numero_njud}: vinheta(s) de NJUD ausente(s) — abortando")
        return None

    # Monta na ordem imutável do Item 9:
    # abertura -> cabeça1..4 -> passagem -> corpo1..4 -> encerramento
    jornal = AudioSegment.empty()
    jornal += vht_abertura

    for cabeca_path, _corpo_path in pares:
        try:
            cabeca_audio = normalize(AudioSegment.from_file(str(cabeca_path)))
        except Exception as e:
            logger.error(f"[{etapa}] Erro ao carregar {cabeca_path}: {e}")
            return None
        jornal += cabeca_audio

    jornal += vht_passagem

    for _cabeca_path, corpo_path in pares:
        try:
            corpo_audio = normalize(AudioSegment.from_file(str(corpo_path)))
        except Exception as e:
            logger.error(f"[{etapa}] Erro ao carregar {corpo_path}: {e}")
            return None
        jornal += corpo_audio

    jornal += vht_encerramento

    # Nome final: NJUD_<numero>_<DD-MM-AAAA>.mp3 (Item 2 + Item 12)
    todos_arquivos = [p for par in pares for p in par]
    data_str = _extrair_data_boletim(todos_arquivos)
    if data_str is None:
        logger.warning(
            f"[{etapa}] NJUD {numero_njud}: data não encontrada no nome dos boletins "
            f"(esperado padrão _DD_MM_AAAA_) — gerando nome sem data"
        )
        nome_arquivo = f"NJUD_{numero_njud}.mp3"
    else:
        nome_arquivo = f"NJUD_{numero_njud}_{data_str}.mp3"

    pasta_saida.mkdir(parents=True, exist_ok=True)
    caminho_saida = pasta_saida / nome_arquivo

    try:
        jornal.export(str(caminho_saida), format="mp3", bitrate="192k")
    except Exception as e:
        logger.error(f"[{etapa}] Erro ao salvar jornal {caminho_saida}: {e}")
        return None

    logger.info(
        f"[{etapa}] NJUD {numero_njud} montado com sucesso: {caminho_saida} "
        f"({len(jornal) / 1000:.1f}s, {len(pares)} boletins)"
    )
    return caminho_saida


def montar_todos(
    pasta_entrada: Path,
    pasta_saida: Path,
    njud_lista: Optional[list[str]] = None,
    logger=None,
) -> tuple[list[Path], list[str]]:
    """Monta todos os jornais NJUD encontrados em pasta_entrada.

    Args:
        pasta_entrada: JORNAIS_DIVIDIDOS (ou pasta de mês contendo NJUDs).
        pasta_saida: JORNAIS_FINAL.
        njud_lista: lista opcional de números de NJUD para filtrar (senão, todos).
        logger: logger opcional.

    Returns:
        (montados, falhas) — Paths dos jornais montados e números de NJUD
        que falharam (peça pendente, vinheta ausente etc.).
    """
    if logger is None:
        logger = LogPipeline()

    etapa = "montagem_jornais_todos"
    pastas_njud = _listar_pastas_njud(pasta_entrada)

    if not pastas_njud:
        logger.warning(f"[{etapa}] Nenhuma pasta de NJUD encontrada em {pasta_entrada}")
        return [], []

    if njud_lista:
        filtro = set(njud_lista)
        pastas_njud = [p for p in pastas_njud if _extrair_numero_njud(p.name) in filtro]

    logger.info(f"[{etapa}] {len(pastas_njud)} NJUD(s) candidato(s) em {pasta_entrada}")

    montados: list[Path] = []
    falhas: list[str] = []

    for pasta_njud in pastas_njud:
        numero = _extrair_numero_njud(pasta_njud.name) or pasta_njud.name
        resultado = montar_jornal(pasta_njud, pasta_saida, logger=logger)
        if resultado is not None:
            montados.append(resultado)
        else:
            falhas.append(numero)

    logger.info(
        f"[{etapa}] Montagem concluída: {len(montados)} jornal(is) montado(s), "
        f"{len(falhas)} falha(s)/pendência(s)"
    )
    if falhas:
        logger.warning(f"[{etapa}] NJUDs não montados (peça pendente ou erro): {', '.join(falhas)}")

    return montados, falhas


# ===========================================================================
# CLI
# ===========================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monta jornais NJUD a partir dos cortes CABEÇA/CORPO do divisor_boletins."
    )
    parser.add_argument(
        "pasta_entrada",
        nargs="?",
        type=Path,
        default=DIR_JORNAIS_DIVIDIDOS,
        help=f"Pasta com os NJUDs divididos (default: {DIR_JORNAIS_DIVIDIDOS})",
    )
    parser.add_argument(
        "pasta_saida",
        nargs="?",
        type=Path,
        default=DIR_JORNAIS_FINAL,
        help=f"Pasta de saída dos jornais montados (default: {DIR_JORNAIS_FINAL})",
    )
    parser.add_argument(
        "--njud",
        action="append",
        default=None,
        help="Número de NJUD a montar (pode repetir); default: todos os encontrados.",
    )
    args = parser.parse_args()

    logger = LogPipeline(args.pasta_saida / "logs" if hasattr(args.pasta_saida, "__truediv__") else None)

    montados, falhas = montar_todos(args.pasta_entrada, args.pasta_saida, njud_lista=args.njud, logger=logger)

    print(f"\nMontados: {len(montados)}")
    for m in montados:
        print(f"  {m}")
    if falhas:
        print(f"\nPendentes/falharam: {len(falhas)}")
        for f in falhas:
            print(f"  NJUD {f}")

    sys.exit(1 if falhas and not montados else 0)


if __name__ == "__main__":
    main()
