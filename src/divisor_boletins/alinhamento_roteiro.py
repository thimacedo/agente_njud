#!/usr/bin/env python3
"""
Módulo de alinhamento de roteiro com transcrição Whisper.

Quando um roteiro (texto exato lido pelo locutor) está disponível,
este módulo alinha o texto do roteiro com os segmentos transcritos
para encontrar os limites exatos de CABEÇA e CORPO com alta precisão.

Uso principal:
    - Recebe o texto do roteiro (ex: Google Doc) com marcações **CABEÇA:** e **OFF:**
    - Extrai os textos de CABEÇA e CORPO do roteiro
    - Alinha cada trecho com os segmentos Whisper usando similaridade de sequência
    - Retorna timestamps precisos de início/fim para cada seção
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional, Tuple


@dataclass
class ResultadoAlinhamento:
    """Resultado do alinhamento de um trecho do roteiro."""
    encontrado: bool
    inicio: float = 0.0
    fim: float = 0.0
    confianca: float = 0.0
    metodo: str = ""
    texto_alvo: str = ""
    texto_casado: str = ""


def extrair_cabeca_off(texto_roteiro: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrai os textos de CABEÇA e OFF/CORPO do roteiro.
    
    Formato esperado:
        **CABEÇA:** <texto da manchete>
        
        **OFF:** <texto do corpo>
    
    Ou variações como:
        CABEÇA: ...
        OFF: ...
        # CABEÇA
        # OFF
    
    Returns:
        (texto_cabeca, texto_off) ou (None, None) se não encontrar
    """
    texto_norm = texto_roteiro.strip()
    
    # Padrões para CABEÇA
    padrao_cabeca = re.compile(
        r"(?:\*\*?\s*)?(?:CABEÇA|MANCHETE|HEADLINE)\s*(?:\*\*?)?[:\-]?\s*(.+?)"
        r"(?=(?:\n\s*(?:\*\*?\s*)?(?:OFF|CORPO|BODY)\s*(?:\*\*?)?[:\-]?|\Z))",
        re.IGNORECASE | re.DOTALL
    )
    
    # Padrões para OFF/CORPO
    padrao_off = re.compile(
        r"(?:\*\*?\s*)?(?:OFF|CORPO|BODY)\s*(?:\*\*?)?[:\-]?\s*(.+?)$",
        re.IGNORECASE | re.DOTALL
    )
    
    cabeca_match = padrao_cabeca.search(texto_norm)
    off_match = padrao_off.search(texto_norm)
    
    texto_cabeca = cabeca_match.group(1).strip() if cabeca_match else None
    texto_off = off_match.group(1).strip() if off_match else None
    
    return texto_cabeca, texto_off


def normalizar_para_alinhamento(texto: str) -> str:
    """
    Normaliza texto para alinhamento: remove pontuação excessiva,
    normaliza espaços, mas preserva palavras-chave.
    """
    import unicodedata
    
    # Lowercase
    texto = texto.lower()
    
    # Remove acentos
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    
    # Normaliza pontuação
    texto = re.sub(r"[.,;:!?\"'()—–-]", " ", texto)
    
    # Normaliza espaços múltiplos
    texto = re.sub(r"\s+", " ", texto).strip()
    
    return texto


