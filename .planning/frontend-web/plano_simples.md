# Frontend + Backend Simples — DIVISOR

## Premissa

- Versão local e versão online, coexistindo.
- Agentes atuais (`src/`, pipelines, dispatcher, etc.) permanecem intactos.
- Frontend e backend são novos, enxutos, chamam os agentes existentes como "motor".
- Vercel pode hospedar o frontend estático. Backend não roda no Vercel (Whisper, minutos, filesystem local). Backend fica em um lugar que tem acesso ao projeto (local com túnel, ou VM/host sempre-on).

## Arquitetura de 2 arquivos (mais simples possível)

```
frontend/
├── index.html      # SPA autocontida (HTML+CSS+JS). Chama /api/...
├── server.py       # FastAPI: serve o index.html + endpoints de upload/jobs/download
└── README.md
```

Sem framework JS, sem build step, sem `package.json`, sem `node_modules`. Só Python (FastAPI) + browser.

## Versão local

```bash
cd E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/frontend
python server.py
```

Abre `http://localhost:8001`. Frontend e backend juntos, chamando os scripts do `src/` que rodam na mesma máquina com acesso ao `E:/.../DIVISOR`.

## Versão online

Dois modos (escolhe um):

### Modo A — Frontend no Vercel + Backend local com túnel (mais simples, reuse arquivos locais)

1. Deploy `frontend/index.html` no Vercel como site estático.
2. No mesmo máquina do DIVISOR, subir `server.py` na porta 8001.
3. Exposer `http://localhost:8001` com túnel (cloudflared `cloudflared tunnel --url http://localhost:8001`, ou ngrok).
4. Frontend no Vercel aponta `BACKEND_URL` para a URL do túnel.
5. Tudo que processa áudio roda na máquina com acesso ao `E:/`.

Vantagem: zero mudança nos arquivos, agentes intactos, backend acessa o filesystem real.

Desvantagem: backend depende da máquina ligada + túnel ativo (perfeito para teste; para produção, backumped ou tunel confiável).

### Modo B — Frontend no Vercel + Backend em host sempre-on (produção)

1. Frontend no Vercel como acima.
2. Backend em Render/Railway/Fly.io/VM com acesso aos scripts (`src/`) e onde os áudios podem ser uploadados+processados.
3. Se o backend nõo tem acesso ao `E:/` local, os áudios sobem via upload, processam no backend, e os resultados sobem via download. Agentes `src/` precisariam estar instalados no backend (ou ter uma versão simplificada que roda sem depender dos caminhos locais).
4. Mais complexo (mover os scripts, dependências, acesso ao Drive se usado). Por isso, Modo A é o mais simples para começar.

Recomendação: começar com Modo A.

## Contrato: Frontend ↔ Backend

O frontend chama estes endpoints (mesma URL base que `server.py`):

```
GET  /                      → serve index.html
POST /api/upload            → recebe arquivo, retorna { id, filename, size_bytes }
POST /api/jobs              → cria job { tipo, inputs: [upload_id, ...] } → retorna { job_id }
GET  /api/jobs              → retorna lista de jobs (ativos + recentes)
GET  /api/jobs/{job_id}     → status do job (etapa, progresso, saida, erro)
DELETE /api/jobs/{job_id}   → cancela job (se rodando)
GET  /api/download/{job_id} → arquivo final (FileResponse)
```

Variável de ambiente no frontend: `BACKEND_URL`. Se não definida, aponta para `""` (mesmo host — usado na versão local onde frontend e backend são servidos pelo mesmo `server.py`).

## Como o `server.py` chama os agentes atuais

Ele não reimplementa nada. Ele:

- Recebe uploads → salva em `data/uploads/` (dentro do projeto, não interfere com `JORNAIS/`).
- Cria um job → roda o agente correspondente com `subprocess` (ou import direto se houver função limpa).
  - Boletins: chama algum script/cli que edita o boletim. Se existir uma função simples, importa; senão subprocess.
  - NJUD: chama montagem NJUD existente.
  - Giro: chama `src/giro/montagem.py` (já tem `montar_programa()`).
- Retorna progresso atualizando job em memória (e opcionalmente persistindo em `data/jobs/jobs.json`).
- Quando pronto, move/copia o resultado para `data/output/...` e oferece download via `/api/download/{job_id}`.

Importante: o `server.py` é opcional para os agentes existentes. Os agentes continuam rodando via CLI/agents atuais; o frontend é só uma interface nova.

## O que NÃO muda

- `src/` (pipeline, dispatcher, orchestration, giro, njud, etc.).
- `data/`, `JORNAIS/`, `GIRO/`, `logs/`, `assets/`.
- Scripts existentes em `scripts_pipeline/`.
- Agentes que rodam via `iniciar_ciclo.py`, `teste_ciclo.py`, etc.
- Acesso ao H: (se usado) continuam restrito a `src/sync/drive.py`.

O novo módulo apenas adiciona uma interface web + um thin server que orquestra os mesmos processos.

## Vercel: o que a gente precisa

1. Frontend estático: `frontend/index.html` + `frontend/vercel.json` (rewrites SPA).
2. Login no Vercel (token ou login interativo). Se o login trava automação, pode ser feito manualmente uma vez, ou usar token com `vercel --token $VERCEL_TOKEN`.
3. Variável de ambiente `BACKEND_URL` configurada no projeto Vercel (Settings → Environment Variables) apontando para o backend online.

Deploy:

```bash
cd E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/frontend
vercel --prod
```

Ou, se o projeto Vercel já existe:

```bash
vercel --prod --cwd frontend
```

Depois, configurar `BACKEND_URL` nas env vars do projeto Vercel para a URL do backend (túnel ou host).

## Decisão rápida

Quero te entregar o mínimo que funciona em local e deixa a porta aberta pro online. Por isso vou:

1. Criar `frontend/index.html` (SPA, 3 modos, upload, jobs, polling, download).
2. Criar `frontend/server.py` (FastAPI, endpoints, chama `src/`).
3. Criar `frontend/vercel.json` (SPA rewrite para Vercel).
4. Criar `frontend/README.md` (como rodar local e como deploy no Vercel).
5. Comentar onde configurar `BACKEND_URL` para versão online.

Se você quiser, posso pular o Vercel por enquanto e entregar só `index.html` + `server.py` rodando localmente. O deploy no Vercel é configurar e subir esse mesmo `index.html` quando estiver pronto — não muda o código.

Me diz se quero continuar com Vercel agora (e se o login vai ser resolvido manualmente ou com token) ou se prefiro entregar o mínimo local primeiro e lidar com Vercel depois.