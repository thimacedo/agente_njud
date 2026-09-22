#!/usr/bin/env python3
"""
Pipeline canônico de edição de boletins — processar_boletim_canonico.py
Uso: processar_boletim_canonico.py <arquivo_entrada> [--roteiros <pasta_roteiros>]
Saída: pasta <arquivo_entrada>_saida/ com boletins editados + auditoria.json
"""
import argparse, re, os, json, shutil, sys, tempfile
from pathlib import Path
from datetime import date
from pydub import AudioSegment

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))  # adiciona scripts_pipeline/ao path

# Usar faster-whisper (CTranslate2) — 1.3-3x mais rápido em CPU (validado spike 002)
try:
    from faster_whisper import WhisperModel
    USE_FASTER = True
except ImportError:
    import whisper
    USE_FASTER = False

from corrigir_alucinacoes import corrigir_transcricao
from shared.bgm_mixer import mix_bgm

# ── Configuração (todas as variáveis antes hardcoded) ─────────────────────────
# Overrides via variáveis de ambiente (opcional): DIVISOR_ASSETS, DIVISOR_TMP,
# DIVISOR_WHISPER_MODEL, DIVISOR_COBERTURA_MIN.
# Defaults derivados da localização deste script — funciona em qualquer checkout.

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VHT_DIR = Path(os.environ.get("DIVISOR_ASSETS", PROJECT_ROOT / "assets" / "vinhetas" / "boletim"))
TMP_DIR = Path(os.environ.get("DIVISOR_TMP", tempfile.gettempdir()))
BG_PATH = VHT_DIR / "BG - BOLETIM.mp3"

WHISPER_MODEL = os.environ.get("DIVISOR_WHISPER_MODEL", "base")
COBERTURA_MIN = float(os.environ.get("DIVISOR_COBERTURA_MIN", "0.6"))  # Item 18: 60% + auditoria humana

# Fallbacks de data quando o filename não traz mês/ano explícitos
MES_PADRAO = "09"   # arquivos "DD SET" → setembro
ANO_PADRAO = "2026" # projeto DIVISOR 2026

# Offset do início do boletim seguinte após a assinatura (segundos)
OFFSET_APOS_ASSINATURA = 0.3


def nomear_boletim(data_str, numero, roteiro_texto=None, data_completa_str=None):
    """Gera nome canônico BOLETIM_RADIO_TJRN_DD_MM_AAAA_B{N}__TITULO.mp3
    
    data_completa_str: string DD_MM_AAAA (ex: "04_09_2026"). 
    Se None, tenta extrair do data_str (ex: "04 SET" -> dia 04) e usa 2026 como padrão.
    """
    dd, mm, aaaa = "??", "??", "????"
    
    if data_completa_str:
        partes = data_completa_str.split("_")
        if len(partes) == 3:
            dd, mm, aaaa = partes[0], partes[1], partes[2]
        else:
            dd, mm, aaaa = "??", "??", "????"
    else:
        # Extrair dia do data_str (ex: "04 SET" -> dia 04)
        m_data = re.search(r'(\d{1,2})\s*[Ss][Ee][Tt]', data_str or "", re.I)
        if m_data:
            dd = m_data.group(1).zfill(2)
            mm = MES_PADRAO
            aaaa = ANO_PADRAO
        else:
            dd, mm, aaaa = "??", "??", "????"
    
    # Extrair título do roteiro se disponível
    titulo = ""
    if roteiro_texto:
        # Tenta formato "B{N}- TITULO"
        m_ret = re.search(rf'B{numero}\s*[-–]\s*(.+?)(?:\n|$)', roteiro_texto, re.I)
        if m_ret:
            titulo = m_ret.group(1).strip()
        else:
            # Tenta formato só "TITULO" (já extraído pelo carregar_roteiros)
            # Remove prefixos como "B{N}-" ou "B{N} " se existirem
            limpo = re.sub(r'^B\d+\s*[-–]?\s*', '', roteiro_texto).strip()
            if limpo:
                titulo = limpo
    
    titulo_limpo = re.sub(r'[^A-Za-z0-_=]', '_', titulo.upper())
    titulo_limpo = re.sub(r'_+', '_', titulo_limpo).strip('_')
    return f"BOLETIM_RADIO_TJRN_{dd}_{mm}_{aaaa}_B{numero}__{titulo_limpo}.mp3"


def extrair_info_nome(arquivo, transcricao_texto=None):
    """Extrai data e faixa de boletins do nome do arquivo e (opcionalmente) da transcrição.
    Retorna (data_str, B_ini, B_fim, data_completa_str)

    Data completa: DD_SET_AAAA (ex: 04_SET_2026)
    Se o filename tem "DD SET" e a transcrição tem "dia de setembro [de AAAA]", prefere a transcrição.
    Se filename tem apenas "DD SET" sem contexto, extrai do filename e assume ano atual ou 2026.
    """
    stem = Path(arquivo).stem

    # Extrair dia do filename: "18 SET", "04 SET", "17 SET", etc.
    m_data = re.search(r'(\d{1,2})\s*[Ss][Ee][Tt]', stem)
    dia_filename = m_data.group(1).zfill(2) if m_data else None

    # Extrair dia e ano da transcrição: "18 de setembro", "18 de setembro de 2026"
    dia_transcricao = None
    ano_transcricao = None
    if transcricao_texto:
        texto_clean = re.sub(r'\s+', ' ', transcricao_texto).lower()
        m_comp = re.search(r'(\d{1,2})\s*de\s+setembro\s*(?:de\s*(\d{4}))?', texto_clean)
        if m_comp:
            dia_transcricao = m_comp.group(1).zfill(2)
            ano_transcricao = m_comp.group(2) or None

    # Decidir qual usar: filename tem prioridade (mais confiável)
    # A transcrição pode conter datas de notícias (ex: "30 de setembro" no texto)
    if dia_filename:
        data_str = f"{dia_filename} SET"
        if ano_transcricao:
            data_completa_str = f"{dia_filename}_SET_{ano_transcricao}"
        else:
            data_completa_str = f"{dia_filename}_SET_{ANO_PADRAO}"
    elif dia_transcricao and ano_transcricao:
        data_str = f"{dia_transcricao} SET"
        data_completa_str = f"{dia_transcricao}_SET_{ano_transcricao}"
    elif dia_transcricao:
        data_str = f"{dia_filename} SET"
        # Se a transcrição só tem dia sem ano, usar ano do filename se tiver, ou 2026
        if dia_transcricao and not ano_transcricao:
            data_completa_str = f"{dia_transcricao}_SET_{ANO_PADRAO}"
        else:
            data_completa_str = None
    else:
        data_str = None
        data_completa_str = None

    # Se não consegui extrair data da transcrição e o filename tem um ano explícito
    # (ex: "18-09-2026" ou "18_09_2026" no nome), usar isso como fallback
    if data_completa_str is None:
        m_ano = re.search(r'(\d{2})[_-](\d{2})[_-](\d{4})', stem)
        if m_ano:
            data_completa_str = f"{m_ano.group(1)}_{m_ano.group(2).upper()}_{m_ano.group(3)}"
            if not data_str:
                data_str = f"{m_ano.group(1)} {m_ano.group(2).upper()}"

    # Fallback final: se ainda nada, usar o que tem
    if not data_completa_str:
        # Se só temos o dia do filename, assumir 2026
        if dia_filename:
            data_completa_str = f"{dia_filename}_SET_{ANO_PADRAO}"
        else:
            data_completa_str = "??_SET_????"

    # Faixa: "B6-B10", "B6 e B7", "B1 B5", "B1-B4", "B8-B10"...
    m_faixa = re.search(r'B(\d{1,2})\s*(?:[-–eE])\s*B(\d{1,2})', stem)
    if m_faixa:
        b_ini, b_fim = int(m_faixa.group(1)), int(m_faixa.group(2))
    else:
        m_faixa2 = re.search(r'(B\d{1,2})(B\d{1,2})', stem)
        if m_faixa2:
            b_ini, b_fim = int(m_faixa2.group(1)[1:]), int(m_faixa2.group(2)[1:])
        else:
            b_ini, b_fim = 1, 10  # fallback

    return data_str, b_ini, b_fim, data_completa_str


