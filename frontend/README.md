# Programador — DIVISOR
Backend mínimo para o frontend web.

## Run (versão local)

```bash
cd E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/frontend
python server.py
```

Abre `http://localhost:8001`. Frontend e backend no mesmo host.

## Env vars

- `BACKEND_URL` (frontend): URL base do backend (vazio = mesmo host).
- `PORT` (backend): porta (default 8001).
- `PROJECT_DIR`: caminho base do projeto DIVISOR (default detectado).
- `UPLOAD_DIR`: pasta de uploads temporários (default `data/uploads`).
- `OUTPUT_DIR`: pasta de saída para resultados (default `data/output`).
- `DRIVER_ENABLED`: se "1", tenta sync com drive (só se `src/sync/drive.py` disponível).
- `SIMULATE`: se "1", roda pipeline em simulação (útil para teste do frontend sem processamento real).
- `VERBOSE`: se "1", log detalhado.

## Deploy online (versão online)

1. Frontend estático: deploy `index.html` no Vercel (ou outro host estático).
2. Backend: roda em um host que tem acesso ao `PROJECT_DIR` e aos scripts Python.
   - Local com túnel (cloudflared/ngrok) apontando para `python server.py`.
   - Host sempre-on (Render, Railway, VPS) com os scripts instalados.
3. Frontend no Vercel: defina `BACKEND_URL` nas env vars apontando para o backend online.

## Limitações

- O backend não roda no Vercel serverless (Whisper, minutos, filesystem local).
- Uploads são temporários; em produção, adicionar limpeza automática.
- Cancelamento: depende do pipeline suportar (hoje pode ser best-effort).
