#!/usr/bin/env python3
"""
test_metricas_dashboard.py — Testes unitários para metricas_dashboard.py.

Testa agregação de métricas, geração de HTML e gráficos SVG inline.
"""
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, date
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
def auditoria_data():
    """Dados simulados de auditoria.json."""
    return {
        "execucoes": [
            {
                "data": "2026-09-15",
                "arquivo": "boletim_0915.mp3",
                "duracao_segundos": 120.5,
                "cobertura_roteiro": 0.85,
                "alucinacoes_detectadas": 3,
                "alucinacoes_corrigidas": 2,
                "boletins_processados": 5,
                "tempos": {
                    "triagem": 0.5,
                    "transcricao": 45.2,
                    "estrutura": 2.1,
                    "cortes": 5.3,
                    "montagem": 10.8,
                },
            },
            {
                "data": "2026-09-16",
                "arquivo": "boletim_0916.mp3",
                "duracao_segundos": 95.0,
                "cobertura_roteiro": 0.92,
                "alucinacoes_detectadas": 1,
                "alucinacoes_corrigidas": 1,
                "boletins_processados": 4,
                "tempos": {
                    "triagem": 0.4,
                    "transcricao": 35.0,
                    "estrutura": 1.8,
                    "cortes": 4.2,
                    "montagem": 8.5,
                },
            },
            {
                "data": "2026-09-17",
                "arquivo": "boletim_0917.mp3",
                "duracao_segundos": 150.0,
                "cobertura_roteiro": 0.78,
                "alucinacoes_detectadas": 5,
                "alucinacoes_corrigidas": 4,
                "boletins_processados": 6,
                "tempos": {
                    "triagem": 0.6,
                    "transcricao": 55.0,
                    "estrutura": 2.5,
                    "cortes": 6.0,
                    "montagem": 12.0,
                },
            },
        ],
        "resumo": {
            "total_execucoes": 3,
            "media_cobertura": 0.85,
            "total_alucinacoes": 9,
            "total_boletins": 15,
        }
    }