def carregar_roteiros(pasta_roteiros, data_str, b_ini, b_fim):
    """Se pasta_roteiros informado, busca roteiros .txt para cada boletim.
    Retorna dict {Bnumero: {"titulo": str, "cabeca": str, "off": str}}
    
    Formatos suportados:
    1. "B{N}- TITULO" por linha (formato compacto)
    2. "B{N}- TITULO\nCABEÇA: ...\nOFF: ..." (roteiro completo)
    """
    roteiros = {}
    if not pasta_roteiros or not pasta_roteiros.exists():
        return roteiros

    # Extrair dia da data_str (ex: "17 SET" -> "17")
    m_dia = re.search(r'(\d{1,2})', data_str)
    dia_str = m_dia.group(1) if m_dia else None

    # Priorizar arquivos com o dia no nome (ex: "roteiros_17_set.txt")
    arquivos = list(pasta_roteiros.glob("*.txt"))
    arquivos_ordenados = sorted(arquivos, key=lambda f: (
        0 if dia_str and dia_str in f.name else 1,
        len(f.name)  # arquivos menores primeiro (mais específicos)
    ))

    for f in arquivos_ordenados:
        texto = f.read_text(encoding="utf-8", errors="ignore")
        encontrou_algo = False
        
        # Formato 1: "B{N}- TITULO" por linha (formato compacto)
        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha:
                continue
            m = re.match(r'B(\d{1,2})\s*[-–—]\s*(.+)', linha)
            if m:
                n = int(m.group(1))
                if b_ini <= n <= b_fim:
                    titulo = m.group(2).strip()
                    if n not in roteiros or (dia_str and dia_str in f.name):
                        roteiros[n] = {"titulo": titulo, "cabeca": "", "off": ""}
                        encontrou_algo = True
        
        # Formato 2: "B{N}- TITULO\nCABEÇA: ...\nOFF: ..." (roteiro completo)
        blocos = re.split(r'={20,}|DOCUMENTO\s+\[\d+/\d+\]', texto)
        for bloco in blocos:
            m_b = re.search(r'B(\d{1,2})\s*[-–—]\s*(.+?)(?:\n|$)', bloco, re.I)
            m_cab = re.search(r'CABEÇA:\s*(.+?)(?:\n|$)', bloco, re.I)
            m_off = re.search(r'OFF:\s*(.+?)(?:\r?\n\r?\n|\Z)', bloco, re.I | re.DOTALL)
            if m_b:
                n = int(m_b.group(1))
                if b_ini <= n <= b_fim:
                    titulo = m_b.group(2).strip()
                    cabeca_texto = m_cab.group(1).strip() if m_cab else ""
                    off_texto = m_off.group(1).strip() if m_off else ""
                    # Sobrescrever se:
                    # - ainda não tem registro para este boletim, OU
                    # - o arquivo tem o dia no nome (prioridade), OU
                    # - o registro anterior não tinha OFF e este tem (mais completo)
                    deve_sobrescrever = (
                        n not in roteiros or
                        (dia_str and dia_str in f.name) or
                        (off_texto and not roteiros.get(n, {}).get("off"))
                    )
                    if deve_sobrescrever:
                        roteiros[n] = {"titulo": titulo, "cabeca": cabeca_texto, "off": off_texto}
                        encontrou_algo = True
        
        # Se encontrou todos os boletins neste arquivo E todos têm OFF, para
        # Caso contrário, continua procurando em outros arquivos (podem ter OFF)
        if encontrou_algo and len(roteiros) >= (b_fim - b_ini + 1):
            todos_tem_off = all(
                isinstance(v, dict) and v.get("off") for v in roteiros.values()
            )
            if todos_tem_off:
                break

    return roteiros


def triagem_audio(audio):
    """ETAPA 0: triagem inicial. Retorna dict com análise e ações."""
    duracao = len(audio) / 1000
    canais = audio.channels
    frame_rate = audio.frame_rate
    sample_width = audio.sample_width

    resultado = {
        "duracao_segundos": duracao,
        "canais": canais,
        "frame_rate": frame_rate,
        "sample_width": sample_width,
        "acoes": []
    }

    # Canal morto: um canal com amplitude próxima de 0
    if canais == 2:
        monoEsq = audio.split_to_mono()[0]
        monoDir = audio.split_to_mono()[1]

        maxEsq = monoEsq.max
        maxDir = monoDir.max

        if maxEsq < 500 and maxDir > 5000:
            resultado["canal_morto"] = "esquerdo"

        if maxEsq < 100 and maxDir > 1000:
            resultado["canal_morto"] = "esquerdo"
            resultado["acoes"].append("CORRIGIR: substituir canal esquerdo pelo direito (multiplicar esquerdo por fator de escala do direito)")
        elif maxDir < 100 and maxEsq > 1000:
            resultado["canal_morto"] = "direito"
            resultado["acoes"].append("CORRIGIR: substituir canal direito pelo esquerdo (multiplicar direito por fator de escala do esquerdo)")

        # Estéreo duplicado
        samplesEsq = list(monoEsq.get_array_of_samples())
        samplesDir = list(monoDir.get_array_of_samples())
        if samplesEsq == samplesDir:
            resultado["estereo_duplicado"] = True
            resultado["acoes"].append("CONVERTER: áudio estereo duplicado (L==R) → converter para mono")

    # Clipping
    if audio.max >= 32767 * 0.99:
        resultado["clipping_detectado"] = True
        resultado["acoes"].append("AVISO: possível clipping (pico próximo de 0dBFS)")

    return resultado


def carregar_modelo():
    """Carrega modelo Whisper (faster-whisper se disponível, senão openai-whisper)."""
    if USE_FASTER:
        print("  Usando faster-whisper (int8, CPU)...")
        return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    else:
        print("  Usando openai-whisper (fallback)...")
        return whisper.load_model(WHISPER_MODEL)


def transcrever(audio, tmp_path, modelo):
    """ETAPA 1: transcrição com Whisper. Compatível com faster-whisper e openai-whisper.
    Usa word_timestamps=True para permitir cortes finos (claquete vs cabeça no mesmo segmento)."""
    audio.export(tmp_path, format="wav")
    
    if USE_FASTER:
        segments_iter, info = modelo.transcribe(tmp_path, language="pt", word_timestamps=True)
        segmentos = []
        for seg in segments_iter:
            entry = {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            }
            # Preservar word timestamps para corte fino de claquetes
            if hasattr(seg, "words") and seg.words:
                entry["words"] = [
                    {"word": w.word, "start": w.start, "end": w.end}
                    for w in seg.words
                ]
            segmentos.append(entry)
        os.unlink(tmp_path)
        return segmentos
    else:
        result = modelo.transcribe(tmp_path, language="pt", fp16=False, word_timestamps=True)
        os.unlink(tmp_path)
        return result["segments"]


