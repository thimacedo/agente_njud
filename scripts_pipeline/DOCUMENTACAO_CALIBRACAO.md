# Documentação de Calibração — Divisor de Boletins (Audios Brutos)

**Data:** 2026-09-17  
**Última revisão:** 2026-09-21 (status atualizado — ver abaixo)  
**Contexto:** Calibração do divisor de boletins para áudios sem vinhetas inseridas (brutos).  
**Objetivo:** Processar 17 arquivos mp3 que contêm múltiplos boletins radiateis semanais do TJRN, separando-os e removendo repetições.

---

## 0. STATUS (2026-09-21) — LEIA ANTES DE USAR ESTE DOCUMENTO

Este documento é **histórico**: registra a investigação de calibração que levou ao pipeline atual. Partes dele foram **superadas**:

| Seção | Status | Observação |
|-------|--------|------------|
| 1-5 (análise de arquivos, correlação, gaps, modelos, padrões) | **VÁLIDA** | Descobertas empíricas que continuam verdadeiras |
| 6 (estratégia de divisão por "Boletim número N") | **SUPERADA** | O pipeline canônico divide por **assinaturas do locutor** ("Tribunal de Justiça do Rio Grande do Norte, [nome]"), não por cabeçalhos falados. Validado 5/5 no 18 SET B6-B10 |
| 7 (padrões por tipo de arquivo) | **VÁLIDA** | Nomenclatura e faixas seguem corretas |
| 8 (remoção de repetições) | **PARCIALMENTE SUPERADA** | Implementado no canônico como ETAPA 3 (`detectar_repeticoes_confirmadas`, confirmação por áudio) + ETAPA 1.5 (`corrigir_alucinacoes.py`) |
| 9 (plano de teste) | **SUPERADA** | Substituído pela auditoria proativa (`scripts_pipeline/boletim/auditoria_proativa.py`) |
| 10-11 (implementação: `calibrar_divisor.py`, `boletins_div/`) | **OBSOLETA** | `calibrar_divisor.py` **nunca foi commitado** (perdido na sessão de 17/09); a funcionalidade foi absorvida pelo canônico. `boletins_div/` nunca existiu |
| 12 (pendências) | **SUPERADA** | Ver estado real abaixo |
| 13 (lições) | **VÁLIDA** | Todas as 8 lições foram incorporadas à skill `divisor-pipeline` |

**Implementação atual (fonte de verdade):** `scripts_pipeline/boletim/processar_boletim_canonico.py`

```
python scripts_pipeline/boletim/processar_boletim_canonico.py "boletins/DD SET Bn-N.mp3" --roteiros boletins/
```

Saída: `boletins/<arquivo>_saida/` com boletins editados + `auditoria.json` + `auditoria_proativa.json`.

**Estado real das pendências da seção 12 (2026-09-21):**
- [x] Otimização: migrado para `faster-whisper` (commit 2539d23, 1.3x speedup, int8 CPU)
- [x] Execução validada: 18 SET B6-B10 (5/5 aprovados) e 17 SET B1-B5 (com bugs A/B/C documentados no Item 18 de `docs/decisoes/DECISOES.md`)
- [x] Remoção de repetições: implementada (ETAPA 3 + 1.5 do canônico)
- [x] Documentação: DECISOES.md Item 18, CHANGELOG.md, skill `divisor-pipeline`
- [ ] Calibração completa dos 17 arquivos brutos restantes: **pendente** (apenas 17 SET e 18 SET processados; 15 arquivos aguardam)
- [ ] Bugs A/B/C do 17 SET B1-B5: **pendente** (detalhados no Item 18)

---


## 1. Visão Geral dos Arquivos

### 1.1 Lista Completa

