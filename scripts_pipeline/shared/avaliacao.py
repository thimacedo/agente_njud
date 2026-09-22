#!/usr/bin/env python3
"""
avaliacao.py — Avaliação semântica de transcrição após cortes.

Regra principal: Após cortes no áudio, avalia se o sentido foi preservado,
não apenas palavras literais. Isso permite que o locutor reescreva trechos
(correções, cacofonias) sem reprovação injusta.

Critérios:
- Sentido (semântica) >= 70% → OK
- Entidades (nomes, valores, termos) >= 80% → OK
- Cobertura literal é informativa mas NÃO reprova sozinha
"""
import re
from dataclasses import dataclass, field

from shared.text_utils import normalizar_texto
from shared.core import calcular_cobertura_roteiro


# Termos jurídicos/essenciais que NÃO podem ser perdidos
TERMOS_ESSENCIAIS = {
    "instituicoes": [
        "tjrn", "tribunal", "justica", "camara", "criminal", "ministerio",
        "publico", "defensoria", "delegacao", "vara", "juizado", "comarca",
        "ferias", "policia", "civil", "federal", "eleitoral"
    ],
    "acoes": [
        "condenou", "reformou", "negou", "manteve", "afastou", "reconheceu",
        "aplicou", "determinou", "suspendeu", "anulou", "julgou", "sentenciou",
        "absolveu", "denegou", "concedeu", "indeferiu"
    ],
    "direito": [
        "remicao", "pena", "regime", "progressao", "regressao", "detencao",
        "prisao", "fuga", "cumpriu", "sentenca", "acusacao", "defesa",
        "recurso", "apelacao", "autos", "reu", "autora"
    ]
}

STOPWORDS = {
    "a", "o", "e", "de", "do", "da", "em", "um", "uma", "que", "para",
    "com", "por", "na", "no", "os", "as", "dos", "das", "se", "ao", "aos",
    "ou", "como", "mais", "mas", "ser", "foi", "sao", "tambem", "ate", "nao",
    "pelo", "pela", "seus", "sua", "suas", "dele", "dela", "entre", "sobre",
    "apos", "durante", "sem", "ja", "ainda", "quando", "cada", "mesmo", "bem",
    "onde", "isso", "este", "esta", "estas", "estes", "aquele", "aquela",
    "ele", "ela", "eles", "elas", "nos", "voce", "meu", "minha", "teu", "tua"
}


@dataclass
class ResultadoAvaliacao:
    """Resultado da avaliação semântica."""
    aprovado: bool
    score_sentido: float
    score_entidades: float
    score_literal: float
    score_final: float
    detalhes: dict = field(default_factory=dict)
    motivo: str = ""


def extrair_entidades(texto: str) -> dict:
    """
    Extrai entidades nomeadas do texto.
    
    Returns:
        {"valores": [...], "datas": [...], "nomes_proprios": [...], "termos_essenciais": [...]}
    """
    texto_lower = texto.lower()
    entidades = {
        "valores": [],
        "datas": [],
        "nomes_proprios": [],
        "termos_essenciais": []
    }
    
    # Valores monetários
    padrao_valores = r'(r\$[\s]?\d[\d.,]*(?:\s*mil|\s*milh[oõ]es?)?|\d[\d.,]*\s*(?:reais|mil|milh[oõ]es?))'
    entidades["valores"] = re.findall(padrao_valores, texto_lower)
    
    # Datas
    padrao_datas = r'\d{1,2}\s+de\s+(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de\s+\d{4})?'
    entidades["datas"] = re.findall(padrao_datas, texto_lower)
    
    # Nomes próprios
    palavras = texto.split()
    for palavra in palavras:
        if palavra[0].isupper() and len(palavra) > 3:
            nome = palavra.strip('.,;:()').lower()
            if nome not in STOPWORDS:
                entidades["nomes_proprios"].append(nome)
    
    # Termos essenciais
    for categoria, termos in TERMOS_ESSENCIAIS.items():
        for termo in termos:
            if termo in texto_lower:
                entidades["termos_essenciais"].append(termo)
    
    return entidades


