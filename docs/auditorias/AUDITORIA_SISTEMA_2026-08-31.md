# Auditoria do Sistema DIVISOR — 2026-08-31

Auditoria completa do repositório: lixo excluível, melhorias planejadas, refatorações necessárias e caminhos/pastas duplicados.

---

## 1. LIXO — pode ser excluído

### 1.1 Exclusão segura (sem impacto funcional)

| Item | Detalhe | Evidência |
|---|---|---|
| 44 pastas de data vazias na raiz de `data/processed/JORNAIS_DIVIDIDOS/` (`02-02-2026`, `03-02-2026`, …) | 0 arquivos no disco, 0 no git | `find … -type f` → 0 |
| `src/core/` | diretório vazio (fantasma do refactor) | 0 arquivos |
| `src/divisor_boletins/{audit,pipeline,plan,sync,utils}` | esqueletos vazios sem `__init__.py` | 0 arquivos |
| `logs/correcoes/`, `projeto_etapa_final_2026/logs/` | vazias | 0 arquivos |
| `data/processed/JORNAIS_FINAL/` | pasta espelhada vazia (o real é `data/output/JORNAIS_FINAL`) | 0 bytes |
| `data/output/JORNAIS_DIVIDIDOS/` | pasta deslocada vazia | 4 KB |
| `data/raw/` | vazia | 0 bytes |
| `__pycache__/` (11 pastas, 70 `.pyc`) | artefatos de compilação | `*.pyc` deve ser gitignored |
| Scratch da raiz: `audio_results_listing.json`, `audio_results_playwright.json` (2 B cada), `audio_results_joomla.json`, `listing_page_sample.html`, `_memory_notes.json` | sobras de testes dos scrapers | tamanho/uso |
| `data/_debug_cortes/` (1.2 MB), `data/_debug_logs/` | resíduo de debug | pontual |
| `data/_substituidos_20260824/` | `.bak` de CSVs já substituídos em 24/08 | são backups de versões antigas |
| `tests/test_sync_cleanup.py` | inútil: uma única asserção aritmética hardcoded (97+270=367), não toca código | leitura do arquivo |
| `scripts_criar_planejamento.py` (raiz) | gerou a estrutura `projeto_etapa_final_2026/` que já existe; zero referências | grep |
| `projeto_etapa_final_2026/scripts/` (7 scripts `run_*`) | one-shots datados de campanha encerrada; zero referências; caminhos absolutos `F:/…` | grep |

### 1.2 Exclusão com verificação prévia (risco de dado único)

| Item | Detalhe | Ação recomendada |
|---|---|---|
| `JORNAIS_DIVIDIDOS_<MES>_2026` (JAN/FEV/MAR/ABR/MAI/JUN_JUL_AGO, 556 MB, 1091 arquivos no git) | snapshots mensais antigos; ex.: FEV tem 128 mp3 com 56 nomes sobrepostos à canônica `02 - FEV - 26` (136 mp3) | diff por nome+hash contra a canônica; o que existir lá, excluir |
| `JORNAIS_DIVIDIDOS_TESTE/` (46 MB) e `JORNAIS_DIVIDIDOS_{ABR,MAI}_PLANO/` | pastas de teste/plano | confirmar descarte |
| `JORNAIS_DIVIDIDOS_PENDENTES/` (3.1 GB, 2008 arquivos no git) | contém variantes duplicadas do mesmo mês (`05_-_MAI_-_26` com 73 mp3 vs `05__MAI__26` vazia) e `*_PLANO*` | consolidar em `JORNAIS_DIVIDIDOS/<MES>` e remover variantes |
| `data/output/_quarentena_invalidos/` (45 MB), `data_quarentena_2027/` (27 MB) | quarentenas | revisar conteúdo antes de excluir |
| `downloads/` (3.3 MB, boletins set/2025) | sobra do downloader | conferir se já absorvidos |
| `legacy_archive/` (884 MB: JORNAIS/, boletins_brutos_*) | arquivo histórico | se já processado, mover para fora do projeto |
| mp3 deletados do working tree (visíveis em `git status`) | já movidos para `…/<MES>/NJUD xxxx/` na estrutura nova | commitar a remoção |

### 1.3 Problema grave de repositório (causa raiz do inchaço)

