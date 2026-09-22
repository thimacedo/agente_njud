# Changelog agente_njud

Histórico de mudanças relevantes do projeto, ordenado do mais recente ao mais antigo.

Formato baseado on [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
seguindo [Semantic Versioning](https://semver.org/lang/pt-BR/) informal.

---

## [Unreleased]

### Adicionado
- `scripts_pipeline/aplicar_deprecacoes.sh` — script shell que aplica Itens 3 e 4 do plano de arquitetura (depreciação de orquestradores + avisos runtime em pacotes mortos), arquivando originais em `.trash/` antes de sobrescrever.
- `scripts_pipeline/boletim/auditoria_proativa.py` — auditoria proativa pós-montagem: claquetes (janela 15s), vazamento de assinatura, vinhetas (NCC), BG no OFF (RMS), cobertura do roteiro (threshold 60%). Reporta OK/PROBLEMA por boletim.
- **Item 18 (DECISOES.md):** correções iterativas no pipeline canônico de boletins (`scripts_pipeline/boletim/processar_boletim_canonico.py`) validadas no processamento do 18 SET B6-B10 (auditoria proativa 5/5 OK): regex de claquetes (geral e individual, com hífen e letra inicial variável), anti-vazamento de assinatura em 2 cenários, corte fino por word-timestamp, loudnorm pós-montagem (I=-16:TP=-1.5:LRA=11), threshold cobertura 60%.

### Alterado
- `scripts_pipeline/shared/bgm_mixer.py`: bug BG inaudível — constantes `-14`/`-28` (interpretadas como ganho sobre BG em -21.5 dBFS → BG em -35.5 dBFS, inaudível) corrigidas para `BGM_FULL_DB=12`/`BGM_DUCK_DB=6` (ganho positivo → BG em -9.5/-15.5 dBFS, audível).
- `.env.example`, `_legado/src/audit/individual_cuts.py`, `docs/auditorias/AUDITORIA_SISTEMA_2026-08-31.md`, `docs/decisoes/DECISOES.md`: migração de caminho `F:/Projetos/DIVISOR` → `E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR` (drive F: desmontado).

### Pendente (não corrigido)
- Bugs A/B/C do 17 SET B1-B5 no pipeline canônico (detalhados no Item 18 de DECISOES.md): (A) `calcular_duracao_cabeca` recebe áudio completo em vez do segmento; (B) corte fino busca claquete no segmento seguinte quando ela está no anterior; (C) regex de remoção de claquete não casa "M2,"/"M3." e anti-vazamento não casa "Narda Omeida". Reprocessamento do 17 SET B1-B5 e processamento do 18 SET B1-B5 aguardam essas correções.

---

## [0.5.0] - 2026-09-15

### Adicionado
- **Item 15 (DECISOES.md):** centralização do `MODELO_WHISPER` em `config.njud.settings`. O dispatcher hardcoded `"tiny"` foi substituído por `_settings.MODELO_WHISPER`, fechando a última divergência do Plano de Modularização.
- **Item 14 (DECISOES.md):** documentação de canonia dos scripts de sync. NJUD usa `src/sync/drive.py`; GIRO usa `src/giro/sync_drive.py`. `scripts_pipeline/sync_drive.sh` foi deprecado.
- 52 testes em `src/gravador_inteligente/tests/` (`test_edicao.py`, `test_montagem.py`, `test_tratamento.py`), 3 skipped (requerem áudio real).
- `scripts_pipeline/validar_pipeline_giro.py` — validação end-to-end do pipeline GIRO com boletim real de 07/01/2026.
- `assets/vinhetas/boletim/` — vinhetas reais de boletim (VHT_ABERTURA, VHT_PASSAGEM, VHT_ENCERRAMENTO).
- `src/divisor_boletins/bgm_mixer.py` (188 linhas) — mixagem de trilha de fundo com Auto-Ducking dinâmico via análise RMS, portado do radioflow/backend. Integração opcional em `montagem.py` (usar_ducking=False para manter comportamento atual).
- `auditar_boletim()` em `src/gravador_inteligente/montagem_boletins.py` — auditoria de qualidade pós-montagem (LUFS, duração, tamanho).
- Expansão de palavras_gatilho de 6 → 35 termos (curados para evitar colisão com vocabulário jurídico do TJRN).

### Alterado
- `pipeline/dispatcher.py` linha 124: hardcoded `"tiny"` → `_settings.MODELO_WHISPER`.
- `src/gravador_inteligente/montagem_boletins.py`: import `normalize_volume` de `src.gravador_inteligente.tratamento_audio` (fix referência).
- `src/gravador_inteligente/montagem_boletins.py`: regex `B+Número` corrigida para capturar whisper errors ("bessinco"→B5, "bedouis"→B2).
- `src/gravador_inteligente/edicao_boletins.py`: fix `editar_boletins_diretorio` — `EdicaoConfig().palavras_gatilho` em vez de `cfg.palavras_gatilho` (bug referência).

### Depreciado
- **8 orquestradores não-canônicos** em `scripts_pipeline/` foram substituídos por shims que chamam `sys.exit(1)` com aviso em stderr. Originais arquivados em `.trash/2026-09-14_deprecados_orquestradores/`:
  - `orquestrador.py` → canônico NJUD: `src/orchestration/safe_runner.py`
  - `orquestrador_giro_jan2026.py` → canônico GIRO: `scripts_pipeline/executar_programa.py`
  - `processar_serial.py`, `processar_njud_por_njud.py`, `processor_v2.py`, `processor_v3.py`, `processor_com_heartbeat.py`, `dispatcher_wrapper.py`
- **Pacotes confirmadamente mortos** (não importados pela cadeia real): `src/giro/__init__.py`, `src/regras/__init__.py`, `src/sync/coletor.py` — agora emitem `DeprecationWarning` em runtime.

### Segurança
- Nenhuma mudança segurança nesta versão.

---

## [0.4.0] - 2026-09-14

### Adicionado
- `DECISOES.md`: Item 12 (separação estrita boletins/NJUDs — nunca renomear BOLETIM_* para NJUD_*), Item 13 (quarentena 58 arquivos ano 2027 em `data_quarentena_2027/`), Item 10 (estrutura canônica modular), Item 11 (procedimento de limpeza de órfãos no Drive).
- `ARQUITETURA_REAL.md`: documento definitivo da cadeia de execução real — confirma `scripts_pipeline/executar_programa.py` → `core.processamento.processar_boletim` → `divisor_boletins/audio.py` como pipeline único. Identifica `src/giro/*` como código paralelo NÃO utilizado.
- `scripts_pipeline/produzir_programa.py`: orquestração completa do pipeline (configuração, execução, validação).
- `scripts_pipeline/run_dispatcher.sh` e `scripts_pipeline/executar_programa.py`: cadeia confirmada para GIRO/NJUD.
- `core/processamento/processar_boletim.py`: módulo canônico de processamento (ConfigPrograma, processar_lote, processar_um_arquivo).
- `core/auditoria/regras.py`: auditoria com escalonamento de estratégia por motivo de reprovação.
- `data/processed/PRODUCAO_2026/` como pasta de produção oficial.

### Alterado
- `processar_boletim.py`: `max_boletins_por_programa` definido como 6 (mín 4, máx 6).
- `processar_boletim.py`: pula divisão se arquivo já é CABECA/CORPO.
- `core/auditoria/regras.py`: Camada D adicionada (auditoria por correlação).
- `.gitignore`: atualizado para subprojetos, Drive H:, `.trash/`.

### Corrigido
- Remoção de bloco duplicado em `processar_boletim.py` que descartava remoção de vinheta.
- `validar_pipeline_giro.py`: corrigido para suportar dict e objeto.
- Datas dos 34 `giro_*.json` corrigidas para coincidir com boletins em H:.
- Default `--boletins` corrigido para `JORNAIS_DIVIDIDOS` (GIRO nas comarcas).

### Limpeza
- Remoção de 63 arquivos órfãos e artefatos (commit `38edfcd`).
- Reorganização completa do workspace: raiz limpa com 8 itens. CSVs consolidados em `data/`, backups em `logs/backups/`, remoção de `_refatoracao_recebida/` e outras pastas mortas.

---

## [0.3.0] - 2026-09-09

### Adicionado
- Auditoria de sistema completa (`AUDITORIA_SISTEMA_2026-09-09.md`): identificado bug DD/MY em datas, NJUD duplicado, leak de BOLETIM, e necessidade de `run_dispatcher.sh`.
- `copiar_boletins.py`: validação do plano ANTES de qualquer alteração em disco (fail-closed). `--dry-run` como padrão.
- `montagem.py`: data do jornal vem do nome dos boletins (não contagem de dias úteis). `montar_todos()` aceita `<NJUD>` direto em `JORNAIS_DIVIDIDOS/`.
- `audio.py`: medição física de borda via RMS (abandono de timestamps do Whisper). Ciclo fechado por arquivo com escalonamento: `calibracao_correlacao` → `ancora_vad_forcado` → `janela_silencio_ampliada` → `grade_fixa_locucao_estendida`.
- `dispatcher_paralelo.py`: workers persistentes com Whisper carregado 1x, estado persistido em `estado_por_arquivo/*.json`.
- `sincronizar_drive.py`: lê de `data/output/JORNAIS_FINAL/` (fallback raiz).
- `config/settings.py`: centralização de configurações com suporte `.env`.
- Estrutura modular canônica `src/`: `divisor_boletins/`, `pipeline/`, `audit/`, `sync/`, `plan/`, `orchestration/`, `utils/`, `config/`, `tools/`.

### Alterado
- Processo único com ciclo fechado por arquivo (v4) substitui fluxo sequencial de 5 etapas (v3).
- `inicio_cabeca` nunca default `0.0` quando calibração falha — cai em detecção via âncora/Silero VAD com log.

### Limpeza
- Reorganização completa: raiz passou de 27+ itens para 8 itens. CSVs duplicados consolidados, `_backup_estado_*` consolidados em `logs/backups/backup_estado_consolidado.csv`.

---

## [0.2.0] - 2026-08-29

### Adicionado
- `docs/PLANO_MODULARIZACAO.md`: plano completo de modularização NJUD vs GIRO (7 fases, fail-closed).
- `docs/REGRAS_ORQUESTRACAO.md`: princípios KISS/YAGNI/DRY, regras de orquestração (1 dispatcher por vez).
- `src/orchestration/safe_runner.py`: orquestrador NJUD canônico.
- `src/giro/sync_drive.py`: sync oficial GIRO-aware.

### Corrigido
- Bug DD/MM em datas de boletins (referenciado em auditorias anteriores).
- Detecção de janela temporal em `detectar_repeticoes`.

---

## [0.1.0] - 2026-08-24

### Adicionado
- Estrutura inicial do projeto `DIVISOR` — pipeline de boletins TJRN.
- `src/divisor_boletins/`: núcleo estável (audio, calibração, detecção, montagem, texto, cli, config, log).
- `src/pipeline/dispatcher.py`, `single_process.py`, `monitor.py`.
- `src/audit/`: individual_cuts, integrity, integrity_report, summaries.
- `src/plan/`: generator, allocator, fixer.
- `src/utils/`: logger, error_handler, validator.
- `src/sync/`: drive.py (única escrita no H:), copy.py.
- Assets de vinhetas em `assets/vinhetas/{njud,giro,boletim}/`.
- `PROCEDIMENTO_PADRAO.md` v3 — fluxo sequencial de 5 etapas (substituído por v4).
- `DECISOES.md` — regras não negociáveis iniciais.

