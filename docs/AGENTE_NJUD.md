# Agente NJUD — Jornal Noticioso do TJRN

## Visão Geral

O **Agente NJUD** é responsável pela produção automática de jornais noticiosos
do Tribunal de Justiça do Rio Grande do Norte (TJRN) a partir de boletins de
rádio diários.

Cada jornal é composto por **4 boletins** (cabeça + corpo) intercalando vozes
de locutores diferentes, com vinhetas de abertura, passagem, encerramento e
trilha de fundo escalada.

## Objetivo

Produção diária de jornais de rádio com duração entre 5 e 15 minutos,
ancorados rigorosamente no início da locução (sem sujeira de vinhetas).

## Pipeline de Trabalho

```
┌─────────────────┐
│ BOLETINS BRUTOS │  ──  BOLETIM_RADIO_TJRN_DD_MM_AAAA_B{N}_*.mp3
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ DIVISÃO         │  ── Whisper + Silero VAD → detecta marcas
│ (cabeça/corpo)  │     (âncoras, passagem, fim manchete, assinatura)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ MONTAGEM        │  ── 4 boletins por jornal + vinhetas + trilha
│ (jornais)      │     (intercalação de vozes)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ AUDITORIA       │  ── Verifica integridade (duração, cortes, contexto)
│ (selo OK/refazer)│     Marca SELLO OK ou lista para refazer
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SINCRONIZAÇÃO   │  ── Copia para H:\ drive de produção
│ (Drive H:)      │
└─────────────────┘
```

## Módulos Principais

| Módulo | Arquivo | Responsabilidade |
|--------|---------|-----------------|
| **Config** | `src/divisor_boletins/config.py` | Thresholds, âncoras de texto, padrões regex |
| **Audio** | `src/divisor_boletins/audio.py` | Transcrição Whisper, corte de áudio, cache de transcrições |
| **Detecção** | `src/divisor_boletins/deteccao.py` | Detecção de âncoras, passagem (VAD+texto), fim manchete, fim corpo |
| **Montagem** | `src/divisor_boletins/montagem.py` | Montagem do jornal: 4 boletins + vinhetas + trilha escalada |
| **Calibração** | `src/divisor_boletins/calibracao.py` | Cross-correlation de vinhetas de referência nos boletins |
| **Texto** | `src/divisor_boletins/texto.py` | Normalização e similaridade de texto |
| **Log** | `src/divisor_boletins/log.py` | Log dual (TXT + JSONL) namespaced em `logs/njud/` |
| **CLI** | `src/divisor_boletins/cli.py` | Subcomandos: `dividir`, `montar` |

## Configuração (SettingsNJUD)

Define-se em `src/config/njud.py`:

```python
from config.njud import settings

# Diretórios
settings.BOLETINS_BRUTOS          # boletins_brutos/
settings.BOLETINS_CORTADOS        # data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/
settings.DIR_OUTPUT               # data/output/
settings.JORNAIS_MONTADOS         # data/output/JORNAIS_FINAL/
settings.LOGS_DIR_NJUD            # logs/njud/
settings.CACHE_TRANSCRICOES       # data/cache/njud/transcricoes/
settings.CACHE_VAD                # data/cache/njud/vad/
settings.VINHETAS_DIR             # assets/vinhetas/njud/

# Vinhetas usadas
settings.VINHETAS_DIR / "VHT_ABERTURA.mp3"
settings.VINHETAS_DIR / "VHT_PASSAGEM_BOLETIM.mp3"
settings.VINHETAS_DIR / "VHT_ENCERRAMENTO.mp3"
settings.VINHETAS_DIR / "TRILHA_ESCALADA_NJUD.mp3"

# Parâmetros de produção
settings.BOLETINS_POR_JORNAL = 4      # 4 boletins por jornal
settings.INTERCALAR_VOCES = True      # intercalar locutores A/B
settings.BLOCO_INTERCALACAO = 5       # bloco de 5 boletins para alternar voz
settings.DURACAO_MINIMA_BOLETIM = 2.0 # minutos
settings.DURACAO_MINIMA_JORNAL = 60.0 # segundos
```

