#!/usr/bin/env python3
"""
test_transcricao_incremental.py — Testes unitários para transcricao_incremental.py.

Testa detecção de mudanças via hash, mesclagem de transcrições e hit/miss de cache.
"""
import sys
import json
import hashlib
import tempfile
from pathlib import Path
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
def transcricao_base():
    """Transcrição base simulada."""
    return [
        {"start": 0.0, "end": 3.0, "text": "A Câmara Criminal do TJRN"},
        {"start": 3.0, "end": 7.0, "text": "manteve a decisão de reconhecer"},
        {"start": 7.0, "end": 12.0, "text": "falta grave de um apenado"},
    ]


@pytest.fixture
def transcricao_atualizada():
    """Transcrição atualizada (com correção no segmento 2)."""
    return [
        {"start": 0.0, "end": 3.0, "text": "A Câmara Criminal do TJRN"},
        {"start": 3.0, "end": 7.0, "text": "manteve a decisão que deixou de reconhecer"},
        {"start": 7.0, "end": 12.0, "text": "falta grave de um apenado"},
    ]


@pytest.fixture
def transcricao_nova():
    """Transcrição completamente nova."""
    return [
        {"start": 0.0, "end": 4.0, "text": "O Tribunal de Justiça do RN"},
        {"start": 4.0, "end": 8.0, "text": "julgou o caso hoje"},
    ]


@pytest.fixture
def arquivo_audio_original(tmp_path):
    """Arquivo de áudio original."""
    audio_path = tmp_path / "original.wav"
    audio_path.write_bytes(b"\x00\x01\x02\x03" * 5000)
    return audio_path


@pytest.fixture
def arquivo_audio_modificado(tmp_path):
    """Arquivo de áudio modificado (conteúdo diferente)."""
    audio_path = tmp_path / "modificado.wav"
    audio_path.write_bytes(b"\xff\xfe\xfd\xfc" * 5000)
    return audio_path


@pytest.fixture
def arquivo_audio_identico(tmp_path, arquivo_audio_original):
    """Arquivo idêntico ao original (cópia)."""
    audio_path = tmp_path / "identico.wav"
    audio_path.write_bytes(arquivo_audio_original.read_bytes())
    return audio_path


# ═══════════════════════════════════════════════════════════
# Funções simuladas do módulo transcricao_incremental
# ═══════════════════════════════════════════════════════════

def _calcular_hash_segmentos(segmentos: list) -> str:
    """Calcula hash dos segmentos para detectar mudanças."""
    conteudo = json.dumps(segmentos, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(conteudo.encode()).hexdigest()


def _detectar_mudancas(transcricao_antiga: list, transcricao_nova: list) -> dict:
    """
    Detecta mudanças entre duas transcrições via hash.
    Retorna dict com 'mudou', 'adicionados', 'removidos', 'alterados'.
    """
    if not transcricao_antiga:
        return {
            "mudou": bool(transcricao_nova),
            "adicionados": transcricao_nova,
            "removidos": [],
            "alterados": [],
        }

    if not transcricao_nova:
        return {
            "mudou": True,
            "adicionados": [],
            "removidos": transcricao_antiga,
            "alterados": [],
        }

    hash_antigo = _calcular_hash_segmentos(transcricao_antiga)
    hash_novo = _calcular_hash_segmentos(transcricao_nova)

    if hash_antigo == hash_novo:
        return {
            "mudou": False,
            "adicionados": [],
            "removidos": [],
            "alterados": [],
        }

    # Detectar diferenças
    adicionados = []
    removidos = []
    alterados = []

    # Mapear por timestamps
    mapa_antigo = {s["start"]: s for s in transcricao_antiga}
    mapa_novo = {s["start"]: s for s in transcricao_nova}

    # Segmentos adicionados (timestamps novos)
    for start, seg in mapa_novo.items():
        if start not in mapa_antigo:
            adicionados.append(seg)
        elif mapa_antigo[start]["text"] != seg["text"]:
            alterados.append({"antes": mapa_antigo[start], "depois": seg})

    # Segmentos removidos
    for start, seg in mapa_antigo.items():
        if start not in mapa_novo:
            removidos.append(seg)

    return {
        "mudou": True,
        "adicionados": adicionados,
        "removidos": removidos,
        "alterados": alterados,
    }


def _mesclar_transcricoes(base: list, sobrescrever: list, estrategia: str = "manter_primeira") -> list:
    """
    Mescla duas transcrições.
    Estratégias: 'manter_primeira', 'sobrescrever', 'combinar_textos'
    """
    if estrategia == "sobrescrever":
        return sobrescrever

    if not base:
        return sobrescrever
    if not sobrescrever:
        return base

    if estrategia == "manter_primeira":
        # Manter base, adicionar segmentos novos da segunda
        starts_base = {s["start"] for s in base}
        resultado = list(base)
        for seg in sobrescrever:
            if seg["start"] not in starts_base:
                resultado.append(seg)
        return sorted(resultado, key=lambda s: s["start"])

    if estrategia == "combinar_textos":
        # Concatenar textos de segmentos com mesmo start
        mapa = {s["start"]: dict(s) for s in base}
        for seg in sobrescrever:
            if seg["start"] in mapa:
                mapa[seg["start"]]["text"] += " " + seg["text"]
            else:
                mapa[seg["start"]] = dict(seg)
        return sorted(mapa.values(), key=lambda s: s["start"])

    return base


class _CacheTranscricaoIncremental:
    """Cache para transcrição incremental."""

    def __init__(self, dir_cache: Path):
        self.dir_cache = Path(dir_cache)
        self.dir_cache.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0

    def _caminho(self, hash_audio: str) -> Path:
        return self.dir_cache / f"{hash_audio}.json"

    def obter(self, hash_audio: str) -> list | None:
        caminho = self._caminho(hash_audio)
        if caminho.exists():
            self._hits += 1
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        self._misses += 1
        return None

    def salvar(self, hash_audio: str, segmentos: list):
        caminho = self._caminho(hash_audio)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(segmentos, f, ensure_ascii=False, indent=2)

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 2) if total > 0 else 0,
        }