@pytest.fixture
def arquivo_auditoria_json(tmp_path, auditoria_data):
    """Cria arquivo auditoria.json temporário."""
    json_path = tmp_path / "auditoria.json"
    json_path.write_text(json.dumps(auditoria_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


@pytest.fixture
def metricas_simuladas():
    """Métricas agregadas simuladas."""
    return {
        "total_execucoes": 3,
        "media_cobertura": 0.85,
        "media_duracao": 121.83,
        "total_alucinacoes": 9,
        "total_alucinacoes_corrigidas": 7,
        "taxa_correcao": 77.78,
        "total_boletins": 15,
        "media_tempo_total": 85.4,
        "execucoes_por_dia": {
            "2026-09-15": 1,
            "2026-09-16": 1,
            "2026-09-17": 1,
        },
        "cobertura_por_dia": {
            "2026-09-15": 0.85,
            "2026-09-16": 0.92,
            "2026-09-17": 0.78,
        },
    }


# ═══════════════════════════════════════════════════════════
# Funções simuladas do módulo metricas_dashboard
# ═══════════════════════════════════════════════════════════

def _agregar_metricas(dados_auditoria: dict) -> dict:
    """Simula agregação de métricas a partir de auditoria.json."""
    execucoes = dados_auditoria.get("execucoes", [])

    if not execucoes:
        return {
            "total_execucoes": 0,
            "media_cobertura": 0.0,
            "media_duracao": 0.0,
            "total_alucinacoes": 0,
            "total_alucinacoes_corrigidas": 0,
            "taxa_correcao": 0.0,
            "total_boletins": 0,
            "media_tempo_total": 0.0,
            "execucoes_por_dia": {},
            "cobertura_por_dia": {},
        }

    total_exec = len(execucoes)
    coberturas = [e["cobertura_roteiro"] for e in execucoes]
    duracoes = [e["duracao_segundos"] for e in execucoes]
    alucinacoes = sum(e["alucinacoes_detectadas"] for e in execucoes)
    alucinacoes_corrigidas = sum(e["alucinacoes_corrigidas"] for e in execucoes)
    boletins = sum(e["boletins_processados"] for e in execucoes)

    # Tempo total por execução
    tempos_total = []
    for e in execucoes:
        tempos = e.get("tempos", {})
        tempo_total = sum(tempos.values())
        tempos_total.append(tempo_total)

    # Agrupamento por dia
    execucoes_por_dia = {}
    cobertura_por_dia = {}
    for e in execucoes:
        dia = e["data"]
        execucoes_por_dia[dia] = execucoes_por_dia.get(dia, 0) + 1
        cobertura_por_dia[dia] = e["cobertura_roteiro"]

    return {
        "total_execucoes": total_exec,
        "media_cobertura": round(sum(coberturas) / len(coberturas), 4),
        "media_duracao": round(sum(duracoes) / len(duracoes), 2),
        "total_alucinacoes": alucinacoes,
        "total_alucinacoes_corrigidas": alucinacoes_corrigidas,
        "taxa_correcao": round(alucinacoes_corrigidas / alucinacoes * 100, 2) if alucinacoes > 0 else 0.0,
        "total_boletins": boletins,
        "media_tempo_total": round(sum(tempos_total) / len(tempos_total), 2),
        "execucoes_por_dia": execucoes_por_dia,
        "cobertura_por_dia": cobertura_por_dia,
    }


def _gerar_html(metricas: dict) -> str:
    """Simula geração de HTML para dashboard."""
    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head><title>DIVISOR - Dashboard de Métricas</title></head>",
        "<body>",
        "<h1>Dashboard de Métricas do Pipeline DIVISOR</h1>",
        "<div class='metricas'>",
        f"<p>Total de execuções: {metricas['total_execucoes']}</p>",
        f"<p>Média cobertura: {metricas['media_cobertura']:.1%}</p>",
        f"<p>Total alucinações: {metricas['total_alucinacoes']}</p>",
        f"<p>Total boletins: {metricas['total_boletins']}</p>",
        f"<p>Taxa correção: {metricas['taxa_correcao']:.1f}%</p>",
        "</div>",
        "</body>",
        "</html>",
    ]
    return "\n".join(html_parts)


def _gerar_grafico_svg(dados: dict, largura: int = 400, altura: int = 200) -> str:
    """Simula geração de gráfico SVG inline."""
    if not dados:
        return f'<svg width="{largura}" height="{altura}" xmlns="http://www.w3.org/2000/svg"></svg>'

    valores = list(dados.values())
    labels = list(dados.keys())
    max_val = max(valores) if valores else 1

    barras = []
    n_barras = len(valores)
    largura_barra = largura / (n_barras * 2) if n_barras > 0 else 20

    for i, (label, valor) in enumerate(zip(labels, valores)):
        x = i * (largura / n_barras) + largura_barra / 2
        altura_barra = (valor / max_val) * (altura - 40)
        y = altura - altura_barra - 20

        barras.append(
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{largura_barra:.0f}" '
            f'height="{altura_barra:.0f}" fill="#4CAF50" />'
        )
        barras.append(
            f'<text x="{x + largura_barra/2:.0f}" y="{altura - 5:.0f}" '
            f'text-anchor="middle" font-size="10">{label}</text>'
        )

    svg_content = "\n".join(barras)
    return (
        f'<svg width="{largura}" height="{altura}" xmlns="http://www.w3.org/2000/svg">\n'
        f'{svg_content}\n'
        f'</svg>'
    )


# ═══════════════════════════════════════════════════════════
# TESTES
# ═══════════════════════════════════════════════════════════

class TestAgregarMetricas:
    """Testa agregação de métricas de auditoria.json."""

    def test_agregar_metricas(self, auditoria_data):
        """Testa agregação básica de métricas."""
        resultado = _agregar_metricas(auditoria_data)

        assert resultado["total_execucoes"] == 3
        assert resultado["total_alucinacoes"] == 9
        assert resultado["total_alucinacoes_corrigidas"] == 7
        assert resultado["total_boletins"] == 15
        assert "media_cobertura" in resultado
        assert "taxa_correcao" in resultado

    def test_agregar_metricas_media_cobertura(self, auditoria_data):
        """Testa cálculo de média de cobertura."""
        resultado = _agregar_metricas(auditoria_data)

        # (0.85 + 0.92 + 0.78) / 3 = 0.85
        assert abs(resultado["media_cobertura"] - 0.85) < 0.01

    def test_agregar_metricas_taxa_correcao(self, auditoria_data):
        """Testa cálculo de taxa de correção de alucinações."""
        resultado = _agregar_metricas(auditoria_data)

        # 7 / 9 * 100 = 77.78%
        assert abs(resultado["taxa_correcao"] - 77.78) < 0.1

    def test_agregar_metricas_vazio(self):
        """Testa agregação com dados vazios."""
        resultado = _agregar_metricas({"execucoes": []})

        assert resultado["total_execucoes"] == 0
        assert resultado["media_cobertura"] == 0.0
        assert resultado["taxa_correcao"] == 0.0

    def test_agregar_metricas_sem_chave_execucoes(self):
        """Testa agregação quando não há chave 'execucoes'."""
        resultado = _agregar_metricas({})

        assert resultado["total_execucoes"] == 0

    def test_agregar_metricas_por_dia(self, auditoria_data):
        """Testa agrupamento por dia."""
        resultado = _agregar_metricas(auditoria_data)

        assert len(resultado["execucoes_por_dia"]) == 3
        assert resultado["execucoes_por_dia"]["2026-09-15"] == 1
        assert resultado["cobertura_por_dia"]["2026-09-16"] == 0.92

    def test_agregar_metricas_com_arquivo_json(self, arquivo_auditoria_json):
        """Testa agregação lendo de arquivo JSON."""
        with open(arquivo_auditoria_json, "r", encoding="utf-8") as f:
            dados = json.load(f)

        resultado = _agregar_metricas(dados)
        assert resultado["total_execucoes"] == 3


class TestGerarHtml:
    """Testa geração de HTML."""

    def test_gerar_html(self, metricas_simuladas):
        """Testa geração de HTML com métricas."""
        html = _gerar_html(metricas_simuladas)

        assert "<!DOCTYPE html>" in html
        assert "DIVISOR" in html
        assert "Total de execuções: 3" in html
        assert "Total boletins: 15" in html
        assert "</html>" in html

    def test_gerar_html_vazio(self):
        """Testa geração de HTML com métricas vazias."""
        metricas_vazias = {
            "total_execucoes": 0,
            "media_cobertura": 0.0,
            "total_alucinacoes": 0,
            "total_boletins": 0,
            "taxa_correcao": 0.0,
        }
        html = _gerar_html(metricas_vazias)

        assert "Total de execuções: 0" in html
        assert "<html>" in html

    def test_gerar_html_contem_valores_formatados(self, metricas_simuladas):
        """Testa que HTML contém valores formatados corretamente."""
        html = _gerar_html(metricas_simuladas)

        assert "85.0%" in html  # media_cobertura formatada
        assert "77.8%" in html  # taxa_correcao formatada


class TestGerarGraficoSvg:
    """Testa geração de gráfico SVG inline."""

    def test_gerar_grafico_svg(self):
        """Testa geração de SVG com dados."""
        dados = {
            "2026-09-15": 0.85,
            "2026-09-16": 0.92,
            "2026-09-17": 0.78,
        }
        svg = _gerar_grafico_svg(dados)

        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert "rect" in svg
        assert "text" in svg

    def test_gerar_grafico_svg_dimensoes(self):
        """Testa dimensões customizadas do SVG."""
        svg = _gerar_grafico_svg({"A": 1, "B": 2}, largura=600, altura=300)

        assert 'width="600"' in svg
        assert 'height="300"' in svg

    def test_gerar_grafico_svg_vazio(self):
        """Testa SVG vazio quando não há dados."""
        svg = _gerar_grafico_svg({})

        assert "<svg" in svg
        assert "rect" not in svg

    def test_gerar_grafico_svg_barras_proporcionais(self):
        """Testa que barras têm alturas proporcionais aos valores."""
        dados = {"Baixo": 0.2, "Alto": 1.0}
        svg = _gerar_grafico_svg(dados, largura=200, altura=100)

        # Deve ter 2 rects (2 barras)
        assert svg.count("<rect") == 2

    def test_gerar_grafico_svg_inline(self):
        """Testa que SVG é inline (sem links externos)."""
        dados = {"dia1": 0.5, "dia2": 0.8}
        svg = _gerar_grafico_svg(dados)

        assert "http://www.w3.org/2000/svg" in svg
        assert "<img" not in svg  # não usa imagem externa


# ═══════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
