#!/usr/bin/env python3
"""Testes reais das regras de negócio (fase P6 do saneamento 2026-08-31).

Cobre funções puras críticas:
  - sync/drive.py: PATTERN_NOME (nomenclatura NJUD + sufixo _INCOMPLETO)
  - divisor_boletins/montagem.py: semana_dia_para_codigo,
    extrair_numero_boletim, intercalar_pares_para_jornal
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from divisor_boletins.log import LogPipeline
from divisor_boletins.montagem import (
    extrair_numero_boletim,
    intercalar_pares_para_jornal,
    semana_dia_para_codigo,
)
from sync.drive import PATTERN_NOME


# ---------------------------------------------------------------------------
# Nomenclatura NJUD (sync/drive.py)
# ---------------------------------------------------------------------------

def test_pattern_njud_valido():
    assert PATTERN_NOME.match("NJUD_0601_02-02-2026.mp3")
    assert PATTERN_NOME.match("NJUD_1802_28-04-2026.mp3")


def test_pattern_njud_incompleto_aceito():
    # feat bc008e6: jornais com 2+ boletins recebem sufixo _INCOMPLETO
    assert PATTERN_NOME.match("NJUD_0601_02-02-2026_INCOMPLETO.mp3")


def test_pattern_njud_invalidos():
    invalidos = [
        "NJUD_601_02-02-2026.mp3",          # código SSDD com 3 dígitos
        "NJUD_0601_02-02-26.mp3",           # ano com 2 dígitos
        "NJUD_0601_02-02-2026.wav",         # extensão errada
        "NJUD_0601_02-02-2026_INCOMPLETO.wav",
        "njud_0601_02-02-2026.mp3",         # caixa baixa
        "NJUD_0601_02-02-2026.mp3.bak",    # sufixo estranho
        "NJUD_0601_02-02-2026_INCOMPLETOX.mp3",
        "",
    ]
    for nome in invalidos:
        assert not PATTERN_NOME.match(nome), f"deveria rejeitar: {nome!r}"


# ---------------------------------------------------------------------------
# Código SSDD (montagem.py)
# ---------------------------------------------------------------------------

def test_semana_dia_para_codigo_datas_reais():
    # Fixtures vindas de arquivos reais de produção
    assert semana_dia_para_codigo("02-02-2026") == "0601"  # NJUD_0601
    assert semana_dia_para_codigo("03-02-2026") == "0602"  # NJUD_0602
    assert semana_dia_para_codigo("28-04-2026") == "1802"  # NJUD_1802
    assert semana_dia_para_codigo("29-04-2026") == "1803"  # NJUD_1803


def test_semana_dia_para_codigo_invalido():
    assert semana_dia_para_codigo("abc") == "0000"
    assert semana_dia_para_codigo("") == "0000"


# ---------------------------------------------------------------------------
# Extração do número do boletim
# ---------------------------------------------------------------------------

def test_extrair_numero_boletim():
    nome = "BOLETIM_RADIO_TJRN_02_02_2026_B2_TJRN_ACAO_CABECA.mp3"
    assert extrair_numero_boletim(nome) == 2
    assert extrair_numero_boletim("BOLETIM_RADIO_TJRN_02_02_2026_B10_X_CORPO.mp3") == 10
    assert extrair_numero_boletim("arquivo_sem_marcacao.mp3") == 0


# ---------------------------------------------------------------------------
# Intercalação de pares (1 NJUD = 4 boletins)
# ---------------------------------------------------------------------------

def _par(n: int) -> tuple[Path, Path]:
    nome = f"BOLETIM_RADIO_TJRN_02_02_2026_B{n}_TJRN_NOTA_CABECA.mp3"
    corpo = nome.replace("_CABECA", "_CORPO")
    return (Path(nome), Path(corpo))


def test_intercalacao_lista_vazia(tmp_path):
    logger = LogPipeline(tmp_path / "logs")
    assert intercalar_pares_para_jornal([], 0, logger) == []


def test_intercalacao_ultimo_jornal_incompleto(tmp_path):
    logger = LogPipeline(tmp_path / "logs")
    pares = [_par(n) for n in (1, 2, 3)]
    resultado = intercalar_pares_para_jornal(pares, 0, logger)
    assert len(resultado) == 3


def test_intercalacao_pool_10_boletins(tmp_path):
    # Pool B1-B10: jornal 0 deve intercalar vozes [B1, B6, B2, B7]
    logger = LogPipeline(tmp_path / "logs")
    pares = [_par(n) for n in range(1, 11)]
    resultado = intercalar_pares_para_jornal(pares, 0, logger)
    numeros = [extrair_numero_boletim(p[0].name) for p in resultado]
    assert len(resultado) == 4
    assert numeros == [1, 6, 2, 7]


def test_intercalacao_sem_segundo_grupo_mantem_ordem(tmp_path):
    # Só B1-B4 no pool: não há locutor B, retorna ordem numérica
    logger = LogPipeline(tmp_path / "logs")
    pares = [_par(n) for n in (1, 2, 3, 4)]
    resultado = intercalar_pares_para_jornal(pares, 0, logger)
    numeros = [extrair_numero_boletim(p[0].name) for p in resultado]
    assert len(resultado) == 4
    assert numeros == [1, 2, 3, 4]


def test_intercalacao_jornal_2_range_correto(tmp_path):
    # Jornal 1 cobre B5-B8 e nunca retorna mais de 4 pares
    logger = LogPipeline(tmp_path / "logs")
    pares = [_par(n) for n in range(1, 11)]
    resultado = intercalar_pares_para_jornal(pares, 1, logger)
    assert 1 <= len(resultado) <= 4
    numeros = [extrair_numero_boletim(p[0].name) for p in resultado]
    assert min(numeros) >= 5
