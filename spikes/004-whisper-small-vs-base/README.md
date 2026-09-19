# 004: whisper-small-vs-base

## Pergunta
Given pipeline com Whisper base (74M params, 85% cobertura), when substituir por Whisper small (466M params), then a cobertura aumenta significativamente (>90%)?

## Hipótese
O modelo small tem 6x mais parâmetros e deve transcrever melhor nomes próprios, termos jurídicos e números.

## Resultados

| Áudio | Base cobertura | Small cobertura | Base tempo | Small tempo | Delta | Slowdown |
|-------|---------------|-----------------|------------|-------------|-------|----------|
| 17 SET B1-B5 | 85.5% | **94.5%** | 57.7s | 143.5s | **+9.1%** | 2.5x |
| 04 SET B1-B4 | 54.8% | **59.5%** | 48.9s | 122.7s | **+4.8%** | 2.5x |

## O que funcionou
- Small melhora consistentemente a cobertura (+5-9%)
- Em áudio de boa qualidade, atinge 94.5% de cobertura
- Melhora é mais pronunciada em áudios com fala clara

## O que não funcionou
- 2.5x mais lento (aceitável para batch, mas relevante para tempo total)
- Em áudio de baixa qualidade, melhora é modesta (+4.8%)

## Surprises
- A diferença é maior em áudios de boa qualidade (17 SET vs 04 SET)
- O small pode valer a pena para produção final, com base para calibração rápida

## Recommendation for the real build
**MANTER base como padrão**, mas oferecer small como opção para reprocessamento de qualidade. O pipeline atual usa base para velocidade; se a cobertura for insuficiente (<70%), reprocessar com small.

Para o caso de uso atual (17 SET B1-B5), small atinge 94.5% — mas o base já atinge 85% que é suficiente para validação.

## Verdict: VALIDATED (com ressalvas)
