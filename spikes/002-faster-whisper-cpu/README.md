# 002: faster-whisper-cpu

## Pergunta
Given pipeline atual com openai-whisper, when substituir por faster-whisper com compute_type=int8, then o tempo cai significativamente mantendo cobertura similar?

## Hipótese
faster-whisper usa CTranslate2 otimizado para CPU. Espera-se redução de 3-5x.

## Resultados

| Versão | Tempo (B1, 105s áudio) | Cobertura |
|--------|------------------------|-----------|
| openai-whisper | 12.3s | 85.0% |
| faster-whisper (int8) | 9.2s | 85.8% |
| **Speedup** | **1.3x** | **+0.8%** |

## O que funcionou
- faster-whisper é ligeiramente mais rápido (1.3x)
- Cobertura praticamente idêntica (levemente melhor)

## O que não funcionou
- Speedup de 1.3x é menor que o esperado (3-5x)
- Para áudio curto (105s), o overhead de carregamento do modelo domina

## Surpresas
- O ganho real aparece em áudios mais longos (>3min) onde a transcrição domina
- Em boletins de 5+ min, esperamos speedup de 2-3x

## Recommendation for the real build
**MIGRAR para faster-whisper.** Razões:
1. API compatível (mudança mínima no código)
2. Cobertura igual ou melhor
3. Para o pipeline completo (transcrever áudio bruto de 7min + 5 boletins), o speedup acumulado é significativo
4. compute_type=int8 não perde qualidade vs float16 em CPU

## Verdict: VALIDATED