```
01 SET B6-B10.mp3          591s   13.5 MB   Esperado: 5 boletins (B6-B10)
02 SET B8-B10.mp3          292s    6.7 MB   Esperado: 3 boletins (B8-B10)
04 SET - B6 E B7.mp3       328s    7.5 MB   Esperado: 2 boletins (B6-B7)
04 SET B1-B4.mp3           417s    9.5 MB   Esperado: 4 boletins (B1-B4)
04 SET B8-B10.mp3          282s    6.5 MB   Esperado: 3 boletins (B8-B10)
08 SET B1-B5.mp3           565s   12.9 MB   Esperado: 5 boletins (B1-B5)
08 SET B6-B10.mp3          413s    9.5 MB   Esperado: 5 boletins (B6-B10)
09 SET B6-B10.mp3          551s   12.6 MB   Esperado: 5 boletins (B6-B10)
090 SET B1-B5.mp3          518s   11.9 MB   Esperado: 5 boletins (B1-B5)
10 SET B6-B10.mp3          595s   13.6 MB   Esperado: 5 boletins (B6-B10)
10 ST B1-B5.mp3            455s   10.4 MB   Esperado: 5 boletins (B1-B5)
11 SET B1- B5.mp3          465s   10.6 MB   Esperado: 5 boletins (B1-B5)
14 SET B1 - B10.mp3       1100s   25.2 MB   Esperado: 10 boletins (B1-B10)
15 SET B1- B5.mp3          441s   10.1 MB   Esperado: 5 boletins (B1-B5)
16 SET B1B5.mp3            404s    9.3 MB   Esperado: 5 boletins (B1-B5)
17 SET B1-B5.mp3           440s   10.1 MB   Esperado: 5 boletins (B1-B5)
18 SET B6-B10.mp3          535s   12.3 MB   Esperado: 5 boletins (B6-B10)
```

**Total: 17 arquivos, ~9.670s de áudio (~2.7 horas)**

### 1.2 Padrão de Nomenclatura

- `DD SET B1-B5.mp3` — data + "SET" + faixa B1-B5
- `DD SET B6-B10.mp3` — data + "SET" + faixa B6-B10
- `DD SET - B6 E B7.mp3` — data + "SET" + faixa B6 E B7
- `DD ST B1-B5.mp3` — data + "ST" + faixa (variante)
- `DD SET B1B5.mp3` — data + faixa sem separador (variante)
- `DD SET B1 - B10.mp3` — data + faixa com hífens (variante)

**Padrão universal:** `<data> SET [variante] B<inicio> [-/E] B<fim>.mp3`

---

## 2. Verificação: Áudios São Verdadeiramente Brutos

### 2.1 Teste de Correlação Espectral

**Método:** Correlacionar o áudio de cada arquivo com a vinheta de abertura conhecida (`VHT_ABERTURA_BOLETIM.mp3`, 11.15s).

**Resultado para 18 SET B6-B10.mp3:**
- Múltiplos picos de correlação detectados em berbagai posições
- **Nenhum pico correlaciona com a vinheta exata** (a correlação máxima era ~149 em escala de 1M+ de amostras — ruído de fundo, não detecção real)
- **Conclusão:** os áudios NÃO contêm vinhetas gravadas. São brutos.

### 2.2 Implicações

Sem vinhetas como âncoras, **não é possível** usar a correlação espectral para detectar limites entre boletins. A separação deve ser feita por análise de conteúdo.

---

## 3. Análise de Gaps de Silêncio

### 3.1 Metodologia

Para cada arquivo, detectou-se segmentos de fala com `pydub.silence.detect_nonsilent()` em vários thresholds (-20, -25, -30, -35 dB) e verificou-se gaps > 1s e > 3s entre segmentos.

### 3.2 Resultados

| Arquivo | Duração | Gaps ≥3s encontrados | Necessário para N boletins |
|---------|---------|---------------------|---------------------------|
| 11 SET B1-B5.mp3 | 465s | 2 | 4 |
| 18 SET B6-B10.mp3 | 535s | 0 | 4 |
| 14 SET B1-B10.mp3 | 1100s | 3 | 9 |
| 02 SET B8-B10.mp3 | 292s | 0 | 2 |
| 04 SET - B6 E B7.mp3 | 328s | 2 | 1 |

**Conclusão chave:** A maioria dos arquivos **não possui gaps longos suficientes** para separação automática por silêncio. O limite entre boletins é apenas uma transição de assunto sem pausa significativa.

### 3.3 Implicação

**Dividir por silêncio não funciona** para estes áudios. A estratégia deve ser de conteúdo.

---

## 4. Comparação de Modelos Whisper

### 4.1 Metodologia

Transcrever os primeiros 40s de 3 arquivos representativos (11 SET B1-B5.mp3, 08 SET B1-B5.mp3, 14 SET B1-B10.mp3) com `tiny` e `base`, e comparar qualidade.

### 4.2 Resultados — Exemplo: 11 SET B1-B5.mp3 (primeiros 40s)

**Tiny:**
```
[0.0-9.1s]  Brutins 11 do 9 do B5, B1, o meio é condenado após a grida excompõe na irra-grave da inção
[9.1-11.3s] consalo do Amorante.
[11.3-16.9s] O um infocondenado há dois anos, dez meses e 15 dias de retlusão pelo crime de lesão
[16.9-22.0s] corporal praticada contra a ismolear, no contexto da lei Maria da Penha.
...
```

