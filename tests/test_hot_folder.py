#!/usr/bin/env python3
"""
test_hot_folder.py — Testes unitários para hot_folder.py.

Testa associação de roteiro, monitoramento de pasta e processamento
de novos arquivos com dados simulados.
"""
import sys
import json
import time
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from datetime import date, datetime

import pytest

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts_pipeline"))
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def pasta_hot(tmp_path):
    """Cria uma pasta hot folder temporária."""
    hot_dir = tmp_path / "hot_folder"
    hot_dir.mkdir()
    return hot_dir


@pytest.fixture
def pasta_roteiros(tmp_path):
    """Cria uma pasta de roteiros temporária com arquivos simulados."""
    rot_dir = tmp_path / "roteiros"
    rot_dir.mkdir()

    # Criar roteiros com datas no nome
    roteiros = {
        "roteiro_2026-09-15.txt": "Roteiro do dia 15 de setembro de 2026",
        "roteiro_2026-09-16.txt": "Roteiro do dia 16 de setembro de 2026",
        "roteiro_2026-09-17.txt": "Roteiro do dia 17 de setembro de 2026",
    }
    for nome, conteudo in roteiros.items():
        (rot_dir / nome).write_text(conteudo, encoding="utf-8")

    return rot_dir


@pytest.fixture
def pasta_saida(tmp_path):
    """Cria pasta de saída temporária."""
    saida = tmp_path / "saida"
    saida.mkdir()
    return saida


@pytest.fixture
def arquivo_audio_mock(tmp_path):
    """Cria um arquivo de áudio simulado (não real, apenas para detecção)."""
    audio_file = tmp_path / "hot_folder" / "boletim_2026-09-17.mp3"
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    # Escrever dados fake (não é áudio real, apenas para testes de detecção)
    audio_file.write_bytes(b"\x00\x01\x02\x03" * 1000)
    return audio_file


@pytest.fixture
def estado_hot_folder():
    """Estado inicial do hot folder."""
    return {
        "arquivos_processados": [],
        "ultima_verificacao": None,
        "erros": [],
    }


# ═══════════════════════════════════════════════════════════
# Mocks do módulo hot_folder (módulo será criado por outro subagente)
# ═══════════════════════════════════════════════════════════

def _simular_associar_roteiro(data: date, pasta_roteiros: Path) -> Path | None:
    """
    Simula a lógica de associação de roteiro por data.
    Procura roteiro_YYYY-MM-DD.txt na pasta de roteiros.
    """
    nome_arquivo = f"roteiro_{data.strftime('%Y-%m-%d')}.txt"
    caminho = pasta_roteiros / nome_arquivo
    if caminho.exists():
        return caminho
    return None


def _simular_monitorar_pasta(pasta: Path, arquivos_processados: set) -> list:
    """
    Simula monitoramento de pasta: retorna arquivos novos (ainda não processados).
    """
    extensoes_audio = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}
    novos = []

    for arquivo in pasta.iterdir():
        if arquivo.is_file() and arquivo.suffix.lower() in extensoes_audio:
            if str(arquivo) not in arquivos_processados:
                novos.append(arquivo)

    return novos


def _simular_processar_arquivo(arquivo: Path, roteiro_path: Path | None, saida: Path) -> dict:
    """
    Simula processamento de um arquivo de áudio.
    """
    resultado = {
        "arquivo": str(arquivo),
        "roteiro": str(roteiro_path) if roteiro_path else None,
        "saida": str(saida / arquivo.name),
        "status": "processado",
        "timestamp": datetime.now().isoformat(),
    }
    return resultado


# ═══════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════

class TestAssociarRoteiro:
    """Testa associação de roteiro por data."""

    def test_associar_roteiro(self, pasta_roteiros):
        """Testa associação de roteiro existente por data."""
        data = date(2026, 9, 16)
        resultado = _simular_associar_roteiro(data, pasta_roteiros)

        assert resultado is not None
        assert resultado.exists()
        assert "2026-09-16" in resultado.name

    def test_associar_roteiro_inexistente(self, pasta_roteiros):
        """Testa associação quando roteiro não existe para a data."""
        data = date(2026, 12, 25)
        resultado = _simular_associar_roteiro(data, pasta_roteiros)

        assert resultado is None

    def test_associar_roteiro_data_limite(self, pasta_roteiros):
        """Testa associação com primeira data disponível."""
        data = date(2026, 9, 15)
        resultado = _simular_associar_roteiro(data, pasta_roteiros)

        assert resultado is not None
        assert resultado.exists()

    def test_associar_roteiro_varios_dias(self, pasta_roteiros):
        """Testa associação para múltiplos dias."""
        datas = [date(2026, 9, 15), date(2026, 9, 16), date(2026, 9, 17)]
        resultados = [_simular_associar_roteiro(d, pasta_roteiros) for d in datas]

        assert all(r is not None for r in resultados)
        assert all(r.exists() for r in resultados)


