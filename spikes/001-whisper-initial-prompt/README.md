# 001: whisper-initial-prompt

## Pergunta
Given boletim TJRN transcrito com Whisper base, when usamos initial_prompt com vocabulário do TJRN/RN, then a cobertura de palavras do roteiro aumenta significativamente?

## Hipótese
O Whisper base erra nomes próprios do RN ("Mossoró", "Caicó", "Natal") e termos jurídicos ("réu", "apenado", "remição", "regressão de regime"). Um prompt de contexto deve reduzir essas alucinações.

## Resultados

| Versão | Cobertura | Delta |
|--------|-----------|-------|
| Sem prompt | 85.0% | baseline |
| Prompt curto (cidades + termos) | 83.5% | -1.5% |
| Prompt expandido (cidades + termos + comarcas + juízes) | 66.9% | -18.1% |

## O que funcionou
- Prompt curto teve efeito neutro (dentro da variação)
- Sem prompt já atinge 85% de cobertura

## O que não funcionou
- Prompt expandido **piorou** significativamente: Whisper começou a alucinar termos do prompt ("cento e noventa e nove reais", "GIP infantil elétrico" → "GIP in...")
- O Whisper base tende a "ouvir" palavras do prompt que não existem no áudio

## Surpresas
- O baseline sem prompt já é razoavelmente bom (85%)
- Adicionar mais contexto ao prompt pode ser contraproducente em modelos pequenos

## Recommendation for the real build
**NÃO usar initial_prompt** para Whisper base neste caso. O risco de alucinação induzida supera o ganho potencial. Se necessário, usar apenas um prompt muito curto (1-2 frases) com o nome do programa, sem listar termos específicos.

## Verdict: INVALIDATED