def detectar_estrutura(segmentos, b_ini, b_fim):
    """ETAPA 2: detectar estrutura dos boletins.
    Usa assinaturas do locutor como delimitadores principais.
    Cada assinatura finaliza um boletim; o próximo começa após a assinatura.
    Retorna dict:
      - marcadores: {n_boletim: tempo_segundo}
      - assinaturas: [(tempo, nome_reporter, texto_assinatura), ...]
      - falta: [numeros faltantes]"""
    marcadores = {}
    assinaturas = []

    # Regex assinatura: "do/no Tribunal de Justiça do Rio Grande do Norte"
    # Aceita variações: "Tribunal de Justiça, do Rio Grande" (com vírgula)
    # Regex para assinatura do locutor — pode estar dividida em 2 segmentos
    # faster-whisper divide "No Tribunal de Justiça do Rio Grande" / "do Norte, Nome"
    # openai-whisper junta tudo em um segmento só
    padrao_ass_parcial = re.compile(
        r'tribunal\s+de\s+justi[çc]a\s*,?\s*do\s+rio\s+grande\s*$',
        re.I
    )
    padrao_ass_completo = re.compile(
        r'tribunal\s+de\s+justi[çc]a\s*,?\s*do\s+rio\s+grande\s+do\s+norte',
        re.I
    )

    # Coletar todas as assinaturas em ordem
    # Assinatura pode estar completa em 1 segmento ou dividida em 2 (faster-whisper)
    i = 0
    while i < len(segmentos):
        seg = segmentos[i]
        texto = seg["text"]
        
        # Tentar match completo primeiro
        m_completo = padrao_ass_completo.search(texto)
        if m_completo:
            pos_ratio = m_completo.start() / len(texto) if len(texto) > 0 else 0
            t = seg["start"] + (seg["end"] - seg["start"]) * pos_ratio
            assinaturas.append(t)
            i += 1
            continue
        
        # Tentar match parcial (faster-whisper divide em 2 segmentos)
        m_parcial = padrao_ass_parcial.search(texto)
        if m_parcial:
            # Verificar se próximo segmento continua com "do Norte"
            if i + 1 < len(segmentos):
                texto_seguinte = segmentos[i + 1]["text"].strip()
                if re.match(r'^do\s+norte', texto_seguinte, re.I):
                    # Assinatura confirmada — timestamp no fim deste segmento
                    assinaturas.append(seg["end"])
                    i += 2
                    continue
        
        i += 1

    # Cada assinatura marca o FIM de um boletim
    # O próximo boletim começa no PRÓXIMO SEGMENTO DE FALA após a assinatura
    # OFFSET_APOS_ASSINATURA agora é constante do módulo (topo do arquivo)

    if assinaturas:
        # B1 começa no início (0s)
        marcadores[b_ini] = 0.0
        # Cada boletim subsequente começa no próximo segmento de fala após a assinatura
        for i, t_ass in enumerate(assinaturas):
            n_proximo = b_ini + i + 1
            if n_proximo <= b_fim:
                # Encontrar o primeiro segmento que COMEÇA após a assinatura
                t_proximo = t_ass + 1.5  # fallback
                for seg in segmentos:
                    if seg["start"] > t_ass + 0.5:
                        t_proximo = seg["start"]
                        break
                
                # CORTE FINO: o segmento pode conter assinatura + claquete + CABEÇA juntos
                # (ex: "do Norte, Leonardo Meida, M2, TJRN reforma decisão e nega...")
                # Nesse caso, o marcador deve apontar para o INÍCIO DA CABEÇA
                # (palavra seguinte à claquete individual "M2,"/"B2,"), não para o segmento seguinte.
                seg_marcador = None
                for seg in segmentos:
                    if abs(seg["start"] - t_proximo) < 0.1:
                        seg_marcador = seg
                        break
                
                if seg_marcador and "words" in seg_marcador and seg_marcador["words"]:
                    palavras_seg = seg_marcador["words"]
                    # Procurar claquete individual (B2, M2, B-10...) dentro do segmento
                    for idx_w in range(len(palavras_seg) - 1):
                        w = palavras_seg[idx_w]
                        w_norm = w["word"].strip().strip('.,;: ').lower()
                        # Claquete individual: letra+numero — mas não a data (17, 2026)
                        if re.match(r'^[a-z][\-\s]?\d{1,2}$', w_norm) and len(w_norm) <= 4:
                            # A palavra seguinte deve ser conteúdo (não número, não claquete)
                            w_prox = palavras_seg[idx_w + 1]["word"].strip().strip('.,;: ').lower()
                            if not re.match(r'^[a-z]?[\-\s]?\d+$', w_prox) and len(w_prox) > 2:
                                # Verificar que a claquete não é o PRIMEIRO conteúdo do segmento
                                # (a assinatura vem antes: "do Norte, Leonardo Meida, M2, ...")
                                # A claquete individual só é válida se houver assinatura antes dela
                                # (palavras como "norte", "leonardo", "meida", "justiça")
                                texto_antes = ' '.join(
                                    palavras_seg[k]["word"] for k in range(max(0, idx_w - 6), idx_w)
                                ).lower()
                                if re.search(r'(norte|nardo|leonardo|justi[çc]a|meida|almeida)', texto_antes):
                                    t_proximo = palavras_seg[idx_w + 1]["start"]
                                    print(f"    [corte fino] cabeça de B{n_proximo} inicia em {t_proximo:.2f}s (após claquete '{w_norm}')")
                                    break
                
                marcadores[n_proximo] = t_proximo

        # Ajuste anti-vazamento: o Whisper pode juntar a última frase do off
        # com a assinatura do locutor no mesmo segmento.
        # Dois cenários:
        # 1. Assinatura no segmento ANTERIOR ao marcador (fim do boletim anterior)
        # 2. Assinatura no segmento NO marcador (início do boletim seguinte)
        for i, t_ass in enumerate(assinaturas):
            n_proximo = b_ini + i + 1
            if n_proximo > b_fim:
                continue
            t_marc = marcadores.get(n_proximo)
            if t_marc is None:
                continue
            
            # Cenário 1: segmento anterior contém assinatura
            for seg in segmentos:
                if abs(seg["end"] - t_marc) < 0.5:
                    texto_seg = seg["text"].strip()
                    if padrao_ass_completo.search(texto_seg) or texto_seg.lower().endswith("norte"):
                        for seg2 in segmentos:
                            if seg2["start"] >= seg["end"] - 0.1:
                                marcadores[n_proximo] = seg2["start"]
                                break
                        break
            
            # Cenário 2: segmento no marcador (início do próximo boletim) contém assinatura
            # Ex: "ele é o Nardo Aumeda. De sete, formação..." — "Nardo Aumeda" é assinatura
            t_marc = marcadores.get(n_proximo)  # recalcular após cenário 1
            for seg in segmentos:
                if abs(seg["start"] - t_marc) < 0.5:
                    texto_seg = seg["text"].strip()
                    # Verificar se o INÍCIO do segmento contém assinatura
                    if re.search(r'tribunal\s+de\s+justi[cç]a', texto_seg, re.I) or \
                       re.search(r'(nardo|leonardo)\s+(almeida|amida|umeda)', texto_seg, re.I) or \
                       re.search(r'(é|o)\s+(nardo|leonardo)', texto_seg, re.I):
                        # Avançar para o próximo segmento com conteúdo real
                        for seg2 in segmentos:
                            if seg2["start"] > seg["end"] and seg2["end"] - seg2["start"] > 1.5:
                                marcadores[n_proximo] = seg2["start"]
                                break
                        break

    else:
        # Sem assinaturas: interpolar igualmente
        for n in range(b_ini, b_fim + 1):
            pos = (n - b_ini) / (b_fim - b_ini + 1)
            marcadores[n] = pos * duracao_estimada

    return {"marcadores": marcadores, "assinaturas": [(t, "", "") for t in assinaturas], "falta": []}

