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
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

from .log import LogPipeline


def semana_dia_para_codigo(data_str: str) -> str:
    """
    Converte uma data no formato DD-MM-AAAA para código SSDD.
    SS = semana ISO com 2 dígitos
    DD = dia da semana ISO com 2 dígitos (1=segunda ... 7=domingo)
    """
    try:
        dia, mes, ano = map(int, data_str.split('-'))
        dt = datetime(ano, mes, dia)
        semana = dt.isocalendar().week
        dia_semana = dt.isocalendar().weekday
        return f"{semana:02d}{dia_semana:02d}"
    except Exception:
        return "0000"


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
    bloco: int = 4,
) -> list[tuple[Path, Path]]:
    """
    Intercala pares (cabeça, corpo) para ter 2 vozes diferentes em cada jornal.
    Mantém o par cabeça↔corpo sempre junto.
    
    Cenário típico: Locutor A grava B1-B5, Locutor B grava B6-B10
    Para NJUD 1 (4 boletins): [B1(A), B6(B), B2(A), B7(B)]
    Isso garante 2 vozes alternadas mesmo com poucos boletins por locutor.
    
    O agrupamento é feito pelo número absoluto do boletim, não por NJUD.
    Assim, B1 e B6 estarão em grupos diferentes mesmo que ambos pertençam
    ao mesmo NJUD (quando NJUD = ((num-1)//4)+1).
    
    REGRA FIXA: 
    - Cada jornal tem EXATAMENTE 4 boletins (B1-B4 → NJUD 1, B5-B8 → NJUD 2)
    - Intercalação automática entre 2 grupos de locutores (B1-B5 vs B6-B10)
    - Se houver apenas 1 grupo, mantém ordem numérica estrita
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

    # Agrupa por METADE: B1-B5 → grupo 1, B6-B10 → grupo 2, etc.
    # Isso cria 2 grupos de locutores baseados no intervalo de gravação.
    # Cada grupo tem ~5 boletins, garantindo que um jornal de 4 boletins
    # pegue 2 de cada grupo (intercalando as vozes).
    metade = 5  # Tamanho típico de gravação por locutor
    grupos: dict[int, list[tuple[Path, Path]]] = {}
    for cabeca, corpo in pares:
        num = extrair_numero_boletim(cabeca.name)
        grupo = ((num - 1) // metade) + 1
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
        f"Intercalação por blocos de {metade}: "
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

    # 3. Intercalação ATIVADA para ter 2 vozes diferentes por jornal
    # Cenário típico: Locutor A grava B1-B5, Locutor B grava B6-B10
    # Resultado desejado no NJUD 1: [B1(A), B6(B), B2(A), B7(B)]
    # Isso garante diversidade de vozes mesmo com poucos boletins por locutor.
    if intercalar and len(cabecas) >= 2:
        pares = intercalar_pares_por_bloco(cabecas, corpos, logger, bloco=4)
    else:
        # Sem intercalação: mantém ordem numérica estrita
        pares = []
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

    # 5. Salva com padrão: NJUD_<SSDD>_<DD-MM-AAAA>.mp3
    pasta_saida.mkdir(parents=True, exist_ok=True)
    data_str = ""
    _padrao_data_boletim = re.compile(r"_(\d{2})_(\d{2})_(\d{4})_")

    for cabeca_path, _ in pares:
        m = _padrao_data_boletim.search(cabeca_path.name)
        if m:
            dia, mes, ano = m.groups()
            data_str = f"{dia}-{mes}-{ano}"
            break

    codigo_semana_dia = semana_dia_para_codigo(data_str) if data_str else "0000"

    # REGRA DE NOMENCLATURA (2026-08-24): priorizar o número real do NJUD
    # contido no nome da subpasta (ex.: 'NJUD 1923' -> 1923). Nunca derivar
    # NJUD do código semana-dia nem do ano — evita colisões de nome quando
    # dois jornais compartilham a mesma data e a captura de dígitos errada.
    m_njud = re.search(r"NJUD\s*_?\s*(\d{4})", nome_jornal, re.IGNORECASE)
    if m_njud:
        codigo_semana_dia = m_njud.group(1)

    if not data_str:
        logger.aviso(
            etapa,
            f"Não foi possível extrair a data do nome dos boletins de "
            f"'{nome_jornal}' (esperado padrão _DD_MM_AAAA_); nome final "
            f"sairá sem data.",
        )
        nome_arquivo_final = f"NJUD_{codigo_semana_dia}.mp3"
    else:
        nome_arquivo_final = f"NJUD_{codigo_semana_dia}_{data_str}.mp3"

    caminho_saida = pasta_saida / nome_arquivo_final
    jornal.export(str(caminho_saida), format="mp3")

    duracao_total = len(jornal) / 1000
    logger.info(
        etapa,
        f"Jornal montado: {caminho_saida}",
        duracao_total=round(duracao_total, 2),
        boletins=len(cabecas),
        intercalado=intercalar and len(pares) > 1,
        codigo_semana_dia=codigo_semana_dia,
        data=data_str,
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

    resultados: list[Path] = []
    erros = 0
    import re

    def _eh_njud(nome: str) -> bool:
        return bool(re.match(r"NJUD\s*\d+", nome, re.IGNORECASE))

    meses = sorted(
        p for p in pasta_entrada.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    )

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

    # Fallback: se não houver subpastas, agrupa arquivos soltos POR JORNAL.
    # Cada jornal deve ter exatamente 4 boletins (4 cabeças + 4 corpos).
    # Os boletins são numerados sequencialmente (B1, B2, B3, ...) e cada
    # grupo de 4 forma um jornal independente, mesmo que compartilhem data.
    if not resultados:
        import shutil
        njud_map = {}
        for mp3 in pasta_entrada.glob("*_CABECA.mp3"):
            # Extrai número do boletim e data do nome:
            # BOLETIM_RADIO_TJRN_DD_MM_AAAA_B{N}_...
            m_njud = re.search(r"_B(\d+)_", mp3.name)
            m_data = re.search(r"BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_", mp3.name)
            if m_njud and m_data:
                num_boletim = int(m_njud.group(1))
                dia, mes, ano = m_data.groups()
                data_str = f"{dia}-{mes}-{ano}"
                # Cada 4 boletins formam 1 jornal: B1-B4 → NJUD 1, B5-B8 → NJUD 2, etc.
                njud_grupo = ((num_boletim - 1) // 4) + 1
                njud_key = f"NJUD_{njud_grupo}_{data_str}"
                njud_map.setdefault(njud_key, {"data": data_str, "arquivos": []}).setdefault("arquivos", []).append(mp3)

        if njud_map:
            tmp_root = pasta_entrada / "_tmp_njud"
            tmp_root.mkdir(parents=True, exist_ok=True)
            for njud_key, info in sorted(njud_map.items()):
                pasta_njud = tmp_root / njud_key
                pasta_njud.mkdir(parents=True, exist_ok=True)
                for mp3 in info["arquivos"]:
                    shutil.copy2(mp3, pasta_njud / mp3.name)
                    corpo = mp3.parent / mp3.name.replace("_CABECA.mp3", "_CORPO.mp3")
                    if corpo.exists():
                        shutil.copy2(corpo, pasta_njud / corpo.name)
                # Monta o jornal COM intercalação para ter 2 vozes diferentes
                caminho = montar_jornal(
                    pasta_njud,
                    pasta_saida,
                    logger,
                    nome_jornal=njud_key,
                    intercalar=True,  # Ativa intercalação de locutores
                )
                if caminho:
                    resultados.append(caminho)
                else:
                    logger.erro("pipeline", f"Falha ao montar jornal: {njud_key}")
                    erros += 1
            try:
                shutil.rmtree(tmp_root, ignore_errors=True)
            except Exception:
                pass
            logger.info(
                "pipeline",
                f"=== Montagem concluída: {len(resultados)} jornais gerados ===",
                total=len(resultados),
                erros=erros,
            )
            return resultados
        logger.aviso(
            "pipeline",
            f"Nenhum boletim encontrado em {pasta_entrada}",
        )
        return []

    logger.info(
        "pipeline",
        f"=== Montagem concluída: {len(resultados)} jornais gerados ===",
        total=len(resultados),
        erros=erros,
    )
    return resultados
