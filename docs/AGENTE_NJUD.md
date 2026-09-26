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

## Receita Imutável (DECISOES.md Item 9)

```
VHT_ABERTURA_NJUD
→ CABEÇA 1 → CABEÇA 2 → CABEÇA 3 → CABEÇA 4
→ EFEITO_PASSAGEM_NJUD
→ CORPO 1 → CORPO 2 → CORPO 3 → CORPO 4
→ VHT_ENCERRAMENTO_NJUD
```

Toda duração é detectada dinamicamente do áudio — zero hardcoded.
BG volume lido de RECEITA_NJUD.txt (ex: "20% DO VOLUME" → dB via `20*log10(percent/100)`).
Silêncio entre blocos: mediana dos gaps do primeiro boletim (clamp 50-500ms).

## Pipeline de Trabalho

```
┌─────────────────┐
│ BOLETINS BRUTOS │  ──  BOLETIM_RADIO_TJRN_DD_MM_AAAA_B{N}_*.mp3
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ DIVISÃO         │  ── Whisper tiny/small + Silero VAD → detecta
│ (cabeça/corpo)  │     âncoras, passagem, fim manchete, assinatura
│ (divisor_boletins)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ MONTAGEM        │  ── 4 boletins por jornal + vinhetas + trilha
│ (jornais)      │     (intercalação de vozes)
│ (montagem_jornais.py)│
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

## Módulos Principais (caminho ativo em disco)

| Módulo | Arquivo | Responsabilidade |
|--------|---------|-----------------|
| **Divisão** | `scripts_pipeline/divisor_boletins/__main__.py` | CLI: `python -m divisor_boletins dividir <entrada> <saida> --apply` |
| **Audio** | `scripts_pipeline/divisor_boletins/audio.py` | Transcrição faster-whisper, calibração, corte CABEÇA/CORPO, `buscar_ancora()` |
| **Detecção** | `scripts_pipeline/divisor_boletins/deteccao.py` | Detecção de âncora de encerramento por regex institucional (busca de trás pra frente na transcrição) |
| **Calibração** | `scripts_pipeline/divisor_boletins/calibracao.py` | Cross-correlation de vinhetas de referência nos boletins |
| **Log** | `scripts_pipeline/divisor_boletins/log.py` | Log estruturado (LogPipeline) |
| **Montagem** | `scripts_pipeline/montagem_jornais.py` | Montagem do jornal: 4 boletins + vinhetas NJUD + trilha escalada |
| **Script orquestrador** | `scripts_pipeline/njud/njud_dividir.sh` | Subcomandos: `divide` (divisor_boletins) e `montar` (montagem_jornais.py) |

### Nota sobre divisão x montagem

O `divisor_boletins` gera os cortes (`_CABECA.mp3`, `_CORPO.mp3`) em subdiretórios
`<boletim>_saida/` dentro de `data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/<NJUD>/`.
O `montagem_jornais.py` lê esses cortes prontos e monta o jornal final —
não re-transcreve os boletins.

### Sobre a contradição "eliminado vs em uso" do divisor_boletins

DECISOES.md Item 19/20 (2026-09-25) — a decisão mais recente — estabelece que
boletins individualizados (`BOLETIM_RADIO_TJRN_DD_MM_AAAA_Bx_...mp3`) usam o
pipeline padrão (`divisor_boletins`), sem roteiro. Só arquivos concatenados com
múltiplas claquetes (`DD MES Bx-By.mp3`) usam `processar_boletim_canonico.py`.

Alegação do `divisor-pipeline` skill de que `divisor_boletins` foi "eliminado
em 2026-09-18" é anterior a essas decisões e sobreposta pela decisão datada
mais recente (princípio do DECISOES.md: evitar reversão silenciosa por
informação desatualizada). Consequência prática: `divisor_boletins` continua
em produção para boletins individualizados NJUD.

## Configuração (via env vars — DECISOES.md Item 10)

```python
# Nenhum caminho hardcoded. Todos via env var com default relativo a BASE_DIR.
DIVISOR_BASE_DIR          # raiz do projeto (default: pai de scripts_pipeline/)
NJUD_JORNAIS_DIVIDIDOS_DIR  # data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS
NJUD_JORNAIS_FINAL_DIR      # data/output/JORNAIS_FINAL
NJUD_ASSETS_VINHETAS_DIR    # assets/vinhetas/njud
NJUD_VHT_ABERTURA_NOME      # VHT_ABERTURA_NJUD.mp3
NJUD_VHT_PASSAGEM_NOME      # EFEITO_PASSAGEM_NJUD.mp3
NJUD_VHT_ENCERRAMENTO_NOME  # VHT_ENCERRAMENTO_NJUD.mp3
NJUD_BOLETINS_POR_JORNAL    # 4
```

## Entradas e Saídas

### Entradas
- **Boletim bruto**: `BOLETIM_RADIO_TJRN_DD_MM_AAAA_B{N}_*.mp3`
  - Ex: `BOLETIM_RADIO_TJRN_26_01_2026_B1_01.mp3`
  - Contém: VHT_ABERTURA + passagem musical + CABEÇA (manchete) + passagem + CORPO (notícias) + VHT_ENCERRAMENTO + assinatura locutor

### Saídas
- **Cortes**: `_CABECA.mp3` e `_CORPO.mp3` por boletim
  - Pasta: `data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/<NJUD>/<boletim>_saida/`
  - Ex: `data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/NJUD_1/B1_saida/B1_CABECA.mp3`
- **Jornal montado**: `NJUD_<numero>_<DD-MM-AAAA>.mp3`
  - Pasta: `data/output/JORNAIS_FINAL/`
  - Ex: `NJUD_1_26-01-2026.mp3`
- **Logs**: `data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/logs/`

### Validação de disco (nunca confiar em "CONCLUÍDA" impresso)

```bash
# Verificar cortes
find data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS -name "*_CABECA.mp3"
find data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS -name "*_CORPO.mp3"
ffprobe -v error -show_entries format=duration,size -of csv=p=0 <arquivo>

