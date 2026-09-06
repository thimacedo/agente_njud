# DECISOES.md

Decisões técnicas aplicadas neste projeto, com motivo e data. O objetivo é evitar reversões silenciosas e garantir que alterações futuras mantenham o comportamento atual.

---

## 1. `audio.py` — import do Silero VAD já garantido em `deteccao.py`

**Motivo:**  
Existe um bug já identificado e corrigido em 2026-08-21: no branch de fallback de abertura, o código chama `_carregar_silero_vad()`. Se esse símbolo não estiver disponível no módulo, o `try/except` externo captura o erro silenciosamente e cai no método antigo `ancoras_fallback`, perdendo a detecção precisa do início da fala.

**Status atual:**  
A função `_carregar_silero_vad` já está definida e exportada por `divisor_boletins/deteccao.py`, que é importado pelo mesmo pacote. Portanto, a proteção já está ativa no local correto. Não foi feita alteração redundante em `audio.py` para evitar duplicação de comentários.

---

## 2. `montagem.py` — data do jornal vem do nome dos boletins, não de contagem de dias úteis

**Motivo:**  
A nomenclatura final dos jornais (`NJUD_XXXX_DD-MM-YYYY.mp3`) deve refletir a data real contida nos nomes dos boletins (`BOLETIM_RADIO_TJRN_DD_MM_AAAA_...`), não uma data derivada de contagem de dias úteis a partir de uma âncora fixa. Qualquer desvio da premissa (feriado não listado, NJUD pulado, ajuste manual prévio) faz a contagem derivada ficar sistematicamente errada, sem aviso.

**Alteração aplicada em:** 2026-08-21  
O script lê diretamente o padrão `_(DD)_(MM)_(AAAA)_` nos nomes dos arquivos de corte para montar `data_str`. Se não encontrar, registra aviso e gera o nome sem data. Não reverter para a lógica antiga de dias úteis.

---

## 3. `copiar_boletins.py` — validação do plano antes de qualquer alteração em disco

**Motivo:**  
Existiu uma versão anterior que executava `shutil.rmtree()` em todas as pastas de NJUD **antes** de validar `plano_alocacao.csv`. Se o CSV estivesse ausente, vazio ou malformado, a limpeza já tinha acontecido e não havia como reverter.

**Alteração aplicada em:** 2026-08-21  
A versão atual:
1. Valida o plano (colunas obrigatórias, origens existem, ano esperado, mês oficial confere) antes de tocar em qualquer pasta.
2. Usa `--dry-run` como padrão; `--apply` executa de fato.
3. Registra backup do estado anterior antes de limpar.
4. Só remove pastas de NJUD que serão recriadas pelo plano atual.

Não reverter para uma versão sem validação prévia nem sem backup.

---

## 4. Estrutura do workspace — separação entre código, dados e assets

**Motivo:**  
A raiz do projeto estava poluída com pastas redundantes (`JORNAIS`, `JORNAIS_DIVIDIDOS`, `jornais_montados`, `boletins_brutos`, `boletins_divididos`, `__pycache__`), dificultando manutenção e causando confusão sobre qual pasta era entrada/saída.

**Estrutura adotada:**
```
F:/Projetos/DIVISOR/
├── src/                      # código-fonte
│   ├── divisor_boletins/
│   ├── core/
│   ├── copiar_boletins.py
│   ├── sincronizar_drive.py
│   └── ...
├── assets/
│   └── vinhetas/
├── data/
│   ├── raw/
│   │   └── JORNAIS/          # boletins por NJUD (origem)
│   ├── processed/
│   │   └── JORNAIS_DIVIDIDOS/ # cortes CABEÇA/CORPO
│   └── output/               # jornais montados prontos para Drive
└── DECISOES.md
```

Mantê-la evita retrabalho e ambiguidade. Qualquer alteração que quebre essa separação deve ser documentada aqui primeiro.

> **ATUALIZAÇÃO 2026-08-24:** esta estrutura foi refinada — ver item 8. A entrada bruta
> continua em `JORNAIS/` na raiz (não `data/raw/JORNAIS/`), todos os CSVs em `data/`,
> cache de vinhetas em `data/cache/`, backups e correções em `logs/`.

## 5. `audio.py` — inicio_cabeca nunca deve default para 0.0 quando calibração de abertura falha


