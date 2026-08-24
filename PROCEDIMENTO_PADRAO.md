# PROCEDIMENTO PADRÃO — PIPELINE DIVISOR (v4, 2026-08-24)

Este documento define o fluxo **oficial** de processamento dos boletins/NJUDs.
**v4**: substitui o fluxo sequencial de 5 etapas (v3) pelo **processo único
com ciclo fechado por arquivo**. A unidade que "termina" não é o lote — é cada
boletim, e ele só está concluído quando a auditoria o aprova.

---

## REGRAS INEGOCIÁVEIS

1. **Drive H: é somente leitura** para todo o pipeline, EXCETO a etapa final
   de sincronização (`src/sincronizar_drive.py`), que copia apenas os jornais
   prontos para `H:\...\02_JORNAIS_NJUD\03_AUDIOS_RADIO\<MÊS>\`.
   - Nenhum outro script cria pastas, renomeia arquivos ou gera cópias `_old`
     no Drive. Correções de nomes são registradas em log, nunca aplicadas no H:.
2. **Fonte de verdade do mês = data no NOME do arquivo**
   (`BOLETIM_RADIO_TJRN_DD_MM_YYYY_Bn_...`). A pasta física NÃO define o mês.
3. **Regra editorial única**: cada NJUD = 4 boletins do mês em questão.
4. Boletins sem NJUD identificável vão para `plano_pendentes_sem_njud.csv` —
   nunca são agrupados por dedução.
5. Máximo 1 dispatcher + 1 monitor ativos. Ao iniciar processo novo,
   matar os antigos primeiro.
6. **Gate por-NJUD** (substitui o gate antigo de 10% por lote): um jornal só é
   montado quando TODOS os seus 4 boletins estão `OK` ou `ESGOTADO_ACEITO`.
   Nunca monta com pendência.

---

## FLUXO ATUAL — PROCESSO ÚNICO COM CICLO FECHADO

### Arquitetura

```
dispatcher_paralelo.py  →  N workers persistentes (Whisper carregado 1x)
        │                        │
        ▼                        ▼
   fila de tarefas         ciclo por arquivo:
   (pula concluídos)       cortar(estrategia) → auditar → classificar motivo
                           → escalar estratégia OU finalizar
                                   │
                                   ▼
                    estado_por_arquivo/<arquivo>.json  (sem lock, 1 escritor)
```

### Como rodar

```powershell
# Janela 1 — processamento
python src/dispatcher_paralelo.py "F:\Projetos\DIVISOR\JORNAIS" \
    "F:\Projetos\DIVISOR\data\processed" --max-workers 3

