# ARQUITETURA_REAL.md — GIRO/NJUD: o que roda de verdade

**Por que este documento existe:** esta investigação identificou que existem
múltiplas implementações paralelas do pipeline GIRO na mesma codebase,
algumas documentadas como se fossem o sistema real (`AGENTE_GIRO.md`)
sem de fato estarem em uso. Isso já causou trabalho de correção aplicado
em código que não roda em produção. Este documento existe para não
repetir esse erro — qualquer pessoa (humana ou agente) que for mexer
no GIRO deve ler isto primeiro e confirmar contra o código real antes
de assumir que um módulo é "o" pipeline.

**Nível de confiança de cada afirmação abaixo é marcado explicitamente.**
Isso não é opcional — esta investigação já reverteu sua própria conclusão
uma vez nesta mesma conversa, então nenhuma afirmação aqui deve ser lida
como definitiva sem o nível de confiança ao lado.

---

## Cadeia de execução real (CONFIRMADO — leitura direta de código)

```
scripts_pipeline/rodar_tudo_giro.sh
  → itera config/planejamento_2026/giro_*.json (34 arquivos, jan–ago/2026)
  → chama scripts_pipeline/executar_programa.py <json> \
        --boletins <H:> --saida <PRODUCAO_2026>
    → importa core.processamento.processar_boletim :: ConfigPrograma, processar_lote
      → processar_lote() → processar_um_arquivo()
        → core/audio/remocao_vinheta.py :: remover_vinheta_boletim()
          (Camada A — usado quando usar_separacao_stems=False, que é o
          caso de todos os giro_*.json gerados por gerar_planejamento_giro.py)
        → divisor_boletins/audio.py :: processar_arquivo()
          → transcrever_audio() → faster_whisper.WhisperModel.transcribe() DIRETO
          → calibrar_boletim() [divisor_boletins/calibracao.py]
          → buscar_ancora() [divisor_boletins/deteccao.py]
          → cortar_audio() [divisor_boletins/audio.py]
        → auditoria [core/auditoria/regras.py], com escalonamento de
          estratégia em caso de reprovação (ver dispatcher.py para o
          equivalente usado no NJUD — mesma família de ciclo)
```

**Evidência:** import literal `from core.processamento.processar_boletim
import ConfigPrograma, processar_lote` em `executar_programa.py`; e
`rodar_tudo_giro.sh` chamando `executar_programa.py` com os JSONs de
`config/planejamento_2026/`.

**33 programas GIRO já produzidos e sincronizados no Drive H:** conforme
`RELATORIO_PRODUCAO_GIRO_2026.md` (jan–set/2026, ~90% de taxa). Esse
relatório é a origem da certeza de que ALGUMA cadeia de produção rodou
de verdade — a investigação nesta conversa identificou qual.

## O que NÃO faz parte da cadeia real (CONFIRMADO como não-referenciado)

Estes três não aparecem em nenhum ponto da cadeia acima:

- **`regras/livro.py`, `regras/njud.py`, `regras/giro.py`** (tipos
  `OrigemBoletim`, `SelecaoBoletins`, `TipoPrograma`) — escrito e
  corrigido nesta conversa (bug de contagem `// 2`, filtro de boletim
  incompleto). Não é importado por `executar_programa.py` nem por
  `processar_boletim.py`.
- **`src/giro/*`** (`cli.py`, `transcricao.py`, `filtro.py`,
  `montagem.py`, `plano.py`, `sync_drive.py`) — documentado inteiro em
  `AGENTE_GIRO.md` como se fosse o pipeline real. `cli.py` importa
  `from .transcricao import processar_boletim`, mas nada na cadeia real
  chama `python -m giro` ou importa `src.giro`.
- **`sync/coletor.py`** — escrito e corrigido nesta conversa (tolerância
  de tamanho, proteção de staging do dia corrente). Não aparece na
  cadeia real; `executar_programa.py` recebe `--boletins <H:>`
  diretamente, sem uma etapa de staging separada visível até agora.

**Isso não significa que esses módulos estejam errados ou sejam inúteis
— apenas que consertar bugs neles não afeta o que roda em produção hoje.**
Se a intenção for migrar para uma dessas arquiteturas no futuro, isso é
uma decisão de projeto separada, não uma correção de bug.

## Ainda não verificado (INFERÊNCIA — verificar antes de confiar)

- **Regras de negócio efetivas do GIRO em produção**: `gerar_planejamento_giro.py`
  gera os JSONs com `boletins_minimos: 4`, `corte_por_silencio: True`,
  `fallback_audio_completo: False` — isto é DIFERENTE do que
  `RELATORIO_PRODUCAO_GIRO_2026.md` descreve como implementado
  (fallback em cascata de 4 passos, threshold de 4 notas antes de
  cair pro fallback de Natal). Essas duas fontes descrevem
  comportamentos de fallback incompatíveis. Não sabemos qual é real sem ler
  o restante de `processar_boletim.py` — a investigação desta conversa só
  leu até a linha 440 deste arquivo no momento em que o documento foi
  criado.

