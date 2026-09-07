# Planejamento Modular - Produção Final NJUD Jan-Ago 2026

## Objetivo
Fechar a produção dos jornais NJUD de janeiro a agosto de 2026, com fluxo modular por unidade de jornal: cópia/seleção de boletins, divisão CABEÇA/CORPO, montagem, quarentena, sincronização no Drive e auditoria contínua.

---

## Estado atual resumido

### 1) Jornais possíveis de montar já com material local
- **Março/2026**: 18 de 22 dias úteis presentes localmente; faltam 26-03, 27-03, 30-03, 31-03
- **Abril/2026**: 12 de 22 dias úteis presentes localmente; faltam 01-04 a 10-04, 13-04, 14-04, 21-04

Observação: já existem 33 jornais montados em `data/output/JORNAIS_FINAL/` para março/abril, mas ainda há pendências locais nesses meses.

### 2) Jornais que dependem de download do site
O domínio principal (`www.tjrn.jus.br`) está bloqueado por WAF Akamai. Workaround confirmado: `radioetv.tjrn.jus.br` (Joomla legado, 200 OK, paginação `?start=N`).

Datas-alvo confirmadas já disponíveis no site e que ainda faltam localmente:
- **Maio/2026**: 01-05, 05-05, 06-05, 07-05, 08-05, 11-05, 12-05, 13-05, 14-05, 15-05, 19-05, 20-05, 22-05, 25-05, 26-05, 27-05, 28-05, 29-05
- **Junho/2026**: 01-06, 05-06, 11-06, 12-06, 15-06, 16-06, 17-06, 18-06, 19-06, 22-06, 23-06, 24-06, 25-06, 26-06, 29-06, 30-06
- **Julho/2026**: 01-07, 02-07, 03-07, 06-07, 07-07, 08-07, 09-07, 10-07, 13-07, 14-07, 15-07, 16-07, 17-07, 20-07, 21-07, 22-07, 23-07, 24-07, 28-07, 29-07, 30-07, 31-07
- **Agosto/2026**: 03-08, 04-08, 05-08, 06-08, 07-08, 10-08, 11-08, 12-08, 13-08, 14-08, 17-08, 18-08, 19-08, 20-08, 21-08, 24-08, 25-08, 27-08, 28-08, 31-08

Cobertura já garantida localmente (não baixar):
- Janeiro/2026: 22/22
- Fevereiro/2026: 20/20
- Março/2026: 18/22
- Abril/2026: 12/22
- Maio/2026: 5/21

---

## Modelo de tempo estimado por etapa

| Etapa | Complexidade | Tempo unitário/jornal | Paralelizável | Observação |
| --- | --- | --- | --- | --- |
| Auditoria local | Baixa | ~1s | Sim | Leitura de disco/metadados |
| Scraping Joomla | Média | ~8s a 15s por página | Sim (1-2 workers) | Delay entre páginas para evitar bloqueio |
| Preparar boletins | Baixa | ~5s | Sim | Cópia/estruturação de pastas |
| Divisão CABEÇA/CORPO | Alta | ~45s a 120s | Limitado (CPU/RAM) | Maior gargalo do pipeline |
| Montagem do jornal | Média | ~30s a 90s | 1 worker/mês | I/O e mixagem |
| Quarentena `_INCOMPLETO` | Baixa | ~2s | Sim | Somente se existir |
| Sync Drive | Baixa | ~10s a 30s | 1 worker | Escrita no H: |
| Auditoria final | Baixa | ~3s | Sim | Nome, qtd, estrutura |

Estimativa de ordem de grandeza para volume total estimado:
- Jornais faltantes confirmados no planejamento: **91 unidades**
- Se considerarmos 4 boletins/jornal, scraping + preparo + divisão + montagem por unidade: em média **3-5 min/jornal**
- Batch total teórico: **~4h30 a 7h30**, com workers limitados e checkpointing
- Cenário realista com gargalos: **~6h a 10h**

---

## Workflow modular por jornal

### Etapa 1 - Auditoria local
- Entrada: checklist + inventário de `data/processed/JORNAIS_DIVIDIDOS*` e `data/output/JORNAIS_FINAL`
- Saída: `projeto_etapa_final_2026/logs/auditoria_local.jsonl` e atualização do CSV checklist
- Regra: se o jornal já existir em `JORNAIS_FINAL` e for válido, marcar `PRODUZIDO` e pular etapas seguintes

### Etapa 2 - Scraping Joomla
- Entrada: lista de datas faltantes
- Ferramenta: `src/tools/scraper_listing.py --target-dates DD-MM-AAAA`
- Saída: `projeto_etapa_final_2026/logs/scraping_joomla.jsonl`
- Política: dry-run primeiro; se retorno 403 ou 0 resultados, interromper lote e reportar
- Limite: 1-2 workers paralelos; delay entre requisições

