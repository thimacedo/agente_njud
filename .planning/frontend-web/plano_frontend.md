# Plano do Frontend Web — DIVISOR

## 1. Objetivo

Criar uma interface web que permita disparar **um programa por vez**, de três tipos:

- **Boletins**: 1 áudio bruto → edição automática (remoção de erros de locução) → boletim editado
- **NJUD**: 4 boletins prontos → montagem automática do jornal → arquivo final
- **Giro**: 4+ boletins prontos → montagem automática do programa → arquivo final

A interface será a **camada de orquestração visual** sobre os pipelines Python já existentes em `src/`. Não reimplementa lógica de negócio; apenas expõe ações, entrada de arquivos, acompanhamento e download.

## 2. Princípios de design

- **Neutro minimal**: sem gradientes forçados, sem decoração, foco na operação.
- **Um programa por vez**: a interface guia o usuário a completar um fluxo de cada vez.
- **Visibilidade de progresso**: cada processo em andamento aparece com etapa atual, barra de progresso e ações (cancelar).
- **Fail-closed**: erros aparecem no card do processo; nunca silencia falhas.
- **Estado persistente é fonte de verdade**: o frontend lê status/resultados de arquivos e endpoints, não confia apenas em memória RAM.

## 3. Stack escolhida

### Frontend

- **HTML + CSS + JavaScript** em arquivo único autocontido (`frontend/index.html`), sem build step.
- Sem frameworks JS; vanilla JS para simplicidade e portabilidade.
- CSS com variáveis customizadas para tokens do tema; sistema de componentes via classes utilitárias mínimas.
- Responsivo: mobile em 1 coluna, desktop em grid.

### Backend (servidor de integração)

- **FastAPI** (já usado no projeto Gravador Inteligente, coerente com o ecossistema).
- Responsável por:
  - Receber uploads (wav, mp3, m4a, ogg, flac).
  - Disparar os módulos do `src/` como subprocessos ou imports diretos.
  - Retornar status de execução via polling.
  - Servir `index.html` e arquivos finalizados para download.
- Roda em porta própria (ex: `8001`) para não conflitar com outros serviços.

### Por que FastAPI aqui

- já é padrão no time/projeto;
- `UploadFile`, `FileResponse`, CORS e async são nativos;
- boa para prototipar endpoints rapidamente sem ORM ou dependências extras.

## 4. Estrutura de diretórios do frontend

```
DIVISOR/
├── frontend/
│   ├── index.html          # SPA autocontida (HTML+CSS+JS)
│   ├── README.md           # como rodar, endpoints, troubleshooting
│   └── server.py           # FastAPI: uploads, jobs, download, status
├── src/...                 # untouched — lógica de negócio permanece aqui
└── ...
```

> Nota: se no futuro quiser unificar, o `server.py` pode ser absorvido em `src/web/` ou `src/orchestration/`. Hoje, `frontend/server.py` é uma camada fina de integração.

## 5. Estados e dados

### Estado do frontend (JS, em memória por sessão)

```js
state = {
  modo: 'boletins' | 'njud' | 'giro',
  slots: [
    { id, file, filename, filesize, error?, backendId? }
  ],
  jobs: [
    {
      id,
      tipo: 'Boletim' | 'NJUD' | 'Giro',
      name,
      status: 'running' | 'done' | 'error' | 'cancelled',
      progress: 0-100,
      etapa: string,       // etapa textual atual
      error?: string,
      downloadUrl?: string,
      createdAt: timestamp,
      files: [ {name, size} ],
      _timer: number|null, // para cancelar simulação/local
    }
  ],
  nextJobId: 1,
  nextSlotId: 1,
}
```

- `modo` altera a quantidade mínima/máxima de slots e as labels.
- `slots` armazenam o `File` do browser e, após upload, `backendId` (id retornado pelo backend).
- `jobs` acompanham cada processo iniciado.

### Estado do backend (fonte de verdade)

Para integrar de verdade, o backend servirá:

- `POST /upload` → recebe arquivo, salva em `data/uploads/`, retorna `{ id, filename, path, size_bytes }`.
- `POST /jobs` → cria um job com `{ tipo, inputs: [upload_id, ...], params }`, retorna `{ job_id }`.
- `GET /jobs/{job_id}` → retorna status, etapa, progresso, resultado, erro.
- `GET /jobs` → lista jobs ativos/recentes.
- `GET /download/{job_id}` → `FileResponse` do arquivo final.
- `GET /health` → saúde do backend.

O frontend consultará `/jobs` periodicamente (polling a cada 2–5s) enquanto houver jobs `running`.

> Futuramente, pode ser substituído por WebSocket ou SSE para push de progresso.

## 6. Backend — servidor de integração (`frontend/server.py`)

### Responsabilidades

