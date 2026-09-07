# Agente GIRO — Giro nas Comarcas

## Visão Geral

O **Agente GIRO** é responsável pela produção semanal do programa de rádio
"**Giro nas Comarcas**" do Tribunal de Justiça do Rio Grande do Norte (TJRN).

Cada programa é gravado na terça-feira e abrange notícias da semana anterior
(segunda a domingo). O pipeline processa boletins diários do TJRN, extraindo
notícias relevantes do Rio Grande do Norte (exceto Natal e fora RN), cortando
o áudio e montando o programa final com vinhetas próprias.

## Objetivo

Produzir semanalmente um programa de rádio com notícias do TJRN das
diversas comarcas do interior do RN, com duração de 5 a 15 minutos,
filtrando geograficamente para excluir notícias de outros estados (inegociável)
e preferencialmente evitar notícias sobre Natal (ajustável).

## Pipeline de Trabalho

```
┌─────────────────┐
│ BOLETINS BRUTOS  │  ── BOLETIM_RADIO_TJRN_DD_MM_AAAA_B{N}_*.mp3
│ (do período)     │     Data: segunda → domingo da semana de notícias
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│ TRANSCREÇÃO     │  ── Whisper (CPU): transcreve áudio integral
│ (Whisper)       │     Gera segmentos com timestamps
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│ SELEÇÃO DE NOTAS│  ── Detecta início/fim de cada nota
│ (assinatura)    │     Via padrão "tribunal de justica do rio grande..."
│                 │     ou por gap de silêncio
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│ FILTRO GEO      │  ── Classifica cada nota:
│ (RN / outros /  │     ACEITA → cidade do RN (exceto Natal)
│  Natal / fora)  │     FILTRADA_OUTRO_ESTADO → inegociável
│                 │     FILTRADA_NATAL → ajustável
│                 │     AMBIGUA → sem menção geo clara
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│ CORTE DE ÁUDIO  │  ── Corta cada nota aceita do áudio original
│ (pydub)         │     Ancorando em silêncios
│                 │     Normaliza volume
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│ SALVA NOTAS     │  ── Salva GNC_<mmss>_N01_DD-MM-YY.mp3
│ (GIRO_COMARCAS) │     em data/processed/GIRO_COMARCAS/
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│ MONTAGEM        │  ── Monta programa GNC_mmss com vinhetas
│ (programa final)│     VHT_ABERTURA_GIRO + notas + VHT_ENCERRAMENTO_GIRO
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│ SINCRONIZAÇÃO   │  ── Copia para H:\ drive de produção
│ (Drive H:)      │     GNC_mmss_DD-MM-YY.mp3
└─────────────────┘
```

## Módulos Principais

| Módulo | Arquivo | Responsabilidade |
|--------|---------|-----------------|
| **Config** | `src/giro/config.py` | Thresholds, âncoras de texto, padrões regex, caminhos namespaced |
| **CLI** | `src/giro/cli.py` | Processamento (`processar`), montagem (`--montar`), planos |
| **Transcrição** | `src/giro/transcricao.py` | Transcreve boletim, detecta notas, filtra, corta áudio |
| **Filtro** | `src/giro/filtro.py` | Filtro geográfico: RN vs. outros estados vs. Natal vs. ambígua |
| **Montagem** | `src/giro/montagem.py` | Monta programa com vinhetas GIRO (abertura, passagem, encerramento) |
| **Plano** | `src/giro/plano.py` | Gera plano semanal: mmss, data terça, faixa de notícias, mês dos boletins |
| **Utils** | `src/giro/utils.py` | Conversão mmss↔data, nomenclatura de arquivos, utilitários de texto |
| **Log** | `src/giro/log.py` | Logger estruturado (logging) namespaced em `logs/giro/` |
| **Sync Drive** | `src/giro/sync_drive.py` | Sincronização com Drive H: (cpia dos programas finais) |

## Configuração (SettingsGiro)

Define-se em `src/config/giro.py` (ou `src/giro/config.py` com import de settings):

