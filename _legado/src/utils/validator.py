"""
Validador de integridade de arquivos de áudio
Implementa checksum MD5, validação de tamanho e duração
"""
import hashlib
import os
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

try:
    import mutagen
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


@dataclass
class ValidationResult:
    """Resultado da validação de um arquivo."""
    file_path: str
    is_valid: bool
    checksum: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None
    errors: list = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def calculate_checksum(file_path: str, algorithm: str = 'md5') -> Optional[str]:
    """
    Calcula checksum de um arquivo.
    
    Args:
        file_path: Caminho do arquivo
        algorithm: Algoritmo de hash (md5, sha256)
    
    Returns:
        Hash hexadecimal ou None se falhar
    """
    try:
        if algorithm == 'md5':
            hasher = hashlib.md5()
        elif algorithm == 'sha256':
            hasher = hashlib.sha256()
        else:
            raise ValueError(f"Algoritmo não suportado: {algorithm}")
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    except Exception as e:
        print(f"Erro ao calcular checksum de {file_path}: {e}")
        return None


def get_file_size(file_path: str) -> Optional[int]:
    """Retorna tamanho do arquivo em bytes."""
    try:
        return os.path.getsize(file_path)
    except Exception as e:
        print(f"Erro ao obter tamanho de {file_path}: {e}")
        return None


def get_audio_duration(file_path: str) -> Optional[float]:
    """
    Obtém duração de arquivo de áudio usando mutagen.
    
    Args:
        file_path: Caminho do arquivo de áudio
    
    Returns:
        Duração em segundos ou None se falhar
    """
    if not MUTAGEN_AVAILABLE:
        print("mutagen não disponível - instalando: pip install mutagen")
        return None
    
    try:
        audio = MP3(file_path)
        return audio.info.length
    except Exception as e:
        print(f"Erro ao obter duração de {file_path}: {e}")
        return None


def validate_audio_file(
    file_path: str,
    min_size: int = 102400,  # 100KB
    min_duration: float = 2.0,  # segundos
    check_checksum: bool = True
) -> ValidationResult:
    """
    Valida integridade completa de um arquivo de áudio.
    
    Args:
        file_path: Caminho do arquivo
        min_size: Tamanho mínimo em bytes
        min_duration: Duração mínima em segundos
        check_checksum: Se deve calcular checksum
    
    Returns:
        ValidationResult com status e detalhes
    """
    result = ValidationResult(file_path=file_path, is_valid=True)
    
    # Verifica se arquivo existe
    if not Path(file_path).exists():
        result.is_valid = False
        result.errors.append(f"Arquivo não existe: {file_path}")
        return result
    
    # Valida tamanho
    file_size = get_file_size(file_path)
    result.file_size = file_size
    
    if file_size is None:
        result.is_valid = False
        result.errors.append("Não foi possível obter tamanho do arquivo")
    elif file_size < min_size:
        result.is_valid = False
        result.errors.append(f"Tamanho ({file_size} bytes) abaixo do mínimo ({min_size} bytes)")
    
    # Valida duração
    duration = get_audio_duration(file_path)
    result.duration = duration
    
    if duration is None:
        result.errors.append("Não foi possível obter duração do áudio")
    elif duration < min_duration:
        result.is_valid = False
        result.errors.append(f"Duração ({duration:.2f}s) abaixo do mínimo ({min_duration}s)")
    
    # Calcula checksum se solicitado
    if check_checksum:
        result.checksum = calculate_checksum(file_path)
        if result.checksum is None:
            result.errors.append("Falha ao calcular checksum")
    
    return result


def validate_directory(
    directory: str,
    pattern: str = "*.mp3",
    min_size: int = 102400,
    min_duration: float = 2.0
) -> Tuple[list, list]:
    """
    Valida todos os arquivos de áudio em um diretório.
    
    Args:
        directory: Diretório a validar
        pattern: Padrão de arquivos (ex: *.mp3)
        min_size: Tamanho mínimo em bytes
        min_duration: Duração mínima em segundos
    
    Returns:
        Tupla (arquivos_válidos, arquivos_inválidos)
    """
    valid_files = []
    invalid_files = []
    
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"Diretório não existe: {directory}")
        return valid_files, invalid_files
    
    for file_path in dir_path.glob(pattern):
        result = validate_audio_file(
            str(file_path),
            min_size=min_size,
            min_duration=min_duration
        )
        
        if result.is_valid:
            valid_files.append(result)
        else:
            invalid_files.append(result)
    
    return valid_files, invalid_files
