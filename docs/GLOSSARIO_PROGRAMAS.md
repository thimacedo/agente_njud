# Glossário dos Programas — TJRN Rádio

> **Regra de ouro para qualquer agente/dev que for mexer neste repositório:**
> Antes de editar, criar ou apagar qualquer script relacionado a um programa,
> confirme em qual dos três programas abaixo ele se encaixa. Se não conseguir
> confirmar com certeza, **pare e pergunte** — não assuma por semelhança de nome.
>
> Fonte de verdade machine-readable: `src/registro_programas.py`
> (importe as constantes de lá em vez de recriar strings/paths na mão).

---

## 1. NJUD — Jornal Noticioso do Judiciário

| | |
|---|---|
| **Repositório** | `agente_njud` (principal) |
| **Orquestração de alto nível** | `src/orchestration/safe_runner.py` |
| **Ponto de entrada / scripts** | `run_pipeline_safe_v2.py`, `iniciar_ciclo.py`, `reprocessar_agosto.sh` |
| **Worker pool** | `src/pipeline/dispatcher.py` (via `run_dispatcher.sh`) |
| **Trilha de fundo** | `TRILHA_ESCALADA_NJUD.mp3`, overlay a 20% fixo (ou `bgm_mixer.py` com ducking, opt-in) — em `src/divisor_boletins/montagem.py` |
| **Identificador em constantes** | `PROGRAMA_NJUD` |

## 2. GIRO (GIRO nas Comarcas)

| | |
|---|---|
| **Repositório** | `agente_njud` |
| **Orquestração** | `scripts_pipeline/executar_programa.py` (via `rodar_tudo_giro.sh`) |
| **Identificador em constantes** | `PROGRAMA_GIRO` |
| **Nota** | `src/giro/*` está **deprecado** (código morto confirmado) — não confundir com o pipeline ativo acima |

## 3. BOLETIM

| | |
|---|---|
| **Repositório** | `agente_njud` (mesmo repo do NJUD, pipeline **distinto**) |
| **Orquestração / pipeline principal** | `montagem_boletins.py` |
| **Função de auditoria** | `auditar_boletim()` (LUFS, duração, existência) em `src/gravador_inteligente/montagem_boletins.py` |
| **Identificador em constantes** | `PROGRAMA_BOLETIM` |

---

## Por que a confusão acontece (diagnóstico)

1. **Nomes de scripts/pastas parecidos** entre os três programas.
2. **Falta de doc central** — este arquivo existe para resolver isso.
3. **Configs/paths compartilhados** (Drive `H:`, trilhas de áudio, etc.) — mesmo diretório físico, programas diferentes.
4. **Disputa histórica pelo mesmo orquestrador** — havia 8+ orquestradores concorrentes não-deprecados; a maioria já foi movida para `.trash/`.

## Convenção daqui pra frente

- **Nunca** hardcodar o nome do programa como string solta em código novo — importar de `src/registro_programas.py`.
- Scripts de sync: cada programa tem (ou deve ter) **um único** script de sync oficial.
- Ao criar função/variável nova que é específica de um programa, **sufixar com o identificador** (`_njud`, `_giro`, `_boletim`) em vez de nome genérico.
- Se um agente de IA (Claude, etc.) for tocar em qualquer um destes pipelines, a primeira ação deve ser ler este glossário e/ou `registro_programas.py` — não inferir pelo nome do arquivo.

---

## Arquitetura de Isolamento

```
DIVISOR/
├── src/
│   ├── registro_programas.py    # Fonte única de verdade
│   ├── isolamento.py            # Guard de isolamento
│   └── ...
├── regras/
│   └── livro.py                 # Regras universais
├── scripts_pipeline/
│   ├── executar_programa.py     # Pipeline oficial unificado
│   └── giro/
│       ├── fix_notes_v2.py      # Seleção de notas (GIRO)
│       └── montar_gnc_v2.py     # Montagem de GNCs (GIRO)
├── data/
│   ├── output/
│   │   ├── GIRO/                # Saída isolada GIRO
│   │   ├── NJUD/                # Saída isolada NJUD
│   │   └── BOLETIM/             # Saída isolada BOLETIM
│   └── staging/
│       ├── GIRO/                # Staging isolado GIRO
│       ├── NJUD/                # Staging isolado NJUD
│       └── BOLETIM/             # Staging isolado BOLETIM
├── GIRO/                        # Pasta raiz GIRO (cortes, etc.)
├── NJUD/                        # Pasta raiz NJUD
└── BOLETIM/                     # Pasta raiz BOLETIM
```

## Regras Universais (`regras/livro.py`)

| Regra | Descrição |
|-------|-----------|
| Janela de coleta | `[X-6, X-1]` dias ANTERIORES à exibição |
| Min/Max notas | 4-6 por programa |
| Nomenclatura | `BOLETIM_RADIO_TJRN_DD_MM_AAAA_BX_*` (imutável) |
| Id boletim | `BX_titulo` (ex: `B1_CNJ_CONCILIAR`) |

---

## Histórico de Decisões Relacionadas

- **Decisão #14**: Fallback cross-month existe em `src/giro/cli.py` (código morto) mas NÃO está na cadeia de produção ativa.
- **Decisão #15**: Scripts de sync oficiais — cada programa tem o seu, sem mistura.
- **Decisão #16**: `src/giro/*` é código morto — não usar, não modificar, não importar.