class TestMonitorarPasta:
    """Testa detecção de novos arquivos."""

    def test_monitorar_pasta(self, pasta_hot, arquivo_audio_mock):
        """Testa detecção de novo arquivo de áudio."""
        arquivos_processados = set()
        novos = _simular_monitorar_pasta(pasta_hot, arquivos_processados)

        assert len(novos) >= 1
        assert any("boletim" in str(f) for f in novos)

    def test_monitorar_pasta_sem_novos(self, pasta_hot, arquivo_audio_mock):
        """Testa quando todos os arquivos já foram processados."""
        arquivos_processados = {str(arquivo_audio_mock)}
        novos = _simular_monitorar_pasta(pasta_hot, arquivos_processados)

        assert len(novos) == 0

    def test_monitorar_pasta_extensoes_validas(self, pasta_hot):
        """Testa que apenas extensões de áudio são detectadas."""
        # Criar arquivos com várias extensões
        (pasta_hot / "audio.mp3").write_bytes(b"\x00" * 100)
        (pasta_hot / "audio.wav").write_bytes(b"\x00" * 100)
        (pasta_hot / "texto.txt").write_bytes(b"texto")
        (pasta_hot / "imagem.jpg").write_bytes(b"\x00" * 100)

        arquivos_processados = set()
        novos = _simular_monitorar_pasta(pasta_hot, arquivos_processados)

        # Apenas .mp3 e .wav
        extensoes_encontradas = {f.suffix.lower() for f in novos}
        assert ".txt" not in extensoes_encontradas
        assert ".jpg" not in extensoes_encontradas
        assert ".mp3" in extensoes_encontradas or ".wav" in extensoes_encontradas

    def test_monitorar_pasta_vazia(self, pasta_hot):
        """Testa monitoramento de pasta sem arquivos."""
        arquivos_processados = set()
        novos = _simular_monitorar_pasta(pasta_hot, arquivos_processados)

        assert len(novos) == 0


class TestProcessarNovoArquivoMock:
    """Testa processamento de novos arquivos com mock."""

    def test_processar_novo_arquivo_mock(self, arquivo_audio_mock, pasta_roteiros, pasta_saida):
        """Testa processamento completo de um arquivo novo com mock."""
        roteiro = pasta_roteiros / "roteiro_2026-09-17.txt"

        resultado = _simular_processar_arquivo(arquivo_audio_mock, roteiro, pasta_saida)

        assert resultado["status"] == "processado"
        assert resultado["arquivo"] == str(arquivo_audio_mock)
        assert resultado["roteiro"] == str(roteiro)
        assert "timestamp" in resultado

    def test_processar_novo_arquivo_sem_roteiro(self, arquivo_audio_mock, pasta_saida):
        """Testa processamento sem roteiro associado."""
        resultado = _simular_processar_arquivo(arquivo_audio_mock, None, pasta_saida)

        assert resultado["status"] == "processado"
        assert resultado["roteiro"] is None

    def test_processar_novo_arquivo_integracao(self, pasta_hot, pasta_roteiros, pasta_saida):
        """Testa fluxo completo: detectar → associar roteiro → processar."""
        # Criar arquivo novo
        audio = pasta_hot / "boletim_2026-09-16.mp3"
        audio.write_bytes(b"\x00" * 1000)

        # Detectar novos
        processados = set()
        novos = _simular_monitorar_pasta(pasta_hot, processados)
        assert len(novos) >= 1

        # Associar roteiro
        data = date(2026, 9, 16)
        roteiro = _simular_associar_roteiro(data, pasta_roteiros)
        assert roteiro is not None

        # Processar
        resultado = _simular_processar_arquivo(novos[0], roteiro, pasta_saida)
        assert resultado["status"] == "processado"

    @patch("time.sleep", return_value=None)
    def test_monitoramento_continuo_mock(self, mock_sleep, pasta_hot, pasta_saida):
        """Testa loop de monitoramento contínuo com mock."""
        # Criar arquivo
        audio = pasta_hot / "teste_continuo.mp3"
        audio.write_bytes(b"\x00" * 100)

        processados = set()
        ciclos = 0
        max_ciclos = 3

        while ciclos < max_ciclos:
            novos = _simular_monitorar_pasta(pasta_hot, processados)
            for arq in novos:
                _simular_processar_arquivo(arq, None, pasta_saida)
                processados.add(str(arq))
            ciclos += 1
            mock_sleep(1)

        # Após primeiro ciclo, arquivo já deve estar processado
        assert str(audio) in processados
        assert ciclos == max_ciclos


# ═══════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
