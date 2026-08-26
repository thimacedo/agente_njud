"""
Configurações centralizadas para o pipeline DIVISOR
Gerencia parâmetros via arquivo .env ou valores padrão
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


class Settings:
    """
    Gerenciador central de configurações do pipeline.
    Carrega variáveis de ambiente do arquivo .env ou usa padrões.
    """
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Inicializa configurações carregando arquivo .env.
        
        Args:
            env_file: Caminho para arquivo .env (padrão: .env na raiz)
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        # Caminhos padrão
        self.BOLETINS_BRUTOS = os.getenv(
            'BOLETINS_BRUTOS',
            './boletins_brutos'
        )
        self.BOLETINS_CORTADOS = os.getenv(
            'BOLETINS_CORTADOS',
            './boletins_cortados'
        )
        self.JORNAIS_MONTADOS = os.getenv(
            'JORNAIS_MONTADOS',
            './jornais_montados'
        )
        self.DRIVE_SYNC = os.getenv(
            'DRIVE_SYNC',
            './drive_sync'
        )
        self.LOGS_DIR = os.getenv(
            'LOGS_DIR',
            './logs'
        )
        
        # Parâmetros de qualidade de áudio
        self.DURACAO_MINIMA_BOLETIM = float(os.getenv('DURACAO_MINIMA_BOLETIM', '2.0'))
        self.DURACAO_MINIMA_JORNAL = float(os.getenv('DURACAO_MINIMA_JORNAL', '60.0'))
        self.TAMANHO_MINIMO_ARQUIVO = int(os.getenv('TAMANHO_MINIMO_ARQUIVO', '102400'))  # 100KB
        self.LIMIAR_SILENCIO = float(os.getenv('LIMIAR_SILENCIO', '-50.0'))  # dB
        
        # Parâmetros de retry
        self.MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
        self.RETRY_DELAY = float(os.getenv('RETRY_DELAY', '1.0'))  # segundos
        self.RETRY_BACKOFF = float(os.getenv('RETRY_BACKOFF', '2.0'))  # multiplicador
        
        # Configurações de NJUD
        self.BOLETINS_POR_JORNAL = int(os.getenv('BOLETINS_POR_JORNAL', '4'))
        self.INTERCALAR_VOCES = os.getenv('INTERCALAR_VOCES', 'true').lower() == 'true'
        self.BLOCO_INTERCALACAO = int(os.getenv('BLOCO_INTERCALACAO', '5'))
        
        # Metadados
        self.VERSAO_PIPELINE = os.getenv('VERSAO_PIPELINE', '1.0.0')
        self.PROJETO_NOME = os.getenv('PROJETO_NOME', 'DIVISOR')
        
    def validate_paths(self) -> bool:
        """
        Valida se todos os caminhos de diretório existem ou podem ser criados.
        
        Returns:
            True se todos os caminhos são válidos, False caso contrário
        """
        paths = [
            self.BOLETINS_BRUTOS,
            self.BOLETINS_CORTADOS,
            self.JORNAIS_MONTADOS,
            self.DRIVE_SYNC,
            self.LOGS_DIR
        ]
        
        for path in paths:
            try:
                Path(path).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Erro ao criar diretório {path}: {e}")
                return False
        
        return True
    
    def to_dict(self) -> dict:
        """Retorna configurações como dicionário."""
        return {
            'BOLETINS_BRUTOS': self.BOLETINS_BRUTOS,
            'BOLETINS_CORTADOS': self.BOLETINS_CORTADOS,
            'JORNAIS_MONTADOS': self.JORNAIS_MONTADOS,
            'DRIVE_SYNC': self.DRIVE_SYNC,
            'LOGS_DIR': self.LOGS_DIR,
            'DURACAO_MINIMA_BOLETIM': self.DURACAO_MINIMA_BOLETIM,
            'DURACAO_MINIMA_JORNAL': self.DURACAO_MINIMA_JORNAL,
            'TAMANHO_MINIMO_ARQUIVO': self.TAMANHO_MINIMO_ARQUIVO,
            'LIMIAR_SILENCIO': self.LIMIAR_SILENCIO,
            'MAX_RETRIES': self.MAX_RETRIES,
            'RETRY_DELAY': self.RETRY_DELAY,
            'RETRY_BACKOFF': self.RETRY_BACKOFF,
            'BOLETINS_POR_JORNAL': self.BOLETINS_POR_JORNAL,
            'INTERCALAR_VOCES': self.INTERCALAR_VOCES,
            'BLOCO_INTERCALACAO': self.BLOCO_INTERCALACAO,
            'VERSAO_PIPELINE': self.VERSAO_PIPELINE,
            'PROJETO_NOME': self.PROJETO_NOME
        }


# Instância global de configurações
settings = Settings()