**Base:**
```
[0.0-5.3s]  Boletins 11 de setembro, do B1 ao B5.
[5.3-10.5s] homem é condenado após agredir esse companheiro a grávida em São Gonçalo do Amarante.
[10.5-19.0s] O homem foi condenado há dois anos, dez meses e quinze dias de reclusão, pelo crime de lesão
[19.0-21.5s] corporal praticada contra a esposa, no contexto da Lei Maria da Penha.
[21.5-28.7s] De acordo com a sentença, a segunda vara da comarca de São Gonçalo do Amarante, a pena deve ser cumprida inicialmente em regime aberto.
...
```

### 4.3 Telemetry de Erros

| Aspecto | Tiny | Base |
|---------|------|------|
| Fidelidade geral | 40-50% | 80-90% |
| Nome do arquivo | "Brutins" | "Boletins" |
| Faixa de boletins | "B5, B1" | "B1 ao B5" |
| Nomes próprios (cidades) | "irra-grave da inção" | "São Gonçalo do Amarante" |
| Termos jurídicos | "lesão corporal" (OK) | "lesão corporal" (OK) |
| Relação causa/efeito | "is momoler" | "esposa" |
| Numeração | Confusa | Clara |

### 4.4 Conclusão

**Base >> tiny para áudio bruto de boletins.** O tiny transcreve com taxa de erro tão alta que perde o sentido — "Brutins" em vez de "Boletins", "is momoler" em vez de "esposa", "irra-grave da inção" em vez de cidade real.

- **tiny:** Apenas para testes rápidos / busy-loop. Não confiável para divisão por conteúdo.
- **base:** Mínimo aceitável. Consegue capturar o cabeçalho "Boletins X de setembro, do B1 ao B5" e distinguir repetições de novo tópico.
- **small:** Melhor ainda, mas 3-4x mais lento. Reservar para validação/finalização.

**Recomendação:** Usar `base` para a fase de divisão. tiny não serve.

---

## 5. Padrões de Estrutura Detectados

### 5.1 Cabeçalho de Entrada (presente em todos os arquivos)

Cada arquivo começa com uma frase de identificação falada:

```
"BOLETINS <DATA> DE <MÊS>, DO B<INICIO> AO B<FIM>"
```

Exemplos extraídos da transcrição do 11 SET B1-B5.mp3 com base:
- `"Boletins 11 de setembro, do B1 ao B5."`

Exemplos do 14 SET B1-B10.mp3 (base):
- `"Boletim 14 de setembro."`

### 5.2 Estrutura de Cada Boletim Individual

Após o cabeçalho, o conteúdo flui continuamente. Cada boletim individual começa com uma transição que pode ser:

1. **Explicitórias:** `"Boletim número N —"` ou `"Boletím N..."` (detectável via regex no transcript)
2. **Implícitas:** Mudança de assunto (nova notícia, novo local, nova data)

### 5.3 Repetições Dentro do Boletim

Detectadas em 14 SET B1-B10.mp3 (40s iniciais, base):

```
[19.2-25.4s] A medida foi tomada em uma ação civil pública que tramita desde 2006 e discute a construção do Próso...
[25.4-26.4s] Repete.
[26.4-32.7s] A medida foi tomada em uma ação civil pública que tramita desde... tramita.
[32.7-33.7s] Repete.
[33.7-40.1s] A medida foi tomada em uma ação civil pública que tramita desde 2006 e discute a construção do empreg...
```

O locutor diz "Repete." e reformula a frase. Isso **não é** um novo boletim — é uma correção dentro do mesmo boletim. O divisor deve detectar "Repete." e remover a repetição, não tratá-la como novo início.

---

## 6. Estratégia de Divisão Proposta

### 6.1 Algoritmo

```
PARA cada arquivo mp3:
  1. Transcrever áudio completo com Whisper base (ou small para maior precisão)
  2. No transcript, detectar TODAS as ocorrências de:
     a) "Boletim número N" / "Boletím N" → início de boletim #N
     b) "Repete." → marca de repetição (para remover, não para cortar)
     c) Mudança de data/local/assunto significativa → possível novo boletim
  3. Agrupar as detecções:
     - Ignorar "Repete." para divisão
     - Manter apenas início de boletim real (padrão a)
     - Usar mudanças de assunto como fallback quando padrão a não detectado
  4. Gerar cortes entre boletins detectados
  5. Exportar cada boletim como arquivo separado
  6. Nome do arquivo: DDMM_B{N}_{titulo_curto}.mp3
  7. Para cada boletim isolado:
     a. Detectar repetições dentro dele (segmentos com similaridade >80%)
     b. Remover as repetições (manter a versão correta)
     c. Exportar versão final
```

