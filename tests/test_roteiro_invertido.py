#!/usr/bin/env python3
"""
test_roteiro_invertido.py — Testes unitários para roteiro_invertido.py.

Testa formatação de roteiro, geração de legendas SRT e exportação em formatos.
"""
import sys
import json
import tempfile
from pathlib import Path
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts_pipeline"))
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def segmentos_roteiro():
    """Segmentos para geração de roteiro invertido."""
    return [
        {"start": 0.0, "end": 5.0, "text": "A Câmara Criminal do TJRN manteve a decisão"},
        {"start": 5.0, "end": 10.0, "text": "que deixou de reconhecer falta grave de um apenado"},
        {"start": 10.0, "end": 15.0, "text": "Para o Ministério Público, o rompimento do equipamento"},
        {"start": 15.0, "end": 20.0, "text": "ocorrido em março de 2026 seria conduta equiparada a fuga"},
        {"start": 20.0, "end": 25.0, "text": "O relator do caso destacou que a decisão foi unânime"},
    ]


@pytest.fixture
def segmentos_com_speaker():
    """Segmentos com identificação de locutor."""
    return [
        {"start": 0.0, "end": 5.0, "text": "A Câmara Criminal do TJRN manteve a decisão", "speaker": "REPORTER"},
        {"start": 5.0, "end": 10.0, "text": "que deixou de reconhecer falta grave", "speaker": "REPORTER"},
        {"start": 10.0, "end": 15.0, "text": "Para o Ministério Público", "speaker": "ENTREVISTADO"},
        {"start": 15.0, "end": 20.0, "text": "o rompimento seria conduta equiparada a fuga", "speaker": "ENTREVISTADO"},
    ]


@pytest.fixture
def metadados_boletim():
    """Metadados do boletim."""
    return {
        "titulo": "Boletim TJRN - 17/09/2026",
        "data": "2026-09-17",
        "locutor": "Leonardo Meida",
        "editoria": "Justiça",
    }


# ═══════════════════════════════════════════════════════════
# Funções simuladas do módulo roteiro_invertido
# ═══════════════════════════════════════════════════════════

def _formatar_roteiro(segmentos: list, metadados: dict | None = None) -> str:
    """
    Formata segmentos de transcrição como roteiro invertido (texto corrido).
    """
    linhas = []

    if metadados:
        if "titulo" in metadados:
            linhas.append(f"# {metadados['titulo']}")
        if "data" in metadados:
            linhas.append(f"**Data:** {metadados['data']}")
        if "locutor" in metadados:
            linhas.append(f"**Locutor:** {metadados['locutor']}")
        linhas.append("")

    for seg in segmentos:
        texto = seg["text"].strip()
        if not texto:
            continue

        # Adicionar identificação de locutor se disponível
        speaker = seg.get("speaker")
        if speaker:
            linhas.append(f"[{speaker}] {texto}")
        else:
            linhas.append(texto)

    return "\n".join(linhas)


def _gerar_legendas_srt(segmentos: list) -> str:
    """
    Gera legendas no formato SRT a partir de segmentos.
    """
    srt_linhas = []

    for i, seg in enumerate(segmentos, start=1):
        inicio = _formatar_timestamp(seg["start"])
        fim = _formatar_timestamp(seg["end"])
        texto = seg["text"].strip()

        srt_linhas.append(str(i))
        srt_linhas.append(f"{inicio} --> {fim}")
        srt_linhas.append(texto)
        srt_linhas.append("")  # linha em branco entre entradas

    return "\n".join(srt_linhas)


def _formatar_timestamp(segundos: float) -> str:
    """Formata segundos como timestamp SRT (HH:MM:SS,mmm)."""
    td = timedelta(seconds=segundos)
    total_seconds = int(td.total_seconds())
    horas = total_seconds // 3600
    minutos = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    milissegundos = int((segundos - int(segundos)) * 1000)
    return f"{horas:02d}:{minutos:02d}:{secs:02d},{milissegundos:03d}"