## Entradas e Saídas

### Entradas
- **Boletim bruto**: `BOLETIM_RADIO_TJRN_DD_MM_AAAA_B{N}_*.mp3`
  - Ex: `BOLETIM_RADIO_TJRN_26_08_2026_B1_01.mp3`
  - Contém: VHT_ABERTURA + passagem musical + CABEÇA (manchete) + passagem + CORPO (notícias) + VHT_ENCERRAMENTO + assinatura locutor

### Saídas
- **Cortes**: `_CABECA.mp3` e `_CORPO.mp3` por boletim
  - Pasta: `data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/<mês>/<NJUD>/`
- **Jornal montado**: `NJUD_SSDD_DD-MM-AAAA.mp3` (ou `_INCOMPLETO` se <4 boletins)
  - Pasta: `data/output/JORNAIS_FINAL/`
  - Formato: SSDD = semana ISO (2d) + dia semana (2d)
- **Estado**: `estado_por_arquivo/*.json` com status (OK/ERRO/PENDENTE/ESGOTADO)
- **Logs**: `logs/njud/divisor_log.txt`, `logs/njud/divisor_log.jsonl`

## Interação com o Orquestrador

O orquestrador (`src/orchestration/safe_runner.py`) coordena o ciclo:

1. **Perceber**: conta estado atual dos NJUDs alvo (`estado_por_arquivo/`)
2. **Planejar**: se há NJUDs com 4+ OK e ainda não auditados, dispara auditoria
3. **Agir**: roda `etapa3_auditoria_montagem.py` para verificar integridade
4. **Adaptar**: se precisa refazer, reinicia o pipeline para os NJUDs afetados

Ciclo com delay configurável (default: 300s).

## Vinhetas Utilizadas

Arquivos em `assets/vinhetas/njud/`:

| Arquivo | Função |
|---------|--------|
| `VHT_ABERTURA.mp3` | Vinheta de abertura do boletim/institucional |
| `VHT_PASSAGEM_BOLETIM.mp3` | Passage instrumental entre cabeça e corpo |
| `VHT_ENCERRAMENTO.mp3` | Vinheta de encerramento |
| `TRILHA_ESCALADA_NJUD.mp3` | Trilha de fundo (20% volume) durante cabeças |

## Âncoras de Texto (Whisper)

Detectadas no áudio transcrito para ancoragem dos cortes:

**Abertura** (início da locução):
- `"boletim informativo do tribunal de justica"`
- `"noticias da hora"`
- `"no ar"`
- `"boletim informativo do rio grande do norte"`

**Encerramento** (fim da locução):
- `"voce acabou de ouvir"`
- `"obrigado por nos ouvir"`
- `"ate a proxima"`
- `"leonardo almeida"` / `"samuel ferreira"` (nomes de locutores)

**Passagem** (música instrumental):
- Detectada por **Silero VAD** (gap de não-fala) ou **gap de silêncio** no texto

## Registro de Estado

Cada arquivo processado gera um JSON em `estado_por_arquivo/`:

```json
{
  "arquivo": "BOLETIM_RADIO_TJRN_26_08_2026_B1_01.mp3",
  "njud": "NJUD 1923",
  "status": "OK",         // OK | ERRO | PENDENTE | ESGOTADO
  "cortes": ["..._CABECA.mp3", "..._CORPO.mp3"],
  "timestamp": "2026-08-26T...",
  "avisos": []
}
```

## Referências

- Receita de montagem: `assets/vinhetas/RECEITA_NJUD.txt`
- Configuração: `src/config/njud.py`
- Logs: `logs/njud/`
- Cache: `data/cache/njud/`