### 6.2 Detectores de Início de Boletim

| Padrão | Regex | Exemplo no áudio |
|--------|-------|-----------------|
| Tipo 1 (explícito) | `Boletim[s]?\s*(número|nº)?\s*(\d+)` | "Boletim número 3" |
| Tipo 2 (abreviado) | `\bB(\d{1,2})\b` com contexto | "B3" perto de "boletim" |
| Tipo 3 (data+local) | Palavra-chave de data + novo local | "na terça-feira" vs "na quinta-feira" |
| Fallback | Embedding de mudança de assunto | Comparar embedding de segmentos adjacentes |

### 6.3 Filtro Anti-Falso-Positivo

**Ignorar** quando o padrão B\d+ aparece em:
- `"do B1 ao B5"` (faixa, não individual)
- `"B6 e B7"` (faixa, não individual)
- `"B1-B10"` (faixa, não individual)

**Critério:** O match só é válido se o contexto dentro de 20 caracteres include "boletim", "nº", "número", ou se for precedido por pause > 2s + nova citação de data/local.

---

## 7. Padrões por Tipo de Arquivo

### 7.1 B1-B5 (5 boletins, média ~95s cada)

Exemplos: 11 SET B1-B5.mp3, 08 SET B1-B5.mp3, 15 SET B1-B5.mp3, 16 SET B1B5.mp3, 17 SET B1-B5.mp3, 090 SET B1-B5.mp3, 10 ST B1-B5.mp3

- Cabeçalho: `"Boletins [data] de setembro, do B1 ao B5."`
- Esperado: 4 cortes (separando 5 boletins)
- Espaço médio por boletim: ~90-100s

### 7.2 B6-B10 (5 boletins, média ~110s cada)

Exemplos: 18 SET B6-B10.mp3, 10 SET B6-B10.mp3, 09 SET B6-B10.mp3, 08 SET B6-B10.mp3, 01 SET B6-B10.mp3

- Cabeçalho: `"Boletins [data] de setembro, do B6 ao B10."`
- Esperado: 4 cortes
- Espaço médio por boletim: ~105-120s

### 7.3 B8-B10 (3 boletins, média ~97s cada)

Exemplos: 02 SET B8-B10.mp3, 04 SET B8-B10.mp3

- Cabeçalho: `"Boletins [data] de setembro, do B8 ao B10."`
- Esperado: 2 cortes

### 7.4 Faixas Menores (2-4 boletins)

- `04 SET - B6 E B7.mp3`: 2 boletins, cabeçalho `"B6 e B7"`
- `04 SET B1-B4.mp3`: 4 boletins

### 7.5 Faixa Completa (10 boletins)

- `14 SET B1 - B10.mp3`: 10 boletins, ~1100s (~18 min)
- Caso mais complexo — requer 9 cortes precisos

---

## 8. Estratégia de Remoção de Repetições

### 8.1 Tipos de Repetição Detectados

1. **"Repete." explícito:** O locutor diz "Repete." e refaz a frase. Detectável via regex.
2. **Repetição involuntária:** O locutor repete parte da frase sem dizer "Repete." Detectável via similaridade de texto (difflib.SequenceMatcher > 0.85).
3. **Claquetes:** Trechos curtos (< 2s) que se repetem. Detectável via análise de gaps.

### 8.2 Algoritmo de Detecção

```
PARA cada boletim isolado:
  1. Transcrever com Whisper base
  2. Para cada par de segmentos adjacentes (ou com até 5s de distância):
     - Calcular similaridade de texto (SequenceMatcher)
     - Se similaridade > 0.85:
       a. Se o segundo segmento contém "Repete.": remover o primeiro
       b. Se não: remover o segundo (o primeiro é a versão correta)
     - Se o primeiro segmento tem < 2s e similaridade > 0.9:
       → claquette, remover ambos e juntar o restante
  3. Exportar a versão limpa
```

### 8.3 Filtro de Contexto

Ignorar similaridade alta quando:
- Os segmentos têm mais de 5s de distância temporal (não são consecutivos)
- O texto é muito curto (< 10 palavras) — poderia ser coincidência
- Um dos segmentos inclui nome próprio ou número que difere