1. **Static serving**: serve `index.html`, CSS e JS (pode ser embutido no HTML).
2. **Upload**: recebe arquivos via `UploadFile`, valida extensão, salva em `data/uploads/` (criar se não existir).
3. **Jobs**: cria registros de job em memória (ou em `data/jobs/` para persistência simples) e dispara execução.
4. **Execução**: chama os módulos do `src/` de duas formas:
   - **Import direto**: quando o módulo tem função Python clara (ex.: `src/giro/montagem.montar_programa(...)`).
   - **Subprocesso**: para fluxos complexos (ex.: `python src/iniciar_ciclo.py <pasta> <saida>`).
   - Decisão por fluxo:
     - Boletins: import de `src/gravador_inteligente/app/edicao_boletins.py` ou `src/divisor_boletins/audio.py` (se existir função de edição simples). Se não houver função única, usar subprocesso com script apropriado.
     - NJUD: import de `src/orchestration/intelligent.py` → `etapa_montagem_jornal()` se houver; senão subprocesso `python src/pipeline/montagem.py` ou `scripts_pipeline/montar.sh`.
     - GIRO: import de `src/giro/montagem.montar_programa()`.
5. **Progresso**: enquanto o processo roda, atualiza `etapa` e `progress` no job.
6. **Download**: quando concluído, registra `downloadUrl` apontando para `/download/{job_id}`.

### Decisão de implementação: import vs subprocesso

- **Import direto** é preferível quando há função clara, síncrona ou assíncrona que retorna resultado.
- **Subprocesso** é mais seguro para fluxos longos que já têm CLI consolidada (ex.: `iniciar_ciclo.py`, scripts `processor_*`).
- Para o primeiro MVP, priorizar subprocesso nos fluxos que ainda não expõem função única, e import nos que já têm (ex.: GIRO tem `montar_programa()`).

### Endpoints planejados

```
GET  /                        → serve index.html
GET  /health                  → { status, timestamp }
GET  /api/jobs                → lista jobs (ativos e recentes)
GET  /api/jobs/{job_id}       → detalhe do job
POST /api/jobs                → cria job { tipo, inputs: [upload_id, ...], params? }
POST /api/upload              → recebe arquivo, retorna { id, filename, path, size_bytes }
GET  /api/download/{job_id}   → arquivo final (FileResponse)
DELETE /api/jobs/{job_id}     → cancelar job (se rodando)
```

### Persistência de jobs

Para sobreviver a restart do servidor, jobs podem ser salvos em `data/jobs/jobs.json` (append + atualização por id). Estado simples:

```json
{
  "job_id": {
    "tipo": "NJUD",
    "status": "running",
    "etapa": "Montando jornal...",
    "progress": 72,
    "inputs": ["upload_123", "upload_124", ...],
    "saida": null,
    "error": null,
    "created_at": "2026-09-09T10:00:00",
    "updated_at": "2026-09-09T10:03:00"
  }
}
```

## 7. Frontend — interface

### Layout

