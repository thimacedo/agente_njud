#!/usr/bin/env python3
"""
core.py — Funcoes puras de logica do pipeline DIVISOR.

Todas as funcoes aqui são puras (sem I/O):
- Nao leem arquivos
- Nao fazem print/write
- Nao acessam rede
- Dados entram por parametros, resultados saem por return

Isso permite teste unitario sem mocks e reutilizacao em qualquer contexto.
"""
import re
from dataclasses import dataclass
from shared.text_utils import normalizar_texto


@dataclass
class Corte:
    """Representa um trecho removido do áudio."""
    inicio: float
    fim: float
    motivo: str = ""


def sincronizar_transcricao_com_cortes(segmentos: list, cortes: list) -> list:
    """
    Sincroniza segmentos de transcrição com cortes de áudio.
    
    Regra: Se o áudio teve cortes (claquetes, repetições, etc),
    a transcrição precisa ser ajustada:
    - Segmentos totalmente dentro de um corte → removidos
    - Segmentos parcialmente sobrepostos → truncados proporcionalmente
    - Timestamps após os cortes → deslocados para trás
    
    Args:
        segmentos: Lista de {"start": float, "end": float, "text": str, ...}
        cortes: Lista de Corte(inicio, fim, motivo)
    
    Returns:
        Segmentos com timestamps ajustados e trechos removidos
    """
    if not cortes or not segmentos:
        return segmentos
    
    cortes_mesclados = _mesclar_cortes(cortes)
    resultado = []
    
    for seg in segmentos:
        seg_inicio = seg["start"]
        seg_fim = seg["end"]
        
        if _segmento_totalmente_cortado(seg_inicio, seg_fim, cortes_mesclados):
            continue
        
        partes_mantidas = _calcular_partes_ajustadas(seg_inicio, seg_fim, cortes_mesclados)
        
        if not partes_mantidas:
            continue
        
        texto_original = seg.get("text", "")
        palavras = texto_original.split()
        duracao_total = seg_fim - seg_inicio
        
        for parte_orig_inicio, parte_orig_fim, parte_ajust_inicio, parte_ajust_fim in partes_mantidas:
            prop_inicio = (parte_orig_inicio - seg_inicio) / duracao_total if duracao_total > 0 else 0
            prop_fim = (parte_orig_fim - seg_inicio) / duracao_total if duracao_total > 0 else 1
            
            idx_inicio = int(len(palavras) * prop_inicio)
            idx_fim = int(len(palavras) * prop_fim)
            
            # Garantir pelo menos 1 palavra se a parte tem duração significativa
            if idx_fim == idx_inicio and (parte_orig_fim - parte_orig_inicio) > 0.5:
                idx_fim = min(idx_inicio + 1, len(palavras))
            
            texto_parte = " ".join(palavras[idx_inicio:idx_fim]).strip()
            
            if texto_parte:
                resultado.append({
                    **seg,
                    "start": parte_ajust_inicio,
                    "end": parte_ajust_fim,
                    "text": texto_parte,
                })
    
    return resultado


def _mesclar_cortes(cortes: list) -> list:
    """Mescla cortes sobrepostos ou adjacentes."""
    if not cortes:
        return []
    
    ordenados = sorted(cortes, key=lambda c: c.inicio)
    mesclados = [Corte(ordenados[0].inicio, ordenados[0].fim, ordenados[0].motivo)]
    
    for corte in ordenados[1:]:
        if corte.inicio <= mesclados[-1].fim:
            mesclados[-1].fim = max(mesclados[-1].fim, corte.fim)
        else:
            mesclados.append(Corte(corte.inicio, corte.fim, corte.motivo))
    
    return mesclados


def _segmento_totalmente_cortado(inicio: float, fim: float, cortes: list) -> bool:
    """Verifica se o segmento está totalmente dentro de algum corte."""
    for corte in cortes:
        if corte.inicio <= inicio and corte.fim >= fim:
            return True
    return False


