"""
Etapa 5: Corte e remoção de trechos (repetições, claquetes, data de referência).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # scripts_pipeline/


def processar_cortes_boletim(segmentos, audio_corte, rep_confirmadas, claquetes,
                              claquete_geral, estrutura, b_ini, b_fim):
    """ETAPA 5: Corte + remoção.
    
    Para cada boletim definido nos marcadores da estrutura:
    1. Recorta o segmento de áudio entre marcador e assinatura
    2. Remove repetições confirmadas
    3. Remove claquetes detectadas
    4. Remove claquete geral (primeiro boletim)
    5. Remove claquetes individuais + data de referência (todos os boletins)
    
    Retorna dict {n_boletim: {"audio": ..., "inicio_original": ..., "fim_original": ...,
                             "duracao_cortada": ..., "repeticoes_removidas": ..., "claquetes_removidas": ...}}
    """
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
        t_fim = len(audio_corte) / 1000  # fallback: fim do áudio
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

    return boletims_cortados
