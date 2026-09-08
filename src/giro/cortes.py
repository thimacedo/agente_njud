"""
Módulo de corte específico para o programa GIRO.

Diferença principal do NJUD:
- Não usa vinheta de passagem como marcador
- Detecta silêncio de 1 segundo para separar CABEÇA e CORPO
"""

import logging
from pathlib import Path
from typing import Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)


def encontrar_silencio(
    audio: np.ndarray,
    sample_rate: int,
    duracao_minima: float = 1.0,
    tolerancia: float = 0.2,
    inicio_busca: float = 2.0
) -> Optional[float]:
    """
    Encontra o primeiro silêncio de duração mínima após o ponto de início.
    
    Args:
        audio: Array de áudio (mono ou stereo)
        sample_rate: Taxa de amostragem em Hz
        duracao_minima: Duração mínima do silêncio em segundos (padrão: 1.0s)
        tolerancia: Tolerância para threshold de silêncio (padrão: 0.2)
        inicio_busca: Ponto inicial da busca em segundos (padrão: 2.0s)
    
    Returns:
        Posição do silêncio encontrado em segundos, ou None se não encontrado
    """
    # Converter para mono se necessário
    if len(audio.shape) > 1:
        audio_mono = np.mean(audio, axis=1)
    else:
        audio_mono = audio
    
    # Calcular threshold baseado na energia do sinal
    energia_total = np.max(np.abs(audio_mono))
    threshold = energia_total * tolerancia
    
    # Identificar regiões silenciosas
    silencio_mask = np.abs(audio_mono) < threshold
    
    # Converter durações para samples
    samples_inicio = int(inicio_busca * sample_rate)
    samples_duracao = int(duracao_minima * sample_rate)
    
    # Buscar sequência contínua de silêncio
    contador_silencio = 0
    for i in range(samples_inicio, len(silencio_mask)):
        if silencio_mask[i]:
            contador_silencio += 1
            if contador_silencio >= samples_duracao:
                # Silêncio encontrado
                pos_segundos = i / sample_rate
                logger.info(f"Silêncio encontrado em {pos_segundos:.2f}s")
                return pos_segundos
        else:
            contador_silencio = 0
    
    logger.warning("Nenhum silêncio adequado encontrado")
    return None


def cortar_giro_silencio(
    caminho_audio: Path,
    duracao_minima_silencio: float = 1.0,
    tolerancia: float = 0.2
) -> Tuple[Optional[Path], Optional[Path], dict]:
    """
    Corta áudio do GIRO separando CABEÇA e CORPO por detecção de silêncio.
    
    Args:
        caminho_audio: Caminho para o arquivo de áudio original
        duracao_minima_silencio: Duração mínima do silêncio em segundos
        tolerancia: Tolerância para detecção de silêncio
    
    Returns:
        Tupla (caminho_cabeca, caminho_corpo, metadados)
        - Se falhar: (None, None, {'erro': mensagem})
    """
    import soundfile as sf
    
    logger.info(f"Cortando áudio GIRO: {caminho_audio}")
    
    try:
        # Carregar áudio
        audio, sample_rate = sf.read(caminho_audio)
        duracao_total = len(audio) / sample_rate
        
        logger.info(f"Duração total: {duracao_total:.2f}s")
        
        # Encontrar silêncio
        pos_silencio = encontrar_silencio(
            audio=audio,
            sample_rate=sample_rate,
            duracao_minima=duracao_minima_silencio,
            tolerancia=tolerancia,
            inicio_busca=2.0  # Começa busca após 2s
        )
        
        if pos_silencio is None:
            erro_msg = "Não foi possível detectar silêncio para separação CABEÇA/CORPO"
            logger.error(erro_msg)
            return None, None, {'erro': erro_msg}
        
        # Calcular pontos de corte em samples
        ponto_corte = int(pos_silencio * sample_rate)
        
        # Extrair CABEÇA e CORPO
        cabeca = audio[:ponto_corte]
        corpo = audio[ponto_corte:]
        
        # Validar durações mínimas
        duracao_cabeca = len(cabeca) / sample_rate
        duracao_corpo = len(corpo) / sample_rate
        
        logger.info(f"CABEÇA: {duracao_cabeca:.2f}s | CORPO: {duracao_corpo:.2f}s")
        
        if duracao_cabeca < 2.0:
            erro_msg = f"CABEÇA muito curta: {duracao_cabeca:.2f}s (mínimo: 2.0s)"
            logger.error(erro_msg)
            return None, None, {'erro': erro_msg}
        
        if duracao_corpo < 5.0:
            erro_msg = f"CORPO muito curto: {duracao_corpo:.2f}s (mínimo: 5.0s)"
            logger.error(erro_msg)
            return None, None, {'erro': erro_msg}
        
        # Salvar stems
        diretorio_saida = caminho_audio.parent
        stem_cabeca = diretorio_saida / f"{caminho_audio.stem}_CABECA.wav"
        stem_corpo = diretorio_saida / f"{caminho_audio.stem}_CORPO.wav"
        
        sf.write(stem_cabeca, cabeca, sample_rate)
        sf.write(stem_corpo, corpo, sample_rate)
        
        metadados = {
            'sucesso': True,
            'posicao_silencio': pos_silencio,
            'duracao_cabeca': duracao_cabeca,
            'duracao_corpo': duracao_corpo,
            'stem_cabeca': str(stem_cabeca),
            'stem_corpo': str(stem_corpo)
        }
        
        logger.info(f"Corte concluído: {stem_cabeca}, {stem_corpo}")
        return stem_cabeca, stem_corpo, metadados
        
    except Exception as e:
        erro_msg = f"Erro ao cortar áudio: {str(e)}"
        logger.exception(erro_msg)
        return None, None, {'erro': erro_msg}


if __name__ == "__main__":
    # Teste rápido
    import sys
    if len(sys.argv) > 1:
        caminho = Path(sys.argv[1])
        cabeca, corpo, meta = cortar_giro_silencio(caminho)
        print(f"Resultado: {meta}")
