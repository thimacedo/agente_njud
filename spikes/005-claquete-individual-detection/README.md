# 005: claquete-individual-detection

## Pergunta
Given boletim com claquete individual no início ("B3. Dona de lava-jato..."), when detectar por padrão regex + duração curta, then remover sem afetar conteúdo real?

## Hipótese
Claquetes individuais seguem padrão: começam com B{N} ou M{N} ou V{N}, têm duração curta (<4s).

## Resultados

### Boletins editados (B1-B5)
- B1-B2: Sem claquete individual (já removida pelo pipeline)
- B3: "M3." detectado (alucinação Whisper, 1s)
- B4-B5: Sem claquete individual

### Boletins brutos (amostra aleatória)
- `17 SET B1-B5.mp3`: "Bolitens 17 do 9 do B1O5" (claquete geral, já removida)
- `04 SET - B6 E B7.mp3`: "B5, 4 de setembro..." (vinheta de data)
- `04 SET B1-B4.mp3`: "B1, 4 de setembro." detectado como claquete (2s)

## O que funcionou
- Padrão regex `^(?:[BMV]\d{1,2})[\s.,:\-–—]` detecta claquetes B{N}, M{N}, V{N}
- Duração < 4s como critério de claquete vs conteúdo

## O que não funcionou
- Claquetes em boletins editados já foram removidas pelo pipeline
- A detecção por regex pega "B1, 4 de setembro" que inclui data (não deveria remover data)

## Surprises
- O Whisper alucina "M3." em boletins editados onde não existe claquete
- Claquetes individuais em ários brutos são raras — a maioria começa com claquete geral

## Recommendation for the real build
**PARCIAL:** A detecção funciona mas o cenário principal (boletins editados) não tem mais claquetes para remover. Para áudios brutos, a lógica atual do pipeline (detectar claquete geral + cortar até conteúdo real) já é suficiente. Se necessário adicionar remoção de claquete individual, usar threshold mais restritivo: duração < 2s E texto < 30 chars.

## Verdict: PARTIAL