```
┌─────────────────────────────────────────────────────┐
│ Programador Online — DIVISOR          backend: ok   │
├─────────────────────────────────────────────────────┤
│ [Boletins] [NJUD] [Giro]    ← modos fixos           │
├─────────────────────────────────────────────────────┤
│ Área de trabalho (dinâmica por modo)                 │
│ ┌──────────┐ ┌──────────┐                           │
│ │ Slot 1   │ │ Slot 2   │  (grid por modo)          │
│ │ (drop)   │ │ (drop)   │                           │
│ └──────────┘ └──────────┘                           │
│ ┌──────────┐ ┌──────────┐                           │
│ │ Slot 3   │ │ Slot 4   │                           │
│ │ (drop)   │ │ (drop)   │                           │
│ └──────────┘ └──────────┘                           │
│ [+ adicionar slot]  (só no Giro, quando possível)   │
│ [Processar]  [Limpar]                               │
├─────────────────────────────────────────────────────┤
│ Processos                                            │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Boletim — audio.mp3          [Boletim] [ativa]   │ │
│ │ Transcrevendo com Whisper...     ████████░░ 72% │ │
│ │ em andamento                            [Cancelar]│ │
│ └─────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────┐ │
│ │ NJUD — 4 arquivos              [NJUD] [concluído]│ │
│ │ Concluído — 120s                       [Baixar]  │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Comportamento por modo

| Modo | Slots mín. | Slots máx. | Grid | Botão "+" | Ação |
|---|---|---|---|---|---|
| Boletins | 1 | 1 | 1 col | não | Processar → `editar_boletim()` |
| NJUD | 4 | 4 | 2×2 | não | Processar → `montar_jornal()` |
| Giro | 4 | N | 2×2 | sim, quando todos iniciais cheios | Processar → `montar_giro()` |

### Interações

- **Upload**: clique no slot abre file picker; drag-and-drop também funciona.
- **Validação**: extensões permitidas `mp3, wav, m4a, ogg, flac`; slot fica com erro visual se formato inválido.
- **Remover**: botão ✕ no slot remove o arquivo; desabilitado se houver job ativo.
- **Limpar**: remove todos os arquivos dos slots; desabilitado se job ativo.
- **Processar**: habilitado só quando todos os slots mínimos estão preenchidos e não há job ativo.
- **Cancelar**: cancela job em andamento (se backend suportar abort).
- **Baixar**: baixa arquivo final do job concluído.
- **Desprezar**: remove card de job concluído/erro da tela.

### Estados visuais dos jobs

- **running**: borda accent, barra de progresso animada, badge "ativo".
- **done**: borda verde, barra cheia, botão "Baixar" + "Desprezar".
- **error/cancelled**: borda vermelha, mensagem de erro, botão "Desprezar".

### Feedback

- Header mostra status do backend (`backend: ok`, `backend: simulação`, `backend: erro`).
- Hint textual ao lado do botão Processar com orientações curtas.
- Progresso por etapa textual (ex.: "Transcrevendo com Whisper…") + barra %.

## 8. Integração com o backend do DIVISOR

### Fluxo Boletins

1. Usuário envia 1 áudio bruto no slot.
2. Clica "Processar".
3. Frontend chama `POST /api/upload` → recebe `upload_id`.
4. Frontend cria job `Boletim` com `inputs: [upload_id]`.
5. Backend executa edição:
   - Via import de `src/gravador_inteligente/app/edicao_boletins.py` se função única existir.
   - Ou via subprocesso `python -m src.gravador_inteligente.app.edicao_boletins <caminho>`.
6. Backend atualiza job com etapas: upload → transcrição → detecção → corte → export.
7. Frontend consulta `GET /api/jobs/{id}` e atualiza barra.
8. Ao concluir, backend registra caminho do arquivo editado; frontend mostra "Baixar".

### Fluxo NJUD

1. Usuário envia 4 boletins prontos (já editados) nos slots.
2. Clica "Processar".
3. Frontend faz upload de cada um → recebe 4 `upload_id`s.
4. Cria job `NJUD` com `inputs: [id1, id2, id3, id4]`.
5. Backend:
   - Monta pasta temporária com os 4 arquivos.
   - Executa lógica de montagem NJUD:
     - Import de `src/orchestration/intelligent.py` (etapas de montagem) se função exposta.
     - Ou subprocesso do pipeline existente que monta o jornal.
6. Backend atualiza etapas: recepção → alinhamento → ordenação → montagem → export.
7. Resultado: arquivo `NJUD_XXXX_DD-MM-YYYY.mp3` em `data/output/JORNAIS_FINAL/`.
8. Frontend libera download.

### Fluxo Giro

1. Usuário envia N boletins prontos (mínimo 4).
2. Clica "Processar".
3. Frontend faz upload de cada um → recebe N `upload_id`s.
4. Cria job `Giro` com `inputs: [id1, ..., idN]`.
5. Backend:
   - Agrupa boletins por notas e programa.
   - Executa `src/giro/montagem.montar_programa(mmss, notas_paths)`.
6. Backend atualiza etapas: recepção → verificação → ordenação → montagem → export.
7. Resultado: arquivo `GNC_XXXX_DD-MM-YYYY.mp3`.
8. Frontend libera download.

## 9. Progresso e polling

### Formato de resposta de `/api/jobs/{id}`

```json
{
  "id": "job_001",
  "tipo": "NJUD",
  "status": "running",
  "etapa": "Montando jornal...",
  "progress": 72,
  "created_at": "2026-09-09T10:00:00",
  "updated_at": "2026-09-09T10:03:00",
  "saida": null,
  "error": null
}
```

### Etapas sugeridas por tipo

**Boletins**:
- `upload` (0-10%)
- `transcricao` (10-35%)
- `deteccao` (35-60%)
- `corte` (60-85%)
- `export` (85-100%)

**NJUD**:
- `upload` (0-8%)
- `alinhamento` (8-30%)
- `ordenacao` (30-55%)
- `montagem` (55-80%)
- `export` (80-100%)

**Giro**:
- `upload` (0-8%)
- `verificacao` (8-28%)
- `ordenacao` (28-50%)
- `montagem` (50-75%)
- `export` (75-100%)

O backend é responsável por emitir essas etapas. O frontend apenas exibe.

## 10. Validações e regras

- Upload: extensão deve estar em `['mp3','wav','m4a','ogg','flac']`.
- Boletins: exatamente 1 arquivo.
- NJUD: exatamente 4 arquivos.
- Giro: mínimo 4 arquivos; máximo teórico ilimitado, mas frontend pode advertir acima de 12 por questões de tempo de processamento.
- Cancelamento: backend deve suportar cancelamento; se não, o botão fica desabilitado ou informa "cancelamento não suportado".
- Limpeza: frontend não apaga arquivos do backend; apenas remove referências visuais.

## 11. Segurança e CORS

- Backend com CORS aberto apenas para origens confiáveis (ou `*` em ambiente interno).
- Uploads sem autenticação:adequado para uso local/rede interna.
- Se exposto remotamente, adicionar autenticação básica (ex.: header token) no `server.py`.
- Nunca expor caminhos absolutos do Windows no frontend; usar apenas `/api/...` relativos.

## 12. Responsividade

- **Desktop (>640px)**:
  - Boletins: slot único centralizado ou à esquerda.
  - NJUD/Giro: grid 2×2.
- **Mobile (≤640px)**:
  - Todos os modos: grid 1 coluna.
  - Slots ocupam largura total.
  - Botões e tipografia mantêm tamanho mínimo de toque (44px).

## 13. Acessibilidade mínima

- Botões e zonas de drop com foco visível.
- Labels claros: "Áudio bruto", "Boletim #1", etc.
- Contraste suficiente (neutro minimal com cinzas + accent azul; testar contraste WCAG AA).
- Mensagens de erro em texto, não apenas cor.

## 14. Como rodar (dev)

```bash
cd E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/frontend
python server.py
```

Abre `http://localhost:8000/index.html`.