---

## 9. Calibração e Validação

### 9.1 Plano de Teste

| Fase | O que testar | Como validar |
|------|-------------|--------------|
| 1. Divisão | Separar B1-B5 de 11 SET B1-B5.mp3 | Verificar que cada parte tem 1 boletim, sem sobreposição |
| 2. Divisão complexa | Separar 10 boletins de 14 SET B1-B10.mp3 | Contar se foram gerados 10 arquivos |
| 3. Faixas pequenas | Separar 2 boletins de 04 SET - B6 E B7.mp3 | Verificar 2 arquivos gerados |
| 4. Remoção de repetições | Processar cada boletim isolado | Verificar que "Repete." foi removido |
| 5. Validação cruzada | Comparar nomes dos arquivos gerados vs nomes esperados | Verificar fórmula DDMM_B{N}_*.mp3 |

### 9.2 Critério de Sucesso

- **Divisão:** 100% dos arquivos geram N-1 cortes para N boletins esperados
- **Remoção de repetições:** Zero ocorrências de "Repete." nos arquivos finais
- **Nomes:** Todos os arquivos gerados seguem o padrão `DDMM_B{N}_*.mp3`

### 9.3 Fonte de Verdade

Os arquivos originais em `E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\boletins\` são a fonte. Nenhuma modificaçãoneles. Saída em pasta separada.

---

## 10. Implementação

### 10.1 Script de Calibração

Arquivo: `E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\scripts_pipeline\calibrar_divisor.py`

**Status:** Implementado, porém com timeout (Whisper base demora ~2-4 min por arquivo de 10 min). Needs otimização ou execução em lote com timeout maior.

### 10.2 Dependências

- `pydub` (já disponível no venv do Hermes)
- `whisper` (openai-whisper, versão 20250625, já instalada)
- `faster-whisper` (disponível, mas não usado — API incompatível com código existente)
- `numpy`, `scipy` (já disponíveis)

### 10.3 Modelo Recomendado

```python
import whisper
modelo = whisper.load_model("base")  # 142MB, ~2-4 min por arquivo de 10 min em CPU
```

**Alternativa se base for muito lenta:** Usar `tiny` para a fase de detecção de início de boletim (só precisa detectar o cabeçalho e posição de "Boletim número N"), e `base` para a fase de remoção de repetições (precisa de precisão).

---

## 11. Arquivos Relevantes

| Caminho | Descrição |
|---------|-----------|
| `E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\boletins\` | Áudio bruto (17 arquivos mp3) |
| `E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\assets\vinhetas\boletim\VHT_ABERTURA_BOLETIM.mp3` | Vinheta de referência (não presente nos áudios brutos) |
| `E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\scripts_pipeline\calibrar_divisor.py` | Script de calibração (implementado, com timeout) |
| `E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\boletins_div\` | Saída dos arquivos divididos (a criar) |

---

## 12. Pendências

- [ ] Otimizar script para rodar sem timeout (background process ou streaming)
- [ ] Executar calibração completa em todos os 17 arquivos
- [ ] Validar que a divisão está correta para cada tipo de faixa
- [ ] Implementar e testar remoção de repetições dentro de cada boletim
- [ ] Documentar resultados da calibração (arquivos gerados, cortes detectados)
- [ ] Se necessário, ajustar threshold de similaridade para remoção de repetições

---

## 13. Lições Aprendidas (Resumo)

1. **Áudios são brutos** — sem vinhetas. Divisão por correlação espectral não funciona.
2. **Silêncios não servem** como separadores — gaps > 3s são raros ou inexistentes.
3. **Whisper base é o mínimo** para áudio bruto — tiny transcreve com 40-50% de erro e perde o sentido.
4. **A separação é por conteúdo** — detectar padrões como "Boletim número N" no transcript.
5. **"Repete." é marca de repetição, não novo boletim** — o algoritmo de divisão deve ignorá-lo.
6. **Faixas variam** (B1-B5, B6-B10, B8-B10, B6 E B7, B1-B10) — o algoritmo deve detectar a faixa a partir do cabeçalho.
7. **14 SET B1-B10.mp3 é o caso mais complexo** — 10 boletins, ~18 min, 9 cortes precisos.
8. **Timeout é problema real** — Whisper base demora ~2-4 min/arquivo em CPU. Para 17 arquivos, ~35-70 min total. Executar em lote com timeout longo ou dividir em 여러 sessions.
