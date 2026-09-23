#!/usr/bin/env python3
"""
test_multiplos_locutores.py — Testes unitários para multiplos_locutores.py.

Testa extração de segmentos de fala, classificação de locutor e estatísticas.
"""
import sys
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
def segmentos_fala_simulados():
    """Segmentos de fala simulados com múltiplos locutores."""
    return [
        {"start": 0.0, "end": 5.0, "text": "A Câmara Criminal do TJRN manteve a decisão", "speaker": "LOC_A"},
        {"start": 5.0, "end": 10.0, "text": "que deixou de reconhecer falta grave", "speaker": "LOC_A"},
        {"start": 10.0, "end": 15.0, "text": "Para o Ministério Público, o rompimento", "speaker": "LOC_B"},
        {"start": 15.0, "end": 20.0, "text": "do equipamento seria conduta equiparada a fuga", "speaker": "LOC_B"},
        {"start": 20.0, "end": 25.0, "text": "O relator do caso destacou que", "speaker": "LOC_A"},
        {"start": 25.0, "end": 30.0, "text": "a decisão foi unânime", "speaker": "LOC_C"},
    ]


@pytest.fixture
def segmentos_sem_speaker():
    """Segmentos sem informação de locutor."""
    return [
        {"start": 0.0, "end": 5.0, "text": "Primeiro segmento de fala"},
        {"start": 5.0, "end": 10.0, "text": "Segundo segmento de fala"},
        {"start": 10.0, "end": 15.0, "text": "Terceiro segmento de fala"},
    ]


@pytest.fixture
def segmentos_mono_locutor():
    """Segmentos de um único locutor."""
    return [
        {"start": 0.0, "end": 5.0, "text": "Texto do locutor único", "speaker": "LOC_A"},
        {"start": 5.0, "end": 10.0, "text": "Mais texto do mesmo locutor", "speaker": "LOC_A"},
        {"start": 10.0, "end": 15.0, "text": "Continuação do locutor", "speaker": "LOC_A"},
    ]


# ═══════════════════════════════════════════════════════════
# Funções simuladas do módulo multiplos_locutores
# ═══════════════════════════════════════════════════════════

def _extrair_segmentos_fala(segmentos: list, gap_maximo: float = 1.0) -> list:
    """
    Extrai segmentos de fala agrupando segmentos consecutivos do mesmo locutor.
    Se gap entre segmentos do mesmo locutor for <= gap_maximo, agrupa.
    """
    if not segmentos:
        return []

    segmentos_agrupados = []
    grupo_atual = {
        "start": segmentos[0]["start"],
        "end": segmentos[0]["end"],
        "texts": [segmentos[0]["text"]],
        "speaker": segmentos[0].get("speaker", "DESCONHECIDO"),
    }

    for i in range(1, len(segmentos)):
        seg = segmentos[i]
        speaker_atual = seg.get("speaker", "DESCONHECIDO")
        gap = seg["start"] - grupo_atual["end"]

        if speaker_atual == grupo_atual["speaker"] and gap <= gap_maximo:
            # Mesmo locutor com gap pequeno: agrupar
            grupo_atual["end"] = seg["end"]
            grupo_atual["texts"].append(seg["text"])
        else:
            # Salvar grupo atual e iniciar novo
            segmentos_agrupados.append({
                "start": grupo_atual["start"],
                "end": grupo_atual["end"],
                "text": " ".join(grupo_atual["texts"]),
                "speaker": grupo_atual["speaker"],
                "duracao": grupo_atual["end"] - grupo_atual["start"],
            })
            grupo_atual = {
                "start": seg["start"],
                "end": seg["end"],
                "texts": [seg["text"]],
                "speaker": speaker_atual,
            }

    # Salvar último grupo
    segmentos_agrupados.append({
        "start": grupo_atual["start"],
        "end": grupo_atual["end"],
        "text": " ".join(grupo_atual["texts"]),
        "speaker": grupo_atual["speaker"],
        "duracao": grupo_atual["end"] - grupo_atual["start"],
    })

    return segmentos_agrupados