```python
from config.giro import settings

# Diretórios
settings.BASE_DIR                           # raiz do projeto
settings.DIR_PROCESSED                      # data/processed/GIRO_COMARCAS/
settings.DIR_OUTPUT                         # data/output/GIRO_COMARCAS/
settings.DIR_PLANOS                         # data/
settings.LOGS_DIR_GIRO                      # logs/giro/
settings.CACHE_TRANSCRICOES                 # data/cache/giro/transcricoes/
settings.VINHETAS_DIR                       # assets/vinhetas/giro/

# Vinhetas usadas
settings.VINHETAS_DIR / "VHT_ABERTURA_GIRO.mp3"
settings.VINHETAS_DIR / "VHT_PASSAGEM_GIRO.mp3"
settings.VINHETAS_DIR / "VHT_ENCERRAMENTO_GIRO.mp3"

# Thresholds de detecção
settings.LIMIAR_ANCORA_GIRO = 0.55           # similaridade mínima âncoras
settings.LIMIAR_FIM_PASSAGEM_GIRO = 0.8       # gap mínimo após passagem
settings.LIMIAR_INICIO_FALA_GIRO = 0.3       # silêncio antes da fala

# Filtro geográfico
settings.OUTROS_ESTADOS_PALAVRAS            # frozenset (inegociável)
settings.NATAL_PALAVRAS                     # frozenset (ajustável)
settings.RN_CIDADES                         # frozenset (cidades RN)

# Metadados
settings.ANO_PADRAO = 2026
```

## Entradas e Saídas

### Entradas
- **Boletim bruto**: `BOLETIM_RADIO_TJRN_DD_MM_AAAA_B{N}_*.mp3`
  - Ex: `BOLETIM_RADIO_TJRN_26_08_2026_B1_01.mp3`
  - Somente boletins do período da semana de notícias (segunda a domingo
    anterior à terça de gravação)

### Saídas
- **Notas processadas**: `GNC_<mmss>_N{N}_{DD-MM-YY}.mp3`
  - Pasta: `data/processed/GIRO_COMARCAS/`
  - N: índice sequencial da nota no programa
- **Estado**: `data/processed/GIRO_COMARCAS/estado/GNC_<mmss>_N{N}_estado.json`
  - Contém status (PENDENTE/OK/ESGOTADO_ACEITO/ERRO) e motivos
- **Programa montado**: `GNC_<mmss>_<DD-MM-YY>.mp3`
  - Pasta: `data/output/GIRO_COMARCAS/`
- **Logs**: `logs/giro/giro_processamento.log`, `logs/giro/giro_montagem.log`

## Filtro Geográfico

O filtro classifica cada nota transcrita em 4 categorias:

### 1. OUTRO ESTADO (INEGOCIÁVEL — rejeita)
Detecta menção a outros estados brasileiros ou suas capitais.
Base de dados: `OUTROS_ESTADOS_PALAVRAS` (frozenset).

Palavras detectadas:
- **"outros estados"**: bahia, ceará, pernambuco, paraíba, piauí, alagoas,
  sergipe, espírito santo, minas gerais, rio de janeiro, são paulo, paraná,
  santa catarina, rio grande do sul, mato grosso, mato grosso do sul,
  goiás, tocantins, amazonas, roraima, acre, amapá, pará, fernando pedroso
- **"capitais"**: salvador, fortaleza, recife, joão pessoa, maceió,
  aracaju, vitória, belo horizonte, rio de janeiro, são paulo, curitiba,
  florianópolis, porto alegre, cuiabá, campo grande, goiânia, palmas,
  manaus, boa vista, rio branco, belém

### 2. NATAL (AJUSTÁVEL — filtra se evitar_natal=True)
Detecta menção à cidade de Natal, RN, com contexto de notícia local.

Condições de detecção:
- Palavra `"natal"` + contexto (comarca, vara, juizado, tribunal, município)
- `"natal"` isolado em texto curto (≤5 palavras) com contexto judicial

### 3. CIDADES DO RN (ACEITA)
Detecta menção a alguma cidade/comarca do RN na lista `RN_CIDADES`.
Ex: mossoró, acari, caicó, patu, natal (em contexto de "comarca de natal"▲
mas aqui é OK se for "Comarca de Natal" sem a palavra-chave isolada)

### 4. INDICADORES GERAIS DO RN (ACEITA)
Detecta menção direta a:
- `"rio grande do norte"`
- `"tjrn"` (Tribunal de Justiça do RN)
- `"tribunal de justica do rio grande do norte"`
- `"tribunal de justiça do rio grande do norte"`
- `"justiça do rio grande do norte"`

### 5. AMBIGUA (mantida para revisão)
Sem menção geográfica clara — não é rejeitada, mas requer revisão humana.

## Transcrição e Detecção de Notas

### Transcrição (Whisper)
Usa `faster-whisper` com modelo configurável (`tiny` default) e `int8` em CPU.
Cache de transcrições em `data/cache/giro/transcricoes/` (MD5 do caminho).