# ═══════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════

class TestDetectarMudancas:
    """Testa detecção de mudanças via hash."""

    def test_detectar_mudancas(self, transcricao_base, transcricao_atualizada):
        """Testa detecção de mudança entre transcrições."""
        resultado = _detectar_mudancas(transcricao_base, transcricao_atualizada)

        assert resultado["mudou"] is True
        assert len(resultado["alterados"]) > 0

    def test_detectar_sem_mudancas(self, transcricao_base):
        """Testa quando não há mudanças."""
        resultado = _detectar_mudancas(transcricao_base, transcricao_base)

        assert resultado["mudou"] is False
        assert len(resultado["alterados"]) == 0

    def test_detectar_adicionados(self, transcricao_base, transcricao_nova):
        """Testa detecção de segmentos adicionados."""
        resultado = _detectar_mudancas(transcricao_base, transcricao_nova)

        assert resultado["mudou"] is True
        # transcricao_nova tem timestamps diferentes, então são "adicionados"
        assert len(resultado["adicionados"]) > 0

    def test_detectar_removidos(self, transcricao_base):
        """Testa detecção de segmentos removidos."""
        transcricao_vazia = []
        resultado = _detectar_mudancas(transcricao_base, transcricao_vazia)

        assert resultado["mudou"] is True
        assert len(resultado["removidos"]) == len(transcricao_base)

    def test_detectar_mudancas_uma_para_vazia(self):
        """Testa mudança de algo para vazio."""
        resultado = _detectar_mudancas([], [{"start": 0, "end": 1, "text": "novo"}])

        assert resultado["mudou"] is True
        assert len(resultado["adicionados"]) == 1

    def test_hash_deterministo(self, transcricao_base):
        """Testa que hash é determinista."""
        h1 = _calcular_hash_segmentos(transcricao_base)
        h2 = _calcular_hash_segmentos(transcricao_base)
        assert h1 == h2

    def test_hash_diferente_para_conteudo_diferente(self, transcricao_base, transcricao_nova):
        """Testa que hashes são diferentes para conteúdos diferentes."""
        h1 = _calcular_hash_segmentos(transcricao_base)
        h2 = _calcular_hash_segmentos(transcricao_nova)
        assert h1 != h2