- **Onde entra o filtro geográfico (RN vs. outros estados vs. Natal)
  na cadeia real**: o filtro geográfico existe em `src/giro/filtro.py`
  e `src/giro/utils.py` (filtro RN_CIDADES, Natal, OUTROS_ESTADOS), e é
  usado por `src/giro/cli.py` (Passo 1 e Passo 2 do processamento). Mas
  **nada na cadeia real (executar_programa.py → processar_boletim.py →
  divisor_boletins/audio.py) importa ou chama esse filtro**. Isso significa
  que o filtro geográfico descrito em `AGENTE_GIRO.md` e implementado em
  `src/giro/filtro.py` **não está ativo na produção atual**. As notas são
  cortadas pelo `divisor_boletins/audio.py` sem passar pelo `filtrar_nota`
  do `src/giro/`. **Não presumir que o filtro geográfico do GIRO existe
  em produção até isso ser confirmado ou migrado.**

- **Quem sincroniza os programas prontos para o Drive H:** `rodar_tudo_giro.sh`
  não faz sync — só processa e salva local em `data/processed/PRODUCAO_2026/`.
  O script de sync que copiou os 33 programas para o H: **ainda não foi
  identificado com certeza**. Ha três candidatos que existem na codebase:

  1. `scripts_pipeline/sync_drive.sh` — copia de `data/output/JORNAIS_FINAL/`
     para `H:/.../02_JORNAIS_NJUD/03_AUDIOS_RADIO/`. Usa padrão de nome
     `NJUD_DD-MM-AAAA.mp3` e mapeia meses. É o sync do NJUD, não do GIRO.
  2. `src/sync/drive.py` — faz o mesmo que o script acima, mas em Python,
     com `PATTERN_NOME = re.compile(r"^NJUD_\d{4}_\d{2}-\d{2}-\d{4}(_INCOMPLETO)?\.mp3$")`.
     Também é NJUD-only (regex exige prefixo NJUD).
  3. `src/giro/sync_drive.py` — existe, é específico para GIRO
     (`GNC_mmss_DD-MM-AA.mp3`), copia para
     `H:/.../00_PRODUCAO_2026/02_JORNAIS_GIRO/03_AUDIOS_RADIO/` ou variável
     `GNC_DRIVE_SYNC`. **É o único que menciona GIRO explicitamente**, mas
     não foi confirmado que foi o usado na produção dos 33 programas.

  Nenhum dos três scripts foi confirmado como o que rodou para os 33
  programas. Exercício para o leitor: checar logs de sync em
  `logs/sync_drive_*.log` ou variáveis de ambiente `GNC_DRIVE_SYNC` para
  descobrir qual foi usado.

- **Se o dispatcher (`pipeline/dispatcher.py`, usado pelo NJUD) também
  processa GIRO**: confirmado nesta conversa que `dispatcher.py` é
  NJUD-only (import de `config.njud`, gate hardcoded de NJUD). O GIRO
  usa `processar_boletim.py`/`processar_lote()` como orquestrador,
  que parece ser um caminho de execução DIFERENTE do dispatcher
  (serial via `executar_programa.py` por JSON, não pool de workers).
  Não confirmado se são a mesma base de código compartilhada por baixo
  ou implementações totalmente separadas.

## Como usar este documento

Antes de propor ou aplicar qualquer correção no pipeline GIRO:

1. Confirme em qual dos três candidatos (cadeia real / `regras/` /
   `src/giro/`) o arquivo que você está tocando realmente vive.
2. Se for `core/processamento/processar_boletim.py` ou
   `divisor_boletins/audio.py` (cadeia real confirmada) — prossiga,
   mas leia o arquivo completo antes de fazer alterações, pois a
   investigação que originou este documento já leu `processar_boletim.py`
   até o fim (744 linhas) e confirmou que ele **não implementa fallback
   por contagem de notas** — apenas escalonamento de estratégias por motivo
   de auditoria via `_proxima_estrategia()` (linhas 560-582). O fallback
   descrito no `RELATORIO_PRODUCAO_GIRO_2026.md` (se < 4 notas, buscar
   mais/ Natal / programas anteriores) **não existe na cadeia real
   confirmada** até o momento desta escrita.
3. Se for `regras/*`, `src/giro/*` ou `sync/coletor.py` — pare e
   pergunte se a intenção é consertar código morto ou migrar
   arquitetura. Não assuma que é a mesma coisa.
4. Atualize este documento quando qualquer item da seção "Ainda não
   verificado" for resolvido, movendo para "Confirmado" com a evidência
   concreta (caminho de arquivo + linha, não resumo).

---

**Histórico desta investigação:** esta conversa partiu de uma hipótese
errada (que `src/giro/transcricao.py` era o código de produção), rastreou
a cadeia real até `executar_programa.py → processar_boletim.py →
divisor_boletins/audio.py`, e descobriu que `src/giro/` existe como
código paralelo não utilizado. O documento foi criado para evitar que
correções futuras sejam aplicadas no caminho errado.