def alinhar_texto_no_audio(
    segmentos: list[dict],
    texto_alvo: str,
    janela_minima_segmentos: int = 2,
    janela_maxima_segmentos: int = 8,
    limiar_confianca: float = 0.55,
) -> ResultadoAlinhamento:
    """
    Alinha um texto alvo (do roteiro) com os segmentos transcritos.
    
    Estratégia:
    1. Desliza uma janela sobre os segmentos acumulando texto
    2. Compara o texto acumulado com o texto alvo via SequenceMatcher
    3. Retorna a janela com maior similaridade acima do limiar
    
    Args:
        segmentos: Lista de segmentos Whisper [{start, end, text}, ...]
        texto_alvo: Texto do roteiro a ser encontrado
        janela_minima_segmentos: Mínimo de segmentos na janela
        janela_maxima_segmentos: Máximo de segmentos na janela
        limiar_confianca: Similaridade mínima para considerar match
    
    Returns:
        ResultadoAlinhamento com timestamps e confiança
    """
    if not segmentos or not texto_alvo.strip():
        return ResultadoAlinhamento(encontrado=False, metodo="invalido")
    
    texto_alvo_norm = normalizar_para_alinhamento(texto_alvo)
    palavras_alvo = set(texto_alvo_norm.split())
    
    melhor_sim = 0.0
    melhor_janela = None
    melhor_texto = ""
    
    # Janela deslizante
    for i in range(len(segmentos)):
        texto_acumulado = []
        for j in range(i, min(i + janela_maxima_segmentos, len(segmentos))):
            texto_acumulado.append(segmentos[j]["text"])
            
            if j - i + 1 >= janela_minima_segmentos:
                texto_janela = " ".join(texto_acumulado)
                texto_janela_norm = normalizar_para_alinhamento(texto_janela)
                
                # Similaridade global
                sim = SequenceMatcher(None, texto_alvo_norm, texto_janela_norm).ratio()
                
                # Bônus por sobreposição de palavras-chave
                palavras_janela = set(texto_janela_norm.split())
                intersecao = palavras_alvo & palavras_janela
                uniao = palavras_alvo | palavras_janela
                overlap = len(intersecao) / len(uniao) if uniao else 0
                
                # Score combinado
                score_combinado = 0.7 * sim + 0.3 * overlap
                
                if score_combinado > melhor_sim:
                    melhor_sim = score_combinado
                    melhor_janela = (i, j)
                    melhor_texto = texto_janela
    
    if melhor_janela and melhor_sim >= limiar_confianca:
        i, j = melhor_janela
        return ResultadoAlinhamento(
            encontrado=True,
            inicio=segmentos[i]["start"],
            fim=segmentos[j]["end"],
            confianca=round(melhor_sim, 3),
            metodo="alinhamento_roteiro",
            texto_alvo=texto_alvo[:100],
            texto_casado=melhor_texto[:100]
        )
    
    return ResultadoAlinhamento(
        encontrado=False,
        confianca=melhor_sim,
        metodo="alinhamento_roteiro_limiar",
        texto_alvo=texto_alvo[:100]
    )


def alinhar_roteiro_completo(
    segmentos: list[dict],
    texto_roteiro: str,
    limiar_cabeca: float = 0.55,
    limiar_corpo: float = 0.50,
) -> dict:
    """
    Alinha roteiro completo (CABEÇA + OFF) com segmentos de áudio.
    
    Args:
        segmentos: Segmentos Whisper
        texto_roteiro: Texto completo do roteiro
        limiar_cabeca: Limiar de confiança para CABEÇA
        limiar_corpo: Limiar de confiança para CORPO
    
    Returns:
        Dicionário com:
        {
            "sucesso": bool,
            "cabeca": ResultadoAlinhamento,
            "corpo": ResultadoAlinhamento,
            "metodo": str
        }
    """
    texto_cabeca, texto_off = extrair_cabeca_off(texto_roteiro)
    
    resultado = {
        "sucesso": False,
        "cabeca": None,
        "corpo": None,
        "metodo": "roteiro"
    }
    
    # Alinhar CABEÇA
    if texto_cabeca:
        resultado["cabeca"] = alinhar_texto_no_audio(
            segmentos, texto_cabeca, limiar_confianca=limiar_cabeca
        )
    
    # Alinhar CORPO/OFF
    if texto_off:
        resultado["corpo"] = alinhar_texto_no_audio(
            segmentos, texto_off, limiar_confianca=limiar_corpo
        )
    
    # Determinar sucesso
    if resultado["cabeca"] and resultado["cabeca"].encontrado:
        if resultado["corpo"] and resultado["corpo"].encontrado:
            resultado["sucesso"] = True
            resultado["metodo"] = "roteiro_completo"
        else:
            # Pelo menos a cabeça foi encontrada
            resultado["sucesso"] = True
            resultado["metodo"] = "roteiro_parcial_cabeca"
    
    return resultado


# =============================================================================
# INTEGRAÇÃO COM O PIPELINE PRINCIPAL
# =============================================================================

