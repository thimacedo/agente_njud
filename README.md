# DIVISOR — Pipeline de Boletins de Rádio TJRN

Processa boletins (MP3) em jornais NJUD montados, com corte VAD calibrado,
transcrição Whisper e montagem por NJUD. Pipeline com ciclo fechado por arquivo
e estado persistido.

## Onde está tudo

```
DIVISOR/
├── src/                      # código canônico (pacotes)
│   ├── divisor_boletins/     # núcleo: audio, calibração, detecção, montagem, texto, cli, config, log
│   ├── pipeline/             # dispatcher paralelo, single_process, monitor
│   ├── audit/                # auditoria (cortes, integridade, relatórios, summaries)
│   ├── sync/                 # drive.py (única escrita no H:) + copy.py
│   ├── plan/                 # gerador/allocator/fixer de plano alocação
│   ├── orchestration/        # safe_runner (compat) + journal_pipeline (placeholder)
│   ├── config/settings.py    # settings centralizados (.env)
│   ├── utils/                # logger, error_handler, validator
│   ├── tools/                # ~50 ferramentas: auditoria, sync, scrapers, padronização, relatórios
│   ├── dispatcher_paralelo.py
│   ├── monitor_tempo_real.py
│   ├── iniciar_ciclo.py      # entry point oficial: mata antigos e inicia
│   ├── teste_ciclo.py        # teste dirigido de UM boletim
│   ├── reprocessar_agosto.sh
│   └── ...
│
├── scripts_pipeline/         # scripts complementares (shell + Python)
│   ├── run_all.sh
│   ├── run_pipeline.sh
│   ├── montar.sh
│   ├── prepare.sh
│   ├── sync_drive.sh
│   ├── cleanup.sh
│   ├── auditoriar.sh
│   ├── serial_jul_ago.py
│   ├── serial_jul_ago_v2.py
│   ├── processor_com_heartbeat.py
│   ├── processor_v2.py
│   ├── processor_v3.py
│   ├── processar_serial.py
│   ├── processar_serial_tiny.py
│   ├── processar_subprocess.py
│   ├── processar_njud_por_njud.py
│   ├── dispatcher_wrapper.py
│   ├── orquestrador.py       # ciclo perceber→planejar→agir→adaptar
│   ├── auditoria.py
│   ├── auditoria_v2.py
│   ├── etapa3_auditoria_*.py
│   ├── montagem_*.py
│   └── ...
│
├── assets/vinhetas/          # VHT_ABERTURA_BOLETIM, VHT_ENCERRAMENTO_*, PASSAGEM_*, etc.
├── BOLETIM/                # agente de produção (tratamento→edição→montagem)
│   ├── 03_SET_B1_tratado.mp3
│   ├── 03_SET_B1_editado.mp3
│   ├── 03_SET_B1_FINAL.mp3
│   └── pipeline_log.json
├── data/                     # dados derivados (não commitado inteiro — veja .gitignore)
│   ├── plano_alocacao.csv, jornal_njuds.csv, njuds_por_mes.csv, ...
│   ├── processed/            # cortes CABEÇA/CORPO, estado_por_arquivo/*.json
│   └── output/               # jornais montados + relatórios
│
├── JORNAIS/                  # entrada bruta copiada do Drive (leitura)
├── BOLETIM/                  # agente de produção (pipeline tratamento→edição→montagem)
├── logs/                     # backups consolidados, correções, relatórios
├── docs/
│   ├── PLANEJAMENTO_JUL_AGO_2026.md
│   ├── PRODUCAO.md
│   └── REGRAS_ORQUESTRACAO.md
├── DECISOES.md               # regras não negociáveis — ler antes de mexer
├── PROCEDIMENTO_PADRAO.md    # fluxo oficial v4 — processo único com ciclo fechado
├── IDEA.md
├── AGENTS.md                 # regras do projeto para agentes
├── NJUDS_VALIDOS.csv
├── .env.example              # configuração (copiar → .env, não commitar .env real)
├── .gitignore
└── README.md
```

## Fluxo principal (v4 — processo único com ciclo fechado por arquivo)

```
1. Gerar plano:  src/plan/generator.py  ou  src/gerar_plano.py
      → lê Drive H: (somente leitura) → data/plano_alocacao.csv

2. Copiar boletins:  src/sync/copy.py  ou  src/copiar_boletins.py
      → JORNAIS/<MES>/<NJUD>/   (validação + backup antes de limpar)

3. Processar:  src/iniciar_ciclo.py <pasta> <saida>
      → dispatcher_paralelo.py abre N workers (Whisper carregado 1x)
      → ciclo por arquivo: calibrar → cortar → auditar → classificar motivo
      → escalar estratégia OU finalizar (estado em estado_por_arquivo/*.json)

4. Sincronizar prontos:  src/sync/drive.py
      → única escrita permitida no H: (apenas jornais aprovados)
```

