# Plano de Modularização: NJUD vs GIRO (v2)

## 1. Visão Geral

Este documento define a estratégia de modularização para **evitar conflitos** entre os dois
programas de produção de áudio do TJRN:

| Programa | Código | Formato de saída | Vinhetas | Estrutura de cortes | Frequência |
|----------|--------|-------------------|----------|--------------------|------------|
| **NJUD** (Jornal Noticioso) | SSDD (semana/dia) | `data/output/JORNAIS_FINAL/` | VHT_ABERTURA, VHT_PASSAGEM_BOLETIM, VHT_ENCERRAMENTO, TRILHA_ESCALADA | 4 pares (`_CABECA.mp3` / `_CORPO.mp3`) por pasta NJUD | Diário |
| **GIRO nas Comarcas** | mmss (mês/semana) | `data/output/GIRO_COMARCAS/` | VHT_ABERTURA_GIRO, VHT_PASSAGEM_GIRO, VHT_ENCERRAMENTO_GIRO | Notas self-contained (`GNC_mmss_N01_*.mp3`) | Semanal |

---

## 2. Diagnóstico: Problemas Reais (não apenas riscos futuros)

### 2.1. WHISPER_MODEL: 6 fontes de verdade divergentes (BUG ATUAL)

Este é o problema mais grave — existe **hoje**, não é risco futuro:

| Arquivo | Modelo | compute_type |
|---|---|---|
| `divisor_boletins/config.py` | `tiny` | `int8` |
| `pipeline/dispatcher.py` (2x) | `tiny` | `int8` |
| `audit/integrity.py` | `small` | `int8` |
| `audit/individual_cuts.py` | `small` | `int8` |
| `tools/executar_reprocessamento.py` | `small` | `int8` |
| `teste_ciclo.py` | `small` | `int8` |
| `giro/transcricao.py` | `tiny` | `int8` |

**Consequência**: o modelo que transcreve para o NJUD (`pipeline/dispatcher.py`) é `tiny`, mas o que audita (`audit/integrity.py`) é `small`. Resultado: transcrição e auditoria usam modelos diferentes → inconsistência silenciosa.

**Solução**: `BaseSettings.WHISPER_MODEL = "tiny"` (padrão compatível com hardware atual i5-8600K sem GPU). Todos os 6+ lugares devem usar `settings.WHISPER_MODEL`.

### 2.2. giro/config.py duplica `_base_dir()`

O `giro/config.py` define `_base_dir()` que é idêntico ao `settings.py`. Após a modularização, `giro/config.py` importa `BaseSettings` e não precisa mais disso.

### 2.3. giro/log.py usa `Path("logs")` relativo ao CWD (BUG)

```python
# giro/cli.py
if log_dir is None:
    log_dir = Path("logs")   # ← relativo ao CWD, não absoluto
```

O NJUD usa `settings.LOGS_DIR` (absoluto, derivado de `BASE_DIR`). Se alguém rodar `python -m giro` de fora da raiz do projeto, logs caem em lugar imprevisível.

**Solução**: `BaseSettings.LOGS_DIR` absoluto + `giro/log.py` usa `settings.LOGS_DIR / "giro"`.

### 2.4. Thresholds de corte nunca foram "compartilhados"

`DURACAO_MINIMA_BOLETIM`, `DURACAO_MINIMA_JORNAL`, `LIMIAR_SILENCIO`, `MAX_RETRIES`, `RETRY_DELAY`, `RETRY_BACKOFF` moram no `settings.py` "compartilhado" mas **só são usados pelo NJUD**. O GIRO tem seus próprios (`LIMIAR_ANCORA_GIRO`, etc.).

**Solução**: esses thresholds vão para `SettingsNJUD`, não para `BaseSettings`. `BaseSettings` fica enxuta.

### 2.5. GIRO ainda não transcriz áudio de verdade (lacuna)

