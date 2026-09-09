# Auditoria do Sistema DIVISOR — 2026-09-09

Auditoria de consistência técnica, regras de não-regressão e persistência de sistema no projeto DIVISOR.

---

## 0. Resumo Executivo

| Critério | Status |
|---|---|
| Persistência do código fonte | ✅ OK — 4 commits, remote configurado |
| Regra DD-MM | ✅ Confirmada — `BOLETIM_RADIO_TJRN_DD_MM_YYYY` |
| Não-regressão (test_edicao.py) | ✅ 24/24 passando após correção |
| Scripts build_all_* (MM_DD) | 🔴 Bug de data — 13 scripts invertem dia/mês |
| `produzir_njuds_jul_ago.ps1` | 🔴 Viola regra #1 (H: leitura) + NJUD duplicado |
| `run_dispatcher.sh` | 🟠 Bug — ponto no lugar de barra |
| `limpar_producao_finalizada.ps1` | 🟠 Risco — Test-NjudFinalizado só por número |
| `BOLETIM/` pasta | 🔴 Vazamento do gravador_inteligente |
| Venv no DIVISOR | ⚠️ Funcional mas dependente de /e (lento) |

---

## 1. Bug Crítico — Convenção de Data (13 scripts MM_DD)

**Problema:** 13 scripts no `/e/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/` interpretam o nome do arquivo `BOLETIM_RADIO_TJRN_XX_YY_ZZZZ` como **MM_DD_YYYY**, mas a regra documentada no `PROCEDIMENTO_PADRAO.md` (Regra Inegociável #2) diz que o padrão é **DD_MM_YYYY**.

**Scripts afetados:**
- `parse_source.py`, `parse_source2.py`–`parse_source5.py`
- `diagnose_dates.py`, `diagnose_dates2.py`
- `build_all_programs.py`, `build_all_v2.py`, `build_all_giros.py`
- `build_all_final.py`, `build_all_comprehensive.py`
- `copy_all_source.py`, `build_all_programs.py`

**Scripts corretos (DD_MM):**
- `fix_notes.py`
- `populate_notes.py`

**Impacto:** Qualquer GNC montado com esses scripts pode ter usado o boletim errado como fonte, sempre que dia ≠ mês (ex: dia 04 mês 06 vs dia 06 mês 04 são datas completamente diferentes). Só passa despercebido quando dia e mês coincidem (ex: dia 05, mês 05) ou quando ambos caem dentro de 1-12 e por acaso o "adjacente" ainda cai numa terça válida.

**Referência:** `DECISOES.md` Item 2 e `PROCEDIMENTO_PADRAO.md` Regra #2.

---

## 2. Bug Crítico — `produzir_njuds_jul_ago.ps1` Viola Regra #1

**Problema:** A regra inegociável do `PROCEDIMENTO_PADRAO.md` diz: *"Drive H: é somente leitura para todo o pipeline, EXCETO a etapa final de sincronização (`src/sync/drive.py`)"*. Esse script:
- Lê **e escreve** diretamente em `H:\...\02_JORNAIS_NJUD\03_AUDIOS_RADIO\` (`Move-Item`)
- **Deleta** as pastas de origem em `H:\...\01_BOLETINS_DIARIOS\...` depois de mover (`Remove-Item -Recurse -Force`)
- Atribui números de NJUD sequencialmente (`$njudAtual++`) sem checar se aquele número já foi usado em outro mês/lote

**Causa raiz plausível para NJUDs duplicados:** `NJUD_1794` aparecendo em 01/01 e 21/01, `NJUD_1811` em 02/02 e 13/02 — o `$nudPrefix = "NJUD_$njudAtual"` sem verificação de data é candidato natural a causa raiz.

**Data do arquivo:** Birth 2026-09-04 16:40, Modify 16:40, Access 16:40. Sem execução documentada desde então.

**Status:** Script recente (4 dias), não é peça arqueológica. Ainda pode ser executado por engano.

---

## 3. Bug — `run_dispatcher.sh`

**Problema:** Linha 4 tem `exec python src/pipeline.dispatcher.py ...` — deveria ser `src/pipeline/dispatcher.py` (barra, não ponto). Como está, o Python falha com `can't open file` (a menos que exista literalmente um arquivo chamado `pipeline.dispatcher.py`).

**Referência:** README e `PROCEDIMENTO_PADRAO.md` documentam `src/pipeline/dispatcher.py`.

---

## 4. Risco de Design — `limpar_producao_finalizada.ps1`

**Problema:** `Test-NjudFinalizado` (linhas 99-113) decide "finalizado" **só pelo número do NJUD**, ignorando a data. Dado que já existem números de NJUD duplicados em datas diferentes, esse script pode **quarentenar um NJUD que ainda não terminou**, só porque outro NJUD com o mesmo número (de outra data) já foi sincronizado.

**Correção sugerida:** Casar por número **e** data, não só número.

**Data do arquivo:** Birth 2026-09-06 22:00. Script recente.

---

## 5. Vazamento de Pipeline — Pasta `BOLETIM/`

**Problema:** `/e/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/BOLETIM/` contém 10 mp3s (03_SET_B1-B4, ~12MB) e `pipeline_log.json`. O log mostra estágios `tratamento_08_SET_B5` → `edicao_08_SET_B5` → `montagem_08_SET_B5` com saída em `E:\...\DIVISOR\BOLETIM\`.

**Causa:** `montagem_boletins.py` tem `WORKSPACE_DIR = os.environ.get("DIVISOR_WORKSPACE", "E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")`. Quando `DIVISOR_WORKSPACE` não é setado, o gravador_inteligente grava direto na raiz do DIVISOR. Os nomes dos estágios (`tratamento`, `edicao`, `montagem`) batem com os módulos do `gravador_inteligente` (`app/tratamento_audio.py`, `app/edicao_boletins.py`, `app/montagem_boletins.py`).

**Impacto:** Pipeline executou hoje (09/09) gravando direto na árvore do DIVISOR — pasta que não existe na estrutura documentada do README (`JORNAIS/`, `data/`, `assets/`, `logs/`, `src/`, `tests/`).

**Status do git:** `BOLETIM/` não está versionado (provavelmente está em `.gitignore` ou é novo).

---

## 6. Persistência Técnica — Repositório

### 6.1 Código fonte
- Local: `/c/Users/THIAGO/gravador_inteligente/`
- Remote: `https://github.com/thimacedo/gravador_inteligente.git` (origin)
- Commits: 4 (`d205b48` head, `7b9bca2`, `5daf7ab`, `40437f7`)
- Sem branches adicionais, sem tags
- `.gitignore` funcional (ignora `__pycache__/`, `.venv/`, outputs do pipeline, logs, eggs)

### 6.2 pyproject.toml
- ✅ Versionado e funcional
- ✅ Dependências: fastapi, uvicorn, pydub, whisper-timestamped, numpy, torch
- ✅ Dev deps: pytest>=7.0.0, black, ruff, httpx
- ✅ Config build: setuptools>=61.0
- ✅ Config lint: black/ruff line-length=100
- ✅ Package find: `include=["app*"]`

### 6.3 .venv
- `/c/Users/THIAGO/gravador_inteligente/.venv` funcional com todos os pacotes
- `pip install -e .` instala o pacote local
- `pytest` passa 24/24

---

## 7. Não-Regressão — Testes

### 7.1 Status atual
**24/24 testes passando** em `tests/test_edicao.py` (app/edicao_boletins.py)

### 7.2 Bug corrigido
- **Local:** `app/edicao_boletins.py`, linha 261
- **Antes:** `if intervalo_seg > tempo_max_retrocesso_seg: continue`
- **Depois:** `if intervalo_seg > tempo_max_retrocesso_seg: break`
- **Motivo:** `detectar_repeticoes()` processa frases em ordem cronológica. Ao encontrar a primeira frase fora da janela temporal, as seguintes também estarão fora (o `continue` permitia verificar similaridade desnecessariamente com frases já fora do limite). Com `break`, a janela temporal é respeitada corretamente.
- **Commit:** `d205b48`

---

## 8. Itens para DECISOES.md (entradas sugeridas)

### Item 14 (2026-09-09): Bug de convenção de data nos scripts build_all_*
**Motivo:** Scripts `build_all_*`, `parse_source*`, `diagnose_dates*` interpretam `BOLETIM_RADIO_TJRN_XX_YY_ZZZZ` como MM_DD_YYYY, violando a Regra #2 do `PROCEDIMENTO_PADRAO.md`.
**Impacto:** GNCs montados com esses scripts podem ter usado boletim errado como fonte quando dia ≠ mês.
**Ação:** Scripts listados na Seção 1 abaixo serão apagados. `fix_notes.py` e `populate_notes.py` são os únicos com a convenção correta.

### Item 15 (2026-09-09): Violação de regra H: somente leitura pelo `produzir_njuds_jul_ago.ps1`
**Motivo:** Script move e deleta arquivos em H: fora do `src/sync/drive.py`.
**Impacto:** NJUDs duplicados plausíveis devido a `$njudAtual++` sem checagem de data.
**Ação:** Bloquear execução, documentar risco histórico.

### Item 16 (2026-09-09): Vazamento de pipeline — `BOLETIM/` na raiz do DIVISOR
**Motivo:** `gravador_inteligente` gravou direto em `E:\...\DIVISOR\BOLETIM\` via `WORKSPACE_DIR` default.
**Impacto:** Pipeline executou hoje gravando na estrutura errada.
**Ação:** Documentar como path incorreto, não como estágio do DIVISOR.

---

## 9. Plano de Ação

### 9.1 Apagar (convenção errada, superseded):
`build_all_programs.py`, `build_all_comprehensive.py`, `build_all_final.py`, `build_all_v2.py`, `build_all_giros.py`, `copy_all_source.py`, `diagnose_dates.py`, `diagnose_dates2.py`, `parse_source.py`, `parse_source2.py`, `parse_source3.py`, `parse_source4.py`, `parse_source5.py`

### 9.2 Consolidar sync:
`sync_all_gnc.py` + `sync_gnc_to_h.py` → um único `sync_gnc_to_h.py` definitivo

### 9.3 Manter (corrigir rota):
`fix_notes.py` e `populate_notes.py` — verificar se têm lógica extra antes de unificar

### 9.4 Manter como está:
`check_final_status.py` (não depende da convenção de data)

### 9.5 Documentar no DECISOES.md:
Entradas 14, 15, 16 (ver Seção 8 acima)

---

## 10. Perguntas em Aberto (requerem confirmação do operador)

1. **`produzir_njuds_jul_ago.ps1` ainda é operacional?** Se sim, precisa ser bloqueado imediatamente (adicionar `--dry-run` default ou desabilitar). Se for peça arqueológica, documentar como risco histórico e remover.

2. **`BOLETIM/` é intencional ou vazamento?** Pela evidência (`WORKSPACE_DIR` default no `montagem_boletins.py`), é vazamento. Se for intencional, precisa ser documentado como novo estágio do DIVISOR.

3. **GNCs já montados com scripts MM_DD precisam de reaudit?** Se `build_all_*` rodou antes de 09/09, os GNCs podem ter boletim errado como fonte. Só passaria despercebido quando dia e mês coincidem.

---

## 11. Arquivos Investigados

| Arquivo | Tamanho | Data Modificação | Status |
|---|---|---|---|
| `produzir_njuds_jul_ago.ps1` | 5.2KB | 2026-09-04 16:40 | 🔴 Bug confirmado |
| `limpar_producao_finalizada.ps1` | 8.3KB | 2026-09-06 22:00 | 🟠 Risco |
| `run_dispatcher.sh` | ~200B | — | 🟠 Bug confirmado |
| `pipeline_log.json` (BOLETIM/) | 12MB total | 2026-09-09 13:41 | 🔴 Vazamento |
| `app/edicao_boletins.py` | 27KB | — | ✅ Corrigido (d205b48) |
| `tests/test_edicao.py` | 7.8KB | — | ✅ 24/24 passando |
| `pyproject.toml` | 764B | — | ✅ Funcional |
| `.gitignore` | 288B | — | ✅ Funcional |
| `DECISOES.md` | 319 linhas | — | ✅ Regra DD-MM implícita (Item 2) |
| `PROCEDIMENTO_PADRAO.md` | 168 linhas | — | ✅ Regra #2 explícita |
| `AUDITORIA_SISTEMA_2026-08-31.md` | 143 linhas | — | ✅ Base de auditoria |

---

*Gerado em: 2026-09-09*
*Autor: Hermes Agent*
*Referências: PROCEDIMENTO_PADRAO.md, DECISOES.md, AUDITORIA_SISTEMA_2026-08-31.md*