def _calcular_partes_ajustadas(inicio: float, fim: float, cortes: list) -> list:
    """
    Calcula partes mantidas com timestamps ajustados.
    
    Returns:
        Lista de (inicio_original, fim_original, inicio_ajustado, fim_ajustado)
    """
    partes = [(inicio, fim, inicio, fim)]
    
    for corte in cortes:
        novas_partes = []
        
        for parte_orig_inicio, parte_orig_fim, parte_ajust_inicio, parte_ajust_fim in partes:
            if corte.fim <= parte_orig_inicio or corte.inicio >= parte_orig_fim:
                if corte.fim <= parte_orig_inicio:
                    duracao_corte = corte.fim - corte.inicio
                    novas_partes.append((
                        parte_orig_inicio, parte_orig_fim,
                        parte_ajust_inicio - duracao_corte, parte_ajust_fim - duracao_corte
                    ))
                else:
                    novas_partes.append((parte_orig_inicio, parte_orig_fim, parte_ajust_inicio, parte_ajust_fim))
                continue
            
            if corte.inicio <= parte_orig_inicio and corte.fim >= parte_orig_fim:
                continue
            
            if corte.inicio <= parte_orig_inicio and corte.fim < parte_orig_fim:
                duracao_corte = corte.fim - corte.inicio
                novas_partes.append((
                    corte.fim, parte_orig_fim,
                    corte.fim - duracao_corte, parte_ajust_fim - duracao_corte
                ))
                continue
            
            if corte.inicio > parte_orig_inicio and corte.fim >= parte_orig_fim:
                novas_partes.append((parte_orig_inicio, corte.inicio, parte_ajust_inicio, corte.inicio))
                continue
            
            if corte.inicio > parte_orig_inicio and corte.fim < parte_orig_fim:
                duracao_corte = corte.fim - corte.inicio
                novas_partes.append((parte_orig_inicio, corte.inicio, parte_ajust_inicio, corte.inicio))
                novas_partes.append((
                    corte.fim, parte_orig_fim,
                    corte.fim - duracao_corte, parte_ajust_fim - duracao_corte
                ))
                continue
        
        partes = novas_partes
    
    return partes


def calcular_cobertura_roteiro(texto_transcrito: str, texto_roteiro: str) -> tuple:
    """
    Calcula cobertura do roteiro na transcricao.
    
    Returns:
        (cobertura_0_1, palavras_cobertas, total_palavras)
    """
    if not texto_roteiro:
        return 0.0, 0, 0
    
    texto_norm = normalizar_texto(texto_transcrito)
    roteiro_norm = normalizar_texto(texto_roteiro)
    
    palavras_roteiro = set(roteiro_norm.split())
    palavras_texto = set(texto_norm.split())
    
    if not palavras_roteiro:
        return 0.0, 0, 0
    
    cobertas = len(palavras_roteiro & palavras_texto)
    total = len(palavras_roteiro)
    cobertura = cobertas / total
    
    return cobertura, cobertas, total


def detectar_assinaturas(segmentos: list, b_ini: int = 1, b_fim: int = 10) -> list:
    """
    Detecta assinaturas de locutor nos segmentos.
    
    Returns:
        Lista de timestamps (segundos) onde foram encontradas assinaturas
    """
    assinaturas = []
    
    padrao_completo = re.compile(
        r'tribunal\s+de\s+justi[çc]a\s*,?\s*do\s+rio\s+grande\s+do\s+norte',
        re.I
    )
    padrao_parcial = re.compile(
        r'tribunal\s+de\s+justi[çc]a\s*,?\s*do\s+rio\s+grande\s*$',
        re.I
    )
    
    i = 0
    while i < len(segmentos):
        seg = segmentos[i]
        texto = seg["text"].strip()
        
        m_completo = padrao_completo.search(texto)
        if m_completo:
            pos_ratio = m_completo.start() / len(texto) if len(texto) > 0 else 0
            t = seg["start"] + (seg["end"] - seg["start"]) * pos_ratio
            assinaturas.append(t)
            i += 1
            continue
        
        m_parcial = padrao_parcial.search(texto)
        if m_parcial and (i + 1 < len(segmentos)):
            texto_seguinte = segmentos[i + 1]["text"].strip()
            if re.match(r'^do\s+norte', texto_seguinte, re.I):
                assinaturas.append(seg["end"])
                i += 2
                continue
        
        i += 1
    
    return assinaturas