O `giro/transcricao.py` criado nesta sessão implementa transcrição com `faster-whisper`, detecção de notas por assinatura, filtro geográfico e corte. Mas o `cli.py` ainda não gera MP3s — o pipeline completo não foi verificado end-to-end. A Fase 3 (isolar cache) só faz sentido **após** o GIRO ter transcrição funcionando com output real.

---

## 3. Arquitetura-Alvo

### 3.1. BaseSettings enxuta (compartilhada)

```python
# src/config/__init__.py
class BaseSettings:
    PROJETO_NOME: str = "DIVISOR"
    VERSAO_PIPELINE: str = "2.0.0"
    BASE_DIR: Path = Path(__file__).resolve().parents[2]
    ASSETS_DIR: Path = BASE_DIR / "assets"
    LOGS_DIR: Path = BASE_DIR / "logs"
    WHISPER_MODEL: str = "tiny"        # compatível com i5-8600K sem GPU
    COMPUTE_TYPE: str = "int8"
```

### 3.2. SettingsNJUD (herda BaseSettings)

```python
# src/config/njud.py
class SettingsNJUD(BaseSettings):
    BOLETINS_BRUTOS: Path = BASE_DIR / "data/boletins_brutos"
    BOLETINS_CORTADOS: Path = BASE_DIR / "data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS"
    JORNAIS_MONTADOS: Path = BASE_DIR / "data/output/JORNAIS_FINAL"
    DRIVE_SYNC_NJUD: Path = Path(r"H:\...\02_JORNAIS_NJUD\03_AUDIOS_RADIO")
    VINHETAS_DIR: Path = BASE_DIR / "assets/vinhetas/njud"
    CACHE_DIR: Path = BASE_DIR / "data/cache/njud"
    BOLETINS_POR_JORNAL: int = 4
    INTERCALAR_VOCES: bool = True
    BLOCO_INTERCALACAO: int = 5
    # Thresholds de corte (nunca foram compartilhados — exclusivos do NJUD)
    DURACAO_MINIMA_BOLETIM: float = 30.0
    DURACAO_MINIMA_JORNAL: float = 600.0
    LIMIAR_SILENCIO: float = -38.0
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 2.0
    RETRY_BACKOFF: float = 2.0
```

### 3.3. SettingsGiro (herda BaseSettings)

```python
# src/config/giro.py
class SettingsGiro(BaseSettings):
    DIR_PROCESSED: Path = BASE_DIR / "data/processed/GIRO_COMARCAS"
    DIR_OUTPUT: Path = BASE_DIR / "data/output/GIRO_COMARCAS"
    DIR_PLANOS: Path = BASE_DIR / "data"
    DRIVE_SYNC_GIRO: Path = Path(r"H:\...\02_JORNAIS_GIRO\03_AUDIOS_RADIO")
    VINHETAS_DIR: Path = BASE_DIR / "assets/vinhetas/giro"
    CACHE_DIR: Path = BASE_DIR / "data/cache/giro"
    # Thresholds específicos do GIRO
    LIMIAR_ANCORA_GIRO: float = 0.55
    LIMIAR_FIM_PASSAGEM_GIRO: float = 0.8
    LIMIAR_INICIO_FALA_GIRO: float = 0.3
```

---

## 4. Plano de Execução (Fases Revisadas)

### Fase 1: Criar BaseSettings + migrar WHISPER_MODEL (ALTA)

**Objetivo**: eliminar as 6+ fontes de verdade para `WhisperModel`.

