# 003: spectral-vinheta-detection

## Pergunta
Given áudio com vinheta de abertura ("No ar, notícias da hora..."), when detectar por correlação espectral (scipy.signal.correlate) contra asset de referência (VHT_ABERTURA_BOLETIM.mp3), then identificar o início/fim da vinheta sem depender do Whisper?

## Hipótese
A vinheta de abertura é idêntica em todos os boletins. Por correlação de forma de onda (cross-correlation), podemos encontrar onde ela ocorre no áudio com precisão de milissegundos.

## Resultados

| Áudio | Detectado | Score |
|-------|-----------|-------|
| 01 SET B6-B10.mp3 | ❌ | 0.022 |
| 10 SET B6-B10.mp3 | ❌ | 0.017 |
| 04 SET - B6 E B7.mp3 | ❌ | 0.027 |

**Threshold usado:** 0.5
**Score máximo obtido:** 0.027

## O que funcionou
- O código executou sem erros (após correção do JSON)
- A correlação espectral roda em <1s por arquivo

## O que não funcionou
- **Scores extremamente baixos** (0.017-0.027) — muito abaixo do threshold (0.5)
- A vinheta no áudio bruto é **diferente** do asset de referência
- Possíveis causas: mixagem com BG, ruído de gravação, compressão MP3 diferente, ou a vinheta do áudio bruto não é idêntica ao asset isolado

## Surpresas
- A correlação espectral é muito sensível a diferenças de mixagem/qualidade
- O asset de referência (VHT_ABERTURA_BOLETIM.mp3) pode ser a vinheta "limpa" que é mixada depois da gravação, não a que aparece no áudio bruto

## Recommendation for the real build
**NÃO usar correlação espectral** para detectar vinhetas em áudios brutos. O Whisper já detecta a vinheta pela transcrição ("No ar, notícias da hora...") de forma mais confiável. Para detectar o fim da vinheta (início do conteúdo real), usar o padrão de transcrição: procurar primeiro segmento significativo (>5 palavras) após a vinheta.

## Verdict: INVALIDATED
