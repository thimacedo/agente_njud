import json
import csv
from pathlib import Path
from datetime import datetime

base = Path('projeto_etapa_final_2026')
for d in [base/'scripts', base/'logs', base/'relatorios', base/'checklists', base/'planejamento']:
    d.mkdir(parents=True, exist_ok=True)

plan = """# Planejamento - Etapa Final Jan-Ago 2026

## Objetivo
Fechar a produção dos jornais NJUD de janeiro a agosto de 2026, priorizando o que já existe localmente e completando o restante via scraping do Joomla (`radioetv.tjrn.jus.br`), com montagem modular por jornal, sincronização no Drive e auditoria contínua.

## Estrutura modular
- `projeto_etapa_final_2026/planejamento/PLANO.md` (este arquivo)
- `projeto_etapa_final_2026/checklists/` — CSV por jornal com status
- `projeto_etapa_final_2026/scripts/` — scripts modularizados por etapa
- `projeto_etapa_final_2026/logs/` — logs JSONL por etapa
- `projeto_etapa_final_2026/relatorios/` — relatórios consolidados

## Etapas
1. `01_auditoria_local.py` — mapeia jornais existentes, pendentes e fontes
2. `02_scraping_joomla.py` — baixa somente os boletins faltantes por data-alvo
3. `03_preparar_boletins.py` — copia/estrutura os MP3s para o formato esperado pelo divisor
4. `04_dividir_cabeca_corpo.py` — executa a divisão CABEÇA/CORPO
5. `05_montar_jornais.py` — monta os jornais finais por mês/dia
6. `06_quarentena.py` — move `_INCOMPLETO` para quarentena
7. `07_sync_drive.py` — sincroniza válidos para o Drive
8. `08_auditoria_final.py` — valida nomenclatura, contagem e estrutura

## Recursos necessários
- CPU: divisão/montagem são CPU-bound; usar workers limitados por RAM
- Disco: espaço para downloads + cortes + montados (H: e local)
- Rede: scraping Joomla com delay de 1s/página
- Assets: vinhetas em `assets/vinhetas/` — missing asset não bloqueia
- H: disponível para leitura dos ativos e gravação final no Drive

## Agentes / Workers
- `scraping-workers`: 1-2 workers paralelos para `?start=` do Joomla
- `divisao-workers`: `os.cpu_count()` mínimo 1, com throttle por RAM
- `montagem-workers`: 1 por mês, sequencial para evitar conflito de I/O
- `sync-worker`: 1, atomicidade por arquivo (temp + rename)

## Skills necessárias
- `radio-bulletin-pipeline-toolkit` (orquestração)
- `radio-bulletin-division` (CABEÇA/CORPO)
- `radio-bulletin-structure` (regras de montagem)
- `productivity/xlsx` (relatórios de auditoria)

## MCPs
- Nenhum MCP adicional necessário nesta etapa; integrações atuais (`sync/drive.py`) são suficientes.

## Gargalos e riscos
1. Whisper/VAD para divisão: maior consumo de tempo; já mitigado por checkpointing
2. H: indisponível: bloqueia leitura de assets e escrita no Drive
3. Scraping Joomla: bloqueado por WAF no domínio principal; usar apenas `radioetv`
4. Nomenclatura inválida: bloqueia sync; resolvido via quarentena prévia
5. Material insuficiente para alguns dias: gera `_INCOMPLETO`; já documentado em `DECISOES.md`

## Impossibilidades técnicas conhecidas
- Domínio `www.tjrn.jus.br` bloqueia scraping (403 Akamai); workaround é `radioetv.tjrn.jus.br`
- `downloader_tjrn.py` retorna 403; não usar nesta etapa
- Sem `_CABECA/_CORPO`, o montador não aceita o arquivo; divisão obrigatória
"""

(base/'planejamento'/'PLANO.md').write_text(plan, encoding='utf-8')