**Motivo:**
`calibrar_boletim()` calcula `inicio_cabeca` (via correlação com VHT_ABERTURA_BOLETIM)
separadamente de `fim_cabeca`/`inicio_corpo` (via correlação com a vinheta de
PASSAGEM). É possível a correlação de abertura falhar (confiança < limiar)
enquanto passagem/encerramento têm sucesso — nesse caso `inicio_cabeca_calibrado`
vem `None`. A versão anterior usava `0.0` como default nesse caso, cortando a
CABEÇA a partir do início ABSOLUTO do arquivo, sem buffer antes da fala.

**Detectado em:** 2026-08-24, auditoria de cortes individuais mostrou 8/8
CABEÇAs com "primeira palavra a 0.00s do início" (taxa de CORTADO 100%,
muito acima do gate de 10% do PROCEDIMENTO_PADRAO.md).

**Correção aplicada em:** 2026-08-24
Quando `inicio_cabeca_calibrado` é `None`, o código cai na detecção normal
(âncora de texto ANCORAS_ABERTURA, com fallback para Silero VAD) em vez de
assumir início do arquivo. `fim_cabeca`/`inicio_corpo` continuam vindos da
calibração por correlação normalmente.

Não reverter para o default `0.0` silencioso.

## 6. `processo_unico.py` — ciclo fechado por arquivo substitui reprocessamento manual (2026-08-24)

**Mudança de modelo:** a unidade de conclusão não é mais o lote, é cada boletim
individual. Um arquivo só está concluído quando a auditoria o classifica OK;
enquanto isso, o processo permanece aberto e escala para a próxima estratégia
de corte usando o MOTIVO estruturado da reprovação — nunca repete estratégia
que já falhou para aquele arquivo.

- Estado persistido em `estado_processo.json` (histórico de tentativas por
  arquivo, retomável entre execuções).
- Gate por-NJUD: montagem só roda quando TODOS os 4 boletins do NJUD estão
  OK ou ESGOTADO_ACEITO. Nenhum jornal sai com peça pendente.
- `audio.py: processar_arquivo()` aceita `estrategia=` como parâmetro
  explícito; `analisar_cortes_individuais.py` expõe `analisar_par()`.
- Estratégias de escalonamento: calibracao_correlacao → ancora_vad_forcado →
  janela_silencio_ampliada (4000ms) → grade_fixa_locucao_estendida.

Não reverter para "rodar run_pipeline_safe_v2.py várias vezes esperando que
dessa vez funcione": isso apaga o histórico de tentativas e permite regressões
silenciosas.

## 7. Auditoria — timestamps do Whisper não são medição física de borda (2026-08-24)

**Evidência:** teste do ciclo fechado (B2/NJUD 1918) mostrou TODAS as 4
estratégias de corte classificadas CORTADO com "primeira palavra a 0.00s".
O Whisper, ao transcrever cortes curtos isolados, ancora as primeiras palavras
em 0.00s por construção — mesmo havendo silêncio real no arquivo.

**Consequência:** enquanto o auditor usar timestamps de palavra para medir
bordas, o escalonamento de estratégias é cego (todas falham pelo mesmo falso
positivo) e arquivos bons vão para ESGOTADO.

**Direção da correção (pendente):** medir borda com energia física
(pydub dBFS / ffmpeg silencedetect) no lugar de timestamps de palavra.
Registrado como LIMITAÇÃO CONHECIDA nº 2 no PROCEDIMENTO_PADRAO.md v4.

## 8. Reorganização completa do workspace (2026-08-24)

**Motivo:**
A raiz acumulava 27 itens: código solto, dados duplicados (raiz vs data/), backups com
timestamp a cada execução sem política de retenção, versões antigas de módulos
(`_refatoracao_recebida/`) e pastas órfãs de convenções mortas. Risco real de o pipeline
ler a cópia errada de um CSV e de regressão via import da versão antiga.

**Diagnóstico que motivou cada ação:**
- CSVs `plano_alocacao.csv`, `njuds_por_mes.csv`, `jornal_njuds.csv` existiam na raiz E em
  `data/`, com conteúdo divergente. A cópia da raiz era mais recente (23-24/08 vs 21-23/08)
  e era a lida pelos scripts → raiz venceu; cópias antigas preservadas em
  `data/_substituidos_20260824/*.bak`.