# CORPO deve ter tamanho > 1MB (nunca 671 bytes = vazio)
# CABEÇA deve ter duração 3-30s (nunca 0s)
```

## Âncoras de Texto (Whisper)

**Divisor (buscar_ancora em deteccao.py):**
Busca por padrão institucional de encerramento procurando de trás para frente
na transcrição. Usa regex estrutural (frase institucional + posição no fim),
não nome de locutor específico. Se não encontrar, retorna None (cai no fim do áudio).

**Vinheta de abertura:**
- `"notícias da hora"` / `"boletim informativo"` / `"no ar"`

**Encerramento:**
- `"você acabou de ouvir"` / `"obrigado por nos ouvir"` / `"até a próxima"`

## Vinhetas Utilizadas

Arquivos em `assets/vinhetas/njud/`:

| Arquivo | Função |
|---------|--------|
| `VHT_ABERTURA_NJUD.mp3` | Vinheta de abertura do jornal |
| `EFEITO_PASSAGEM_NJUD.mp3` | Passagem instrumental entre boletins |
| `VHT_ENCERRAMENTO_NJUD.mp3` | Vinheta de encerramento |
| `TRILHA_ESCALADA_NJUD.mp3` | Trilha de fundo (volume da RECEITA_NJUD.txt) durante cabeças |

**VINHETAS DE BOLETIM (`*_BOLETIM.mp3`) NÃO SÃO USADAS em NJUD** (Item 9, regra 1).

## Gate por-NJUD (DECISOES.md Item 6/6b)

Nenhum jornal é montado com peça pendente:
- Exige as 4 cabeças E os 4 corpos presentes antes de montar
- Se faltar qualquer peça: jornal NÃO será montado (nunca parcial)
- Log de aviso listando NJUDs não montados

## Registro de Estado

Cada NJUD gera metadados:
```json
{
  "nome": "NJUD_1_26-01-2026",
  "data_geracao": "2026-09-26T08:19:53",
  "duracao_total_s": 374.0,
  "arquivo_final": "data/output/JORNAIS_FINAL/NJUD_1_26-01-2026.mp3",
  "bg_volume_percent": 20,
  "silence_between_blocks_ms": 230,
  "boletins": [
    {"boletim": 1, "arquivo": "B1.mp3", "duracao_cabeca_s": 5.7, "duracao_corpo_s": 73.8}
  ]
}
```

## Lições Aprendidas (2026-09-26)

### Raiz do bug do `_CORPO.mp3` vazio (671 bytes)

**Causa:** `buscar_ancora()` sempre retornava `tempo_ancora_s=0.0` porque
nunca detectava a assinatura de encerramento de fato. Em `_salvar_cortado()`,
`tempo_assinatura_s = 0.0` (não `None`), fazendo `cortar_audio()` fazer
`corpo = audio[fim_cabeca_ms : 0]` — um slice vazio.

**Correção:** `buscar_ancora()` agora faz regex de padrão institucional
buscando de trás pra frente na transcrição. Se não achar, retorna `None`
(caindo no fim do áudio). `transcrever_audio()` expõe segmentos com timestamps.

### `njud_dividir.sh` e `montagem_jornais.py`

**Problema:** `njud_dividir.sh` chamava `$SCRIPTS_DIR/montagem_jornais.py`
que não existia em disco. `montar_jornal.py` fazia tudo (transcrição + montagem)
mas o fluxo correto é: `divisor_boletins` gera cortes → `montagem_jornais.py`
recebe cortes prontos e monta.

**Correção:** Criado `scripts_pipeline/montagem_jornais.py` (15KB).
`njud_dividir.sh` restaurado para chamar `montagem_jornais.py`.

### Estrutura de diretórios

**Problema:** `divisor_boletins` gera cortes em `B1_saida/`, `B2_saida/`, etc.
diretamente em `JORNAIS_DIVIDIDOS/`, mas `montagem_jornais.py` espera
`JORNAIS_DIVIDIDOS/<NJUD>/<boletim>_saida/`.

**Solução:** Organizar cortes em `JORNAIS_DIVIDIDOS/NJUD_1/` (ou similar).

## Referências

- Receita de montagem: `assets/vinhetas/njud/RECEITA_NJUD.txt`
- DECISOES.md Item 9 (receita imutável), Item 19/20 (divisor_boletins em uso)
- Scripts: `scripts_pipeline/njud/njud_dividir.sh`, `scripts_pipeline/montagem_jornais.py`
- Auditores: `scripts_pipeline/boletim/auditoria_proativa.py` (não aplicável a NJUD por Item 19)
