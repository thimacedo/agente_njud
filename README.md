# DIVISOR — Pipeline de Produção de Jornais TJRN

Pipeline automatizado para produção de jornais (NJUDs) a partir dos boletins
de rádio da TJRN. Copia boletins do Drive H:, processa localmente (corte,
transcrição, montagem) e sincroniza os jornais prontos de volta ao H:.

---

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| `README.md` | Este arquivo — visão geral e mapa do projeto |
| `PROCEDIMENTO_PADRAO.md` | Fluxo técnico do pipeline (corte → montagem → sync) |
| `DECISOES.md` | Decisões técnicas aplicadas (histórico, não reverter) |
| `docs/PRODUCAO.md` | Procedimento de produção (genérico, qualquer mês) |
| `docs/PLANEJAMENTO_<MES>_<ANO>.md` | Planejamento específico de cada produção |

---

## Mapa do Diretório

```
DIVISOR/
├── src/                        # código-fonte
│   ├── divisor_boletins/       # pacote principal
│   │   ├── audio.py            # processamento de áudio (corte, VAD)
│   │   ├── calibracao.py       # calibração por correlação com vinhetas
│   │   ├── deteccao.py         # detecção de início/fim de fala (Silero VAD)
│   │   ├── montagem.py         # montagem dos jornais (montar_todos_jornais)
│   │   ├── config.py           # configurações centralizadas
│   │   ├── log.py              # logging
│   │   └── cli.py              # interface CLI
│   │
│   ├── pipeline/               # motores de execução
│   │   ├── dispatcher.py       # pool paralelo de workers (Whisper + VAD)
│   │   ├── monitor.py          # heartbeat e dashboard em tempo real
│   │   └── single_process.py   # processo único: ciclo fechado por arquivo
│   │
│   ├── audit/                  # auditoria e validação
│   │   ├── individual_cuts.py  # análise física por _CABECA/_CORPO
│   │   └── integrity.py        # auditoria de integridade do lote
│   │
│   ├── sync/                   # sincronização
│   │   ├── drive.py            # ÚNICA escrita permitida no H:
│   │   └── copy.py             # cópia seletiva de boletins para workspace
│   │
│   ├── plan/                   # planejamento
│   │   ├── generator.py        # gera plano_alocacao.csv
│   │   └── fixer.py            # correções de mês/ano no plano
│   │
│   └── iniciar_ciclo.py        # entry point: mata instâncias e inicia dispatcher
│
├── assets/vinhetas/            # vinhetas de áudio para calibração
├── data/                       # dados derivados
│   ├── processed/
│   │   └── PRODUCAO_<ANO>/
│   │       ├── JORNAIS_DIVIDIDOS/   # cortes CABEÇA/CORPO por NJUD
│   │       └── estado_por_arquivo/  # JSON de estado por boletim
│   └── output/
│       └── JORNAIS_FINAL/           # jornais montados (temporário)
│
├── JORNAIS/<MES>/              # entrada bruta copiada do H: (temporário)
├── docs/                       # documentação de produção
├── logs/                       # logs de todas as execuções
├── NJUDS_VALIDOS.csv           # mapeamento data útil → código NJUD
├── DECISOES.md                 # decisões técnicas
├── PROCEDIMENTO_PADRAO.md      # fluxo técnico do pipeline
└── README.md                   # este arquivo
```

---

## Fluxo Resumido

```
H: (boletins) → ETAPA 1: Copiar → JORNAIS/<MES>/
             → ETAPA 2: Dispatcher (corte) → JORNAIS_DIVIDIDOS/<NJUD>/
             → ETAPA 4: Montagem → JORNAIS_FINAL/<NJUD>/
             → ETAPA 6: Corrigir datas
             → ETAPA 7: Sync → H: (jornais prontos)
             → ETAPA 8: Limpeza local
             → ETAPA 9: Relatório
```

Para detalhes completos, ver `docs/PRODUCAO.md`.

---

## Regras Críticas

1. **H: é SOMENTE LEITURA** exceto `src/sync/drive.py` (sync final)
2. **1 NJUD = exatamente 4 boletins**
3. **Data do NJUD = data do dia útil no CSV**, nunca data do boletim de origem
4. **Nunca sobrescrever no H:** — se já existe, pular
5. **Limpeza local somente após sync confirmado no H:**
6. **Mês = data no nome do arquivo**, não a pasta física

---

*v3 — 2026-09-05. Consolidação da documentação.*