### Etapa 3 - Preparar boletins
- Entrada: `./downloads/` ou pasta de origem temporária
- Saída: estrutura em `data/processed/JORNAIS_DIVIDIDOS/<MES>/<DIA>/NJUD_*/BOLETIM_*_CABECA.mp3` + `_CORPO.mp3`
- Regra: se já existirem cortes locais para o dia, usar estes; senão, usar os baixados

### Etapa 4 - Dividir CABEÇA/CORPO
- Entrada: arquivos crus válidos
- Ferramenta: `divisor_boletins dividir` com checkpointing
- Saída: `data/processed/JORNAIS_DIVIDIDOS/<MES>/<DIA>/NJUD_*/`
- Regra: timeout tolerado; se travar, registrar falha e seguir próximo dia (não travar lote)
- Tratamento: arquivos insuficientes geram `_INCOMPLETO`, que seguem para quarentena

### Etapa 5 - Montar jornais
- Entrada: cortes CABEÇA/CORPO válidos
- Ferramenta: `divisor_boletins montar` por mês
- Saída: `data/output/JORNAIS_FINAL/NJUD_XXXX_DD-MM-AAAA.mp3`
- Regra: 4 boletins por jornal; se <4, gerar `_INCOMPLETO`

### Etapa 6 - Quarentena
- Entrada: `JORNAIS_FINAL`
- Ação: mover `*_INCOMPLETO*` para `data/output/_quarentena_invalidos/`
- Saída: `projeto_etapa_final_2026/logs/quarentena.jsonl`

### Etapa 7 - Sync Drive
- Entrada: `JORNAIS_FINAL` válidos
- Ferramenta: `src/sync/drive.py`
- Saída: arquivos em `H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/02_JORNAIS_NJUD/03_AUDIOS_RADIO/<MES>/`
- Regra: atomicidade por arquivo; registrar pendentes se H: indisponível

### Etapa 8 - Auditoria final
- Entrada: Drive + local + checklist
- Saída: `projeto_etapa_final_2026/relatorios/auditoria_final.csv` e `resumo_final.txt`
- Regra: validar nomenclatura, contagem por mês, existência no Drive, arquivos inválidos/quarentena

---

## Gargalos, necessidades e impossibilidades

### Gargalos
1. **Divisão CABEÇA/CORPO (VAD/Silero)**: etapa mais custosa e com maior risco de timeout
2. **I/O disco/H:**: cópias grandes em H: podem aumentar latência
3. **Scraping sequencial**: paginação do Joomla pode variar; bloqueio por WAF se exceder taxa
4. **Montagem mensal**: concorrência entre workers pode causar contenção de escrita

### Necessidades
1. **Assets de vinhetas**: `assets/vinhetas/` devem estar presentes; missing asset não deve bloquear produção, mas deve ser registrado
2. **H: disponível**: leitura dos ativos e escrita final no Drive
3. **Python 3.11 + dependências**: `pydub`, `torch`, `whisper`, `requests` instalados
4. **Workers supervisionados**: limite por RAM/CPU para evitar travamento total

### Impossibilidades técnicas
1. **Domínio principal bloqueado**: `www.tjrn.jus.br` retorna 403 Akamai; impossível scraping direto
2. **downloader_tjrn.py**: abandonado nesta etapa (403 confirmado)
3. **Montagem sem divisão prévia**: `montar` não aceita arquivos crus; `dividir` é obrigatório
4. **WAF dinâmico**: Joomla pode endurecer bloqueios futuros; mitigação atual é `radioetv` + delay

---

## Agentes, subagentes e workers

### Agentes/subagentes recomendados
- **Agente de scraping**: worker controlado para `scraper_listing.py` com retry/backoff
- **Agente de divisão**: worker por dia, com timeout e checkpointing
- **Agente de montagem**: sequencial por mês, para evitar conflito
- **Agente de sync**: único, serial, para evitar escrita concorrente no H:

### Workers
- Scraping: 1-2 paralelos
- Divisão: limitado por `os.cpu_count()` e RAM disponível
- Montagem: 1 por mês
- Sync: 1

### Skills necessárias
- `radio-bulletin-pipeline-toolkit`
- `radio-bulletin-division`
- `radio-bulletin-structure`
- `productivity/xlsx`

### MCPs
- Nenhum adicional necessário nesta etapa; usar integrações existentes (`sync/drive.py`)

---

## Protocolo de execução

1. Ler `checklist_jornais.csv`
2. Executar cada etapa modular com logs JSONL
3. Ao final de cada etapa, atualizar checklist
4. Ao final do lote, gerar relatórios em `relatorios/`
5. Nunca apagar logs históricos; usar `logs/error.log` quando necessário