def detectar_repeticoes_confirmadas(segmentos, audio, threshold_similaridade=0.90):
    """ETAPA 3: detectar repetições confirmadas por análise de áudio.
    Somente mantém "Repete." se o áudio antes e depois tiver similaridade >= threshold.
    Retorna: (repeticoes_confirmadas, repeticoes_rejeitadas)"""
    confirmadas = []
    rejeitadas = []

    for i, seg in enumerate(segmentos[:-1]):
        texto = seg["text"].strip()
        if texto.lower() != "repete.":
            continue

        # Procurar próximo segmento com conteúdo (pular outros "Repete.")
        seg_prox = None
        for j in range(i + 1, min(i + 5, len(segmentos))):
            if segmentos[j]["text"].strip().lower() != "repete.":
                seg_prox = segmentos[j]
                break

        if not seg_prox:
            rejeitadas.append({"posicao": seg["start"], "motivo": "sem segmento próximo com conteúdo"})
            continue

        # Comparar áudio antes e depois
        t_antes_inicio = max(0, seg["start"] - 3)
        t_antes_fim = seg["start"]
        t_depois_inicio = seg_prox["start"]
        t_depois_fim = min(len(audio)/1000, seg_prox["end"] + 3)

        try:
            audio_antes = audio[int(t_antes_inicio*1000):int(t_antes_fim*1000)]
            audio_depois = audio[int(t_depois_inicio*1000):int(t_depois_fim*1000)]

            if len(audio_antes) < 500 or len(audio_depois) < 500:
                rejeitadas.append({"posicao": seg["start"], "motivo": "trecho muito curto para comparação"})
                continue

            # Similaridade por correlação cruzada simplificada
            import numpy as np
            samples_antes = np.array(audio_antes.get_array_of_samples(), dtype=np.float32)
            samples_depois = np.array(audio_depois.get_array_of_samples(), dtype=np.float32)

            if len(samples_antes) < 100 or len(samples_depois) < 100:
                rejeitadas.append({"posicao": seg["start"], "motivo": "amostras insuficientes"})
                continue

            # Normalizar
            s_antes = samples_antes - np.mean(samples_antes)
            s_depois = samples_depois - np.mean(samples_depois)

            if np.std(s_antes) < 1e-6 or np.std(s_depois) < 1e-6:
                rejeitadas.append({"posicao": seg["start"], "motivo": "um dos trechos é silêncio"})
                continue

            corr = np.correlate(s_antes, s_depois, mode='valid')
            similaridade = np.max(np.abs(corr)) / (np.linalg.norm(s_antes) * np.linalg.norm(s_depois))

            if similaridade >= threshold_similaridade:
                confirmadas.append({
                    "inicio": seg_prox["start"],
                    "fim": seg_prox["end"],
                    "texto_repetido": seg_prox["text"].strip()[:80],
                    "similaridade": float(similaridade)
                })
            else:
                rejeitadas.append({"posicao": seg["start"], "motivo": f"similaridade {similaridade:.2f} < {threshold_similaridade}"})

        except Exception as e:
            rejeitadas.append({"posicao": seg["start"], "motivo": f"erro na análise: {str(e)}"})

    return confirmadas, rejeitadas


def detectar_claquete_geral(segmentos, b_ini, b_fim):
    """Detecta claquete geral introdutória no início do áudio.
    
    Formatos conhecidos (variam conforme data e faixa):
    - "Boletins 17 do 9 do B1O5" (dia 17, setembro, B1 a B5)
    - "Boletins 4 do 9 do B6O7" (dia 4, setembro, B6 a B7)
    - "Boletins 18 do 9 do B1O10" (dia 18, setembro, B1 a B10)
    - "Bolitinhos 18 de setembro do B6-LB10" (com hífen, L antes do número)
    
    Retorna (inicio, fim) da claquete geral ou None se não encontrada.
    O fim inclui eventuais claquetes individuais introdutórias (ex: "B6.").
    """
    # Padrão 1: Faixa de boletins — tolerante a alucinações do Whisper
    # "B1O5", "B1 O5", "B6-LB10", "B105", "B1 05", "B6 B10"
    padrao_faixa = re.compile(r'B\d+\s*[O0\-]\s*L?\d+', re.I)

    # Padrão 2: "Boletins" (qualquer variação) + números (anúncio da faixa)
    # Tolerante a alucinações: "Bolitinhos", "Boleteins", "boletins", "Bolitins", etc.
    padrao_boletins = re.compile(
        r'b\w*?t[ií]nh?o?s\s+\d+',
        re.I
    )

    # NOTA: Vinheta de abertura ("No ar, notícias da hora...") NÃO é lixo — faz parte do boletim final

    for seg in segmentos:
        if seg["start"] > 15:
            break
        texto = seg["text"]
        if padrao_faixa.search(texto) or padrao_boletins.search(texto):
            # Encontrou início da claquete geral
            # Agora encontrar o FIM da introdução: primeiro segmento com conteúdo real
            # O conteúdo real começa APÓS todas as claquetes introdutórias
            
            # CORTE FINO: se o segmento contém claquete + cabeça juntos
            # (ex: "Bolitens 17 do 9 do B1O5, B1, empresa terá que devolver..."), 
            # usar word timestamps para cortar apenas após a claquete individual
            # e preservar a cabeça que vem na sequência
            fim_intro = seg["end"]
            
            # Buscar claquete individual dentro do próprio segmento usando words
            # Ex: "Bolitens 17 do 9 do B1O5, B1," → cortar após "B1,"
            if "words" in seg and seg["words"]:
                palavras = seg["words"]
                # Procurar o padrão claquete individual: "B1," / "B6." / "B-10."
                # seguido de conteúdo (palavra não-claquete)
                for idx_w in range(len(palavras) - 1):
                    w = palavras[idx_w]
                    w_norm = w["word"].strip().strip('.,;: ').lower()
                    # Claquete individual: letra+numero (b1, b6, b-10, m-10)
                    if re.match(r'^[a-z][\-\s]?\d+$', w_norm):
                        # Verificar se a palavra seguinte NÃO é outra claquete
                        # (é o início da cabeça/conteúdo)
                        w_prox = palavras[idx_w + 1]["word"].strip().strip('.,;: ').lower()
                        if not re.match(r'^[a-z]?\d+$', w_prox) and not re.match(r'^[a-z][\-\s]?\d+$', w_prox):
                            # Corte fino: manter a partir da palavra seguinte (cabeça)
                            fim_intro = palavras[idx_w + 1]["start"]
                            return (seg["start"], fim_intro)
            
            for seg2 in segmentos:
                if seg2["start"] <= seg["start"]:
                    continue
                if seg2["start"] > seg["start"] + 15:
                    break
                texto2 = seg2["text"].strip()

                # Claquete individual do primeiro boletim: "B1.", "B1,", "B6.", "B-10."
                # O Whisper pode transcrever com hífen: "B-10" ou letra errada: "M-10"
                if re.match(r'^[A-Z][\-\s]?\d+[\.\s,]', texto2, re.I) and len(texto2) < 80:
                    # NÃO parar aqui — a claquete individual também deve ser removida
                    # Continuar procurando o verdadeiro início do conteúdo
                    fim_intro = seg2["end"]
                    continue

                # Se o segmento tem mais de 8 palavras, é conteúdo real
                palavras = texto2.split()
                if len(palavras) > 8:
                    fim_intro = seg2["start"]
                    break

                # Se é um segmento curto mas não é claquete, pode ser continuação da intro
                if len(texto2) < 40:
                    fim_intro = seg2["end"]
                    continue

                # Segmento médio — provavelmente conteúdo
                fim_intro = seg2["start"]
                break

            return (seg["start"], fim_intro)

    return None