Testes dirigidos de UM boletim (sem multiprocessing):

```bash
python teste_ciclo.py "<caminho do mp3>" --saida data/teste_ciclo
```

## Como rodar o dispatcher + monitor (processamento em lote)

```powershell
# Janela 1 — processamento
python src/pipeline/dispatcher.py "F:\Projetos\DIVISOR\JORNAIS" ^
    "F:\Projetos\DIVISOR\data\processed" --max-workers 3

# Janela 2 — monitor em tempo real (só leitura; abrir/fechar à vontade)
python src/pipeline/monitor.py "F:\Projetos\DIVISOR\data\processed" --intervalo 5 --log
```

Alternativas (processamento serial / por-NJUD / orquestração):

- `scripts_pipeline/processor_com_heartbeat.py` — serial com heartbeat
- `scripts_pipeline/processor_v2.py` / `processor_v3.py` — serial com filtro/status
- `scripts_pipeline/serial_jul_ago.py` / `serial_jul_ago_v2.py` — 1 arquivo por vez
- `scripts_pipeline/processar_njud_por_njud.py` — 1 NJUD por processo separado
- `scripts_pipeline/orquestrador.py` — ciclo continuo perceber→planejar→agir→adaptar
- `scripts_pipeline/dispatcher_wrapper.py` — reinício automático do dispatcher (estado persisente)

## Regras inegociáveis

- **H: é somente leitura** exceto `src/sync/drive.py` — só copia jornais prontos.
- **Mês = mês no nome do arquivo**, não da pasta. 1 NJUD = 4 boletins do mês.
- **Gate por-NJUD**: um jornal só é montado quando TODOS os seus 4 boletins
  estão `OK` ou `ESGOTADO_ACEITO` — nunca monta com pendência.
- **Máximo 1 dispatcher + 1 monitor** ativos. `iniciar_ciclo.py` mata os antigos.
- **Estado persistido** em `data/processed/PRODUCAO_2026/estado_por_arquivo/*.json` —
  é a fonte de verdade, não logs ou memória.
- **Agente BOLETIM/**: etapa de pipeline (tratamento→edição→montagem) gravada
  em `BOLETIM/`. O `gravador_inteligente` utiliza `DIVISOR_WORKSPACE` para apontar
  para a raiz do DIVISOR. Não executar com CWD errado.
- Boletins sem NJUD identificável vão para `plano_pendentes_sem_njud.csv` — nunca
  agrupados por dedução.
- Corte nunca default 0.0 quando calibração parcial falha (âncora→VAD + log).

## Auditoria

- `src/audit/integrity.py` — integridade do lote
- `src/audit/individual_cuts.py` — análise física por _CABECA/_CORPO
- `src/audit/integrity_report.py` + `summaries.py` — relatórios consolidados
- `scripts_pipeline/auditoria.py` / `auditoria_v2.py` — verificação de cortes, montagem, vinhetas, contexto

Ciclo de reaprendizado por arquivo (cada reprovação gera motivo estruturado):

| Motivo da auditoria | Próxima estratégia |
|---|---|
| palavra a 0.00s do início | `ancora_vad_forcado` |
| palavra colada na borda | `janela_silencio_ampliada` (janela 4000ms) |
| conectivo isolado no início/fim | `grade_fixa_locucao_estendida` |
| motivo desconhecido / esgotou tudo | `ESGOTADO` (fila manual) |

Ordem completa: `calibracao_correlacao` → `ancora_vad_forcado` → `janela_silencio_ampliada` → `grade_fixa_locucao_estendida`.

## Documentação chave

- `DECISOES.md` — decisões técnicas e regras para evitar reversões silenciosas
- `PROCEDIMENTO_PADRAO.md` — fluxo oficial v4 (processo único com ciclo fechado)
- `docs/REGRAS_ORQUESTRACAO.md` — princípios KISS/YAGNI/DRY e regras de orquestração
- `docs/PLANEJAMENTO_JUL_AGO_2026.md` — planejamento da produção jul/ago 2026
- `docs/PRODUCAO.md` — guia de produção

## Ambiente

Copiar `.env.example` → `.env` e ajustar caminhos (BASE_DIR, BOLETINS_BRUTOS, DIR_OUTPUT,
DRIVE_SYNC, etc.). Nunca commitar o `.env` real — já está no `.gitignore`.