- `_refatoracao_recebida/dispatcher_paralelo.py` diff contra `src/`: versão ANTIGA (sem
  heartbeat, RAM_POR_WORKER=1.5GB pré-OOM). `analisar_cortes_individuais.py` e
  `processo_unico.py`: idênticos. `audio.py`: órfão (equivalente em divisor_boletins/audio.py).
  → pasta deletada inteira.
- `entrada/`, `processamento/`, `saida/`: zero referências no código (grep duplo) → removidas.
- `_backup_estado_antes_*.csv`: 13 arquivos gerados sem retenção; consolidados em
  `logs/backups/backup_estado_consolidado.csv` (cada bloco precedido de `### <nome original>`)
  e os originais apagados.

**Movimentações:**
- Raiz → src/: executar_reprocessamento.py, run_pipeline_safe_v2.py, iniciar_ciclo.py,
  teste_ciclo.py, reprocessar_agosto.sh.
- Raiz → data/: plano_alocacao.csv, njuds_por_mes.csv, jornal_njuds.csv,
  njuds_faltantes.csv, alocacao_boletins.csv, plano_pendentes_sem_njud.csv,
  plano_agosto_real.csv.
- _vinhetas_cache.pkl → data/cache/ (a cópia duplicada em src/ foi apagada).

**Referências corrigidas (9 arquivos):**
| Arquivo | Ajuste |
|---|---|
| copiar_boletins.py | PLAN_CSV, REPORT_CSV, NJUDS_POR_MES_CSV → data/ |
| corrigir_plano.py | PLANO_CSV, NJUDS_POR_MES_CSV → data/; LOG_DIR → logs/correcoes/ |
| gerar_plano.py | NJUDS_CSV, PLAN_CSV, REPORT_CSV, MISSING_CSV → data/ |
| run_pipeline_safe_v2.py | PLAN_CSV, NJUDS_POR_MES_CSV, JOURNAL_NJUDS_CSV → PROJECT_ROOT/data |
| divisor_boletins/calibracao.py | _CACHE_PATH de relativo ("_vinhetas_cache.pkl", dependia do CWD) para fixo F:/Projetos/DIVISOR/data/cache/_vinhetas_cache.pkl |
| teste_ciclo.py | removido sys.path hack para _refatoracao_recebida (deletada); path local |
| iniciar_ciclo.py | `src = dirname(__file__)` (antes: dirname/src, errado após mudança p/ src/) |
| rodar_auditoria.py | saída → logs/relatorio_integridade_autonomo.json; pasta montados → data/output/JORNAIS_DIVIDIDOS_montados |
| reprocessar_agosto.sh | cd → F:/Projetos/DIVISOR/src |

**Deletados:** _refatoracao_recebida/, src/_backup_pre_refatoracao_20260824_084255/,
__pycache__/ (raiz e src/), _logs_correcao/, entrada/, processamento/, saida/,
13x _backup_estado_antes_*.csv.

**Validação executada:** py_compile em todos os módulos (28 OK / 0 erro);
gerar_plano.py --help lê plano de data/ (552 boletins); calibracao._CACHE_PATH resolve no
novo caminho com cache existente. Pipeline completo ainda não exercitado com áudio real —
primeiro iniciar_ciclo.py confirma o dispatcher.

**Estrutura final da raiz (8 itens):**
assets/ · data/ · JORNAIS/ · logs/ · src/ · DECISOES.md · PROCEDIMENTO_PADRAO.md · README.md

**Proibido reverter:** não criar arquivos de dados/código na raiz; não duplicar CSVs fora
de data/; não regenerar _backup_estado_* sem política de retenção (consolidar ou manter só N).

---

## Item 11. Procedimento de limpeza de órfãos e arquivos não-canônicos no Drive (2026-08-29)

**Motivo:** Após sincronização, o Drive acumula arquivos históricos/órfãos que não devem ficar misturados aos jornais ativos. O operador definiu que `H:` é somente leitura, exceto `sync/drive.py`. Para manter a regra e ainda permitir limpeza, o procedimento usa:
- relatórios locais em `data/output/_logs/`
- movimentação dentro do próprio Drive, sem API
- destino único: `_arquivo_morto`

**Fluxo obrigatório:**
1. Gerar `relatorio_orfaos_drive.csv` com arquivos presentes no Drive e ausentes em `JORNAIS_FINAL`.
2. Gerar `relatorio_nao_canonicos_drive.csv` com arquivos fora do padrão `NJUD_XXXX_DD-MM-AAAA.mp3`.
3. Mover arquivos listados para `_arquivo_morto` preservando a estrutura de pasta mensal.
4. Validar soma: `JORNAIS_FINAL + _arquivo_merto == total_drive`.
5. Registrar log em `logs/mover_orfaos_drive.log` e `logs/mover_nao_canonicos_drive.log`.

