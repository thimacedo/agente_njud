"""
Etapa 2-4: Detecção de estrutura, repetições e claquetes.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # scripts_pipeline/


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
    # Aceita variações do modelo small: "Tribunal da Justiça", "e do Norte"
    # O modelo small pode dividir em vários padrões diferentes - ser flexível
    padrao_ass_parcial = re.compile(
        r'(?:tribunal\s+(?:de|da)\s+)?justi[çc]a\s*,?\s*(?:do\s+)?(?:rio\s+grande\s*(?:e\s+do)?|do)\s*$',
        re.I
    )
    padrao_ass_completo = re.compile(
        r'(?:tribunal\s+(?:de|da)\s+)?justi[çc]a\s*,?\s*(?:do\s+)?rio\s+grande\s*(?:e\s+do|do)\s+norte',
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
                if re.match(r'^(?:e\s+do\s+)?norte', texto_seguinte, re.I):
                    # Assinatura confirmada — timestamp no fim deste segmento
                    assinaturas.append(seg["end"])
                    i += 2
                    continue
        
        i += 1

    # Cada assinatura marca o FIM de um boletim
    # O próximo boletim começa no PRÓXIMO SEGMENTO DE FALA após a assinatura
    OFFSET_APOS_ASSINATURA = 0.3

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
        duracao_estimada = segmentos[-1]["end"] if segmentos else 60
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
    Retorna dict {n_boletim_claquete: {"inicio": t, "fim": t_estimado", "motivo": ...}}"""
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
