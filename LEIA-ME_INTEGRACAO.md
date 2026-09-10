# Integração — Fases 3 a 6 da Arquitetura Unificada

Verifiquei o repositório real (`github.com/thimacedo/agente_njud`) antes de
escrever qualquer código. Resultado importante: **as Fases 1 e 2 do plano já
estão implementadas em produção** — não precisam ser refeitas.

## O que já existe no repositório (não mexer, não duplicar)

| Peça | Onde | Status |
|---|---|---|
| Remoção de vinheta por transcrição (Camada A) | `src/core/audio/remocao_vinheta.py` | ✅ Implementado e chamado em `processar_um_arquivo()` |
| `max_boletins_por_programa` (corrige 10-41 notas) | `ConfigPrograma` em `processar_boletim.py` | ✅ Implementado, default 10 |
| `RegraVinhetaBoletimAusente` (Camada C) | `core/auditoria/regras.py`, incluída no `Auditor` padrão | ✅ Implementado |
| `RegraSemFallbackParaAudioCompleto` (obrigatória) | `core/auditoria/regras.py` | ✅ Implementado |
| Separação de stems com cache | `core/stems/separacao_stems.py` | ✅ Implementado, ainda como opção manual (`usar_separacao_stems`) |

O que falta é exatamente o que você pediu agora: **desacoplar a auditoria do
processo produtor, introduzir decisão adaptativa por áudio no lugar do JSON
estático, e um portão de regressão executável.** É isso que os 5 arquivos
novos entregam.

## Arquivos novos (nesta entrega)

```
core/
├── fila/queue_client.py           # Fase 3 — fila compartilhada (SQLite)
├── auditoria/auditor_service.py   # Fase 3 — auditoria como processo externo
├── aprendizado/knowledge_base.py  # Fase 4 — KB assíncrona
├── decisao/analisador.py          # Fase 5 — decisão adaptativa por áudio
└── governanca/regras_regressao.py # Fase 6 — DECISOES.md como testes executáveis
```

Todos foram testados isoladamente (sintaxe + fluxo fila→KB) neste ambiente.
Nenhum deles foi testado contra o Whisper/Demucs reais — isso só é possível
na sua máquina, com os pacotes de áudio instalados.

## Como aplicar, na ordem certa

### Fase 3 — Auditoria externa (maior mudança de comportamento)

1. Copie `core/fila/` e `core/auditoria/auditor_service.py` para dentro do
   projeto DIVISOR, em `src/core/`.
2. **Não apague** a chamada direta a `analisar_par_consolidado()` ainda.
   Rode em paralelo por 1-2 lotes: além da chamada síncrona atual, publique
   também na fila (`fila.publicar("pendente_auditoria", {...})`) e compare
   se o `auditor_service` chega no mesmo veredito. Isso valida a migração
   sem risco de regressão silenciosa.
3. Quando os resultados baterem de forma consistente, troque a chamada
   síncrona em `processar_um_arquivo()` por só publicar na fila, e mova a
   decisão de "OK vs ESGOTADO" para consumir a fila `pronto_para_sync` /
   `requeue` em vez do retorno de função direto.
4. Rode o serviço como processo separado:
   ```bash
   python -m core.auditoria.auditor_service --loop --intervalo 5
   ```
   Pode rodar na mesma máquina, em outra janela — igual ao padrão que você
   já usa para dispatcher + monitor.

### Fase 4 — Base de conhecimento

Não exige mudança de comportamento imediata — o `auditor_service` já grava
na KB a cada ciclo (aprovado ou reprovado), passivamente. Deixe rodando por
alguns dias/lotes antes de ativar a Fase 5, para ter dado real de taxa de
sucesso por estratégia.

### Fase 5 — Analisador substituindo JSON estático

1. Em `processar_um_arquivo()`, antes da etapa de stems, chame:
   ```python
   from core.decisao.analisador import decidir_estrategia
   from core.aprendizado.knowledge_base import KnowledgeBase

   plano = decidir_estrategia(
       caminho_audio=Path(arquivo),
       programa=config.nome,
       kb=KnowledgeBase(),
       tentativas_anteriores=estado.tentativas,
   )
   ```
2. Use `plano.usar_stems` no lugar de `config.usar_separacao_stems`, e
   `plano.estrategia_sugerida` no lugar do primeiro item fixo de
   `estrategias`. **Mantenha `config.usar_separacao_stems` no JSON como
   override manual opcional** (se setado explicitamente, vence a decisão
   automática) — isso dá um botão de emergência sem reintroduzir hardcode
   como regra geral.
3. Só ative isso depois que a Fase 6 (abaixo) estiver rodando, para ter uma
   rede de segurança contra regressão.

### Fase 6 — Portão de regressão

```bash
python -m core.governanca.regras_regressao --raiz "E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR"
```

Rode isso:
- antes de qualquer merge que toque `core/`;
- como uma regra a mais dentro do `auditor_service` (regra de *código*, não
  de áudio) — pode ser chamada 1x por lote, não por arquivo, já que audita o
  repositório, não o áudio.

As 4 regras iniciais cobrem os itens mais críticos já documentados
(convenção de data, dry-run padrão, H: somente leitura, regra obrigatória de
auditoria). Adicione novas funções `checar_item_N` conforme itens novos
entrarem em `DECISOES.md` — cada item relevante do documento deveria, no
limite, virar uma função aqui.

## O que este pacote NÃO faz (para não criar expectativa errada)

- Não decide sozinho: o "botão de emergência" do JSON continua existindo por
  design, para você poder intervir manualmente se o Analisador errar.
- Não testa Whisper/Demucs de verdade — a extração de `features_audio` usa
  só `pydub` (energia/silêncio), que é rápido e roda sem GPU; é
  deliberadamente mais simples que uma análise espectral completa, para
  poder validar o fluxo agora e evoluir a extração depois sem mudar o
  contrato de dados (`FeaturesAudio`).
- Não apaga nem substitui nenhum arquivo do repositório atual — é aditivo.