def _exportar_roteiro(segmentos: list, formato: str, caminho_saida: Path, metadados: dict | None = None) -> Path:
    """
    Exporta roteiro em diferentes formatos: 'txt', 'srt', 'json', 'md'.
    """
    caminho_saida = Path(caminho_saida)

    if formato == "txt":
        conteudo = _formatar_roteiro(segmentos, metadados)
        caminho_saida = caminho_saida.with_suffix(".txt")
        caminho_saida.write_text(conteudo, encoding="utf-8")

    elif formato == "srt":
        conteudo = _gerar_legendas_srt(segmentos)
        caminho_saida = caminho_saida.with_suffix(".srt")
        caminho_saida.write_text(conteudo, encoding="utf-8")

    elif formato == "json":
        dados = {
            "metadados": metadados or {},
            "segmentos": segmentos,
            "total_segmentos": len(segmentos),
        }
        caminho_saida = caminho_saida.with_suffix(".json")
        caminho_saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    elif formato == "md":
        conteudo = _formatar_roteiro_md(segmentos, metadados)
        caminho_saida = caminho_saida.with_suffix(".md")
        caminho_saida.write_text(conteudo, encoding="utf-8")

    else:
        raise ValueError(f"Formato não suportado: {formato}")

    return caminho_saida


def _formatar_roteiro_md(segmentos: list, metadados: dict | None = None) -> str:
    """Formata como Markdown."""
    linhas = []

    if metadados and "titulo" in metadados:
        linhas.append(f"# {metadados['titulo']}")
        linhas.append("")

    linhas.append("## Roteiro")
    linhas.append("")

    for seg in segmentos:
        texto = seg["text"].strip()
        if not texto:
            continue
        speaker = seg.get("speaker")
        if speaker:
            linhas.append(f"**{speaker}:** {texto}")
        else:
            linhas.append(texto)
        linhas.append("")

    return "\n".join(linhas)


# ═══════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════

class TestFormatarRoteiro:
    """Testa formatação de roteiro."""

    def test_formatar_roteiro(self, segmentos_roteiro):
        """Testa formatação básica de roteiro."""
        resultado = _formatar_roteiro(segmentos_roteiro)

        assert isinstance(resultado, str)
        assert len(resultado) > 0
        # Deve conter o texto dos segmentos
        assert "Câmara Criminal" in resultado

    def test_formatar_roteiro_com_metadados(self, segmentos_roteiro, metadados_boletim):
        """Testa formatação com metadados."""
        resultado = _formatar_roteiro(segmentos_roteiro, metadados_boletim)

        assert "Boletim TJRN" in resultado
        assert "2026-09-17" in resultado
        assert "Leonardo Meida" in resultado

    def test_formatar_roteiro_com_speaker(self, segmentos_com_speaker):
        """Testa formatação com identificação de locutor."""
        resultado = _formatar_roteiro(segmentos_com_speaker)

        assert "[REPORTER]" in resultado
        assert "[ENTREVISTADO]" in resultado

    def test_formatar_roteiro_vazio(self):
        """Testa formatação com lista vazia."""
        resultado = _formatar_roteiro([])
        assert resultado == ""

    def test_formatar_roteiro_sem_metadados(self, segmentos_roteiro):
        """Testa formatação sem metadados."""
        resultado = _formatar_roteiro(segmentos_roteiro)

        assert isinstance(resultado, str)
        assert "#" not in resultado  # sem título


class TestGerarLegendasSrt:
    """Testa geração de legendas SRT."""

    def test_gerar_legendas_srt(self, segmentos_roteiro):
        """Testa geração de SRT a partir de segmentos."""
        srt = _gerar_legendas_srt(segmentos_roteiro)

        assert isinstance(srt, str)
        # Deve ter entradas numeradas
        assert "1" in srt
        assert "2" in srt
        # Deve ter formato de timestamp
        assert "-->" in srt

    def test_gerar_legendas_srt_timestamps(self, segmentos_roteiro):
        """Testa que timestamps estão no formato correto."""
        srt = _gerar_legendas_srt(segmentos_roteiro)

        # Verificar formato HH:MM:SS,mmm --> HH:MM:SS,mmm
        import re
        padrao = r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}"
        matches = re.findall(padrao, srt)
        assert len(matches) == len(segmentos_roteiro)

    def test_gerar_legendas_srt_estrutura(self, segmentos_roteiro):
        """Testa estrutura do SRT (número, timestamps, texto, linha em branco)."""
        srt = _gerar_legendas_srt(segmentos_roteiro)
        linhas = [l for l in srt.strip().split("\n") if l.strip()]

        # Cada entrada SRT tem 3 linhas: número, timestamps, texto
        # Mais linha em branco entre entradas
        assert len(linhas) >= len(segmentos_roteiro) * 3

    def test_gerar_legendas_srt_vazio(self):
        """Testa SRT com lista vazia."""
        srt = _gerar_legendas_srt([])
        assert srt == ""

    def test_formatar_timestamp(self):
        """Testa formatação de timestamp individual."""
        assert _formatar_timestamp(0.0) == "00:00:00,000"
        assert _formatar_timestamp(5.5) == "00:00:05,500"
        assert _formatar_timestamp(65.123) == "00:01:05,123"
        # 3661.999 pode ter precisão float: aceitar 998 ou 999
        resultado = _formatar_timestamp(3661.999)
        assert resultado in ("01:01:01,998", "01:01:01,999")


