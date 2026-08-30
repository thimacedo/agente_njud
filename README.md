# DIVISOR — Pipeline de Boletins de Rádio TJRN

Modularizado em 2026-08-29. Estrutura canônica, sem dados na raiz.

## Mapa de diretórios

```
DIVISOR/
├── src/                  # TODO o código
│   ├── divisor_boletins/ # pacote principal (audio, calibracao, montagem, log...)
│   │
│   ├── pipeline/         # motores de execução
│   │   ├── single_process.py    # processo único: ciclo fechado por arquivo
│   │   ├── dispatcher.py        # pool paralelo de workers (Whisper + VAD)
│   │   ├── monitor.py           # heartbeat e dashboard em tempo real
│   │   └── assembly.py          # montagem automática pós-processamento
│   │
│   ├── audit/            # auditoria e validação
│   │   ├── individual_cuts.py   # análise física por _CABECA/_CORPO
│   │   ├── integrity.py         # auditoria de integridade do lote
│   │   ├── integrity_report.py  # relatórios consolidados
│   │   └── summaries.py         # resumo por método/estratégia
│   │
│   ├── sync/             # sincronização e cópia
│   │   ├── drive.py      # única escrita permitida no H:
│   │   └── copy.py       # cópia seletiva de boletins
│   │
│   ├── plan/             # planejamento
│   │   ├── generator.py  # plano_alocacao.csv a partir do Drive
│   │   ├── allocator.py  # workspace temporário + manifest
│   │   └── fixer.py      # correções de mês/ano no plano
│   │
│   ├── orchestration/    # orquestradores de topo
│   │   ├── safe_runner.py       # run_pipeline_safe_v2 (compat)
│   │   ├── intelligent.py       # pipeline v3 legado (compat)
│   │   └── journal_pipeline.py  # integração Sheets/roteiros (placeholder)
│   │
│   ├── utils/            # utilitários (logger, validator, error_handler)
│   ├── config/           # settings centralizados (.env)
│   │
│   ├── tools/            # scripts utilitários legados
│   │   ├── reprocessar_falhos.py
│   │   ├── downloader_tjrn.py
│   │   └── ...
│   │
│   ├── iniciar_ciclo.py  # entry point oficial: mata instâncias antigas e inicia
│   ├── teste_ciclo.py    # teste dirigido de UM boletim
│   └── ...
│
├── assets/vinhetas/      # VHT_ABERTURA_BOLETIM etc.
├── data/                 # TODOS os dados derivados
│   ├── plano_alocacao.csv, jornal_njuds.csv, njuds_por_mes.csv
│   ├── cache/_vinhetas_cache.pkl, cache/transcricoes/
│   ├── processed/JORNAIS_DIVIDIDOS/ # cortes CABEÇA/CORPO
│   ├── output/                       # jornais montados + _logs + relatórios
│   └── _substituidos_20260824/       # versões antigas dos CSVs (.bak)
│
├── JORNAIS/<MES>/        # entrada bruta copiada do Drive (leitura)
├── logs/                 # backups consolidados, correcoes/, relatórios de integridade
├── DECISOES.md           # regras não negociáveis — LER ANTES DE MEXER NO PIPELINE
├── PROCEDIMENTO_PADRAO.md
└── README.md
```

## Fluxo

1. `src/plan/generator.py` → lê Drive (H:, somente leitura) → `data/plano_alocacao.csv`
2. `src/sync/copy.py` → copia para `JORNAIS/<MES>/<NJUD>/`
3. `src/iniciar_ciclo.py <pasta> <saida>` → dispatcher paralelo corta/transcreve/monta → `data/output/`
4. `src/sync/drive.py` → única escrita permitida no H:

## Regras críticas

- **H: é somente leitura** exceto `src/sync/drive.py`.
- Mês = mês **no nome do arquivo**, não da pasta. 1 NJUD = 4 boletins.
- Corte nunca default 0.0 quando calibração parcial falha (âncora→VAD + log).
- Nunca deixar dois dispatchers rodando (`iniciar_ciclo.py` mata os antigos).
- Cache de vinhetas em `data/cache/` — caminho fixo, independe do CWD.

## Modularização

- Scripts movidos para pacotes: `pipeline/`, `audit/`, `sync/`, `plan/`, `orchestration/`
- Wrappers de compatibilidade mantidos na raiz com `DeprecationWarning`
- Entry points devem usar os caminhos canônicos dos pacotes