### Detecção de Notas
Duas estratégias disponíveis:

#### a) Por assinatura (default)
Detecta padrão de assinatura de locutor em cada nota:
```regex
tribunal de justica do rio grande do norte(?: para a radio justi[çc]a)?[\s,]+[A-Za-z]+
```
Cada ocorrência = início de nova nota.

#### b) Por silêncio
Detecta gaps de ≥2.5s entre segmentos de fala (proveniente da passagem
instrumental entre notas).

## Montagem do Programa

Cada programa segue a receita:

1. **VHT_ABERTURA_GIRO** — vinheta de abertura
2. **Notas** (ordenadas por índice N{n})
   - Para cada nota: **VHT_PASSAGEM_GIRO** → nota (LOC+OFF integrados)
3. **VHT_ENCERRAMENTO_GIRO** — vinheta de encerramento

Diferente do NJUD: **não há separação CABEÇA/CORPO** — cada nota é uma
unidade self-contained (LOC + OFF juntos), e as vinhetas só aparecem ENTRE
notas, não cortando o interior das notas.

## Nomenclatura

### Código do programa (mmss)
- `mm` = mês (01..12)
- `ss` = semana dentro do mês (01..04) — conta a partir da 1ª terça

### Data da terça
Calculada pela fórmula:
```
data_terça(mm, ss) = primeira terça de janeiro + ((mm-1)*4 + (ss-1)) semanas
```
Implementação em `src/giro/utils.py` → `terça_do_programa(mmss, ano=2026)`.

### Nomes de arquivos

| Tipo | Formato | Exemplo |
|------|---------|---------|
| Nota processada | `GNC_<mmss>_N{N}_{DD-MM-YY}.mp3` | `GNC_0101_N01_06-01-26.mp3` |
| Programa montado | `GNC_<mmss>_<DD-MM-YY>.mp3` | `GNC_0101_06-01-26.mp3` |

`mmss` = código do programa, `N` = índice da nota, `DD-MM-YY` = data da terça.

## Registro de Estado

Cada nota processada gera um JSON em `data/processed/GIRO_COMARCAS/estado/`:

```json
{
  "mmss": "0101",
  "idx_nota": 1,
  "status": "OK",
  "timestamp": "2026-01-06T12:00:00+00:00",
  "motivos": []
}
```

Status possíveis: `PENDENTE`, `OK`, `ESGOTADO`, `ESGOTADO_ACEITO`, `ERRO`.

## Scripts Shell (namespaced)

| Script | Função |
|--------|--------|
| `scripts_pipeline/giro/processar.sh` | Processa boletins → notas filtradas |
| `scripts_pipeline/giro/montar.sh` | Monta programas a partir de notas |
| `scripts_pipeline/giro/sync_drive.sh` | Sincroniza com Drive H: |
| `scripts_pipeline/shared/orchestrate.py` | Orquestrador unificado (com `--giro`) |

Uso do orchestrator:
```bash
python scripts_pipeline/shared/orchestrate.py --giro processar
python scripts_pipeline/shared/orchestrate.py --giro montar
python scripts_pipeline/shared/orchestrate.py --giro sync
```

## Diferenças Chave: NJUD vs GIRO

| Característica | NJUD | GIRO |
|---------------|------|------|
| **Frequência** | Diário (4 boletins/dia) | Semanal (programa por terça) |
| **Saída** | Jornal: 4 boletins + vinhetas | Programa: notas filtradas + vinhetas |
| **Cortes** | CABEÇA/CORPO separados | Nota única (LOC+OFF integrados) |
| **Vinheta passagem** | Entre cabeça e corpo (dentro do boletim) | Entre notas (no programa final) |
| **Filtro geo** | Não aplica (todos os boletins) | Sim (RN, exceto Natal, fora RN) |
| **Código** | SSDD (semana/dia) | mmss (mês/semana) |
| **Cache transcrição** | `data/cache/njud/transcricoes/` | `data/cache/giro/transcricoes/` |
| **Logs** | `logs/njud/` | `logs/giro/` |
| **Assets vinhetas** | `assets/vinhetas/njud/` | `assets/vinhetas/giro/` |

## Referências

- Receita de montagem: `src/giro/montagem.py` (docstring)
- Configuração: `src/config/giro.py` (ou `src/giro/config.py`)
- Logs: `logs/giro/`
- Cache: `data/cache/giro/`
- Vinhetas: `assets/vinhetas/giro/`