**Proibido reverter:** não apagar arquivos do Drive sem mover para `_arquivo_morto`; não alterar pastas mensais fora desse fluxo.

*Fim do registro de decisões.*

## Item 10. Estrutura modular canônica (2026-08-29)

**Motivo:** A raiz `src/` acumulava 42 scripts com sobreposição de responsabilidades e caminhos hardcoded. Para impedir regressão e facilitar manutenção, o código foi reorganizado em pacotes temáticos.

**Estrutura canônica:**
- `divisor_boletins/` — core estável (`audio.py`, `deteccao.py`, `calibracao.py`, `montagem.py`, `config.py`, `log.py`, `texto.py`, `cli.py`)
- `pipeline/` — motores de execução (`single_process.py`, `dispatcher.py`, `monitor.py`, `assembly.py`)
- `audit/` — auditoria e validação (`individual_cuts.py`, `integrity.py`, `integrity_report.py`, `summaries.py`)
- `sync/` — sincronização e cópia (`drive.py`, `copy.py`)
- `plan/` — planejamento (`generator.py`, `allocator.py`, `fixer.py`)
- `orchestration/` — orquestradores de topo (`safe_runner.py`, `intelligent.py`, `journal_pipeline.py`)
- `utils/` — utilitários compartilhados (`logger.py`, `validator.py`, `error_handler.py`)
- `config/` — configurações centralizadas (`settings.py` e `.env`)
- `tools/` — scripts utilitários legados (`monitor_paralelo_simples.py`, `dashboard_streamlit.py`, `monitor_job.py`, `monitor_montagem_auto.py`, `executar_reprocessamento.py`, `reprocessar_falhos.py`, `sanear_drive.py`, `downloader_tjrn.py`, `gerar_relatorio_pos_download.py`)

**Regras de migração e compatibilidade:**
- Wrappers `DeprecationWarning` foram deixados na raiz para imports antigos, mas o caminho canônico é sempre o pacote.
- Entry points devem usar os caminhos de pacote. `iniciar_ciclo.py` importa `pipeline/dispatcher.py` e `pipeline/monitor.py` diretamente.
- Nenhum caminho hardcoded de projeto (`F:/Projetos/DIVISOR`, `C:/Users/THIAGO`) é permitido fora de `config/settings.py`; todo caminho deve vir de `config.settings` ou CLI.
- Não mover código de volta para a raiz de `src/`; não duplicar módulos em múltiplas localizações; não remover wrappers de compatibilidade sem antes atualizar TODOS os consumidores.

**Validação obrigatória após alterações:**
- `python tests/test_imports.py` — todos os módulos canônicos + wrappers devem importar.
- `py_compile` em toda a árvore `src/` — 0 erros.
- `grep` por caminhos hardcoded em `src/` — 0 ocorrências.


## Item 6 (2026-08-24 — execução AGOSTO/NJUD 1918)
1. Auditor acusou "0.00s do início" nos 4 boletins em TODAS as estratégias → ESGOTADO.
   Auditoria física (pydub silencedetect + re-transcrição) provou cortes íntegros
   (sil_ini 30–130ms, sil_fim 0ms, bordas com frases completas). Falso positivo do
   timestamp Whisper confirmado; classificado ESGOTADO_ACEITO com evidência no JSON.
   PENDENTE: migrar o auditor para medição física de energia (limitação 2 do P.P.).
2. montagem.py (`montar_todos`) espera <entrada>/<MÊS>/<NJUD>/, mas dispatcher grava
   direto em JORNAIS_DIVIDIDOS/<NJUD>/. Contorno: chamar montar_jornal(njud_pasta)
   diretamente. PENDENTE: alinhar árvore entre dispatcher e montagem.
3. sincronizar_drive.py lê mp3 de data/output/ raiz, não de data/output/JORNAIS_FINAL/.
   Contorno aplicado: copiar o montado para a raiz antes do sync. PENDENTE: unificar.
4. Atenção a artefatos stale: NJUD_1918_26-08-2026.mp3 antigo (07:13) sobreviveu na
   pasta de saída e passaria por produto novo. Sempre checar mtime antes de confiar.