- **`.gitignore` está quebrado**: o arquivo inteiro está envolto em cercas ```` ```python ```` (linhas 1 e final), então **nenhuma regra é aplicada**. Resultado: `.pyc`, logs e afins entram no git.
- **Binários versionados**: 4776 `.mp3`, 2121 `.json`, 63 `.csv`, 56 `.log/.jsonl/.txt` rastreados → **`.git` = 3.6 GB**.
- Áudio e cache não deveriam estar no git (estão no disco e no Drive H:).

**Plano de correção (P1):**
1. Corrigir `.gitignore` (remover as cercas) e ampliar: `data/processed/`, `data/output/`, `data/cache/`, `legacy_archive/`, `downloads/`, `*.mp3`, `*.pkl`.
2. `git rm -r --cached` dos binários + commit.
3. (Opcional, coordenado) `git filter-repo` para expurgar mp3 do histórico — reduz o `.git` de 3.6 GB para dezenas de MB; exige re-clone de todas as cópias.

---

## 2. CAMINHOS E PASTAS EM LOCAIS MÚLTIPLOS

### 2.1 Logs — 16 locais diferentes

```
logs/                                           (raiz; utils/logger.py default "./logs")
logs/_arquivo_morto_logs/                       (arquivo morto)
logs/backups/
logs/correcoes/                                 (vazia)
data/_pipeline_logs/                            (LOGS_DIR do .env!)
data/_debug_logs/
data/output/_logs/                              (safe_runner, executar_reprocessamento)
data/output/JORNAIS_FINAL/_logs/
data/output/_arquivo_morto_local/
data/processed/_logs/
data/processed/JORNAIS_DIVIDIDOS/_logs/         (worker_N do dispatcher)
data/processed/JORNAIS_DIVIDIDOS/JORNAIS_FINAL/_logs/   ← espelho deslocado
data/processed/JORNAIS_DIVIDIDOS_<MES>_2026/_logs/  (7 variantes mensais)
projeto_etapa_final_2026/logs/                  (vazia)
plan/fixer.py → "_logs_correcao"                (fixer.py:13)
data/output/… + relatórios CSV avulsos de log
```

Três sistemas de logging coexistem: `src/utils/logger.py` (RotatingFileHandler → `./logs`), `src/divisor_boletins/log.py` (LogPipeline dual TXT+JSONL → pasta passada pelo chamador) e `logging` básico em tools.

**Conflito ativo**: `.env` define `LOGS_DIR=data/_pipeline_logs`, mas o default de `settings.py` é `logs/` (settings.py:55-58) — ambos existem e recebem logs.

**Proposta de consolidação:**
- Log global/permanente → `logs/` (raiz), com subpastas `backups/`, `correcoes/`, `_arquivo_morto_logs/`.
- Log de lote → `<saida>/_logs` apenas.
- Todo módulo usa `settings.LOGS_DIR`; ninguém constrói caminho próprio.
- Mover conteúdo de `data/_pipeline_logs`, `data/_debug_logs` e dos `_logs` órfãos para `logs/_arquivo_morto_logs/`.

### 2.2 Saídas e relatórios duplicados/deslocados

- `data/output/` mistura: pastas de mês (`01 - JAN - 26`…), pastas-placeholder `26-MM-YYYY` (vazias, de planejamento), 2 quarentenas, `_arquivo_morto_local`, e **12 relatórios `relatorio_auditoria_*.csv` avulsos** na raiz da pasta.
- `JORNAIS_FINAL` existe em 3 lugares: `data/output/JORNAIS_FINAL` (real), `data/processed/JORNAIS_DIVIDIDOS/JORNAIS_FINAL` (espelho), `data/processed/JORNAIS_FINAL` (vazia).
- CSVs de planejamento espalhados: raiz (`NJUDS_VALIDOS.csv`, `dias_uteis_*.csv`), `data/` (9 CSVs de plano/alvos), `projeto_etapa_final_2026/checklists/`, `logs/backups/backup_estado_consolidado.csv`.

### 2.3 Configuração divergente do disco

| Fonte | Diz | Realidade |
|---|---|---|
| `.env` `BOLETINS_BRUTOS=JORNAIS` | pasta `JORNAIS/` na raiz | não existe; brutos estão em `legacy_archive/JORNAIS` |
| `.env` `JORNAIS_MONTADOS=data/output` | montagem em `data/output` | default do settings.py é `data/output/JORNAIS_FINAL` |
| `.env` `LOGS_DIR=data/_pipeline_logs` | logs em data | settings.py default `logs/` |
| `.env` `DRIVE_SYNC=H:\Meu Drive\RADIO TJRN CONTEÚDO_PRODUCAO_2026_JORNAIS_NJUD_AUDIOS_RADIO` | **caminho corrompido** (separadores viraram `_`) | caminho real no default do settings.py e hardcoded em 6 arquivos |
| README | "sem dados na raiz" | raiz tem 5 arquivos de dados soltos |

---

## 3. REFATORAÇÃO

### 3.1 Wrappers depreciados (duplicação direta)
15 scripts flat de 8 linhas em `src/` duplicam módulos dos pacotes (ex.: `dispatcher_paralelo.py` ↔ `pipeline/dispatcher.py`, `gerar_plano.py` ↔ `plan/generator.py`). Único consumidor automático: `tests/test_imports.py`.
- **Mortos na prática** (só docs citam): `corrigir_plano`, `resumo_metodos`, `relatorio_audit`, `planejador_copia`, `processo_unico`.
- **Ainda invocados**: `run_pipeline_safe_v2.py` (por `src/reprocessar_agosto.sh:21,25`).
- Ação: remover wrappers, atualizar `reprocessar_agosto.sh`, DECISOES.md, PROCEDIMENTO_PADRAO.md e PLANO_POVOAR_NJUDS_2026.md para os nomes canônicos; ajustar `test_imports.py`.

### 3.2 Caminhos hardcoded (fora de settings.py)
~40 ocorrências, destaque:
- `F:/Projetos/DIVISOR` literal em 11 scripts de `src/tools/` (`BASE = Path("F:/Projetos/DIVISOR")`): auditar_passado_presente:18, auditar_pastas_alvo:20, organizar_boletins_por_data:17, padronizar_passado_presente:18, remover_duplicatas:17, renomear_boletins_mapeaveis:18, resolver_conflitos_boletins:18, tratar_sem_num_csv:18, standardize_njud_names:9, standardize_njud_names_alvo:9, standardize_programas_projetados:9.
- `H:\Meu Drive\…` duplicado em 7 arquivos: settings.py:52, sync/drive.py:19, tools/executar_reprocessamento.py:26, tools/gerar_relatorio_orfaos_drive.py:20, tools/mover_orfaos_drive.py:11,13, tools/sanear_drive.py:271.
- Import quebrado `from src.utils.logger` (só funciona rodando fora de `src/`): tools/downloader_tjrn.py:34, tools/gerar_relatorio_pos_download.py:13, tools/sanear_drive.py:22.
- Ação: tudo passa a usar `from config.settings import settings`; caminho do Drive vira constante única.

### 3.3 Logging unificado
- Definir papéis: `utils/logger.py` para logs de infra/raiz; `divisor_boletins/log.py` para log de pipeline (lote). Eliminar `logging` básico solto (gerar_plano_faltantes.py:5, padronizador_completo.py).
- Ambos respeitam `settings.LOGS_DIR`; fim dos 16 locais.

### 3.4 `src/tools/` (31 scripts)
Nenhum é importado por código algum (são CLIs avulsos). Padronizar: usar settings, remover os que pertencem a campanhas encerradas (padronizadores/standardize já executados segundo `logs/_arquivo_morto_logs`).

### 3.5 Testes
Sem testes de lógica (corte, montagem, plano, sync). Plano: testes de unidade para `divisor_boletins` (detecção/corte com fixture de áudio sintético), `plan/allocator` e `sync/copy`; remover `test_sync_cleanup.py`.

---

## 4. PLANO DE EXECUÇÃO (ordem sugerida)

| Fase | Ação | Risco |
|---|---|---|
| **P1 — Higiene git** (1 dia) | Consertar `.gitignore`; `git rm --cached` de binários; commit das remoções já feitas no working tree; deletar pastas vazias e scratch da raiz (itens 1.1) | Baixo |
| **P2 — Consolidar dados** (1-2 dias) | Diff das variantes mensais vs canônica; consolidar PENDENTES em estrutura mensal única; decidir quarentenas e legacy_archive | Médio (verificar antes de excluir) |
| **P3 — Caminhos únicos** (1 dia) | `.env` saneado (DRIVE_SYNC correto, LOGS_DIR único, BOLETINS_BRUTOS real); settings.py defaults alinhados ao .env; remover hardcoded F:/ e H:\ | Médio |
| **P4 — Logging único** (0.5 dia) | Mover logs órfãos para `logs/_arquivo_morto_logs`; todos os módulos via settings.LOGS_DIR | Baixo |
| **P5 — Código morto** (0.5 dia) | Remover 15 wrappers, 7 scripts da etapa final, scripts_criar_planejamento.py, test_sync_cleanup.py; atualizar docs e .sh | Baixo |
| **P6 — Qualidade** (contínuo) | Testes reais de corte/montagem/plano; enxugar tools/ | Baixo |
| **P7 — Histórico git** (opcional) | `git filter-repo` para expurgar mp3 do histórico (.git 3.6 GB → ~50 MB); requer re-clone geral | Alto (reescrita de histórico) |

**Ganho estimado**: remoção de ~4 GB de dados redundantes no disco, `.git` futuro muito menor, 1 local de log em vez de 16, e eliminação de ~25 arquivos de código duplicado/morto.
