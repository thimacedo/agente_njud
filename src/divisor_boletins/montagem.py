"""
Montagem do jornal completo a partir de cortes CABEÇA/CORPO.

Receita:
  1. VHT_ABERTURA
  2. TRILHA ESCALADA (20% volume BG) + CABEÇAs
  3. Fim da trilha (fade out)
  4. PASSAGEM + CORPO 1 + PASSAGEM + CORPO 2 + ...
  5. VHT_ENCERRAMENTO
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

from .log import LogPipeline


# Estrutura padronizada de diretórios do workspace
PASTA_ENTRADA = Path("boletins_brutos")
PASTA_DIVIDIDOS = Path("boletins_divididos")
PASTA_MONTADOS = Path("jornais_montados")

VINHETAS_DIR = Path("F:/Projetos/DIVISOR/assets/vinhetas")
TRILHA_ESCALADA_NOME = "TRILHA_ESCALADA_NJUD.mp3"
PASSAGEM_NOME = "VHT_PASSAGEM_BOLETIM.mp3"
VHT_ABERTURA_NOME = "VHT_ABERTURA_NJUD.mp3"
VHT_ENCERRAMENTO_NOME = "VHT_ENCERRAMENTO_NJUD.mp3"

VOLUME_TRILHA_ESCALADA = 0.2
PAUSA_ENTRE_CABECAS_MS = 500
FADE_OUT_TRILHA_MS = 2000


# ===========================================================================
# UTILITÁRIOS
# ===========================================================================

def extrair_numero_boletim(nome_arquivo: str) -> int:
    """
    Extrai o número do boletim do nome do arquivo.
    Ex: 'BOLETIM_RADIO_TJRN_26_11_2026_B2_...' -> 2
    """
    match = re.search(r"_B(\d+)_", nome_arquivo)
    if match:
        return int(match.group(1))
    return 0


# ===========================================================================
# INTERCALAÇÃO POR BLOCO DE NUMERAÇÃO
# ===========================================================================

def intercalar_pares_por_bloco(
    cabecas: list[Path],
    corpos: list[Path],
    logger: LogPipeline,
    bloco: int = 5,
) -> list[tuple[Path, Path]]:
    """
    Intercala pares (cabeça, corpo) por blocos de numeração de boletim.
    Mantém o par cabeça↔corpo sempre junto.
    """
    if not cabecas or not corpos:
        return []

    mapa_corpo = {}
    for corpo in corpos:
        nome_base = corpo.name.replace("_CORPO.mp3", "")
        mapa_corpo[nome_base] = corpo

    pares = []
    for cabeca in sorted(cabecas, key=lambda p: extrair_numero_boletim(p.name)):
        nome_base = cabeca.name.replace("_CABECA.mp3", "")
        corpo = mapa_corpo.get(nome_base)
        if corpo is not None:
            pares.append((cabeca, corpo))

    if len(pares) <= 1:
        return pares

    grupos: dict[int, list[tuple[Path, Path]]] = {}
    for cabeca, corpo in pares:
        num = extrair_numero_boletim(cabeca.name)
        grupo = ((num - 1) // bloco) + 1
        grupos.setdefault(grupo, []).append((cabeca, corpo))

    if len(grupos) <= 1:
        logger.info(
            "intercalacao",
            "Apenas um grupo de locutor; mantendo ordem original",
        )
        return pares

    for grupo in grupos:
        grupos[grupo].sort(key=lambda p: extrair_numero_boletim(p[0].name))

    resultado: list[tuple[Path, Path]] = []
    indices = {g: 0 for g in grupos}
    grupo_ids = sorted(grupos.keys())

    while any(indices[g] < len(grupos[g]) for g in grupo_ids):
        for g in grupo_ids:
            if indices[g] < len(grupos[g]):
                resultado.append(grupos[g][indices[g]])
                indices[g] += 1

    logger.info(
        "intercalacao",
        f"Intercalação por blocos de {bloco}: "
        f"{len(resultado)} pares de {len(grupos)} grupos",
        grupos={
            g: [c[0].name for c in grupos[g]]
            for g in grupos
        },
    )
    return resultado


# ===========================================================================
# MONTAGEM DO JORNAL
# ===========================================================================

def montar_jornal(
    pasta_cortes: Path,
    pasta_saida: Path,
    logger: LogPipeline,
    nome_jornal: str = "jornal",
    intercalar: bool = True,
) -> Optional[Path]:
    """Monta UM jornal a partir dos cortes _CABECA/_CORPO."""
    etapa = "montagem"
    logger.info(etapa, f"=== Iniciando montagem: {nome_jornal} ===")

    # 1. Carrega vinhetas
    vht_abertura_path = VINHETAS_DIR / VHT_ABERTURA_NOME
    vht_encerramento_path = VINHETAS_DIR / VHT_ENCERRAMENTO_NOME
    trilha_escalada_path = VINHETAS_DIR / TRILHA_ESCALADA_NOME
    passagem_path = VINHETAS_DIR / PASSAGEM_NOME

    for v, nome in [
        (vht_abertura_path, "VHT_ABERTURA"),
        (vht_encerramento_path, "VHT_ENCERRAMENTO"),
        (trilha_escalada_path, "TRILHA_ESCALADA"),
        (passagem_path, "PASSAGEM"),
    ]:
        if not v.exists():
            logger.erro(etapa, f"Vinheta não encontrada: {v}")
            return None

    vht_abertura = AudioSegment.from_file(str(vht_abertura_path))
    vht_encerramento = AudioSegment.from_file(str(vht_encerramento_path))
    trilha_escalada = AudioSegment.from_file(str(trilha_escalada_path))
    trilha_escalada = trilha_escalada.apply_gain(
        20 * (VOLUME_TRILHA_ESCALADA - 1)
    )
    passagem = AudioSegment.from_file(str(passagem_path))

    # 2. Descobre cortes, descartando arquivos inválidos (<5KB = vazio/corrompido)
    MIN_BYTES = 5000
    cabecas = [p for p in pasta_cortes.rglob("*_CABECA.mp3") if p.stat().st_size >= MIN_BYTES]
    corpos = [p for p in pasta_cortes.rglob("*_CORPO.mp3") if p.stat().st_size >= MIN_BYTES]
    for p in pasta_cortes.rglob("*_CORPO.mp3"):
        if p.stat().st_size < MIN_BYTES:
            logger.aviso(etapa, f"CORPO inválido (vazio), ignorado: {p.name}")

    if not cabecas:
        logger.erro(etapa, "Nenhuma CABEÇA encontrada")
        return None

    cabecas.sort(key=lambda p: extrair_numero_boletim(p.name))
    corpos.sort(key=lambda p: extrair_numero_boletim(p.name))

    # 3. Intercala pares
    pares = []
    if intercalar and len(cabecas) > 1 and len(corpos) > 1:
        pares = intercalar_pares_por_bloco(cabecas, corpos, logger, bloco=5)
    else:
        mapa_corpo = {c.name.replace("_CORPO.mp3", ""): c for c in corpos}
        for cabeca in sorted(
            cabecas, key=lambda p: extrair_numero_boletim(p.name)
        ):
            nome_base = cabeca.name.replace("_CABECA.mp3", "")
            corpo = mapa_corpo.get(nome_base)
            if corpo is not None:
                pares.append((cabeca, corpo))

    logger.info(
        etapa,
        "Pares: "
        + ", ".join(f"{c1.name} -> {c2.name}" for c1, c2 in pares),
    )

    # 4. Monta seguindo a receita
    jornal = AudioSegment.empty()

    # VHT ABERTURA
    jornal += vht_abertura

    # TRILHA ESCALADA como BG durante as CABEÇAs
    bloco_cabecas = AudioSegment.empty()
    for i, (cabeca_path, _) in enumerate(pares):
        cabeca = AudioSegment.from_file(str(cabeca_path))
        bloco_cabecas += cabeca
        if i < len(pares) - 1:
            bloco_cabecas += AudioSegment.silent(duration=PAUSA_ENTRE_CABECAS_MS)

    trilha_bg = trilha_escalada
    if len(trilha_bg) < len(bloco_cabecas):
        repete = (len(bloco_cabecas) // len(trilha_bg)) + 1
        trilha_bg = trilha_bg * repete
    trilha_bg = trilha_bg[: len(bloco_cabecas)]
    trilha_bg = trilha_bg.fade_in(500).fade_out(FADE_OUT_TRILHA_MS)

    jornal += bloco_cabecas.overlay(trilha_bg)

    # PASSAGEM + CORPOS
    for _, corpo_path in pares:
        jornal += passagem
        corpo = AudioSegment.from_file(str(corpo_path))
        jornal += corpo

    # VHT ENCERRAMENTO
    jornal += vht_encerramento

    # 5. Salva com padrão de nomenclatura: NJUD_1826_02-03-2026.mp3
    #
    # NÃO REVERTER PARA CONTAGEM DE DIAS ÚTEIS: a data vem da leitura
    # direta do nome dos boletins que compõem este jornal (padrão
    # BOLETIM_RADIO_TJRN_DD_MM_AAAA_...), não de uma contagem de dias
    # úteis a partir de uma âncora fixa (NJUD 1792 = 08/01/2026+ tabela
    # de feriados). A contagem por dias úteis é uma segunda fonte de
    # verdade independente da data real — qualquer desvio da premissa
    # (feriado não listado, NJUD pulado, ajuste manual já feito antes)
    # faz toda data derivada dali em diante ficar sistematicamente
    # errada, sem nenhum aviso. Ler a data direto do nome do arquivo não
    # pode divergir da fonte real, porque é a própria fonte. Corrigido
    # em 2026-08-21; já reapareceu uma vez por restauração de versão antiga.
    pasta_saida.mkdir(parents=True, exist_ok=True)
    num_match = re.search(r"(\d+)", nome_jornal)
    data_str = ""
    _padrao_data_boletim = re.compile(r"_(\d{2})_(\d{2})_(\d{4})_")

    for cabeca_path, _ in pares:
        m = _padrao_data_boletim.search(cabeca_path.name)
        if m:
            dia, mes, ano = m.groups()
            data_str = f"{dia}-{mes}-{ano}"
            break

    if not data_str:
        logger.aviso(
            etapa,
            f"Não foi possível extrair a data do nome dos boletins de "
            f"'{nome_jornal}' (esperado padrão _DD_MM_AAAA_); nome final "
            f"sairá sem data.",
        )

    if num_match:
        num_njud = num_match.group(1)
        nome_arquivo_final = (
            f"NJUD_{num_njud}_{data_str}.mp3" if data_str else f"NJUD_{num_njud}.mp3"
        )
    else:
        nome_arquivo_final = f"{nome_jornal}.mp3"

    caminho_saida = pasta_saida / nome_arquivo_final
    jornal.export(str(caminho_saida), format="mp3")

    duracao_total = len(jornal) / 1000
    logger.info(
        etapa,
        f"Jornal montado: {caminho_saida}",
        duracao_total=round(duracao_total, 2),
        boletins=len(cabecas),
        intercalado=intercalar and len(pares) > 1,
    )

    return caminho_saida


# ===========================================================================
# MONTAGEM RECURSIVA POR JORNAL
# ===========================================================================

def montar_todos_jornais(
    pasta_entrada: Path,
    pasta_saida: Path,
    logger: LogPipeline,
    intercalar: bool = True,
) -> list[Path]:
    """Processa cada subpasta de NJUD como UM jornal e monta o áudio final."""
    logger.info("pipeline", "=== Iniciando montagem de todos os jornais ===")

    if not pasta_entrada.is_dir():
        logger.erro("pipeline", f"Pasta de entrada não existe: {pasta_entrada}")
        return []

    # 1. Nível esperado: <pasta_entrada>/<MES>/<NJUD XXXX>
    #    (alinhamento 2026-08-24, DECISOES.md item 6): o dispatcher_paralelo
    #    grava os cortes DIRETO em <pasta_entrada>/<NJUD XXXX>/ — sem nível
    #    de mês. Ambas as formas são aceitas: subpasta cujo nome casa com
    #    "NJUD <num>" é tratada como jornal direto.
    import re

    def _eh_njud(nome: str) -> bool:
        return bool(re.match(r"NJUD\s*\d+", nome, re.IGNORECASE))

    meses = sorted(
        p for p in pasta_entrada.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    )
    if not meses:
        logger.aviso(
            "pipeline",
            f"Nenhuma subpasta de mês encontrada em {pasta_entrada}",
        )
        return []

    resultados: list[Path] = []
    erros = 0
    for mes_pasta in meses:
        if not mes_pasta.is_dir():
            continue

        # Formato plano do dispatcher: a subpasta JÁ É o NJUD.
        if _eh_njud(mes_pasta.name):
            caminho = montar_jornal(
                mes_pasta,
                pasta_saida,
                logger,
                nome_jornal=mes_pasta.name,
                intercalar=intercalar,
            )
            if caminho:
                resultados.append(caminho)
            else:
                logger.erro("pipeline", f"Falha ao montar jornal: {mes_pasta.name}")
                erros += 1
            continue

        njuds = sorted(
            p for p in mes_pasta.iterdir()
            if p.is_dir() and not p.name.startswith("_")
        )
        if not njuds:
            logger.aviso("pipeline", f"Nenhum NJUD encontrado em {mes_pasta}")
            continue

        for njud_pasta in njuds:
            nome_jornal = njud_pasta.name
            caminho = montar_jornal(
                njud_pasta,
                pasta_saida,
                logger,
                nome_jornal=nome_jornal,
                intercalar=intercalar,
            )
            if caminho:
                resultados.append(caminho)
            else:
                logger.erro("pipeline", f"Falha ao montar jornal: {nome_jornal}")
                erros += 1

    logger.info(
        "pipeline",
        f"=== Montagem concluída: {len(resultados)} jornais gerados ===",
        total=len(resultados),
        erros=erros,
    )
    return resultados