def detectar_claquetes_por_assinatura(segmentos, assinaturas, b_ini, b_fim):
    """ETAPA 4: detectar claquetes após assinatura do locutor.
    Para cada assinatura encontrada, busca nos próximos 5s a próxima claquete B{N}.
    Retorna dict {n_boletim_claquete: {"inicio": t, "fim": t_estimado, "motivo": ...}}"""
    claquetes = {}
    marcadores_b = {}

    for seg in segmentos:
        m = re.search(r'\bB(\d{1,2})\.', seg["text"])
        if m:
            try:
                n = int(m.group(1))
                if b_ini <= n <= b_fim:
                    if n not in marcadores_b:
                        marcadores_b[n] = seg["start"]
            except ValueError:
                pass

    for t_ass, nome, texto_ass in assinaturas:
        # Buscar próximo B{N}. nos próximos 5s
        t_max_busca = t_ass + 5
        claquette_encontrada = None

        for seg in segmentos:
            if seg["start"] >= t_ass and seg["start"] <= t_max_busca:
                m = re.search(r'\bB(\d{1,2})\.', seg["text"])
                if m:
                    try:
                        n = int(m.group(1))
                        if b_ini <= n <= b_fim and n != len(claquetes) + 1:
                            claquette_encontrada = n
                            # Estimar fim: até início do conteúdo útil ou próxima assinatura
                            fim = seg["end"]
                            for s2 in segmentos:
                                if s2["start"] > seg["start"] and "Tribunal de Justiça" not in s2["text"]:
                                    fim = s2["start"]
                                    break
                            claquetes[n] = {"inicio": seg["start"], "fim": fim, "numero": n}
                            break
                    except ValueError:
                        pass

        if not claquette_encontrada:
            # Registrar para análise manual
            claquetes["sem_deteccao"] = claquetes.get("sem_deteccao", []) + [{"tempo_assinatura": t_ass, "nome_reporter": nome}]

    return claquetes


def carregar_vht(nome):
    """Carrega uma vinheta do diretório de assets."""
    caminho = VHT_DIR / nome
    if caminho.exists():
        return AudioSegment.from_mp3(str(caminho))
    return None


def calcular_duracao_cabeca(segmento_audio, texto_cabeca, modelo):
    """Calcula a duração da cabeça no áudio com base no texto do roteiro.
    
    Usa word-level timestamps do Whisper para encontrar onde cada palavra
    do roteiro aparece no áudio. A cabeça termina na última palavra encontrada.
    
    Retorna a duração em segundos.
    Se não encontrar correspondência, retorna 20s como fallback.
    """
    if not texto_cabeca:
        return 20  # fallback
    
    # Transcrever com word timestamps
    tmp = tempfile.mktemp(suffix='.wav', dir=str(TMP_DIR))
    segmento_audio.export(tmp, format="wav")
    
    if USE_FASTER:
        segments_iter, info = modelo.transcribe(tmp, language="pt", word_timestamps=True)
        segmentos_boletim = [{"start": s.start, "end": s.end, "text": s.text, "words": s.words} for s in segments_iter]
    else:
        result = modelo.transcribe(tmp, language="pt", word_timestamps=True)
        segmentos_boletim = result["segments"]
    
    os.unlink(tmp)
    
    # Normalizar texto da cabeça para comparação
    cabeca_norm = re.sub(r'[^\w\s]', '', texto_cabeca.lower()).strip()
    palavras_cabeca = cabeca_norm.split()
    
    if not palavras_cabeca:
        return 20
    
    # Coletar todas as palavras com timestamps
    todas_palavras = []
    for seg in segmentos_boletim:
        if "words" in seg:
            for w in seg["words"]:
                todas_palavras.append({"word": w.word, "start": w.start, "end": w.end})
        else:
            # Fallback: estimar timestamps
            todas_palavras.append({"word": seg["text"], "start": seg["start"], "end": seg["end"]})
    
    # Procurar palavras da cabeça em ordem no áudio
    # A cabeça termina quando encontramos uma palavra que NÃO pertence à cabeça
    palavras_encontradas = []
    idx_palavra = 0
    
    for palavra_audio in todas_palavras:
        if idx_palavra >= len(palavras_cabeca):
            break
        
        palavra_cabeca = palavras_cabeca[idx_palavra]
        palavra_norm = re.sub(r'[^\w]', '', palavra_cabeca.lower())
        palavra_audio_norm = re.sub(r'[^\w]', '', palavra_audio["word"].lower())
        
        if not palavra_norm or not palavra_audio_norm:
            continue
        
        # Verificar se a palavra do áudio corresponde à palavra da cabeça
        if palavra_norm in palavra_audio_norm or palavra_audio_norm in palavra_norm:
            score = len(set(palavra_norm) & set(palavra_audio_norm)) / max(len(palavra_norm), len(palavra_audio_norm))
            if score >= 0.5:
                palavras_encontradas.append({
                    "palavra": palavra_cabeca,
                    "timestamp": palavra_audio["end"],
                    "score": score
                })
                idx_palavra += 1
    
    if palavras_encontradas:
        # A cabeça termina na última palavra encontrada em ordem
        ultima_palavra = palavras_encontradas[-1]
        duracao = ultima_palavra["timestamp"]
        print(f"  [DEBUG] cabeça termina em {duracao:.1f}s ({len(palavras_encontradas)}/{len(palavras_cabeca)} palavras encontradas)")
        return duracao
    
    # Fallback: 20% do boletim
    duracao_total = len(segmento_audio) / 1000
    fallback = min(max(duracao_total * 0.20, 10), 30)
    print(f"  [DEBUG] FALLBACK: {fallback:.1f}s (duracao_total={duracao_total:.1f}s)")
    return fallback


def montar_boletim_com_vinhetas(segmento_audio, vht_abertura, vht_passagem, vht_encerramento, cabeça_duracao=20):
    """ETAPA 6: monta estrutura completa: ABERTURA + CABEÇA + PASSAGEM + OFF(com BG ducking) + ENCERRAMENTO.

    - BG (background music) toca durante o OFF com ducking (volume reduzido).
    - BG nunca ultrapassa o fim do off.
    - Se o off é mais curto que o BG, o BG é cortado.
    - Se o off é mais longo, o BG termina antes do encerramento.
    - A vinheta de passagem é inserida entre a cabeça e o OFF.
    """
    vht_a = vht_abertura or carregar_vht("VHT_ABERTURA_BOLETIM.mp3")
    vht_p = vht_passagem or carregar_vht("VHT_PASSAGEM_BOLETIM.mp3")
    vht_e = vht_encerramento or carregar_vht("VHT_ENCERRAMENTO_BOLETIM.mp3")
    bg = carregar_vht("BG - BOLETIM.mp3")

    # Dividir em cabeça e off
    duracao_total = len(segmento_audio) / 1000
    if duracao_total > cabeça_duracao:
        cabeça = segmento_audio[:int(cabeça_duracao * 1000)]
        off = segmento_audio[int(cabeça_duracao * 1000):]
    else:
        cabeça = segmento_audio
        off = AudioSegment.silent(duration=0)

    # Montar partes sem BG primeiro
    partes = []
    if vht_a:
        partes.append(vht_a)

    partes.append(cabeça)

    # Inserir vinheta de passagem entre cabeça e OFF
    if vht_p:
        partes.append(vht_p)

    # OFF com BG em ducking dinâmico (BG desce durante a fala, sobe no silêncio)
    if len(off) > 0 and bg is not None:
        # Usa mix_bgm para ducking profissional baseado em RMS da voz
        off_com_bg = mix_bgm(off, BG_PATH)
        partes.append(off_com_bg)
    elif len(off) > 0:
        partes.append(off)

    if vht_e:
        partes.append(vht_e)

    if len(partes) > 1:
        montado = sum(partes[1:], partes[0])
    elif partes:
        montado = partes[0]
    else:
        montado = AudioSegment.silent(duration=1000)
    
    # Normalizar loudness para -16 LUFS (padrão rádio), TP=-1.5, LRA=11
    # Vinhetas estão em ~-19.6 dBFS; voz em ~-10 dBFS (estourando)
    # loudnorm equaliza para que voz e vinhetas fiquem no mesmo nível percebido
    import subprocess
    tmp_in = tempfile.mktemp(suffix='.wav', dir=str(TMP_DIR))
    tmp_out = tempfile.mktemp(suffix='.wav', dir=str(TMP_DIR))
    montado.export(tmp_in, format="wav")
    subprocess.run([
        "ffmpeg", "-y", "-i", tmp_in,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        tmp_out
    ], check=True, capture_output=True)
    os.unlink(tmp_in)
    resultado = AudioSegment.from_wav(tmp_out)
    os.unlink(tmp_out)
    return resultado