| Tarefa | Arquivo | Detalhe |
|--------|---------|---------|
| Criar `BaseSettings` | `src/config/__init__.py` | `BASE_DIR`, `LOGS_DIR`, `ASSETS_DIR`, `PROJETO_NOME`, `VERSAO_PIPELINE`, `WHISPER_MODEL="tiny"`, `COMPUTE_TYPE="int8"` |
| Criar `SettingsNJUD` | `src/config/njud.py` | Herda BaseSettings + paths NJUD + thresholds de corte |
| Criar `SettingsGiro` | `src/config/giro.py` | Herda BaseSettings + paths GIRO + thresholds GIRO |
| Atribuir `WHISPER_MODEL` | `divisor_boletins/config.py` | Trocar `MODELO_WHISPER = "tiny"` por `from config.njud import settings` → `settings.WHISPER_MODEL` |
| Atribuir `WHISPER_MODEL` | `pipeline/dispatcher.py` (2x) | `WhisperModel(settings.WHISPER_MODEL, ...)` |
| Atribuir `WHISPER_MODEL` | `audit/integrity.py` | `WhisperModel(settings.WHISPER_MODEL, ...)` |
| Atribuir `WHISPER_MODEL` | `audit/individual_cuts.py` | `WhisperModel(settings.WHISPER_MODEL, ...)` |
| Atribuir `WHISPER_MODEL` | `tools/executar_reprocessamento.py` | `WhisperModel(settings.WHISPER_MODEL, ...)` |
| Atribuir `WHISPER_MODEL` | `teste_ciclo.py` | `WhisperModel(settings.WHISPER_MODEL, ...)` |
| Atribuir `WHISPER_MODEL` | `giro/transcricao.py` | `WhisperModel(settings.WHISPER_MODEL, ...)` |
| Migrar thresholds NJUD | `divisor_boletins/config.py` | Mover `DURACAO_MINIMA_*`, `LIMIAR_SILENCIO`, `MAX_RETRIES`, etc. para `SettingsNJUD` |
| Atualizar `giro/config.py` | `src/giro/config.py` | Remover `_base_dir()`, importar de `config.giro.settings` |

**Validação**: `grep -rn 'WhisperModel(' src/` deve mostrar apenas `settings.WHISPER_MODEL`, nunca literal.

### Fase 2: Isolar Logs (ALTA)

**Objetivo**: logs absolutos e namespaced.

| Tarefa | Arquivo | Detalhe |
|--------|---------|---------|
| Atualizar `giro/log.py` | `src/giro/log.py` | Usar `settings.LOGS_DIR / "giro"` (absoluto) |
| Atualizar `giro/cli.py` | `src/giro/cli.py` | `log_dir = settings.LOGS_DIR / "giro"` (não `Path("logs")`) |
| Atualizar `divisor_boletins/log.py` | `src/divisor_boletins/log.py` | Usar `settings.LOGS_DIR / "njud"` |
| Atualizar `divisor_boletins/cli.py` | `src/divisor_boletins/cli.py` | Usar `settings.LOGS_DIR / "njud"` |

### Fase 3: Verificar transcrição GIRO end-to-end (ALTA)

**Objetivo**: garantir que o GIRO gera MP3s reais antes de isolar cache.

| Tarefa | Arquivo | Detalhe |
|--------|---------|---------|
| Corrigir caminho de saída | `src/giro/cli.py` | `saida = DIR_PROCESSED` (não `DIR_PROCESSED.parent / "output"`) |
| Verificar geração de MP3 | `src/giro/transcricao.py` | `cortar_nota()` salva em `pasta_saida / nome_arquivo` |
| Testar pipeline completo | CLI | `python -m src.giro <pasta> --mmss 0203` → MP3s em `data/processed/GIRO_COMARCAS/0203/` |
| Validar filtro geográfico | Resultado | Notas de Natal filtradas, notas de outro estado excluídas |

### Fase 4: Isolar Caches (MÉDIA — só após Fase 3)

| Tarefa | Arquivo | Detalhe |
|--------|---------|---------|
| Cache NJUD | `src/divisor_boletins/audio.py` | `settings.CACHE_DIR / "transcricoes"` |
| Cache GIRO | `src/giro/transcricao.py` | `settings.CACHE_DIR / "transcricoes"` |
| Cache VAD | `src/divisor_boletins/deteccao.py` | `settings.CACHE_DIR / "vad"` |

### Fase 5: Isolar Assets de Vinhetas (MÉDIA)

