# Status do Pipeline — DIVISOR

Data: 2026-08-24
Commit: 258537f

## Estado atual
- **8 de 8 ferramentas de acurácia/produtividade implementadas** e compiladas.
- **Bug crítico corrigido** em `src/processo_unico.py`: 44 arquivos estavam marcados como `ERRO` por falha de serialização (`erro` não era aceito pelo dataclass). Após a correção, eles podem ser reprocessados.
- **Teste de jornal finalizado concluído** com sucesso: `data/output/JORNAIS_FINAL/NJUD_1849_06-04-2026.mp3` (3.384.050 bytes).
- **Planejamento em JSON implementado**: `src/planejador_copia.py` gera o plano, copia apenas arquivos necessários para workspace temporário e permite limpeza automática ao final.

## Ferramentas entregues
1. **ffmpeg silencedetect** como validador cruzado em `src/analisar_cortes_individuais.py`.
2. **Detecção de resíduo de vinheta** (energia espectral) em `src/divisor_boletins/audio.py`.
3. **whisper-timestamped** como backend opcional em `src/dispatcher_paralelo.py`.
4. **Auto-reinício de workers** no dispatcher (`src/dispatcher_paralelo.py`).
5. **Montagem automática por evento** via `src/monitor_montagem_auto.py`.
6. **Dashboard Streamlit** em `src/dashboard_streamlit.py`.
7. **Cache de transcrições** em memória + disco em `src/divisor_boletins/audio.py`.
8. **Validação pós-sync** em `src/sincronizar_drive.py`.

## Resultado do último teste
- **Saída:** `data/processed/JORNAIS_DIVIDIDOS_TESTE_NJUD_1849`
- **Relatório de auditoria:** pendente de geração no momento deste documento.
- **Avaliação qualitativa:** jornal finalizado está **99% perfeito**.
  - Há algumas falhas nos pontos de corte.
  - Não foram identificadas sobras de vinhetas dos boletins.
  - Houve evolução expressiva em relação à linha base anterior.

## Fluxo canônico atual
1. **Copiar** — planejamento JSON + cópia seletiva para workspace temporário.
2. **Cortar** — divisão em `_CABECA` e `_CORPO` com âncora em silêncio/vale adaptativo.
3. **Auditar** — validação individual dos cortes (`analisar_cortes_individuais.py`).
4. **Montar** — composição do jornal completo (`montar_jornal`).
5. **Subir** — sincronização com Drive (`sincronizar_drive.py`), somente leitura fora deste script.

## Nova lógica de produção (futura)
- Boletins produzidos em um dia alimentam a programação do dia útil seguinte.
- Segunda → terça, terça → quarta, ..., sexta → segunda seguinte.
- Quando estável, a rotina passa a pegar **4 jornais do TJRN** para compor o jornal do dia seguinte.

## Pendências conhecidas
- Ajuste fino dos pontos de corte que ainda falham ocasionalmente.
- Reprocessar os 44 arquivos que estavam bloqueados pelo bug de serialização.
- Validar o dashboard Streamlit em execução contínua.
- Integrar o planejador JSON como caminho padrão do orquestrador.