def calcular_marcadores(b_ini: int, b_fim: int, assinaturas: list, 
                        segmentos: list, offset: float = 0.3) -> dict:
    """
    Calcula marcadores de inicio de cada boletim.
    
    Returns:
        {n_boletim: tempo_segundo}
    """
    marcadores = {}
    
    if assinaturas:
        marcadores[b_ini] = 0.0
        for idx, t_ass in enumerate(assinaturas):
            n_proximo = b_ini + idx + 1
            if n_proximo <= b_fim:
                t_proximo = t_ass + offset
                for seg in segmentos:
                    if seg["start"] > t_ass + 0.1:
                        t_proximo = seg["start"]
                        break
                marcadores[n_proximo] = t_proximo
    else:
        duracao = segmentos[-1]["end"] if segmentos else 120
        for n in range(b_ini, b_fim + 1):
            pos = (n - b_ini) / (b_fim - b_ini + 1)
            marcadores[n] = pos * duracao
    
    return marcadores


def detectar_claquete_geral(segmentos: list, b_ini: int, b_fim: int) -> tuple | None:
    """
    Detecta claquete geral introdutoria no inicio do audio.
    
    Returns:
        (inicio_seg, fim_seg) ou None
    """
    padrao_faixa = re.compile(r'B\d+\s*[O0\-]\s*L?\d+', re.I)
    padrao_boletins = re.compile(r'b\w*?t[ií]nh?o?s\s+\d+', re.I)
    
    for seg in segmentos:
        if seg["start"] > 15:
            break
        texto = seg["text"]
        if padrao_faixa.search(texto) or padrao_boletins.search(texto):
            fim_intro = seg["end"]
            
            # Buscar claquete individual dentro do segmento
            if "words" in seg and seg["words"]:
                palavras = seg["words"]
                for idx_w in range(len(palavras) - 1):
                    w = palavras[idx_w]
                    w_norm = w["word"].strip().strip('.,;: ').lower()
                    if re.match(r'^[a-z][\-\s]?\d+$', w_norm):
                        w_prox = palavras[idx_w + 1]["word"].strip().strip('.,;: ').lower()
                        if not re.match(r'^[a-z]?\d+$', w_prox):
                            fim_intro = palavras[idx_w + 1]["start"]
                            return (seg["start"], fim_intro)
            
            for seg2 in segmentos:
                if seg2["start"] <= seg["start"]:
                    continue
                if seg2["start"] > seg["start"] + 15:
                    break
                texto2 = seg2["text"].strip()
                
                if re.match(r'^[A-Z][\-\s]?\d+[\.\s,]', texto2, re.I) and len(texto2) < 80:
                    fim_intro = seg2["end"]
                    continue
                
                palavras = texto2.split()
                if len(palavras) > 8:
                    fim_intro = seg2["start"]
                    break
                
                if len(texto2) < 40:
                    fim_intro = seg2["end"]
                    continue
                
                fim_intro = seg2["start"]
                break
            
            return (seg["start"], fim_intro)
    
    return None


def extrair_palavras(texto: str, min_len: int = 3) -> set:
    """
    Extrai conjunto de palavras significativas de um texto.
    
    Returns:
        Set de palavras unicas (normalizadas, sem stopwords)
    """
    return normalizar_texto(texto).split()