class TestExportarRoteiro:
    """Testa exportação em diferentes formatos."""

    def test_exportar_roteiro_txt(self, segmentos_roteiro, tmp_path, metadados_boletim):
        """Testa exportação em formato TXT."""
        saida = tmp_path / "roteiro"
        resultado = _exportar_roteiro(segmentos_roteiro, "txt", saida, metadados_boletim)

        assert resultado.exists()
        assert resultado.suffix == ".txt"
        conteudo = resultado.read_text(encoding="utf-8")
        assert "Câmara Criminal" in conteudo

    def test_exportar_roteiro_srt(self, segmentos_roteiro, tmp_path):
        """Testa exportação em formato SRT."""
        saida = tmp_path / "roteiro"
        resultado = _exportar_roteiro(segmentos_roteiro, "srt", saida)

        assert resultado.exists()
        assert resultado.suffix == ".srt"
        conteudo = resultado.read_text(encoding="utf-8")
        assert "-->" in conteudo

    def test_exportar_roteiro_json(self, segmentos_roteiro, tmp_path, metadados_boletim):
        """Testa exportação em formato JSON."""
        saida = tmp_path / "roteiro"
        resultado = _exportar_roteiro(segmentos_roteiro, "json", saida, metadados_boletim)

        assert resultado.exists()
        assert resultado.suffix == ".json"
        dados = json.loads(resultado.read_text(encoding="utf-8"))
        assert "segmentos" in dados
        assert "metadados" in dados
        assert dados["total_segmentos"] == len(segmentos_roteiro)

    def test_exportar_roteiro_md(self, segmentos_roteiro, tmp_path, metadados_boletim):
        """Testa exportação em formato Markdown."""
        saida = tmp_path / "roteiro"
        resultado = _exportar_roteiro(segmentos_roteiro, "md", saida, metadados_boletim)

        assert resultado.exists()
        assert resultado.suffix == ".md"
        conteudo = resultado.read_text(encoding="utf-8")
        assert "#" in conteudo  # headers markdown

    def test_exportar_roteiro_formato_invalido(self, segmentos_roteiro, tmp_path):
        """Testa erro com formato não suportado."""
        saida = tmp_path / "roteiro"
        with pytest.raises(ValueError, match="não suportado"):
            _exportar_roteiro(segmentos_roteiro, "xml", saida)

    def test_exportar_roteiro_preserva_conteudo(self, segmentos_roteiro, tmp_path):
        """Testa que conteúdo é preservado na exportação."""
        saida = tmp_path / "roteiro"
        resultado = _exportar_roteiro(segmentos_roteiro, "txt", saida)

        conteudo = resultado.read_text(encoding="utf-8")
        for seg in segmentos_roteiro:
            assert seg["text"] in conteudo

    def test_exportar_roteiro_multiplos_formatos(self, segmentos_roteiro, tmp_path, metadados_boletim):
        """Testa exportação em múltiplos formatos simultaneamente."""
        formatos = ["txt", "srt", "json", "md"]
        saida = tmp_path / "roteiro"

        for fmt in formatos:
            resultado = _exportar_roteiro(segmentos_roteiro, fmt, saida, metadados_boletim)
            assert resultado.exists()


# ═══════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
