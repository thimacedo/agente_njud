# DIVISOR — Pipeline de Boletins de Rádio TJRN

Reorganizado em 2026-08-24. Estrutura única, sem dados na raiz.

## Mapa de diretórios

```
DIVISOR/
├── src/                  # TODO o código
│   ├── divisor_boletins/ # pacote principal (audio, calibracao, montagem, log...)
│   ├── dispatcher_paralelo.py      # processamento paralelo (Whisper + VAD)
│   ├── iniciar_ciclo.py            # entry point: mata instâncias antigas e inicia dispatcher+monitor
│   ├── monitor_tempo_real.py       # heartbeat/tempo real
│   ├── gerar_plano.py              # gera data/plano_alocacao.csv a partir do Drive
│   ├── copiar_boletins.py          # copia JORNAIS conforme plano
│   ├── executar_reprocessamento.py / run_pipeline_safe_v2.py
│   ├── corrigir_plano.py           # corrige mes_destino/ano no plano
│   ├── analisar_cortes_individuais.py / rodar_auditoria.py / relatorio_audit.py / resumo_metodos.py
│   └── sincronizar_drive.py        # ÚNICO script com escrita no H: (regra DRIVE)
├── assets/vinhetas/      # VHT_ABERTURA_BOLETIM etc. (BOLETIM vs NJUD — ver DECISOES.md)
├── data/                 # TODOS os dados derivados
│   ├── plano_alocacao.csv, jornal_njuds.csv, njuds_por_mes.csv,
│   │   njuds_faltantes.csv, alocacao_boletins.csv, plano_*.csv
│   ├── cache/_vinhetas_cache.pkl   # cache de calibração (caminho fixo em calibracao.py)
│   ├── processed/JORNAIS_DIVIDIDOS/ # cortes CABEÇA/CORPO
│   ├── output/                       # jornais montados + _logs + relatórios
│   └── _substituidos_20260824/       # versões antigas dos CSVs (.bak)
├── JORNAIS/<MES>/        # entrada bruta copiada do Drive (leitura)
├── logs/                 # backups consolidados, correcoes/, relatórios de integridade
├── DECISOES.md           # regras não negociáveis — LER ANTES DE MEXER NO PIPELINE
├── PROCEDIMENTO_PADRAO.md
└── README.md
```

## Fluxo

1. `src/gerar_plano.py` → lê Drive (H:, somente leitura) → `data/plano_alocacao.csv`
2. `src/copiar_boletins.py` → copia para `JORNAIS/<MES>/<NJUD>/`
3. `src/iniciar_ciclo.py <pasta> <saida>` → dispatcher paralelo corta/transcreve/monta → `data/output/`
4. `src/sincronizar_drive.py` → única escrita permitida no H:

## Regras críticas

- **H: é somente leitura** exceto `sincronizar_drive.py`.
- Mês = mês **no nome do arquivo**, não da pasta. 1 NJUD = 4 boletins.
- Corte nunca default 0.0 quando calibração parcial falha (âncora→VAD + log).
- Nunca deixar dois dispatchers rodando (`iniciar_ciclo.py` mata os antigos).
- Cache de vinhetas em `data/cache/` — caminho fixo, independe do CWD.