def processar_canonico(arquivo_entrada, pasta_roteiros=None):
    """Pipeline canônico completo. Retorna dict com resultados e estatísticas."""
    arquivo = Path(arquivo_entrada)
    if not arquivo.exists():
        return {"erro": f"Arquivo não encontrado: {arquivo}"}

    print(f"\n{'='*60}")
    print(f"PROCESSAMENTO CANÔNICO: {arquivo.name}")
    print(f"{'='*60}\n")

    # Carregar modelo Whisper uma vez (faster-whisper se disponível)
    print("Carregando modelo de transcrição...")
    modelo = carregar_modelo()

    # ETAPA 0: Triagem
    print("\n── ETAPA 0: TRIAGEM INICIAL DO ÁUDIO ──")
    audio = AudioSegment.from_mp3(str(arquivo))
    triagem = triagem_audio(audio)
    print(f"  Duração: {triagem['duracao_segundos']:.2f}s")
    print(f"  Canais: {triagem['canais']}, Samplerate: {triagem['frame_rate']}Hz")
    if triagem.get('acoes'):
        print(f"  Ações de correção: {triagem['acoes']}")

    # Aplicar correções de triagem (após transcrição, não antes)
    # NOTA: converter para mono ANTES da transcrição causa perda de qualidade
    # no Whisper (transcrições incompletas). Converter apenas para montagem.
    precisa_mono = triagem.get("canal_morto") or triagem.get("estereo_duplicado")

    # ETAPA 1: Transcrição
    print("\n── ETAPA 1: TRANSCRIÇÃO (Whisper base) ──")
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False, dir=str(TMP_DIR)) as tmp:
        tmp_path = tmp.name
    segmentos = transcrever(audio, tmp_path, modelo)

    # ETAPA 1.5: Correção de alucinações do Whisper
    print("\n── ETAPA 1.5: CORREÇÃO DE ALUCINAÇÕES ──")
    # Extrair faixa do nome do arquivo para carregar roteiros
    _, b_ini_f, b_fim_f, _ = extrair_info_nome(arquivo, None)
    # Compilar texto completo dos roteiros para correção
    texto_roteiro_completo = None
    if pasta_roteiros:
        roteiros_dict = carregar_roteiros(pasta_roteiros, "", b_ini_f, b_fim_f)
        if roteiros_dict:
            texto_roteiro_completo = " ".join(
                v["titulo"] + " " + v["off"] if isinstance(v, dict) else v
                for v in roteiros_dict.values()
            )

    segmentos_antes = len(segmentos)
    segmentos = corrigir_transcricao(segmentos, texto_roteiro_completo)
    removidos = segmentos_antes - len(segmentos)
    print(f"  Segmentos antes: {segmentos_antes}, depois: {len(segmentos)}, removidos: {removidos}")

    print(f"  Transcrito: {len(segmentos)} segmentos")
    print("\n  Transcrição completa:")
    for seg in segmentos:
        print(f"    [{seg['start']:7.2f}s - {seg['end']:7.2f}s] {seg['text'].strip()}")

    # ETAPA 2: Estrutura
    print("\n── ETAPA 2: DETECÇÃO DE ESTRUTURA ──")
    data_str, b_ini, b_fim, data_completa_str = extrair_info_nome(arquivo, " ".join(s["text"] for s in segmentos))
    if not data_completa_str or data_completa_str.startswith("??"):
        today = date.today()
        data_completa_str = f"{today.day:02d}_SET_{today.year}"
        data_str = f"{today.day} SET"
    print(f"  Data detectada: {data_str} → {data_completa_str}")
    print(f"  Faixa: B{b_ini} - B{b_fim}")

    roteiros = {}
    if pasta_roteiros:
        print(f"  Buscando roteiros em: {pasta_roteiros}")
        roteiros = carregar_roteiros(pasta_roteiros, data_str, b_ini, b_fim)
        print(f"  Roteiros encontrados: {len(roteiros)} boletins")

    estrutura = detectar_estrutura(segmentos, b_ini, b_fim)
    print(f"  Marcadores B{{N}}. encontrados: {list(estrutura['marcadores'].keys())}")
    print(f"  Assinaturas detectadas: {len(estrutura['assinaturas'])}")
    for t, nome, txt in estrutura['assinaturas']:
        print(f"    [{t:.2f}s] {nome} — {txt[:60]}")
    if estrutura['falta']:
        print(f"  Faltantes (interpolação): {estrutura['falta']}")

    # ETAPA 3: Repetições confirmadas
    print("\n── ETAPA 3: DETECÇÃO DE REPETIÇÕES (confirmação por áudio) ──")
    rep_confirmadas, rep_rejeitadas = detectar_repeticoes_confirmadas(segmentos, audio)
    print(f"  Repetições confirmadas: {len(rep_confirmadas)}")
    for r in rep_confirmadas:
        print(f"    [{r['inicio']:.2f}s - {r['fim']:.2f}s] similaridade={r['similaridade']:.2f} — '{r['texto_repetido'][:50]}'")
    print(f"  Repetições rejeitadas: {len(rep_rejeitadas)}")
    for r in rep_rejeitadas[:5]:
        print(f"    [{r['posicao']:.2f}s] {r['motivo'][:50]}")
    if len(rep_rejeitadas) > 5:
        print(f"    ... +{len(rep_rejeitadas)-5} mais")

    # ETAPA 4: Claquetes por assinatura
    print("\n── ETAPA 4: DETECÇÃO DE CLAKETES (gatilho por assinatura) ──")
    claquetes = detectar_claquetes_por_assinatura(segmentos, estrutura['assinaturas'], b_ini, b_fim)
    if "sem_deteccao" in claquetes:
        print(f"  Assinaturas sem claquete detectada nos próximos 5s: {len(claquetes['sem_deteccao'])}")
        for item in claquetes['sem_deteccao']:
            print(f"    [{item['tempo_assinatura']:.2f}s] {item['nome_reporter']}")
        del claquetes["sem_deteccao"]
    print(f"  Claquetes detectadas: {len([k for k in claquetes if isinstance(k, int)])}")
    for n, info in claquetes.items():
        if isinstance(n, int):
            print(f"    B{n}: [{info['inicio']:.2f}s - {info['fim']:.2f}s]")

    # ETAPA 4.5: Detectar claquete geral introdutória (B1)
    claquete_geral = detectar_claquete_geral(segmentos, b_ini, b_fim)
    if claquete_geral:
        print(f"\n── ETAPA 4.5: CLAQUETE GERAL DETECTADA ──")
        print(f"  Claquete geral: [{claquete_geral[0]:.2f}s - {claquete_geral[1]:.2f}s]")
        print(f"  Será removida do B1")
    else:
        print(f"\n── ETAPA 4.5: Claquete geral não detectada ──")

    # ETAPA 5: Corte e remoção
    print("\n── ETAPA 5: CORTE + REMOÇÃO ──")
    # Criar pasta de saída
    saida = arquivo.parent / f"{arquivo.stem}_saida"
    saida.mkdir(exist_ok=True)

    # Converter para mono se necessário (após transcrição, antes do corte)
    if precisa_mono:
        print(f"  Convertendo para mono (canal morto: {triagem.get('canal_morto')})")
        audio_corte = audio.set_channels(1) if triagem.get("estereo_duplicado") else audio.split_to_mono()[0 if triagem['canal_morto'] == 'direito' else 1].set_channels(1)
    else:
        audio_corte = audio

    # Gerar corte_limpo para cada boletim
    boletims_cortados = {}

    marcadores_ordenados = sorted(estrutura['marcadores'].items(), key=lambda x: x[1])
    assinaturas_ordenadas = sorted([t for t, _, _ in estrutura['assinaturas']])

    for i, (n, t_ini) in enumerate(marcadores_ordenados):
        if n < b_ini or n > b_fim:
            continue

        # Limite de início: marcação B{n} (claquete)
        t_start = max(0, t_ini)

        # Limite de fim: assinatura do boletim atual
        # A assinatura é a primeira que vem DEPOIS do início do boletim
        t_fim = len(audio) / 1000  # fallback: fim do áudio
        for t_ass in assinaturas_ordenadas:
            if t_ass > t_start + 2:  # pelo menos 2s de conteúdo
                # Usar o INÍCIO do segmento que contém a assinatura
                # (não o timestamp exato da assinatura, que pode estar no meio do segmento)
                for seg in segmentos:
                    if seg["start"] <= t_ass <= seg["end"]:
                        t_fim = seg["start"]
                        break
                else:
                    t_fim = t_ass
                break

        # Recortar boletim crú
        t_start_ms = int(t_start * 1000)
        t_fim_ms = int(t_fim * 1000)
        if t_fim_ms <= t_start_ms:
            t_fim_ms = t_start_ms + 1000  # mínimo 1s
        segmento = audio_corte[t_start_ms:t_fim_ms]

        # Remover repetições confirmadas dentro do boletim
        cortes_repeticao = [r for r in rep_confirmadas if r['inicio'] >= t_start and r['fim'] <= t_fim]
        if cortes_repeticao:
            print(f"  B{n}: removendo {len(cortes_repeticao)} repetição(ões) confirmada(s)")

        # Remover claquetes detectadas dentro do boletim
        cortes_claquette = [info for n2, info in claquetes.items() if isinstance(n2, int) and info['inicio'] >= t_start and info['fim'] <= t_fim]
        if cortes_claquette:
            print(f"  B{n}: removendo {len(cortes_claquette)} claquete(s)")

        # Remover claquete introdutória do primeiro boletim (B1 ou equivalente)
        # Inclui: claquete geral, claquete individual, e data de referência
        # Tudo que vier ANTES do conteúdo real (primeira frase do OFF) deve ser cortado
        if n == b_ini and claquete_geral:
            cg_inicio, cg_fim = claquete_geral
            if cg_inicio >= t_start - 1 and cg_fim <= t_fim:
                cortes_claquette.append({"inicio": cg_inicio, "fim": cg_fim})
                print(f"  B{n}: removendo claquete geral [{cg_inicio:.2f}s - {cg_fim:.2f}s]")
        
        # Para TODOS os boletins: remover claquete individual + data de referência
        # que aparecem nos primeiros ~8s (antes do conteúdo real)
        for seg in segmentos:
            if seg["start"] < t_start or seg["start"] >= t_start + 8:
                continue
            if seg["start"] >= t_fim:
                break
            texto_seg = seg["text"].strip()
            eh_claquete = False
            motivo = ""
            
            # Padrão 1: Claquete individual "B{N}." ou "B{N}, título" (curta, sem conteúdo)
            if re.match(r'^B\d+[\.\s,]', texto_seg, re.I) and len(texto_seg) < 60:
                if "tribunal" not in texto_seg.lower() and "justiça" not in texto_seg.lower():
                    eh_claquete = True
                    motivo = "claquete individual"
            
            # Padrão 2: Data de referência "Natal, 17 de setembro de 2026"
            if re.search(r'\d{1,2}\s+de\s+\w+\s+de\s+\d{4}', texto_seg) and len(texto_seg) < 80:
                # Verificar se é só a data (não é conteúdo)
                palavras_significativas = [w for w in texto_seg.split() if w.lower() not in (
                    'natal', 'de', 'do', 'da', 'em', 'no', 'na', 'e', 'rn', 'rio', 'grande', 'norte',
                    'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo',
                    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho',
                    'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'
                ) and not re.match(r'^\d+$', w) and not re.match(r'^\d{1,2}h\d{2}$', w)]
                if len(palavras_significativas) <= 2:
                    eh_claquete = True
                    motivo = "data de referência"
            
            if eh_claquete:
                # Estimar fim: próximo segmento ou +2s
                fim_claquete = seg["end"]
                for seg2 in segmentos:
                    if seg2["start"] > seg["start"] and seg2["start"] < seg["start"] + 5:
                        fim_claquete = seg2["start"]
                        break
                cortes_claquette.append({"inicio": seg["start"], "fim": fim_claquete})
                print(f"  B{n}: removendo {motivo} [{seg['start']:.2f}s - {fim_claquete:.2f}s]")

        # Aplicar cortes sequencialmente (do fim para o início para manter timestamps)
        segmento_limpo = segmento
        for corte in sorted(cortes_repeticao, key=lambda x: x['fim'], reverse=True) + \
                       sorted(cortes_claquette, key=lambda x: x['fim'], reverse=True):
            t_inicio_seg = max(0, corte['inicio'] - t_start)
            t_fim_seg = min(len(segmento)/1000, corte['fim'] - t_start)
            if t_fim_seg > t_inicio_seg:
                segmento_limpo = segmento_limpo[:int(t_inicio_seg*1000)] + segmento_limpo[int(t_fim_seg*1000):]

        boletims_cortados[n] = {
            "audio": segmento_limpo,
            "inicio_original": t_start,
            "fim_original": t_fim,
            "duracao_cortada": len(segmento_limpo)/1000,
            "repeticoes_removidas": len(cortes_repeticao),
            "claquetes_removidas": len(cortes_claquette)
        }

        rot_n = roteiros.get(n, {}) if roteiros else {}
        titulo_rot = rot_n.get("titulo", "") if isinstance(rot_n, dict) else rot_n
        nome_arquivo = nomear_boletim(data_str, n, titulo_rot, data_completa_str)
        print(f"  B{n}: [{t_start:.2f}s → {t_fim:.2f}s] = {boletims_cortados[n]['duracao_cortada']:.2f}s → {nome_arquivo}")

    # ETAPA 6: Montagem com vinhetas
    print("\n── ETAPA 6: MONTAGEM COM VINHETAS ──")
    for n, info in boletims_cortados.items():
        if info['duracao_cortada'] < 3:
            print(f"  B{n}: skipping montagem (duração muito curta: {info['duracao_cortada']:.2f}s)")
            continue

        rot_n = roteiros.get(n, {}) if roteiros else {}
        titulo_rot = rot_n.get("titulo", "") if isinstance(rot_n, dict) else rot_n
        cabeca_rot = rot_n.get("cabeca", "") if isinstance(rot_n, dict) else ""
        nome_arquivo = nomear_boletim(data_str, n, titulo_rot, data_completa_str)
        info['nome'] = nome_arquivo
        
        # Calcular duração da cabeça baseada no roteiro (se disponível)
        # Usar o áudio original (com vinheta de abertura) para detectar a cabeça
        if cabeca_rot:
            duracao_cabeca = calcular_duracao_cabeca(audio, cabeca_rot, modelo)
            print(f"  B{n}: cabeça do roteiro = {duracao_cabeca:.1f}s")
        else:
            duracao_cabeca = 20  # fallback
        
        montado = montar_boletim_com_vinhetas(
            info['audio'],
            None, None, None,  # VHTs carregadas dentro da função
            duracao_cabeca
        )

        caminho_saida = saida / nome_arquivo
        montado.export(str(caminho_saida), format="mp3")
        print(f"  ✓ B{n}: montado → {nome_arquivo} ({len(montado)/1000:.2f}s)")

    # ETAPA 7: Auditoria
    print("\n── ETAPA 7: AUDITORIA ──")
    auditoria = {
        "arquivo_entrada": str(arquivo),
        "data_detectada": data_str,
        "faixa": [b_ini, b_fim],
        "duracao_original": triagem['duracao_segundos'],
        "triagem": triagem,
        "transcricao": {
            "segmentos": len(segmentos),
            "texto_completo": " ".join(s["text"].strip() for s in segmentos)
        },
        "estrutura": estrutura,
        "repeticoes": {
            "confirmadas": rep_confirmadas,
            "rejeitadas": rep_rejeitadas[:10]
        },
        "claquetes": {str(k): v for k, v in claquetes.items()},
        "boletims_gerados": []
    }

    for n in sorted(boletims_cortados.keys()):
        info = boletims_cortados[n]
        if 'nome' not in info:
            rot_n = roteiros.get(n, {}) if roteiros else {}
            titulo_rot = rot_n.get("titulo", "") if isinstance(rot_n, dict) else rot_n
            info['nome'] = nomear_boletim(data_str, n, titulo_rot, data_completa_str)
        caminho = saida / info['nome']
        try:
            if not caminho.exists():
                info['audio'].export(str(caminho), format="mp3")
            if caminho.exists():
                audio_b = AudioSegment.from_mp3(str(caminho))
                auditoria["boletims_gerados"].append({
                    "arquivo": info['nome'],
                    "duracao_segundos": round(len(audio_b)/1000, 2),
                    "tamanho_bytes": caminho.stat().st_size
                })
                print(f"  ✓ {info['nome']} — {len(audio_b)/1000:.2f}s, {caminho.stat().st_size/1024:.1f} KB")
            else:
                print(f"  ✗ ARQUIVO NÃO EXISTE: {caminho.name}")
        except Exception as e:
            print(f"  ✗ ERRO ao processar {info['nome']}: {e}")
            import traceback
            traceback.print_exc()
            # Garante que a chave exista mesmo em caso de erro
            if "boletims_gerados" not in auditoria:
                auditoria["boletims_gerados"] = []

    # ETAPA 7.5: Validação de qualidade da transcrição vs roteiro
    if roteiros:
        print(f"\n── ETAPA 7.5: VALIDAÇÃO DE QUALIDADE (transcrição vs roteiro) ──")
        from corrigir_alucinacoes import corrigir_transcricao as corrige_aluc, normalizar_texto
        from difflib import SequenceMatcher
        
        for n in sorted(boletims_cortados.keys()):
            info = boletims_cortados[n]
            caminho = saida / info['nome']
            if not caminho.exists() or caminho.stat().st_size < 1000:
                continue
            
            # Transcrever boletim editado
            tmp = tempfile.mktemp(suffix='.wav', dir=str(TMP_DIR))
            audio_b = AudioSegment.from_mp3(str(caminho))
            segmentos_transcritos = transcrever(audio_b, tmp, modelo)
            
            texto_transcrito = " ".join(s["text"] for s in segmentos_transcritos)
            
            # Obter texto do roteiro para este boletim (usar OFF)
            rot_n = roteiros.get(n, {}) if roteiros else {}
            if isinstance(rot_n, dict):
                roteiro_b = rot_n.get("off", "") or rot_n.get("titulo", "")
            else:
                roteiro_b = rot_n
            if not roteiro_b:
                continue
            
            # Calcular similaridade (usando cobertura do roteiro)
            texto_norm = normalizar_texto(texto_transcrito)
            roteiro_norm = normalizar_texto(roteiro_b)
            
            palavras_roteiro = set(roteiro_norm.split())
            palavras_transcrito = set(texto_norm.split())
            
            if palavras_roteiro:
                # Cobertura: % das palavras do roteiro que aparecem na transcrição
                cobertura = len(palavras_roteiro & palavras_transcrito) / len(palavras_roteiro)
            else:
                cobertura = 0.0
            
            sim_original = cobertura
            
            print(f"  B{n}: cobertura original = {sim_original:.2%}")
            
            # Se cobertura baixa (< 60%), aplicar correções e retranscrever
            # Threshold 60%: Whisper alucina nomes próprios (ex: "Tejota Reino" em vez de "TJRN")
            if sim_original < COBERTURA_MIN:
                print(f"  B{n}: cobertura baixa — aplicando correções de alucinações...")
                
                # Aplicar correções na transcrição
                segmentos_corrigidos = corrige_aluc(segmentos_transcritos, roteiro_b)
                texto_corrigido = " ".join(s.get("text", s.get("text_corrigido", "")).strip() for s in segmentos_corrigidos)
                texto_corrigido_norm = normalizar_texto(texto_corrigido)
                
                palavras_corrigido = set(texto_corrigido_norm.split())
                if palavras_roteiro:
                    cobertura_corrigida = len(palavras_roteiro & palavras_corrigido) / len(palavras_roteiro)
                else:
                    cobertura_corrigida = 0.0
                
                sim_corrigido = cobertura_corrigida
                
                print(f"  B{n}: cobertura corrigida = {sim_corrigido:.2%}")
                
                # Adicionar info na auditoria (cobertura = % do roteiro presente na transcrição)
                for bg in auditoria["boletims_gerados"]:
                    if f"_B{n}__" in bg["arquivo"]:
                        bg["qualidade"] = {
                            "cobertura_roteiro_original": round(sim_original, 3),
                            "cobertura_roteiro_corrigida": round(sim_corrigido, 3),
                            "correcoes_aplicadas": True,
                            "texto_corrigido": texto_corrigido[:500],
                            "nota": "Cobertura de palavras do roteiro. NAO substitui audicao humana."
                        }
                        break
            else:
                for bg in auditoria["boletims_gerados"]:
                    if f"_B{n}__" in bg["arquivo"]:
                        bg["qualidade"] = {
                            "cobertura_roteiro_original": round(sim_original, 3),
                            "correcoes_aplicadas": False,
                            "nota": "Cobertura de palavras do roteiro. NAO substitui audicao humana."
                        }
                        break

    # Salvar auditoria
    auditoria_path = saida / "auditoria.json"
    with open(auditoria_path, "w", encoding="utf-8") as f:
        json.dump(auditoria, f, indent=2, ensure_ascii=False)
    print(f"\n  Auditoria salva: {auditoria_path}")

    print(f"\n{'='*60}")
    print(f"PROCESSAMENTO COMPLETO: {len(auditoria['boletims_gerados'])} boletins gerados")
    print(f"Saída: {saida}")
    print(f"{'='*60}")
    print(f"\n⚠️  AUDITORIA HUMANA OBRIGATÓRIA ANTES DE ENTREGAR:")
    print(f"   1. Ouvir cada boletim gerado")
    print(f"   2. Verificar: sem repetições, sem claquetes, conteúdo faz sentido")
    print(f"   3. Cobertura de palavras NÃO substitui audição")
    print(f"   4. Se reprovações: ajustar pipeline e reprocessar")
    print(f"{'='*60}\n")

    return auditoria


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline canônico de edição de boletins")
    parser.add_argument("arquivo", help="Arquivo MP3 de entrada")
    parser.add_argument("--roteiros", help="Pasta com roteiros em texto (opcional)", default=None)
    args = parser.parse_args()

    pasta_roteiros = Path(args.roteiros) if args.roteiros else None
    # Se --roteiros for um arquivo, usar o diretório pai
    if pasta_roteiros and pasta_roteiros.is_file():
        pasta_roteiros = pasta_roteiros.parent
    resultado = processar_canonico(args.arquivo, pasta_roteiros)

    if "erro" in resultado:
        print(f"ERRO: {resultado['erro']}")
        sys.exit(1)
    
    # Garantir que a auditoria tenha a chave boletims_gerados para impressão final
    if "boletims_gerados" not in resultado:
        resultado["boletims_gerados"] = []
    print(f"PROCESSAMENTO COMPLETO: {len(resultado['boletims_gerados'])} boletins gerados")