## Item 6b (2026-08-24 — correções estruturais aplicadas)
1. AUDITOR FÍSICO: analisar_cortes_individuais.py não usa mais timestamp do
   Whisper para bordas. Borda = RMS de janela 50ms vs piso de fala (percentil
   10 do RMS global); corte só se energia >= piso+12dB. Conectivo isolado só
   reprova se o arquivo não tiver fala real (artigos iniciam frases naturais).
   Validado: 4/4 pares NJUD 1918 agora OK sem intervenção.
2. MONTAGEM: montar_todos() aceita <NJUD> direto em JORNAIS_DIVIDIDOS/ (formato
   do dispatcher) além de <MES>/<NJUD>/ — detectado por regex "NJUD <num>".
3. SYNC: sincronizar_drive.py lê de data/output/JORNAIS_FINAL/ (fallback:
   raiz data/output). Não precisa mais copiar manualmente antes do sync.

## 9. Estrutura imutável de BOLETIM e JORNAL + regra de limpeza de vinhetas (2026-08-24)

**Definições fornecidas pelo operador — IMUTÁVEIS, não negociáveis:**

**Origem: boletim** (unidade bruta), formado por:
```
vinheta de abertura → cabeça → vinheta de passagem → corpo → vinheta de encerramento
```

**Destino: jornal** (produto final), formado por 4 boletins:
```
vinheta de abertura → cabeça 1 → cabeça 2 → cabeça 3 → cabeça 4 →
vinheta de passagem → corpo 1 → corpo 2 → corpo 3 → corpo 4 →
vinheta de encerramento
```

**Regras derivadas:**
1. **Vinhetas de boletim ≠ vinhetas de jornal.** São assets distintos
   (`assets/vinhetas/`: VHT_ABERTURA/PASSAGEM/ENCERRAMENTO_BOLETIM vs
   VHT_ABERTURA_NJUD / EFEITO_PASSAGEM_NJUD / VHT_ENCERRAMENTO_NJUD).
   Nunca usar a vinheta de um contexto no outro.
2. **Limpeza de vinhetas dentro dos cortes é FUNDAMENTAL:** a CABEÇA não pode
   carregar resíduo da vinheta de abertura do boletim, e o CORPO não pode
   carregar resíduo das vinhetas de passagem/encerramento — senão a "sujeira"
   do boletim contamina o jornal montado. Na dúvida entre margem frouxa e
   resíduo audível de jingle, cortar mais apertado contra a vinheta.
3. Se as ferramentas atuais (correlação com asset, VAD, energia) não forem
   suficientes para garantir cortes sem resíduo de vinheta, **validar novas
   ferramentas** é escopo aprovado pelo operador.

**Proibido reverter:** qualquer lógica que monte jornal com estrutura diferente
da acima ou trate as vinhetas de boletim e jornal como intercambiáveis.

## Item 12. Separação estrita entre boletins e NJUDs (2026-08-29)

**Motivo:** Em 2026-08-29 houve sobreposição indevida entre domínios: scripts de
padronização renomearam arquivos `BOLETIM_RADIO_TJRN_*` para `NJUD_*` em pastas
de origem/processamento. Isso quebrou a distinção fundamental do fluxo:
- **Boletim**: unidade bruta de entrada (abertura → cabeça → passagem → corpo → encerramento)
- **NJUD**: produto final montado (4 boletins → 1 jornal)

**Regra imutável:**
1. Não renomear `BOLETIM_RADIO_TJRN_*` para `NJUD_*` em nenhuma pasta.
2. Pastas de boletins mantêm apenas `BOLETIM_RADIO_TJRN_*`.
3. Pastas de jornais/jornal final contêm apenas `NJUD_*`.
4. Qualquer script de organização física deve preservar o nome original dos arquivos.
5. Se houver dúvida sobre o domínio de um arquivo, considere-o boletim por padrão.

**Proibido reverter:** misturar boletins e NJUDs na mesma pasta ou tratamento.

## Item 13. Quarentena de arquivos com ano 2027 (2026-08-29)

**Decisão:** manter a pasta `data/output/data_quarentena_2027/` para revisão futura.
Foram isolados **58** arquivos com ano `2027` encontrados nas pastas-alvo.
As pastas principais estão limpas e sem misturas entre boletins e jornais.

**Proibido reverter:** excluir a quarentena sem confirmação explícita do operador.