checklist = []
faltantes = [
    ('03 - MAR - 26','26-03-2026'),('03 - MAR - 26','27-03-2026'),('03 - MAR - 26','30-03-2026'),('03 - MAR - 26','31-03-2026'),
    ('04 - ABR - 26','01-04-2026'),('04 - ABR - 26','02-04-2026'),('04 - ABR - 26','03-04-2026'),('04 - ABR - 26','06-04-2026'),
    ('04 - ABR - 26','07-04-2026'),('04 - ABR - 26','08-04-2026'),('04 - ABR - 26','09-04-2026'),('04 - ABR - 26','10-04-2026'),
    ('04 - ABR - 26','13-04-2026'),('04 - ABR - 26','14-04-2026'),('04 - ABR - 26','21-04-2026'),
    ('05 - MAI - 26','01-05-2026'),('05 - MAI - 26','05-05-2026'),('05 - MAI - 26','06-05-2026'),('05 - MAI - 26','07-05-2026'),
    ('05 - MAI - 26','08-05-2026'),('05 - MAI - 26','11-05-2026'),('05 - MAI - 26','12-05-2026'),('05 - MAI - 26','13-05-2026'),
    ('05 - MAI - 26','14-05-2026'),('05 - MAI - 26','15-05-2026'),('05 - MAI - 26','19-05-2026'),('05 - MAI - 26','20-05-2026'),
    ('05 - MAI - 26','22-05-2026'),('05 - MAI - 26','25-05-2026'),('05 - MAI - 26','26-05-2026'),('05 - MAI - 26','27-05-2026'),
    ('05 - MAI - 26','28-05-2026'),('05 - MAI - 26','29-05-2026'),
    ('06 - JUN - 26','01-06-2026'),('06 - JUN - 26','05-06-2026'),('06 - JUN - 26','11-06-2026'),('06 - JUN - 26','12-06-2026'),
    ('06 - JUN - 26','15-06-2026'),('06 - JUN - 26','16-06-2026'),('06 - JUN - 26','17-06-2026'),('06 - JUN - 26','18-06-2026'),
    ('06 - JUN - 26','19-06-2026'),('06 - JUN - 26','22-06-2026'),('06 - JUN - 26','23-06-2026'),('06 - JUN - 26','24-06-2026'),
    ('06 - JUN - 26','25-06-2026'),('06 - JUN - 26','26-06-2026'),('06 - JUN - 26','29-06-2026'),('06 - JUN - 26','30-06-2026'),
    ('07 - JUL - 26','01-07-2026'),('07 - JUL - 26','02-07-2026'),('07 - JUL - 26','03-07-2026'),('07 - JUL - 26','06-07-2026'),
    ('07 - JUL - 26','07-07-2026'),('07 - JUL - 26','08-07-2026'),('07 - JUL - 26','09-07-2026'),('07 - JUL - 26','10-07-2026'),
    ('07 - JUL - 26','13-07-2026'),('07 - JUL - 26','14-07-2026'),('07 - JUL - 26','15-07-2026'),('07 - JUL - 26','16-07-2026'),
    ('07 - JUL - 26','17-07-2026'),('07 - JUL - 26','20-07-2026'),('07 - JUL - 26','21-07-2026'),('07 - JUL - 26','22-07-2026'),
    ('07 - JUL - 26','23-07-2026'),('07 - JUL - 26','24-07-2026'),('07 - JUL - 26','28-07-2026'),('07 - JUL - 26','29-07-2026'),
    ('07 - JUL - 26','30-07-2026'),('07 - JUL - 26','31-07-2026'),
    ('08 - AGO - 26','03-08-2026'),('08 - AGO - 26','04-08-2026'),('08 - AGO - 26','05-08-2026'),('08 - AGO - 26','06-08-2026'),
    ('08 - AGO - 26','07-08-2026'),('08 - AGO - 26','10-08-2026'),('08 - AGO - 26','11-08-2026'),('08 - AGO - 26','12-08-2026'),
    ('08 - AGO - 26','13-08-2026'),('08 - AGO - 26','14-08-2026'),('08 - AGO - 26','17-08-2026'),('08 - AGO - 26','18-08-2026'),
    ('08 - AGO - 26','19-08-2026'),('08 - AGO - 26','20-08-2026'),('08 - AGO - 26','21-08-2026'),('08 - AGO - 26','24-08-2026'),
    ('08 - AGO - 26','25-08-2026'),('08 - AGO - 26','27-08-2026'),('08 - AGO - 26','28-08-2026'),('08 - AGO - 26','31-08-2026'),
]

for mes, data in faltantes:
    checklist.append({
        'mes': mes,
        'data': data,
        'status': 'PENDENTE_SCRAPING',
        'fonte': 'radioetv',
        'boletins_esperados': 4,
        'boletins_ok': 0,
        'caminho_local': '',
        'detalhe': 'aguardando scraping'
    })

with open(base/'checklists'/'checklist_jornais.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['mes','data','status','fonte','boletins_esperados','boletins_ok','caminho_local','detalhe'])
    writer.writeheader()
    writer.writerows(checklist)

print('Estrutura criada em', base)
print('Checklist:', len(checklist), 'linhas')