# Janela 2 — monitor em tempo real (só leitura; abrir/fechar à vontade)
python src/monitor_tempo_real.py "F:\Projetos\DIVISOR\data\processed" --intervalo 5 --log
```

Para um teste dirigido de UM boletim (sem multiprocessing):

```bash
python teste_ciclo.py "<caminho do mp3>" --saida data/teste_ciclo
```

### Ciclo de reaprendizado por arquivo

Cada reprovação da auditoria gera um **motivo estruturado**, que decide a
próxima estratégia — nunca repete a que falhou:

| Motivo da auditoria | Próxima estratégia |
|---|---|
| palavra a `0.00s` do início | `ancora_vad_forcado` |
| palavra colada na borda | `janela_silencio_ampliada` (janela 4000ms) |
| conectivo isolado no início/fim | `grade_fixa_locucao_estendida` |
| motivo desconhecido / esgotou tudo | `ESGOTADO` (fila manual) |

Ordem completa: `calibracao_correlacao` → `ancora_vad_forcado` →
`janela_silencio_ampliada` → `grade_fixa_locucao_estendida`.

---

## STATUS POR ARQUIVO (estado_por_arquivo/*.json)

| Status | Significado | Ação operacional |
|---|---|---|
| `PENDENTE` | ainda na fila ou em processamento | nada — o worker cuida |
| `OK` | auditoria aprovou o corte atual | nada — pronto para montagem |
| `ESGOTADO` | todas as estratégias falharam | **audição manual**; motivo da última tentativa está no JSON e no monitor |
| `ESGOTADO_ACEITO` | humano ouviu e aceitou mesmo com ressalva | editar o JSON mudando o status; entra na montagem |
| `ERRO` | falha de infraestrutura (I/O, crash) | verificar `_logs/worker_N/`; apagar o JSON para reenfileirar |

A fila de revisão manual (`ESGOTADO`) aparece no dashboard do monitor com o
motivo — é a lista que precisa de ouvido humano antes de decidir entre aceitar
ou descartar.

---

## MONTAGEM E SINCRONIZAÇÃO (etapas finais)

1. Quando o monitor mostra NJUDs `completos`, rodar a montagem apenas desses:

   ```bash
   python -m divisor_boletins montar data/processed/JORNAIS_DIVIDIDOS \
       data/output/JORNAIS_FINAL --log-dir data/output/_logs
   ```

2. Sincronização (única escrita permitida no H:):

   ```bash
   python src/sincronizar_drive.py
   ```

   Falha de conexão → registra `pendentes_drive.json`, não bloqueia nada.

---

## PARÂMETROS DE DIMENSIONAMENTO (ajustar após primeira execução real)

Estes valores foram calibrados por raciocínio, NÃO medidos nesta máquina.
Revê-los após a primeira execução com workers ≥ 2:

| Parâmetro | Valor inicial | Onde | Como ajustar |
|---|---|---|---|
| `THREADS_POR_WORKER` | 2 | dispatcher_paralelo.py | manter 2; Whisper small int8 escala mal acima disso |
| `RAM_POR_WORKER_GB` | **2.5 (medido)** | dispatcher_paralelo.py | medido em 2026-08-24: 1.5 causou OOM (`mkl_malloc`) com 2 workers e 5.6GB livres |
| `RAM_RESERVADA_GB` | **3.0 (medido)** | dispatcher_paralelo.py | elevado de 2.0 após OOM; aumentar se o PC travar com outros apps abertos |
| `LIMIAR_CPU_PAUSA` | 85% | dispatcher_paralelo.py | dispatcher pausou corretamente a 90–100%; reduzir para 75 se o operador usar a máquina durante o lote |
| `HEARTBEAT_ATRASADO_S` / `MORTO_S` | 15s / 60s | monitor_tempo_real.py | se cortes legítimos aparecerem como ATRASADOS, subir ATRASADO para 30s |

---

## LIMITAÇÕES CONHECIDAS (2026-08-24)

1. **Worker morto não é reiniciado automaticamente.** Se um worker crashar,
   as tarefas restantes da fila ficam retidas. O monitor marca `[PID NÃO EXISTE MAIS]`.
   Mitigação manual: matar o dispatcher e rodar de novo — arquivos já OK são
   pulados pelo próprio dispatcher (é a vantagem do estado persistido).
2. **Auditor pode acusar falso `0.00s`.** O Whisper ancora timestamps das
   primeiras palavras em zero em cortes curtos mesmo havendo silêncio real.
   Enquanto o auditor não migrar para medição física de energia (pydub/ffmpeg),
   esse motivo pode gerar escalonamentos desnecessários. O ciclo continua seguro
   (no pior caso vai para revisão manual), mas custa mais tentativas.
3. **Montagem ainda manual** — dispara quando o monitor mostra NJUDs completos.
   Automação desse disparo fica para versão futura.

---

## LIÇÕES QUE LEVARAM A ESTA VERSÃO

| Problema histórico | Correção definitiva |
|---|---|
| Palavras coladas nas bordas (CORTADO) | Ancoragem em silêncio real + fronteira compartilhada CABEÇA/CORPO |
| CORPO vazio abortava montagem | Filtro <5KB na montagem |
| `inicio_cabeca=0.0` silencioso | DECISOES.md item 5; fallback âncora/VAD explícito |
| Centenas de cópias `_old` no Drive | H: somente leitura exceto sync final; overwrite sem _old |
| Reprocessar lote inteiro apagava histórico | Processo único: estado por arquivo, nunca repete estratégia |
| Monitor contando .mp3 não distinguia status | monitor_tempo_real.py lê os JSONs de estado |
| Mês definido pela pasta gerava lotes errados | Data do nome do arquivo é a fonte de verdade |

*Versão 4 — 2026-08-24. v3 → v4: fluxo sequencial substituído pelo processo
único com ciclo fechado, dispatcher paralelo com heartbeat, gate por-NJUD,
monitor de tempo real e documentação de status/dimensionamento.*

---
## ATUALIZAÇÃO 2026-08-24 (item 6b das DECISOES)
- Limitação 2 (falso 0.00s) RESOLVIDA: auditor migrado para medição física
  de energia (RMS 50ms vs piso percentil-10, limiar +12dB). O motivo
  "0.00s do início" não existe mais; motivo atual é "energia de fala na borda".
- Montagem e sync alinhados à árvore do dispatcher (sem cópia manual):
  cortes em JORNAIS_DIVIDIDOS/<NJUD>/ → montar_todos → JORNAIS_FINAL/ → sync.
