"""
Configuração central do Gravador Inteligente.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    """Configurações gerais da aplicação."""
    
    # Diretório base do projeto
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    
    # Diretório para uploads de áudio
    upload_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "uploads")
    
    # Diretório para áudios processados
    processed_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "processed")
    
    # Diretório para EDLs persistentes
    edl_dir: Path = field(default=lambda: Path(__file__).parent.parent / "edls")
    
    # URL do frontend (para WebSocket)
    frontend_url: str = "http://localhost:3000"
    
    # Porta do servidor
    port: int = 8000
    
    # Habilitar CORS
    cors_enabled: bool = True


@dataclass
class AudioConfig:
    """Configurações de processamento de áudio."""
    
    # Formato de áudio suportado
    formatos_suportados: tuple[str, ...] = ("mp3", "wav", "m4a", "ogg", "flac")
    
    # Frequência de amostragem padrão para exportação
    sample_rate: int = 44100
    
    # Canais de áudio
    channels: int = 2
    
    # Codec de exportação
    codec: str = "libmp3lame"
    
    # Bitrate de exportação (kbps)
    bitrate: str = "192k"
    
    # Crossfade duration in ms for EDL rendering
    crossfade_ms: int = 500


@dataclass
class WhisperConfig:
    """Configurações de transcrição Whisper."""
    
    # Modelo a usar (tiny, base, small, medium, large)
    modelo: str = "base"
    
    # Idioma padrão
    idioma: str = "pt"
    
    # Forçar idioma (None para auto-detect)
    force_lang: Optional[str] = None
    
    # Nível de detalhe da transcrição (verbose, json, etc.)
    task: str = "transcribe"
    
    # Habilitar tradução para inglês (se idioma != en)
    translate: bool = False


@dataclass
class EdicaoConfig:
    """Configurações do módulo de edição de boletins."""
    
    # Limiar de similaridade para detectar repetições (0.0 - 1.0)
    limiar_similaridade: float = 0.65
    
    # Janela máxima de retrocesso em segundos para comparação
    tempo_max_retrocesso_seg: float = 25.0
    
    # Palavras-gatilho que indicam correção/repetição
    palavras_gatilho: tuple[str, ...] = (
        "repete",
        "novamente",
        "de novo",
        "volta",
        "refaça",
        "outra vez",
    )
    
    # Tempo padrão para retrocesso quando detecta gatilho (ms)
    tempo_retrocesso_padrao_ms: int = 8000
    
    # Tempo mínimo de pausa para considerar corte limpo (ms)
    pausa_minima_para_corte_ms: int = 1000
    
    # Gerar log detalhado das exclusões
    gerar_log_exclusoes: bool = True


@dataclass
class Config:
    """Configuração única do sistema."""
    
    app: AppConfig = field(default_factory=AppConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    edicao: EdicaoConfig = field(default_factory=EdicaoConfig)
    
    # Versão do schema de EDL
    edl_schema_version: str = "1.0"
    
    # Chave secreta para sessões (se necessário)
    secret_key: str = "change-me-in-production"


# Instância global
config = Config()


def initialize_directories():
    """Cria os diretórios necessários se não existirem."""
    for dir_path in [
        config.app.upload_dir,
        config.app.processed_dir,
        config.app.edl_dir,
        config.app.base_dir / "logs_edicao",
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)


# Inicializa na importação
initialize_directories()
