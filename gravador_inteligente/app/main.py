"""
Gravador Inteligente - API Principal
FastAPI server para upload de áudios, processamento e geração de boletins.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import config
from app.edicao_boletins import editar_boletim, EdicaoConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gravador-inteligente")


# =============================================================================
# Lifecycle
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação."""
    logger.info("Iniciando Gravador Inteligente...")
    logger.info(f"Diretório base: {config.app.base_dir}")
    logger.info(f"Diretório uploads: {config.app.upload_dir}")
    yield
    logger.info("Encerrando Gravador Inteligente...")


# =============================================================================
# App
# =============================================================================

app = FastAPI(
    title="Gravador Inteligente",
    description="Pipeline de processamento de áudio para geração automática de boletins diários",
    version="0.1.0",
    lifespan=lifespan,
)

if config.app.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# =============================================================================
# Endpoints - Health
# =============================================================================

@app.get("/health")
async def health():
    """Verifica o status do servidor."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "upload_dir": str(config.app.upload_dir),
        "processed_dir": str(config.app.processed_dir),
    }


# =============================================================================
# Endpoints - Upload
# =============================================================================

@app.post("/upload")
async def upload_audio(file: UploadFile) -> dict[str, Any]:
    """
    Recebe um áudio e retorna o caminho onde foi salvo.
    
    O áudio fica disponível para processamento até ser limpo.
    """
    ext = Path(file.filename).suffix.lstrip(".").lower()
    
    if ext not in config.audio.formatos_suportados:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {ext}. Formatos: {config.audio.formatos_suportados}",
        )
    
    # Gera nome único
    import uuid
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    destino = config.app.upload_dir / unique_name
    
    # Salva
    content = await file.read()
    destino.write_bytes(content)
    
    logger.info(f"Áudio recebido: {file.filename} → {destino}")
    
    return {
        "filename": file.filename,
        "saved_as": unique_name,
        "path": str(destino),
        "size_bytes": len(content),
        "duration_estimate_ms": None,  # Pode ser calculado com pydub se necessário
    }


# =============================================================================
# Endpoints - Process (gerar boletim)
# =============================================================================

@app.post("/processar/{audio_id}")
async def processar_boletim(
    audio_id: str,
    limiar_similaridade: float = 0.65,
    janela_retrocesso: float = 25.0,
) -> dict[str, Any]:
    """
    Processa um áudio uploadado e gera o boletim editado.
    
    Removes erros de locução detectados por:
    1. Palavras-gatilho (repete, novamente, etc.)
    2. Similaridade textual entre frases adjacentes
    
    Args:
        audio_id: ID do áudio (nome do arquivo sem extensão ou UUID)
        limiar_similaridade: Limiar para detectar repetições (0.0-1.0)
        janela_retrocesso: Janela temporal de busca em segundos
    """
    # Busca o arquivo original
    caminho_original = _find_audio(audio_id)
    
    if not caminho_original:
        raise HTTPException(status_code=404, detail=f"Áudio não encontrado: {audio_id}")
    
    # Configura edição
    edicao_cfg = EdicaoConfig(
        limiar_similaridade=limiar_similaridade,
        tempo_max_retrocesso_seg=janela_retrocesso,
    )
    
    # Define saída
    saida = config.app.processed_dir / f"{audio_id}_editado.mp3"
    
    logger.info(f"Processando boletim: {caminho_original} → {saida}")
    
    try:
        resultado = editar_boletim(caminho_original, saida, edicao_cfg)
        return resultado
    except Exception as e:
        logger.error(f"Erro ao processar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/processar-json")
async def processar_boletim_json(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Processa um áudio a partir de um JSON com parâmetros.
    
    Body esperado:
    {
        "audio_id": "uuid-do-áudio",
        "saida": "nome_opcional.mp3",
        "limiar_similaridade": 0.65,
        "janela_retrocesso": 25.0,
        "palavras_gatilho": ["repete", "novamente"]
    }
    """
    audio_id = payload.get("audio_id")
    if not audio_id:
        raise HTTPException(status_code=400, detail="audio_id é obrigatório")
    
    caminho_original = _find_audio(audio_id)
    if not caminho_original:
        raise HTTPException(status_code=404, detail=f"Áudio não encontrado: {audio_id}")
    
    from app.edicao_boletins import EdicaoConfig
    
    edicao_cfg = EdicaoConfig(
        limiar_similaridade=payload.get("limiar_similaridade", 0.65),
        tempo_max_retrocesso_seg=payload.get("janela_retrocesso", 25.0),
        palavras_gatilho=tuple(payload.get("palavras_gatilho", list(EdicaoConfig().palavras_gatilho))),
        gerar_log_exclusoes=payload.get("gerar_log_exclusoes", True),
    )
    
    saida = payload.get("saida")
    if saida:
        saida = config.app.processed_dir / saida
    else:
        saida = config.app.processed_dir / f"{audio_id}_editado.mp3"
    
    try:
        resultado = editar_boletim(caminho_original, saida, edicao_cfg)
        return resultado
    except Exception as e:
        logger.error(f"Erro ao processar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Endpoints - Download
# =============================================================================

@app.get("/download/{audio_id}")
async def download_audio(audio_id: str):
    """Baixa o áudio processado."""
    caminho = config.app.processed_dir / f"{audio_id}_editado.mp3"
    
    if not caminho.exists():
        # Tenta o original
        caminho_original = _find_audio(audio_id)
        if caminho_original:
            return FileResponse(caminho_original)
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    
    return FileResponse(caminho, media_type="audio/mpeg")


@app.get("/download-original/{audio_id}")
async def download_original(audio_id: str):
    """Baixa o áudio original (não editado)."""
    caminho = _find_audio(audio_id)
    
    if not caminho:
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    
    return FileResponse(caminho)


# =============================================================================
# Endpoints - Lista
# =============================================================================

@app.get("/audios")
async def listar_audios():
    """Lista todos os áudios disponíveis para processamento."""
    uploads = list(config.app.upload_dir.glob("*"))
    processed = list(config.app.processed_dir.glob("*"))
    
    return {
        "uploaded": [
            {
                "id": p.stem,
                "filename": p.name,
                "path": str(p),
                "size_bytes": p.stat().st_size,
                "modified": p.stat().st_mtime,
            }
            for p in uploads
            if p.is_file()
        ],
        "processed": [
            {
                "id": p.stem.replace("_editado", ""),
                "filename": p.name,
                "path": str(p),
                "size_bytes": p.stat().st_size,
                "modified": p.stat().st_mtime,
            }
            for p in processed
            if p.is_file()
        ],
    }


# =============================================================================
# Endpoints - Limpeza
# =============================================================================

@app.delete("/limpar/{audio_id}")
async def limpar_audio(audio_id: str):
    """Remove um áudio (original e/ou processado)."""
    import os
    
    removidos = []
    
    # Tenta remover original
    caminho_original = _find_audio(audio_id)
    if caminho_original and caminho_original.exists():
        caminho_original.unlink()
        removidos.append(str(caminho_original))
    
    # Tenta remover processado
    caminho_processado = config.app.processed_dir / f"{audio_id}_editado.mp3"
    if caminho_processado.exists():
        caminho_processado.unlink()
        removidos.append(str(caminho_processado))
    
    if not removidos:
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    
    logger.info(f"Áudio removido: {audio_id}")
    return {"removed": removidos}


# =============================================================================
# WebSocket - Progresso em tempo real
# =============================================================================

@app.websocket("/ws/{audio_id}")
async def websocket_progresso(websocket: WebSocket, audio_id: str):
    """WebSocket para transmitir progresso do processamento em tempo real."""
    await websocket.accept()
    
    try:
        # Em uma implementação completa, aqui seria usado um task queue
        # para processamento async com streaming de progresso
        await websocket.send_json({
            "type": "started",
            "audio_id": audio_id,
            "message": "Processamento iniciado",
        })
        
        # Simula progresso (na versão real, integra com o processo de edição)
        await websocket.send_json({
            "type": "progress",
            "stage": "transcricao",
            "message": "Transcrevendo áudio com Whisper...",
            "progress": 0.25,
        })
        
        await websocket.send_json({
            "type": "progress",
            "stage": "analise",
            "message": "Analisando repetições e erros...",
            "progress": 0.50,
        })
        
        await websocket.send_json({
            "type": "progress",
            "stage": "edicao",
            "message": "Aplicando cortes ao áudio...",
            "progress": 0.75,
        })
        
        await websocket.send_json({
            "type": "completed",
            "audio_id": audio_id,
            "message": "Processamento concluído",
            "progress": 1.0,
        })
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket desconectado para {audio_id}")
    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except Exception:
            pass


# =============================================================================
# Helpers
# =============================================================================

def _find_audio(audio_id: str) -> Path | None:
    """Busca um áudio pelo ID nos diretórios conhecidos."""
    # Tenta ID exato
    for dir_path in [config.app.upload_dir, config.app.processed_dir]:
        for p in dir_path.glob(f"{audio_id}*"):
            if p.is_file():
                return p
    
    # Tenta por UUID parcial
    for p in config.app.upload_dir.glob("*"):
        if p.stem.startswith(audio_id[:8]) and p.is_file():
            return p
    
    return None


# =============================================================================
# Run
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Iniciando servidor na porta {config.app.port}...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=config.app.port,
        reload=True,
    )
