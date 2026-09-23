#!/usr/bin/env python3
"""
calibracao_audio.py — AgenteCalibracaoAudio para análise e calibração de áudio.

Analisa automaticamente o áudio de entrada e ajusta parâmetros:
  - Detecção de canal morto
  - Medição de loudness (LUFS)
  - Detecção de clipping
  - Sugestão de normalização

Uso:
    from shared.agentes.calibracao_audio import AgenteCalibracaoAudio

    agente = AgenteCalibracaoAudio(target_lufs=-16.0)
    resultado = agente.calibrar("caminho/audio.wav")
    print(resultado["nivel"])  # OK / ALERTA / CRITICO
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

from shared.logging_config import get_logger

logger = get_logger("calibracao_audio")


# ═════════════════════════════════════════════════════════════════════════════
# Constantes
# ═════════════════════════════════════════════════════════════════════════════

LIMIAR_CANAL_MORTO_DB = -60.0  # dBFS — abaixo disso, canal considerado morto
LIMIAR_CLIPPING_DB = -0.5      # dBFS — picos acima disso são clipping
TARGET_LUFS_PADRAO = -16.0     # Target padrão para normalização (broadcast)
TOLERANCIA_LUFS = 1.5          # Tolerância em LUFS para considerar "no target"


# ═════════════════════════════════════════════════════════════════════════════
# Funções auxiliares standalone
# ═════════════════════════════════════════════════════════════════════════════

def _db_to_amplitude(db: float, max_amplitude: float = 1.0) -> float:
    """Converte dBFS para amplitude linear (0.0 a max_amplitude)."""
    return max_amplitude * (10.0 ** (db / 20.0))


def _rms_to_dbfs(rms: float, max_amplitude: float = 32768.0) -> float:
    """Converte RMS para dBFS (referência: int16)."""
    if rms <= 0.0:
        return -math.inf
    return 20.0 * math.log10(rms / max_amplitude)


def detectar_canal_morto(audio: AudioSegment, limiar_db: float = LIMIAR_CANAL_MORTO_DB) -> dict[str, Any]:
    """
    Identifica se um canal tem amplitude próxima de 0 (canal morto).

    Para áudios stereo, analisa cada canal separadamente.

    Args:
        audio: Objeto AudioSegment do pydub.
        limiar_db: Limiar em dBFS abaixo do qual o canal é considerado morto.

    Returns:
        dict com:
            - canais_mortos: lista de índices de canais mortos (0=mono/esquerdo, 1=direito)
            - canais_ativos: lista de índices de canais ativos
            - rms_por_canal: dict {indico: rms_dbfs}
            - nivel: "OK" | "ALERTA" | "CRITICO"
            - mensagens: lista de strings descritivas
    """
    mensagens = []
    num_canais = audio.channels
    rms_por_canal: dict[int, float] = {}
    canais_mortos: list[int] = []
    canais_ativos: list[int] = []

    # P RMS global como fallback
    rms_global = audio.rms

    for ch in range(num_canais):
        canal = audio.split_to_mono()[ch]
        rms_ch = canal.rms
        max_amp = audio.sample_width * 8  # bits por sample
        max_val = 2 ** (max_amp - 1)  # valor máximo (ex: 32768 para 16-bit)

        if rms_ch <= 0:
            rms_db = -math.inf
        else:
            rms_db = 20.0 * math.log10(rms_ch / max_val)

        rms_por_canal[ch] = round(rms_db, 2)

        if rms_db <= limiar_db:
            canais_mortos.append(ch)
            nome_canal = _nome_canal(ch, num_canais)
            mensagens.append(
                f"Canal {nome_canal} morto: RMS={rms_db:.1f} dBFS (limiar: {limiar_db} dBFS)"
            )
        else:
            canais_ativos.append(ch)

    # Determinar nível
    if len(canais_mortos) == num_canais:
        nivel = "CRITICO"
        mensagens.insert(0, "Todos os canais estão mortos!")
    elif len(canais_mortos) > 0:
        nivel = "ALERTA"
        mensagens.insert(0, f"{len(canais_mortos)} canal(is) morto(s) detectado(s)")
    else:
        nivel = "OK"
        mensagens.append("Todos os canais ativos.")

    return {
        "canais_mortos": canais_mortos,
        "canais_ativos": canais_ativos,
        "rms_por_canal": rms_por_canal,
        "nivel": nivel,
        "mensagens": mensagens,
    }


def calcular_loudness(audio: AudioSegment) -> dict[str, Any]:
    """
    Mede o LUFS integrado do áudio.

    Usa a aproximação RMS + offset do pydub (pydub não tem LUFS nativo,
    mas usamos RMS calibrado como proxy padrão da indústria para conteúdo
    de fala/broadcast).

    Args:
        audio: Objeto AudioSegment do pydub.

    Returns:
        dict com:
            - lufs: valor estimado de LUFS integrado
            - rms_dbfs: RMS em dBFS
            - pico_dbfs: nível de pico em dBFS
            - duracao_seg: duração em segundos
            - nivel: "OK" | "ALERTA" | "CRITICO"
            - mensagens: lista de strings descritivas
    """
    mensagens = []

    # RMS em dBFS
    max_val = 2 ** (audio.sample_width * 8 - 1)
    rms = audio.rms
    rms_dbfs = 20.0 * math.log10(rms / max_val) if rms > 0 else -math.inf

    # Pico em dBFS
    pico = audio.max
    pico_dbfs = 20.0 * math.log10(pico / max_val) if pico > 0 else -math.inf

    # Estimativa LUFS: RMS + offset de correção para fala/broadcast
    # Offset típico: +3 dB (RMS sub-estima loudness percebida em ~3dB para fala)
    lufs_estimado = rms_dbfs + 3.0

    duracao_seg = len(audio) / 1000.0

    # Avaliação qualitativa
    if lufs_estimado < -23.0:
        nivel = "ALERTA"
        mensagens.append(f"Áudio muito silencioso: {lufs_estimado:.1f} LUFS (abaixo de -23)")
    elif lufs_estimado > -10.0:
        nivel = "ALERTA"
        mensagens.append(f"Áudio muito alto: {lufs_estimado:.1f} LUFS (acima de -10)")
    else:
        nivel = "OK"
        mensagens.append(f"Loudness dentro do range aceitável: {lufs_estimado:.1f} LUFS")

    return {
        "lufs": round(lufs_estimado, 2),
        "rms_dbfs": round(rms_dbfs, 2),
        "pico_dbfs": round(pico_dbfs, 2),
        "duracao_seg": round(duracao_seg, 3),
        "nivel": nivel,
        "mensagens": mensagens,
    }


def detectar_clipping(audio: AudioSegment, limiar_db: float = LIMIAR_CLIPPING_DB) -> dict[str, Any]:
    """
    Detecta picos próximos a 0dBFS (clipping/distorção).

    Analisa amostras individuais para encontrar picos que atingem ou
    se aproximam do nível máximo digital.

    Args:
        audio: Objeto AudioSegment do pydub.
        limiar_db: Limiar em dBFS acima do qual é considerado clipping.

    Returns:
        dict com:
            - clipping_detectado: bool
            - pico_dbfs: nível de pico em dBFS
            - percentual_amostras_clipping: % de amostras no limiar
            - nivel: "OK" | "ALERTA" | "CRITICO"
            - mensagens: lista de strings descritivas
    """
    mensagens = []
    max_val = 2 ** (audio.sample_width * 8 - 1)

    # Nível de pico
    pico = audio.max
    pico_dbfs = 20.0 * math.log10(pico / max_val) if pico > 0 else -math.inf

    # Contar amostras próximas ao clipping (acima do limiar)
    limiar_linear = max_val * (10.0 ** (limiar_db / 20.0))

    # Para performance, analisar em chunks se áudio muito longo
    total_amostras_clipping = 0
    total_amostras = 0

    # Converter para array de amostras (mono para simplificar)
    samples = audio.split_to_mono()[0].get_array_of_samples()

    for i in range(0, len(samples), 100):  # amostragem a cada 100 amostras
        chunk = samples[i:i + 100]
        for s in chunk:
            total_amostras += 1
            if abs(s) >= limiar_linear:
                total_amostras_clipping += 1

    if total_amostras > 0:
        perc_clipping = (total_amostras_clipping / total_amostras) * 100.0
    else:
        perc_clipping = 0.0

    clipping_detectado = pico_dbfs >= limiar_db or perc_clipping > 0.1

    # Determinar nível
    if pico_dbfs >= -0.1 or perc_clipping > 5.0:
        nivel = "CRITICO"
        mensagens.append(
            f"Clipping severo: pico={pico_dbfs:.2f} dBFS, "
            f"{perc_clipping:.2f}% das amostras distorcidas"
        )
    elif clipping_detectado:
        nivel = "ALERTA"
        mensagens.append(
            f"Clipping leve: pico={pico_dbfs:.2f} dBFS, "
            f"{perc_clipping:.2f}% das amostras no limiar"
        )
    else:
        nivel = "OK"
        mensagens.append(f"Sem clipping detectado. Pico: {pico_dbfs:.2f} dBFS")

    return {
        "clipping_detectado": clipping_detectado,
        "pico_dbfs": round(pico_dbfs, 2),
        "percentual_amostras_clipping": round(perc_clipping, 4),
        "nivel": nivel,
        "mensagens": mensagens,
    }


def sugerir_normalizacao(
    audio: AudioSegment,
    target_lufs: float = TARGET_LUFS_PADRAO,
    tolerancia: float = TOLERANCIA_LUFS,
) -> dict[str, Any]:
    """
    Sugere ganho para atingir target LUFS.

    Calcula o ganho necessário para levar o áudio ao nível desejado,
    respeitando limites de headroom para evitar clipping.

    Args:
        audio: Objeto AudioSegment do pydub.
        target_lufs: LUFS alvo desejado.
        tolerancia: Tolerância em LUFS para considerar "já no target".

    Returns:
        dict com:
            - ganho_db: ganho sugerido em dB (negativo = reduzir, positivo = aumentar)
            - lufs_atual: loudness atual estimada
            - lufs_alvo: target desejado
            - headroom_db: espaço disponível antes de clipping
            - seguro: bool — se a normalização é segura (não causará clipping)
            - nivel: "OK" | "ALERTA" | "CRITICO"
            - mensagens: lista de strings descritivas
    """
    mensagens = []

    # Calcular loudness atual
    max_val = 2 ** (audio.sample_width * 8 - 1)
    rms = audio.rms
    rms_dbfs = 20.0 * math.log10(rms / max_val) if rms > 0 else -math.inf
    lufs_atual = rms_dbfs + 3.0

    # Pico atual
    pico = audio.max
    pico_dbfs = 20.0 * math.log10(pico / max_val) if pico > 0 else -math.inf

    # Headroom: quanto falta para 0dBFS
    headroom_db = abs(pico_dbfs) if pico_dbfs != -math.inf else 0.0

    # Ganho necessário
    ganho_necessario = target_lufs - lufs_atual

    # Verificar se a normalização é segura
    pico_apos_normalizacao = pico_dbfs + ganho_necessario
    seguro = pico_apos_normalizacao < -0.5  # deixa 0.5dB de margem

    # Se não for seguro, limitar o ganho
    if not seguro:
        ganho_limitado = -0.5 - pico_dbfs
        mensagens.append(
            f"Ganho limitado de {ganho_necessario:.1f}dB para {ganho_limitado:.1f}dB "
            f"para evitar clipping"
        )
        ganho_necessario = ganho_limitado

    # Determinar nível
    if abs(lufs_atual - target_lufs) <= tolerancia:
        nivel = "OK"
        mensagens.append(
            f"Áudio já está no target ({lufs_atual:.1f} LUFS ≈ {target_lufs} LUFS)"
        )
    elif seguro:
        nivel = "OK"
        mensagens.append(
            f"Aplicar ganho de {ganho_necessario:+.1f}dB para atingir {target_lufs} LUFS"
        )
    else:
        nivel = "ALERTA"
        mensagens.append(
            f"Normalização parcial possível: ganho limitado a {ganho_necessario:+.1f}dB"
        )

    return {
        "ganho_db": round(ganho_necessario, 2),
        "lufs_atual": round(lufs_atual, 2),
        "lufs_alvo": target_lufs,
        "headroom_db": round(headroom_db, 2),
        "seguro": seguro,
        "nivel": nivel,
        "mensagens": mensagens,
    }


def _nome_canal(indice: int, total: int) -> str:
    """Retorna nome legível do canal."""
    if total == 1:
        return "mono"
    elif total == 2:
        return "esquerdo" if indice == 0 else "direito"
    else:
        return f"canal_{indice + 1}"


# ═════════════════════════════════════════════════════════════════════════════
# Classe principal: AgenteCalibracaoAudio
# ═════════════════════════════════════════════════════════════════════════════

class AgenteCalibracaoAudio:
    """
    Agente de calibração de áudio do pipeline DIVISOR.

    Executa todas as verificações de qualidade no áudio de entrada
    e retorna um diagnóstico completo com sugestões de normalização.
    """

    def __init__(
        self,
        target_lufs: float = TARGET_LUFS_PADRAO,
        limiar_canal_morto_db: float = LIMIAR_CANAL_MORTO_DB,
        limiar_clipping_db: float = LIMIAR_CLIPPING_DB,
        tolerancia_lufs: float = TOLERANCIA_LUFS,
    ):
        self.target_lufs = target_lufs
        self.limiar_canal_morto_db = limiar_canal_morto_db
        self.limiar_clipping_db = limiar_clipping_db
        self.tolerancia_lufs = tolerancia_lufs
        self.logger = get_logger("calibracao_audio.agent")

    def calibrar(self, audio_path: str | Path) -> dict[str, Any]:
        """
        Executa todas as verificações e retorna dict com resultados.

        Args:
            audio_path: Caminho para o arquivo de áudio.

        Returns:
            dict com:
                - nivel: "OK" | "ALERTA" | "CRITICO" (pior nível entre as verificações)
                - audio_path: caminho do arquivo analisado
                - formato: formato detectado (wav, mp3, etc.)
                - duracao_seg: duração em segundos
                - canais: número de canais
                - sample_rate: taxa de amostragem
                - bit_depth: profundidade de bits
                - resultado_canal_morto: dict de detectar_canal_morto
                - resultado_loudness: dict de calcular_loudness
                - resultado_clipping: dict de detectar_clipping
                - resultado_normalizacao: dict de sugerir_normalizacao
                - mensagens: lista consolidada de mensagens
                - valores_numericos: dict com todos os valores numéricos relevantes
        """
        audio_path = Path(audio_path)
        self.logger.info(f"Calibrando áudio: {audio_path}")

        # Carregar áudio
        try:
            audio = AudioSegment.from_file(str(audio_path))
        except CouldntDecodeError as e:
            self.logger.error(f"Falha ao decodificar áudio: {e}")
            return self._resultado_erro(str(audio_path), f"Erro ao carregar áudio: {e}")
        except FileNotFoundError:
            self.logger.error(f"Arquivo não encontrado: {audio_path}")
            return self._resultado_erro(str(audio_path), f"Arquivo não encontrado: {audio_path}")

        # Executar verificações
        resultado_canal_morto = detectar_canal_morto(audio, self.limiar_canal_morto_db)
        resultado_loudness = calcular_loudness(audio)
        resultado_clipping = detectar_clipping(audio, self.limiar_clipping_db)
        resultado_normalizacao = sugerir_normalizacao(audio, self.target_lufs, self.tolerancia_lufs)

        # Consolidar nível (pior caso)
        niveis = [
            resultado_canal_morto["nivel"],
            resultado_loudness["nivel"],
            resultado_clipping["nivel"],
            resultado_normalizacao["nivel"],
        ]
        nivel_final = self._pior_nivel(niveis)

        # Consolidar mensagens
        mensagens = []
        mensagens.extend(resultado_canal_morto["mensagens"])
        mensagens.extend(resultado_loudness["mensagens"])
        mensagens.extend(resultado_clipping["mensagens"])
        mensagens.extend(resultado_normalizacao["mensagens"])

        # Valores numéricos consolidados
        valores_numericos = {
            "rms_dbfs": resultado_loudness["rms_dbfs"],
            "lufs_estimado": resultado_loudness["lufs"],
            "pico_dbfs": resultado_clipping["pico_dbfs"],
            "percentual_clipping": resultado_clipping["percentual_amostras_clipping"],
            "ganho_sugerido_db": resultado_normalizacao["ganho_db"],
            "headroom_db": resultado_normalizacao["headroom_db"],
            "canais_mortos_count": len(resultado_canal_morto["canais_mortos"]),
        }

        resultado = {
            "nivel": nivel_final,
            "audio_path": str(audio_path),
            "formato": audio_path.suffix.lstrip(".").lower(),
            "duracao_seg": resultado_loudness["duracao_seg"],
            "canais": audio.channels,
            "sample_rate": audio.frame_rate,
            "bit_depth": audio.sample_width * 8,
            "resultado_canal_morto": resultado_canal_morto,
            "resultado_loudness": resultado_loudness,
            "resultado_clipping": resultado_clipping,
            "resultado_normalizacao": resultado_normalizacao,
            "mensagens": mensagens,
            "valores_numericos": valores_numericos,
        }

        self.logger.info(
            f"Calibração concluída: nivel={nivel_final}, "
            f"lufs={valores_numericos['lufs_estimado']}, "
            f"clipping={valores_numericos['percentual_clipping']}%"
        )

        return resultado

    @staticmethod
    def _pior_nivel(niveis: list[str]) -> str:
        """Retorna o pior nível entre OK < ALERTA < CRITICO."""
        if "CRITICO" in niveis:
            return "CRITICO"
        elif "ALERTA" in niveis:
            return "ALERTA"
        return "OK"

    @staticmethod
    def _resultado_erro(audio_path: str, erro: str) -> dict[str, Any]:
        """Retorna resultado padrão para casos de erro."""
        return {
            "nivel": "CRITICO",
            "audio_path": audio_path,
            "formato": "",
            "duracao_seg": 0.0,
            "canais": 0,
            "sample_rate": 0,
            "bit_depth": 0,
            "resultado_canal_morto": {},
            "resultado_loudness": {},
            "resultado_clipping": {},
            "resultado_normalizacao": {},
            "mensagens": [erro],
            "valores_numericos": {},
        }