Para produção, pode ser executado via systemd/service ou como parte do startup do pipeline.

## 15. Exposição remota

- Backend serve tanto o frontend quanto os arquivos.
- Para acesso externo, usar tunnel (cloudflared/ngrok) apontando para a porta do `server.py`.
- Cuidado com tamanho de upload: nginx/tunnel pode ter limite; configurar timeout adequado para uploads grandes (vários MB por boletim).

## 16. Futuras melhorias (fora do MVP)

- WebSocket ou SSE para progresso em tempo real, eliminando polling.
- Histórico de programas na sessão (localStorage).
- Drag-and-drop reordenável nos slots do Giro.
- Autenticação por usuário.
- Modo escuro/claro via toggle.
- Internacionalização (i18n) mínimo PT-BR/EN.
- Logs do frontend consolidados em `logs/frontend/`.
- Agendamento de execução (cron via backend).
- Integração com Google Sheets (`journal_pipeline.py`) para buscar roteiros e refinar cortes.

## 17. Critérios de aceitação (MVP)

- [ ] `frontend/server.py` sobe e serve `index.html` em `/`.
- [ ] Upload de 1 arquivo no modo Boletins → cria job → acompanha progresso → download do editado.
- [ ] Upload de 4 arquivos no modo NJUD → cria job → acompanha progresso → download do jornal.
- [ ] Upload de 4+ arquivos no modo Giro → cria job → acompanha progresso → download do programa.
- [ ] Botão Cancelar funciona (ou é desabilitado com clareza se não suportado).
- [ ] Erros aparecem no card do job (não em alerta).
- [ ] Layout responsivo até 320px largura.
- [ ] Nenhuma alteração em `src/` para fazer o MVP funcionar (server.py usa subprocesso).

## 18. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Backend do DIVISOR não tem função única para edição de boletim | Usar subprocesso com script CLI existente; manter interface estável. |
| Processos longos travam o servidor | Rodar execução em threadpool/processpool; FastAPI responde imediatamente com job_id. |
| Uploads grandes estouram memória | Limitar tamanho em `server.py` (ex.: 200MB por arquivo); ou usar streaming. |
| Caminhos do Windows quebram no subprocesso | Usar `pathlib` e `str()` sempre; não hardcode caminhos. |
| Estado do job se perde se `server.py` reiniciar | Persistir jobs em `data/jobs/jobs.json`. |
| Drive H: só leitura + escrita restrita | Frontend não acessa Drive diretamente; backend respeita regra. |
| Dois dispatchers rodando | `iniciar_ciclo.py` já mata antigos; se frontend usar subprocesso, chamar ele. |

## 19. Decisões arquiteturais (ADRs resumidos)

- **ADR 1**: frontend é uma camada fina sobre `src/` existente. Motivo: reaproveitar lividade testada e evitar duplicação.
- **ADR 2**: `server.py` é separado de `src/`. Motivo: não misturar interface web com pipeline CLI; facilita remover/modificar frontend sem tocar no núcleo.
- **ADR 3**: polling em vez de WebSocket no MVP. Motivo: simplicidade; WebSocket pode ser adicionado depois sem mudar a UI.
- **ADR 4**: uploads salvos em `data/uploads/` (não em `JORNAIS/`). Motivo: `JORNAIS/` é entrada bruta do pipeline; uploads do frontend são transient.
