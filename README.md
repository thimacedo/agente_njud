# DIVISOR — Pipeline de Boletins de Rádio TJRN

Reorganizado em 2026-08-24. Estrutura modular com separação por responsabilidade.

## Mapa de diretórios

```
DIVISOR/
├── src/                      # TODO o código
│   ├── __init__.py           # Pacote principal
│   ├── cli/                  # Pontos de entrada (CLI)
│   │   ├── __init__.py
│   │   ├── iniciar_ciclo.py            # Entry point: mata instâncias antigas e inicia dispatcher+monitor
│   │   ├── monitor_tempo_real.py       # heartbeat/tempo real
│   │   └── dashboard_streamlit.py      # Dashboard web
│   ├── core/                 # Motor principal do pipeline
│   │   ├── __init__.py
│   │   ├── divisor_boletins/ # pacote principal (audio, calibracao, montagem, log...)
│   │   ├── dispatcher_paralelo.py      # processamento paralelo (Whisper + VAD)
│   │   ├── processo_unico.py           # ciclo corte->auditoria->reaprendizado
│   │   ├── pipeline_jornal.py          # integração com planilha (MÉTODO 2)
│   │   ├── executar_reprocessamento.py # reprocessamento seguro
│   │   └── run_pipeline_safe_v2.py     # pipeline seguro v2
│   ├── services/             # Integração com dados e serviços externos
│   │   ├── __init__.py
│   │   ├── gerar_plano.py              # gera data/plano_alocacao.csv a partir do Drive
│   │   ├── copiar_boletins.py          # copia JORNAIS conforme plano
│   │   ├── corrigir_plano.py           # corrige mes_destino/ano no plano
│   │   ├── planejador_copia.py         # planejamento de cópia
│   │   └── sincronizar_drive.py        # ÚNICO script com escrita no H: (regra DRIVE)
│   ├── utils/                # Ferramentas auxiliares
│   │   ├── __init__.py
│   │   ├── monitor_job.py              # monitor de jobs
│   │   ├── monitor_montagem_auto.py    # monitor de montagem automática
│   │   ├── monitor_paralelo_simples.py # monitor simples (legado)
│   │   ├── analisar_cortes_individuais.py
│   │   ├── rodar_auditoria.py
│   │   ├── relatorio_audit.py
│   │   ├── resumo_metodos.py
│   │   └── teste_ciclo.py
│   └── scripts/              # Scripts de tarefa única
│       ├── __init__.py
│       └── reprocessar_agosto.sh
├── assets/vinhetas/          # VHT_ABERTURA_BOLETIM etc. (BOLETIM vs NJUD — ver DECISOES.md)
├── data/                     # TODOS os dados derivados
│   ├── plano_alocacao.csv, jornal_njuds.csv, njuds_por_mes.csv,
│   │   njuds_faltantes.csv, alocacao_boletins.csv, plano_*.csv
│   ├── cache/_vinhetas_cache.pkl   # cache de calibração (caminho fixo em calibracao.py)
│   ├── processed/JORNAIS_DIVIDIDOS/ # cortes CABEÇA/CORPO
│   ├── output/                       # jornais montados + _logs + relatórios
│   └── _substituidos_20260824/       # versões antigas dos CSVs (.bak)
├── JORNAIS/<MES>/            # entrada bruta copiada do Drive (leitura)
├── logs/                     # backups consolidados, correcoes/, relatórios de integridade
├── DECISOES.md               # regras não negociáveis — LER ANTES DE MEXER NO PIPELINE
├── PROCEDIMENTO_PADRAO.md
└── README.md
```

## Fluxo

1. `python -m src.services.gerar_plano` → lê Drive (H:, somente leitura) → `data/plano_alocacao.csv`
2. `python -m src.services.copiar_boletins --apply` → copia para `JORNAIS/<MES>/<NJUD>/`
3. `python -m src.cli.iniciar_ciclo <pasta_boletins> <pasta_saida>` → dispatcher paralelo corta/transcreve/monta → `data/output/`
4. `python -m src.services.sincronizar_drive` → única escrita permitida no H:

## Comandos principais

```bash
# Gerar plano de alocação
python -m src.services.gerar_plano

# Copiar boletins conforme o plano (dry-run primeiro!)
python -m src.services.copiar_boletins --dry-run
python -m src.services.copiar_boletins --apply

# Iniciar ciclo de processamento
python -m src.cli.iniciar_ciclo <pasta_boletins> <pasta_saida>

# Monitorar em tempo real
python -m src.cli.monitor_tempo_real <pasta_saida>

# Sincronizar resultados com Drive
python -m src.services.sincronizar_drive
```

## Regras críticas

- **H: é somente leitura** exceto `src/services/sincronizar_drive.py`.
- Mês = mês **no nome do arquivo**, não da pasta. 1 NJUD = 4 boletins.
- Corte nunca default 0.0 quando calibração parcial falha (âncora→VAD + log).
- Nunca deixar dois dispatchers rodando (`iniciar_ciclo.py` mata os antigos).
- Cache de vinhetas em `data/cache/` — caminho fixo, independe do CWD.
