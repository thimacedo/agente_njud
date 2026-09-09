# Programador — Frontend DIVISOR

Interface web para disparar 1 programa por vez: **Boletins**, **NJUD** ou **Giro**.

## Versão local

```bash
cd E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/frontend
python server.py
```

Abre `http://localhost:8001`. Frontend e backend no mesmo host.

Para testar sem processamento real (simulação):
```bash
SIMULATE=1 python server.py
```

## Versão online (Vercel + Backend separado)

### Deploy do frontend no Vercel

1. O `index.html` é estático. O `vercel.json` configura rewrite para SPA.
2. Conecte o repositório no Vercel (ou use `vercel --prod`).
3. O frontend precisa saber a URL do backend. Três formas:
   - **Query string**: `https://seu-app.vercel.app/?backend=https://seu-backend.com`
   - **Botão ⚙** no header: abre modal para salvar URL no localStorage
   - **localStorage**: `localStorage.setItem('BACKEND_URL', 'https://...')`

### Onde o backend roda

O `server.py` (FastAPI) **não roda no Vercel** (Whisper, minutos, filesystem local). Opções:

| Onde | Como |
|---|---|
| **Local + túnel** | `python server.py` + `cloudflared tunnel --url http://localhost:8001` |
| **Render/Railway** | Deploy como Web Service Python |
| **VPS** | `python server.py` atrás de nginx |

### Variáveis de ambiente (backend)

| Var | Default | Descrição |
|---|---|---|
| `PORT` | 8001 | Porta do servidor |
| `PROJECT_DIR` | auto | Caminho do projeto DIVISOR |
| `UPLOAD_DIR` | `data/uploads` | Pasta de uploads temporários |
| `OUTPUT_DIR` | `data/output` | Pasta de saída dos resultados |
| `SIMULATE` | 0 | 1 = roda pipelines em simulação |
| `VERBOSE` | 0 | 1 = log detalhado |

## Endpoints da API

| Método | Path | Descrição |
|---|---|---|
| GET | `/health` | Status do backend |
| POST | `/api/upload` | Upload de arquivo (multipart) |
| POST | `/api/jobs` | Criar job `{tipo, inputs:[ids]}` |
| GET | `/api/jobs` | Listar jobs |
| GET | `/api/jobs/{id}` | Status do job |
| DELETE | `/api/jobs/{id}` | Cancelar job |
| GET | `/api/download/{id}` | Baixar arquivo final |

## Arquitetura

```
Navegador (Vercel)
    │
    │  fetch('/api/...')
    ▼
Backend (server.py) ──▶ src/divisor_boletins/ (corte)
                       src/giro/montagem.py   (giro)
                       src/orchestration/     (njud)
```

O backend é uma camada fina: recebe uploads, chama os agentes existentes via subprocess ou import, retorna progresso via polling.
