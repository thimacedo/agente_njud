# PLANO COMPLETO — POVOAMENTO DOS NJUDs 2026
Gerado em 2026-08-24. Fonte de verdade: `data/njuds_por_mes.csv` + varredura do Drive (somente leitura).

## 1. Demanda e oferta (medidos, não estimados)

| Mês | NJUDs | Boletins necessários (×4) | Datas úteis com boletim no mês da data | Boletins disponíveis naquele mês |
|---|---|---|---|---|
| JANEIRO  | 18 | 72 | 18 | 179 (353 livres / 84 bloqueados) |
| FEVEREIRO| 17 | 68 | 17 | 170 (348 / 49) |
| MARÇO    | 22 | 88 | 22 | 218 (271 / 37) |
| ABRIL    | 17 | 68 | 18 | 180 (178 / 28) |
| MAIO     | 20 | 80 | 20 | 200 (503* / 79) |
| JUNHO    | 14 | 56 | 13 | 131 (240 / 38) |
| JULHO    | 23 | 92 | 1  | 10 (23 / 7) ⚠ DÉFICIT |
| AGOSTO   | 7  | 28 | 1  | 10 (16 / 4) ⚠ DÉFICIT |
| **TOTAL**| **138** | **552** | | |

\* MAIO inclui duplicatas `(1)` e variantes `_v2` na contagem bruta — o plano deduplica por (data, B#).

**Dias úteis reais com produção** = datas únicas no nome dos arquivos (regra DECISOES item 2: mês vem do NOME do arquivo).

## 2. Situação atual do plano
- `data/plano_alocacao.csv` já cobre **552 linhas = 138 NJUDs × 4**, `njuds_faltantes.csv` vazio.
- **Risco identificado:** para JULHO (demanda 92) e AGOSTO (28) quase não existem boletins com data jul/agosto no Drive — os poucos existentes estão soltos na raiz de `03_AUDIOS_RADIO`. O `gerar_plano.py` completa esses NJUDs via fallback de OUTRO mês (regra já implementada: 1 mês alternativo, bloqueados só se necessário). Isso é aceitável, mas deve ficar registrado no relatório de alocação.
- `plano_pendentes_sem_njud.csv` (3.205 linhas) é artefato antigo com parse quebrado (`NJUD N/A`, boletim=retranca inteira) — **não usar como insumo**; será regenerado apenas se sobrar boletim sem NJUD após execução.
- Já processado: apenas NJUD 1918 (AGOSTO, montado e auditado). Restam **137 NJUDs / ~548 boletins**.

## 3. Ordem de execução (mês a mês, controlada)

Ordem cronológica; cada mês só inicia se o anterior estiver 100% auditado:

```
ABRIL → MAIO → JUNHO → JULHO → AGOSTO → (JAN–MAR ao final, opcional)
```
(Abril segue primeiro porque NJUD 1849/1850 já têm cortes parciais em `data/processed/` — retoma de checkpoint.)

Para CADA mês:
1. **Matar instâncias antigas**: sempre via `python src/iniciar_ciclo.py ...` (nunca dispatcher manual).
2. **Copiar**: `python src/copiar_boletins.py --mes <MES> --dry-run` → validar relatório (colunas, origens existem, ano 2026, sem bloqueado indevido) → `--apply`.
3. **Dividir/transcrever**: `python src/iniciar_ciclo.py JORNAIS/<MES> data/processed/JORNAIS_DIVIDIDOS --max-workers 4`
   - Monitor tempo real ativo (heartbeat visível).
   - Checkpoint `_checkpoint.json`: interrupção retoma sem retrabalho.
   - Regra dura: corte nunca default 0.0; âncora→VAD→fallback proporcional, tudo logado.
4. **Auditar**: `python src/analisar_cortes_individuais.py --mes <MES>` + `rodar_auditoria.py`
   - Limiar: cortes truncados ou < 5KB > 10% → correlacionar método (VAD vs fallback) e reprocessar SÓ os afetados (`executar_reprocessamento.py`).
   - Cortes < 5 KB filtrados automaticamente.
5. **Montar**: `pipeline_jornal.py` (usa data do nome dos boletins, nunca dias úteis derivados).
6. **Sincronizar**: `python src/sincronizar_drive.py` — ÚNICO script com escrita no H:. Sobrescreve, nunca cria `_old`.

## 4. Estimativa de tempo
Transcrição observada: ~50 s/boletim (Whisper small int8, 1 worker). Com 4 workers:
- ~548 boletins ÷ 4 ≈ 137 ciclos × ~60 s ≈ **2,5 h de divisão** total, distribuídos ~30 min/mês médio.
- Cópia + auditoria + montagem + sync: ~15 min/mês.
- **Janela realista: 1 dia útil para todos os meses restantes**, rodando mês a mês com validação entre eles.

## 5. Salvaguardas (invioláveis)
- H: somente leitura exceto `sincronizar_drive.py`.
- Nunca dois dispatchers simultâneos (`iniciar_ciclo.py` mata os anteriores).
- Validação do plano ANTES de qualquer rmtree (`copiar_boletins.py` item 3 de DECISOES).
- Backup do estado anterior antes de limpar pastas de NJUD.
- Falha de vinheta ausente não bloqueia: cai para transcrição/silêncio/VAD automaticamente.

## 6. Pendências para decisão rápida
1. **JULHO/AGOSTO:** aceitar fallback com boletins de outros meses (já previsto) ou aguardar upload dos áudios de julho/agosto no Drive antes de fechar esses NJUDs?
2. **JAN–MAR:** o Drive tem folga enorme (353+348+271 livres); executar agora junto ou deixar para depois?