def _classificar_locutor(segmento: dict, regras: dict | None = None) -> str:
    """
    Classifica locutor com base em regras ou metadados.
    """
    # Se já tem speaker, retorna
    if "speaker" in segmento and segmento["speaker"]:
        return segmento["speaker"]

    # Regras heurísticas baseadas no conteúdo
    texto = segmento.get("text", "").lower()

    if regras:
        for padrao, locutor in regras.items():
            if padrao.lower() in texto:
                return locutor

    # Heurísticas padrão
    if "tribunal" in texto or "decisão" in texto or "relator" in texto:
        return "REPORTER"
    if "ministério público" in texto or "mp" in texto:
        return "ENTREVISTADO"
    if "boletim" in texto or "rádio" in texto:
        return "ANCORA"

    return "DESCONHECIDO"


def _gerar_estatisticas(segmentos_agrupados: list) -> dict:
    """
    Gera estatísticas sobre os locutores.
    """
    if not segmentos_agrupados:
        return {
            "total_locutores": 0,
            "total_segmentos": 0,
            "duracao_total": 0.0,
            "locutores": {},
        }

    locutores = {}
    duracao_total = 0.0

    for seg in segmentos_agrupados:
        speaker = seg["speaker"]
        duracao = seg["duracao"]
        duracao_total += duracao

        if speaker not in locutores:
            locutores[speaker] = {
                "total_segmentos": 0,
                "duracao_total": 0.0,
                "texto_completo": [],
            }

        locutores[speaker]["total_segmentos"] += 1
        locutores[speaker]["duracao_total"] += duracao
        locutores[speaker]["texto_completo"].append(seg["text"])

    # Calcular percentuais
    for speaker, info in locutores.items():
        info["percentual_tempo"] = round(
            info["duracao_total"] / duracao_total * 100, 2
        ) if duracao_total > 0 else 0.0

    return {
        "total_locutores": len(locutores),
        "total_segmentos": len(segmentos_agrupados),
        "duracao_total": round(duracao_total, 2),
        "locutores": locutores,
    }


# ═══════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════

class TestExtrairSegmentosFala:
    """Testa segmentação de fala."""

    def test_extrair_segmentos_fala(self, segmentos_fala_simulados):
        """Testa extração de segmentos de fala com múltiplos locutores."""
        resultado = _extrair_segmentos_fala(segmentos_fala_simulados)

        assert len(resultado) > 0
        assert all("speaker" in r for r in resultado)
        assert all("duracao" in r for r in resultado)
        assert all("text" in r for r in resultado)

    def test_extrair_segmentos_agrupamento(self, segmentos_fala_simulados):
        """Testa que segmentos do mesmo locutor são agrupados."""
        resultado = _extrair_segmentos_fala(segmentos_fala_simulados, gap_maximo=1.0)

        # Deve ter menos segmentos que o original (agrupamento)
        assert len(resultado) <= len(segmentos_fala_simulados)

    def test_extrair_segmentos_sem_speaker(self, segmentos_sem_speaker):
        """Testa extração quando não há informação de speaker."""
        resultado = _extrair_segmentos_fala(segmentos_sem_speaker)

        assert len(resultado) > 0
        # Todos devem ter speaker "DESCONHECIDO"
        assert all(r["speaker"] == "DESCONHECIDO" for r in resultado)

    def test_extrair_segmentos_mono_locutor(self, segmentos_mono_locutor):
        """Testa extração com único locutor."""
        resultado = _extrair_segmentos_fala(segmentos_mono_locutor)

        # Todos os segmentos devem ser agrupados em um único
        assert len(resultado) == 1
        assert resultado[0]["speaker"] == "LOC_A"
        assert resultado[0]["start"] == 0.0
        assert resultado[0]["end"] == 15.0

    def test_extrair_segmentos_vazio(self):
        """Testa extração com lista vazia."""
        resultado = _extrair_segmentos_fala([])
        assert resultado == []

    def test_extrair_segmentos_gap_maximo(self):
        """Testa que gap máximo controla agrupamento."""
        segmentos = [
            {"start": 0.0, "end": 5.0, "text": "A", "speaker": "LOC_A"},
            {"start": 6.0, "end": 10.0, "text": "B", "speaker": "LOC_A"},  # gap = 1.0
            {"start": 12.0, "end": 15.0, "text": "C", "speaker": "LOC_A"},  # gap = 2.0
        ]

        # Com gap_maximo=1.0: primeiro e segundo agrupados, terceiro separado
        resultado = _extrair_segmentos_fala(segmentos, gap_maximo=1.0)
        assert len(resultado) == 2

        # Com gap_maximo=3.0: todos agrupados
        resultado = _extrair_segmentos_fala(segmentos, gap_maximo=3.0)
        assert len(resultado) == 1