def integrar_alinhamento_roteiro(
    segmentos: list[dict],
    texto_roteiro: Optional[str],
    duracao_total: float,
    fallback_strategy: str = "ancoras_vad",
) -> dict:
    """
    Função de integração para usar no pipeline principal.
    
    Tenta alinhamento por roteiro primeiro. Se falhar ou indisponível,
    retorna instruções para usar estratégia fallback.
    
    Args:
        segmentos: Segmentos Whisper
        texto_roteiro: Texto do roteiro (ou None se indisponível)
        duracao_total: Duração total do áudio
        fallback_strategy: Estratégia fallback ("ancoras_vad", "calibracao", etc.)
    
    Returns:
        Dicionário com limites calculados ou instrução de fallback:
        {
            "metodo_usado": str,
            "inicio_cabeca": float (se disponível),
            "fim_cabeca": float (se disponível),
            "inicio_corpo": float (se disponível),
            "fim_corpo": float (se disponível),
            "confianca": float,
            "fallback_necessario": bool,
            "motivo_fallback": str (se aplicável)
        }
    """
    if not texto_roteiro:
        return {
            "metodo_usado": fallback_strategy,
            "fallback_necessario": True,
            "motivo_fallback": "roteiro_indisponivel"
        }
    
    # Tentar alinhamento
    alinhamento = alinhar_roteiro_completo(segmentos, texto_roteiro)
    
    if alinhamento["sucesso"]:
        resultado = {
            "metodo_usado": alinhamento["metodo"],
            "confianca": max(
                alinhamento["cabeca"].confianca if alinhamento["cabeca"] else 0,
                alinhamento["corpo"].confianca if alinhamento["corpo"] else 0
            ),
            "fallback_necessario": False
        }
        
        if alinhamento["cabeca"] and alinhamento["cabeca"].encontrado:
            resultado["inicio_cabeca"] = alinhamento["cabeca"].inicio
            resultado["fim_cabeca"] = alinhamento["cabeca"].fim
        
        if alinhamento["corpo"] and alinhamento["corpo"].encontrado:
            resultado["inicio_corpo"] = alinhamento["corpo"].inicio
            resultado["fim_corpo"] = alinhamento["corpo"].fim
        
        # Garantir consistência temporal
        if "inicio_corpo" in resultado and "fim_cabeca" in resultado:
            if resultado["inicio_corpo"] <= resultado["fim_cabeca"]:
                resultado["inicio_corpo"] = resultado["fim_cabeca"] + 0.5
        
        return resultado
    
    # Falhou no alinhamento
    return {
        "metodo_usado": fallback_strategy,
        "fallback_necessario": True,
        "motivo_fallback": f"alinhamento_baixa_confianca ({alinhamento['cabeca'].confianca if alinhamento['cabeca'] else 'N/A'})"
    }


if __name__ == "__main__":
    # Teste rápido
    print("Módulo de alinhamento de roteiro - TJRN")
    print("=" * 50)
    
    # Exemplo de uso
    roteiro_exemplo = """
    **CABEÇA:** Tribunal de Justiça lança nova plataforma digital
    
    **OFF:** O sistema permite acompanhamento processual em tempo real
    e integra serviços de todas as comarcas do estado.
    """
    
    segmentos_exemplo = [
        {"start": 0.0, "end": 2.5, "text": "no ar noticias da hora"},
        {"start": 2.5, "end": 6.0, "text": "tribunal de justiça lança nova plataforma digital"},
        {"start": 6.5, "end": 12.0, "text": "o sistema permite acompanhamento processual"},
        {"start": 12.5, "end": 18.0, "text": "e integra serviços de todas as comarcas"},
    ]
    
    cabeca, off = extrair_cabeca_off(roteiro_exemplo)
    print(f"CABEÇA extraída: {cabeca}")
    print(f"OFF extraído: {off}")
    
    if cabeca:
        resultado = alinhar_texto_no_audio(segmentos_exemplo, cabeca)
        print(f"\nAlinhamento CABEÇA: encontrado={resultado.encontrado}, confiança={resultado.confianca}")
        if resultado.encontrado:
            print(f"  Timestamps: {resultado.inicio:.1f}s → {resultado.fim:.1f}s")