def calcular_preservacao_entidades(roteiro: str, transcricao: str) -> tuple:
    """
    Calcula % de entidades do roteiro presentes na transcrição.
    
    Returns:
        (score_0_1, detalhes_dict)
    """
    ent_roteiro = extrair_entidades(roteiro)
    ent_transcricao = extrair_entidades(transcricao)
    
    detalhes = {}
    total_entidades = 0
    preservadas = 0
    
    for tipo in ["valores", "datas", "nomes_proprios", "termos_essenciais"]:
        roteiro_set = set(ent_roteiro[tipo])
        transcricao_set = set(ent_transcricao[tipo])
        
        if roteiro_set:
            preservadas_tipo = len(roteiro_set & transcricao_set)
            total_tipo = len(roteiro_set)
            detalhes[tipo] = {
                "total": total_tipo,
                "preservadas": preservadas_tipo,
                "score": preservadas_tipo / total_tipo if total_tipo > 0 else 1.0
            }
            total_entidades += total_tipo
            preservadas += preservadas_tipo
    
    score = preservadas / total_entidades if total_entidades > 0 else 1.0
    return score, detalhes


def calcular_similaridade_semantica(roteiro: str, transcricao: str) -> float:
    """
    Calcula similaridade semântica usando bag-of-words ponderado.
    
    Peso maior para palavras significativas e termos essenciais.
    """
    palavras_roteiro = normalizar_texto(roteiro).split()
    palavras_transcricao = normalizar_texto(transcricao).split()
    
    if not palavras_roteiro or not palavras_transcricao:
        return 0.0
    
    def calcular_tf(palavras):
        tf = {}
        for p in palavras:
            tf[p] = tf.get(p, 0) + 1
        return tf
    
    tf_roteiro = calcular_tf(palavras_roteiro)
    tf_transcricao = calcular_tf(palavras_transcricao)
    
    def peso_palavra(p):
        if p in STOPWORDS:
            return 0.5
        for categoria, termos in TERMOS_ESSENCIAIS.items():
            if p in termos:
                return 3.0
        return 2.0
    
    todas_palavras = set(palavras_roteiro) | set(palavras_transcricao)
    
    produto_escalar = 0.0
    norma_roteiro = 0.0
    norma_transcricao = 0.0
    
    for palavra in todas_palavras:
        peso = peso_palavra(palavra)
        v_roteiro = tf_roteiro.get(palavra, 0) * peso
        v_transcricao = tf_transcricao.get(palavra, 0) * peso
        
        produto_escalar += v_roteiro * v_transcricao
        norma_roteiro += v_roteiro ** 2
        norma_transcricao += v_transcricao ** 2
    
    if norma_roteiro == 0 or norma_transcricao == 0:
        return 0.0
    
    similaridade = produto_escalar / (norma_roteiro ** 0.5 * norma_transcricao ** 0.5)
    return min(similaridade, 1.0)


def avaliar_transcricao(roteiro: str, transcricao: str) -> ResultadoAvaliacao:
    """
    Avalia se a transcrição mantém o sentido do roteiro após cortes.
    
    Regra:
    - Sentido >= 70% E Entidades >= 80% → APROVADO
    - Cobertura literal é informativa mas não reprova sozinha
    
    Isso permite que o locutor reescreva trechos (correções, cacofonias)
    sem reprovação injusta, desde que o sentido seja preservado.
    """
    # Camada 1: Sentido (peso 50%)
    score_sentido = calcular_similaridade_semantica(roteiro, transcricao)
    
    # Camada 2: Entidades (peso 30%)
    score_entidades, detalhes_entidades = calcular_preservacao_entidades(roteiro, transcricao)
    
    # Camada 3: Cobertura literal (peso 20%, informativa)
    score_literal, _, _ = calcular_cobertura_roteiro(transcricao, roteiro)
    
    # Decisão: sentido E entidades são obrigatórios
    aprovado = score_sentido >= 0.70 and score_entidades >= 0.80
    
    # Score final ponderado
    score_final = (
        score_sentido * 0.50 +
        score_entidades * 0.30 +
        score_literal * 0.20
    )
    
    if not aprovado:
        if score_sentido < 0.70:
            motivo = f"Sentido insuficiente ({score_sentido:.0%} < 70%)"
        else:
            motivo = f"Entidades perdidas ({score_entidades:.0%} < 80%)"
    else:
        motivo = "Sentido e entidades preservados"
    
    return ResultadoAvaliacao(
        aprovado=aprovado,
        score_sentido=score_sentido,
        score_entidades=score_entidades,
        score_literal=score_literal,
        score_final=score_final,
        detalhes={"entidades": detalhes_entidades},
        motivo=motivo
    )