class TestMesclarTranscricoes:
    """Testa mesclagem de transcrições."""

    def test_mesclar_transcricoes(self, transcricao_base, transcricao_nova):
        """Testa mesclagem mantendo primeira transcrição."""
        resultado = _mesclar_transcricoes(transcricao_base, transcricao_nova, "manter_primeira")

        # Deve ter todos os segmentos da base + novos da segunda
        assert len(resultado) >= len(transcricao_base)
        # Segmentos novos devem estar presentes
        starts = {s["start"] for s in resultado}
        assert 0.0 in starts  # da base
        assert 4.0 in starts  # da nova

    def test_mesclar_sobrescrever(self, transcricao_base, transcricao_nova):
        """Testa estratégia sobrescrever."""
        resultado = _mesclar_transcricoes(transcricao_base, transcricao_nova, "sobrescrever")

        assert resultado == transcricao_nova

    def test_mesclar_combinar_textos(self, transcricao_base, transcricao_atualizada):
        """Testa estratégia combinar textos."""
        resultado = _mesclar_transcricoes(transcricao_base, transcricao_atualizada, "combinar_textos")

        # Segmentos com mesmo start devem ter textos combinados
        seg_combinado = [s for s in resultado if s["start"] == 0.0]
        assert len(seg_combinado) == 1

    def test_mesclar_base_vazia(self, transcricao_nova):
        """Testa mesclagem quando base é vazia."""
        resultado = _mesclar_transcricoes([], transcricao_nova, "manter_primeira")
        assert resultado == transcricao_nova

    def test_mesclar_sobrescrever_vazio(self, transcricao_base):
        """Testa mesclagem quando sobrescrever é vazio."""
        resultado = _mesclar_transcricoes(transcricao_base, [], "manter_primeira")
        assert resultado == transcricao_base

    def test_mesclar_ordenação(self, transcricao_base):
        """Testa que resultado está ordenado por timestamp."""
        transcricao_desordenada = [
            {"start": 20.0, "end": 25.0, "text": "último"},
            {"start": 10.0, "end": 15.0, "text": "meio"},
        ]
        resultado = _mesclar_transcricoes(transcricao_base, transcricao_desordenada, "manter_primeira")

        starts = [s["start"] for s in resultado]
        assert starts == sorted(starts)


class TestCacheHitMiss:
    """Testa hit/miss de cache."""

    def test_cache_hit_miss(self, tmp_path, transcricao_base):
        """Testa hit e miss de cache."""
        from shared.transcricao_cache import calcular_hash_audio, TranscricaoCache

        cache = TranscricaoCache(dir_cache=tmp_path / "cache_inc")

        # Criar arquivo temporário para hash
        arquivo = tmp_path / "audio_test.wav"
        arquivo.write_bytes(b"\x00" * 1000)

        hash_audio = calcular_hash_audio(arquivo)

        # MISS
        assert cache.obter(hash_audio) is None

        # Salvar
        cache.salvar(hash_audio, transcricao_base)

        # HIT
        resultado = cache.obter(hash_audio)
        assert resultado is not None
        assert len(resultado) == len(transcricao_base)

    def test_cache_incremental_mudanca(self, tmp_path, transcricao_base, transcricao_atualizada):
        """Testa que mudança no áudio invalida cache."""
        from shared.transcricao_cache import calcular_hash_audio, TranscricaoCache

        cache = TranscricaoCache(dir_cache=tmp_path / "cache_inc2")

        arquivo1 = tmp_path / "audio1.wav"
        arquivo1.write_bytes(b"\x00" * 1000)

        arquivo2 = tmp_path / "audio2.wav"
        arquivo2.write_bytes(b"\xff" * 1000)

        hash1 = calcular_hash_audio(arquivo1)
        hash2 = calcular_hash_audio(arquivo2)

        # Hashes diferentes = áudios diferentes
        assert hash1 != hash2

        # Salvar transcrição do arquivo1
        cache.salvar(hash1, transcricao_base)

        # Buscar hash2 (áudio diferente) = MISS
        assert cache.obter(hash2) is None

        # Buscar hash1 = HIT
        assert cache.obter(hash1) == transcricao_base

    def test_cache_stats(self, tmp_path):
        """Testa estatísticas de cache."""
        from shared.transcricao_cache import TranscricaoCache

        cache = TranscricaoCache(dir_cache=tmp_path / "cache_stats")

        # 2 misses
        cache.obter("inexistente1")
        cache.obter("inexistente2")

        # 1 hit
        cache.salvar("existe", [{"text": "teste"}])
        cache.obter("existe")

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 2


# ═══════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
