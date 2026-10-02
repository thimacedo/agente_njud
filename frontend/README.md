# Programador — Frontend DIVISOR

## Ambiente de desenvolvimento e testes

Use **Python 3.11** e o mesmo `.venv_pipeline` para backend e áudio.
Na raiz do projeto, em PowerShell:

```powershell
./dev.ps1 setup
./dev.ps1 check
./dev.ps1 test
./dev.ps1 backend
./dev.ps1 pipeline -m divisor_boletins --help
./dev.ps1 pipeline scripts_pipeline/montagem_jornais.py --help
```

O wrapper usa o interpretador explícito, fixa a raiz de execução e inclui
`scripts_pipeline` nos imports, inclusive nos subprocessos do backend.
Não é necessário ativar o ambiente. Os comandos de backend/pipeline usam
`data/tmp` para temporários de áudio, respeitando `DIVISOR_TMP` se definido. `requirements-dev.txt` inclui backend,
pipeline e testes. FFmpeg e ffprobe precisam estar no PATH (instalação externa).
Para Whisper alternativo, auditoria com SciPy e VAD Silero:

```powershell
./dev.ps1 pipeline -m pip install -r requirements-optional.txt
```

O carregador Silero usa o modelo incluído no pacote. FFmpeg/pydub fazem a
leitura de áudio; os extras de I/O do Silero não são necessários ao pipeline.
As dependências opcionais incluem PyTorch. Whisper pode baixar modelos na primeira execução; use um caminho local em `DIVISOR_WHISPER_MODEL` para o modelo faster-whisper já disponível.

Para simular: `$env:SIMULATE='1'; ./dev.ps1 backend`.
`DATA_DIR`, `UPLOAD_DIR` e `OUTPUT_DIR` permitem isolar dados de testes.
O pipeline não é executado pelo setup. Testes unitários não baixam modelos.
A validação de áudio real deve usar pastas isoladas por `DATA_DIR`, `UPLOAD_DIR`,
`OUTPUT_DIR` e `DIVISOR_TMP`; nunca sobrescrever as entradas de produção.

Avisos conhecidos: pydub usa `audioop` do Python 3.11; Silero/PyTorch usam
APIs de recursos e TorchScript em descontinuação. Não há filtros que ocultem
esses avisos. FastAPI usa `lifespan`, e os testes HTTP incluem `httpx2`.
O aviso de `audioop` exige avaliar uma migração de pydub antes de Python 3.13.


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
