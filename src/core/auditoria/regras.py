"""
core/auditoria/regras.py

Regras de auditoria CONSOLIDADAS para o pipeline unificado.

Substitui e unifica:
  - src/audit/individual_cuts.py (analisar_par)
  - src/scripts_pipeline/auditoria.py
  - src/scripts_pipeline/auditoria_v2.py
  - src/scripts_pipeline/etapa3_auditoria_final.py

Todas as regras recebem apenas os dados necessários e retornam
(status: bool, motivo: Optional[str]).

Regra obrigatória: RegraSemFallbackParaAudioCompleto — detecta se o
corte não aconteceu de verdade (áudio bruto sendo usado no lugar do
corte). Esta regra é a lição do incidente do Giro (2026-09-07) e do
etapa3b_re_montagem_completa.py. Não pode ser desativada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, Callable, Any
from pathlib import Path

import subprocess
import json

# --- Tipos ---

@dataclass
class Auditavel:
    """
    Dados necessários para auditoria de um par CABEÇA/CORPO.
    Instanciado a partir dos resultados do processo de corte.
    """
    arquivo_original: str  # Caminho do boletim original (para RegraSemFallback)
    cabeca: str  # Caminho do arquivo CABEÇA
    corpo: str   # Caminho do arquivo CORPO
    duracao_cabeca: Optional[float] = None  # em segundos
    duracao_corpo: Optional[float] = None   # em segundos
    duracao_original: Optional[float] = None  # duração do boletim original

    def __post_init__(self):
        self.cabeca = str(self.cabeca)
        self.corpo = str(self.corpo)
        self.arquivo_original = str(self.arquivo_original)

@dataclass
class ResultadoAuditoria:
    """Resultado da auditoria de um par."""
    status: str  # "OK", "CORTADO", "ERRO"
    motivos: list[str] = field(default_factory=list)
    regras_falharam: list[str] = field(default_factory=list)
    detalhes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "motivos": self.motivos,
            "regras_falharam": self.regras_falharam,
            "detalhes": self.detalhes,
        }

# --- Protocolo de regra ---

class RegraAuditoria(Protocol):
    """Protocolo que toda regra de auditoria deve implementar."""
    nome: str
    def verificar(self, auditavel: Auditavel, **kwargs) -> tuple[bool, Optional[str]]:
        ...

# --- Regras ---

class RegraSemFallbackParaAudioCompleto:
    """
    REGRADE OBRIGATÓRIA — não pode ser desativada.

    Detecta se o corte não aconteceu de verdade, comparando a duração
    total dos cortes (CABECA + CORPO) com a duração do arquivo original.

    Se a proporção for > 0.95, significa que o "corte" é praticamente
    o arquivo inteiro — ou seja, o processo de corte falhou silenciosamente
    e estamos usando o áudio bruto.

    Motivação: incidente do Giro (2026-09-07) onde 101/108 notas foram
    processadas sem corte real, e o etapa3b_re_montagem_completa.py que
    substituiu cortes truncados por áudio completo sem avisar.

    Veja: DECISOES.md, seção sobre fallback para áudio completo.
    """
    nome = "sem_fallback_para_audio_completo"
    LIMIAR_PROPORCAO = 0.95

    def verificar(self, auditavel: Auditavel, **kwargs) -> tuple[bool, Optional[str]]:
        if auditavel.duracao_original is None:
            return True, None  # Não temos dado para comparar

        if auditavel.duracao_cabeca is None or auditavel.duracao_corpo is None:
            return True, None

        duracao_total_cortes = auditavel.duracao_cabeca + auditavel.duracao_corpo

        if auditavel.duracao_original <= 0:
            return True, None

        proporcao = duracao_total_cortes / auditavel.duracao_original

        if proporcao > self.LIMIAR_PROPORCAO:
            return False, (
                f"CRITICO: Proporção de corte {proporcao:.2%} excede limite {self.LIMIAR_PROPORCAO:.0%} — "
                f"áudio original ({auditavel.duracao_original:.1f}s) quase não foi cortado "
                f"(CABECA={auditavel.duracao_cabeca:.1f}s + CORPO={auditavel.duracao_corpo:.1f}s). "
                f"Ver DECISOES.md: possível fallback para áudio completo."
            )

        return True, None


class RegraDurationsValidas:
    """Verifica se as durações dos cortes são físicamente plausíveis."""

    # CABEÇA deve ter entre 2s e 120s (evita cortes vazios ou que comeram o corpo)
    MIN_DURACAO_CABECA = 2.0
    MAX_DURACAO_CABECA = 120.0

    # CORPO deve ter entre 5s e 600s
    MIN_DURACAO_CORPO = 5.0
    MAX_DURACAO_CORPO = 600.0

    # Diferença máxima entre CABEÇA e CORPO (para detectar desalinhamento)
    MAX_RAZAO_CABECA_CORPO = 10.0  # CABEÇA não pode ser 10x maior que CORPO

    nome = "duracoes_validas"

    def verificar(self, auditavel: Auditavel, **kwargs) -> tuple[bool, Optional[str]]:
        erros: list[str] = []

        if auditavel.duracao_cabeca is not None:
            if auditavel.duracao_cabeca < self.MIN_DURACAO_CABECA:
                erros.append(
                    f"CABEÇA muito curto ({auditavel.duracao_cabeca:.1f}s < {self.MIN_DURACAO_CABECA:.0f}s) — "
                    f"possível corte que comeu o início do corpo"
                )
            elif auditavel.duracao_cabeca > self.MAX_DURACAO_CABECA:
                erros.append(
                    f"CABEÇA muito longo ({auditavel.duracao_cabeca:.1f}s > {self.MAX_DURACAO_CABECA:.0f}s) — "
                    f"possível deslocamento da fronteira"
                )

        if auditavel.duracao_corpo is not None:
            if auditavel.duracao_corpo < self.MIN_DURACAO_CORPO:
                erros.append(
                    f"CORPO muito curto ({auditavel.duracao_corpo:.1f}s < {self.MIN_DURACAO_CORPO:.0f}s) — "
                    f"possível corte que comeu o final ou arquivo corrompido"
                )
            elif auditavel.duracao_corpo > self.MAX_DURACAO_CORPO:
                erros.append(
                    f"CORPO muito longo ({auditavel.duracao_corpo:.1f}s > {self.MAX_DURACAO_CORPO:.0f}s) — "
                    f"possível falha na detecção do final"
                )

        # Verifica razão CABEÇA/CORPO
        if (auditavel.duracao_cabeca and auditavel.duracao_corpo and
                auditavel.duracao_corpo > 0):
            razao = auditavel.duracao_cabeca / auditavel.duracao_corpo
            if razao > self.MAX_RAZAO_CABECA_CORPO:
                erros.append(
                    f"Razão CABEÇA/CORPO extremamente desbalanceada ({razao:.1f}x) — "
                    f"CABEÇA ({auditavel.duracao_cabeca:.1f}s) é muito maior que CORPO ({auditavel.duracao_corpo:.1f}s)"
                )

        if erros:
            return False, "; ".join(erros)
        return True, None


class RegraCabecaCorpoExistentes:
    """Verifica se os arquivos CABEÇA e CORPO realmente existem."""

    nome = "cabeca_corpo_existentes"

    def verificar(self, auditavel: Auditavel, **kwargs) -> tuple[bool, Optional[str]]:
        erros: list[str] = []

        if not Path(auditavel.cabeca).exists():
            erros.append(f"Arquivo CABEÇA não encontrado: {auditavel.cabeca}")

        if not Path(auditavel.corpo).exists():
            erros.append(f"Arquivo CORPO não encontrado: {auditavel.corpo}")

        if erros:
            return False, "; ".join(erros)
        return True, None


class RegraSemAlucinacoesWhisper:
    """
    Filtra falsos-positivos de corte causados por alucinações do Whisper
    em trechos silenciosos.
    """

    PADROES_ALUCINACAO = {
        "amara.org", "amara", "legendas pela comunidade amara.org",
        "obrigado por assistir", "se inscreva no canal", "like e se inscreva",
        "www.youtube.com", "subtitles by", "transcrito por",
        "obrigada por assistir", "gracias por ver", "subscribe",
    }

    nome = "sem_alucinacoes_whisper"

    def __init__(self):
        self._padroes = {p.lower() for p in self.PADROES_ALUCINACAO}

    def verificar(self, auditavel: Auditavel, **kwargs) -> tuple[bool, Optional[str]]:
        # Esta regra depende da transcrição — se não tivermos transcrição,
        # pulamos. O callable `transcricao_fn` pode ser passado via kwargs.
        transcricao_fn = kwargs.get("transcricao_fn")
        if transcricao_fn is None:
            return True, None  # Não podemos verificar sem transcrição

        try:
            texto_cabeca = transcricao_fn(auditavel.cabeca)
            texto_corpo = transcricao_fn(auditavel.corpo)
        except Exception:
            return True, None  # Erro na transcrição não é falso-positivo de corte

        # Verifica se as primeiras/ últimas palavras são alucinações
        palavras_cabeca_inicio = (
            texto_cabeca.strip().split()[:3] if texto_cabeca.strip() else []
        )
        palavras_cabeca_fim = (
            texto_cabeca.strip().split()[-3:] if texto_cabeca.strip() else []
        )
        palavras_corpo_inicio = (
            texto_corpo.strip().split()[:3] if texto_corpo.strip() else []
        )
        palavras_corpo_fim = (
            texto_corpo.strip().split()[-3:] if texto_corpo.strip() else []
        )

        todas_as_palavras = (
            palavras_cabeca_inicio + palavras_cabeca_fim +
            palavras_corpo_inicio + palavras_corpo_fim
        )

        alucinacoes = [
            p for p in todas_as_palavras
            if p.lower() in self._padroes
        ]

        if alucinacoes:
            return False, (
                f" possíveis alucinações do Whisper nas bordas: {', '.join(alucinacoes)} — "
                f"pode ser falso-positivo para corte"
            )

        return True, None


# --- Auditoria principal ---

class Auditor:
    """
    Executa todas as regras sobre um Auditavel e devolve ResultadoAuditoria.

    A ordem das regras é importante:
    1. Primeiro verificações básicas (arquivos existem, durações são válidas)
    2. Depois verificações de qualidade (sem fallback, sem alucinações)
    3. Se qualquer regra crítica falhar, o status é "CORTADO" ou "ERRO"
    """

    def __init__(self, regras: Optional[list[RegraAuditoria]] = None):
        if regras is None:
            self._regras = [
                RegraCabecaCorpoExistentes(),
                RegraDurationsValidas(),
                RegraSemFallbackParaAudioCompleto(),  # OBRIGATÓRIA
                RegraSemAlucinacoesWhisper(),
            ]
        else:
            self._regras = regras

    def auditar(self, auditavel: Auditavel, **kwargs) -> ResultadoAuditoria:
        """
        Executa todas as regras sobre o Auditavel.

        Returns:
            ResultadoAuditoria com status "OK", "CORTADO" ou "ERRO".
        """
        motivos: list[str] = []
        regras_falharam: list[str] = []
        detalhes: dict[str, Any] = {}

        # Mede durações se não tiver sido feito
        if auditavel.duracao_cabeca is None or auditavel.duracao_corpo is None:
            try:
                duracoes = _medir_duracoes(
                    auditavel.cabeca,
                    auditavel.corpo,
                    auditavel.arquivo_original,
                )
                auditavel.duracao_cabeca = duracoes["cabeca"]
                auditavel.duracao_corpo = duracoes["corpo"]
                auditavel.duracao_original = duracoes["original"]
                detalhes["duracoes_medidas"] = duracoes
            except Exception as e:
                detalhes["erro_medicao_duracoes"] = str(e)

        for regra in self._regras:
            try:
                ok, motivo = regra.verificar(auditavel, **kwargs)
                if not ok:
                    regras_falharam.append(regra.nome)
                    if motivo:
                        motivos.append(f"[{regra.nome}] {motivo}")
            except Exception as e:
                motivos.append(f"[{regra.nome}] ERRO NA REGRAA: {e}")

        # Determina status final
        if not motivos:
            status = "OK"
        elif any("CRITICO" in m for m in motivos):
            status = "CORTADO"
        else:
            status = "CORTADO"  # Qualquer problema de qualidade = CORTADO

        return ResultadoAuditoria(
            status=status,
            motivos=motivos,
            regras_falharam=regras_falharam,
            detalhes=detalhes,
        )


def _medir_duracoes(
    caminho_cabeca: str,
    caminho_corpo: str,
    caminho_original: str,
) -> dict[str, Optional[float]]:
    """
    Mede durações dos arquivos via ffprobe (rápido, sem carregar áudio).
    """
    def _duracao(caminho: str) -> Optional[float]:
        if not Path(caminho).exists() or not Path(caminho).stat().st_size > 0:
            return None
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(caminho)],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass
        return None

    return {
        "cabeca": _duracao(caminho_cabeca),
        "corpo": _duracao(caminho_corpo),
        "original": _duracao(caminho_original),
    }


# --- Função compatível com analisar_par existente ---

def analisar_par_consolidado(
    caminho_cabeca: str,
    caminho_corpo: str,
    modelo=None,  # mantido para compatibilidade, não usado pelas regras atuais
    caminho_fonte_original: Optional[str] = None,
) -> tuple[str, list[str]]:
    """
    Versão consolidada de analisar_par compatível com a assinatura existente.

    Única diferença: aceita caminho_fonte_original para habilitar
    RegraSemFallbackParaAudioCompleto.
    """
    auditavel = Auditavel(
        arquivo_original=caminho_fonte_original or "",
        cabeca=caminho_cabeca,
        corpo=caminho_corpo,
    )

    auditor = Auditor()
    resultado = auditor.auditar(auditavel)

    if resultado.status == "OK":
        return "OK", []
    elif resultado.status == "ERRO":
        return "ERRO", resultado.motivos
    else:
        return "CORTADO", resultado.motivos