| Tarefa | Arquivo | Detalhe |
|--------|---------|---------|
| Criar subpastas | `assets/vinhetas/njud/`, `assets/vinhetas/giro/` | Mover arquivos existentes |
| Atualizar `SettingsNJUD.VINHETAS_DIR` | `src/config/njud.py` | `BASE_DIR / "assets/vinhetas/njud"` |
| Atualizar `SettingsGiro.VINHETAS_DIR` | `src/config/giro.py` | `BASE_DIR / "assets/vinhetas/giro"` |
| Atualizar `divisor_boletins/montagem.py` | — | Usar `settings.VINHETAS_DIR` |
| Atualizar `divisor_boletins/calibracao.py` | — | Usar `settings.VINHETAS_DIR` |
| Atualizar `giro/montagem.py` | — | Usar `settings.VINHETAS_DIR` |

### Fase 6: Shell Scripts Separados (BAIXA)

| Tarefa | Arquivo | Detalhe |
|--------|---------|---------|
| Criar `scripts_pipeline/njud/` | Novos | `prepare.sh`, `montar.sh`, `auditar.sh`, `sync_drive.sh` |
| Criar `scripts_pipeline/giro/` | Novos | `processar.sh`, `montar.sh`, `sync_drive.sh` |
| Criar `scripts_pipeline/shared/orchestrate.py` | Novo | Ponto único com `--njud` / `--giro` |

### Fase 7: Separar Orquestrador (BAIXA)

| Tarefa | Arquivo | Detalhe |
|--------|---------|---------|
| Mover `orquestrador.py` | `scripts_pipeline/njud/orquestrador.py` | NJUD only |
| Criar `giro/orquestrador.py` | Novo | Ciclo semanal GIRO |

---

## 5. Regras de Isolamento (Fail-Closed)

1. **Nenhum import cruzado**: `divisor_boletins` NUNCA importa de `giro` e vice-versa
2. **Settings namespaced**: cada módulo só lê seu próprio `settings` (nunca o `BaseSettings` diretamente)
3. **Logs namespaced**: `logs/njud/` e `logs/giro/` — nada em `logs/` raiz
4. **Assets namespaced**: `assets/vinhetas/njud/` e `assets/vinhetas/giro/`
5. **Cache namespaced**: `data/cache/njud/` e `data/cache/giro/`
6. **WHISPER_MODEL centralizado**: `BaseSettings.WHISPER_MODEL` — zero literais no código
7. **Thresholds de corte**: exclusivos de `SettingsNJUD` (nunca em `BaseSettings`)

---

## 6. Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Quebra de imports ao mover config | Testar `import divisor_boletins` e `import giro` após cada mudança |
| Assets de vinhetas não encontrados | Validar existência de arquivos antes de mover |
| `WHISPER_MODEL` literal remanescente | `grep -rn "WhisperModel(" src/` — zero tolerância |
| Regressão no NJUD | Rodar `python -m src.divisor_boletins --help` + teste de sanidade após cada fase |
| GIRO não gera MP3 | Fase 3 bloqueia Fase 4 — não adiantar estrutura sobre areia |

---

## 7. Resumo de Prioridades

| Fase | Prioridade | Bloqueia |
|------|------------|----------|
| 1 — BaseSettings + WHISPER_MODEL | **ALTA** | Fase 2, 4 |
| 2 — Logs absolutos/namespaced | **ALTA** | — |
| 3 — GIRO transcrição end-to-end | **ALTA** | Fase 4 |
| 4 — Caches isolados | MÉDIA | — |
| 5 — Assets vinhetas | MÉDIA | — |
| 6 — Shell scripts | BAIXA | — |
| 7 — Orquestrador | BAIXA | — |

---

## 8. Referências

- Receita NJUD: `assets/vinhetas/RECEITA_NJUD.txt`
- Receita GIRO: `src/giro/montagem.py` (docstring)
- Configurações atuais: `src/config/settings.py`, `src/giro/config.py`
- Orquestração: `docs/REGRAS_ORQUESTRACAO.md`
- Produção: `docs/PRODUCAO.md`