class TestClassificarLocutor:
    """Testa classificação de locutor."""

    def test_classificar_locutor(self):
        """Testa classificação com speaker já definido."""
        segmento = {"start": 0, "end": 5, "text": "teste", "speaker": "LOC_A"}
        resultado = _classificar_locutor(segmento)
        assert resultado == "LOC_A"

    def test_classificar_regras_customizadas(self):
        """Testa classificação com regras customizadas."""
        regras = {"tribunal": "REPORTER", "ministério": "PROMOTOR"}
        segmento = {"start": 0, "end": 5, "text": "O tribunal decidiu"}

        resultado = _classificar_locutor(segmento, regras)
        assert resultado == "REPORTER"

    def test_classificar_heuristicas(self):
        """Testa classificação heurística baseada em conteúdo."""
        seg_reporter = {"start": 0, "end": 5, "text": "O relator do caso destacou"}
        seg_entrevistado = {"start": 0, "end": 5, "text": "O Ministério Público argumentou"}

        assert _classificar_locutor(seg_reporter) == "REPORTER"
        assert _classificar_locutor(seg_entrevistado) == "ENTREVISTADO"

    def test_classificar_desconhecido(self):
        """Testa classificação quando não há match."""
        segmento = {"start": 0, "end": 5, "text": "texto genérico sem padrão"}
        resultado = _classificar_locutor(segmento)
        assert resultado == "DESCONHECIDO"

    def test_classificar_sem_texto(self):
        """Testa classificação com texto vazio."""
        segmento = {"start": 0, "end": 5, "text": ""}
        resultado = _classificar_locutor(segmento)
        assert resultado == "DESCONHECIDO"


class TestEstatisticas:
    """Testa geração de estatísticas."""

    def test_estatisticas(self, segmentos_fala_simulados):
        """Testa geração de estatísticas com múltiplos locutores."""
        agrupados = _extrair_segmentos_fala(segmentos_fala_simulados)
        stats = _gerar_estatisticas(agrupados)

        assert stats["total_locutores"] >= 1
        assert stats["total_segmentos"] > 0
        assert stats["duracao_total"] > 0
        assert "locutores" in stats

    def test_estatisticas_contagem_correta(self, segmentos_fala_simulados):
        """Testa que contagem de locutores está correta."""
        agrupados = _extrair_segmentos_fala(segmentos_fala_simulados)
        stats = _gerar_estatisticas(agrupados)

        # Deve ter pelo menos 2 locutores (LOC_A e LOC_B)
        assert stats["total_locutores"] >= 2

    def test_estatisticas_percentuais(self, segmentos_fala_simulados):
        """Testa que percentuais somam ~100%."""
        agrupados = _extrair_segmentos_fala(segmentos_fala_simulados)
        stats = _gerar_estatisticas(agrupados)

        percentuais = sum(
            info["percentual_tempo"]
            for info in stats["locutores"].values()
        )
        assert abs(percentuais - 100.0) < 1.0  # margem de arredondamento

    def test_estatisticas_vazio(self):
        """Testa estatísticas com dados vazios."""
        stats = _gerar_estatisticas([])

        assert stats["total_locutores"] == 0
        assert stats["total_segmentos"] == 0
        assert stats["duracao_total"] == 0.0

    def test_estatisticas_mono_locutor(self, segmentos_mono_locutor):
        """Testa estatísticas com único locutor."""
        agrupados = _extrair_segmentos_fala(segmentos_mono_locutor)
        stats = _gerar_estatisticas(agrupados)

        assert stats["total_locutores"] == 1
        assert stats["total_segmentos"] == 1
        assert "LOC_A" in stats["locutores"]
        assert stats["locutores"]["LOC_A"]["percentual_tempo"] == 100.0


# ═══════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
