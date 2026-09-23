#!/usr/bin/env python3
"""
metricas_dashboard.py — Gera HTML com histórico de qualidade dos boletins.

Uso:
    from shared.agentes.metricas_dashboard import dashboard

    dashboard(pasta_boletins="/path/boletins", output_path="/path/dashboard.html")
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Adiciona raiz do projeto ao path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from shared.logging_config import get_logger

logger = get_logger("metricas_dashboard")

# ── Constantes ───────────────────────────────────────────────────────────────

COBERTURA_MINIMA = 0.60
APROVACAO_MINIMA = 0.80
DEGRADACAO_THRESHOLD = 0.10  # Queda de 10% é alerta


def agregar_metricas(pasta_boletins: Path) -> dict:
    """
    Lê todos auditoria.json recursivamente e agrega métricas (cobertura, aprovação).

    Args:
        pasta_boletins: Pasta raiz onde buscar auditoria.json.

    Returns:
        Dict com métricas agregadas e histórico.
    """
    pasta_boletins = Path(pasta_boletins)
    historico = []
    batches = []

    if not pasta_boletins.exists():
        logger.warning(f"Pasta não encontrada: {pasta_boletins}")
        return _metricas_vazias()

    # Buscar todos os auditoria.json recursivamente
    for auditoria_path in pasta_boletins.rglob("auditoria.json"):
        try:
            with open(auditoria_path, "r", encoding="utf-8") as f:
                dados = json.load(f)

            entrada = {
                "arquivo": str(auditoria_path),
                "cobertura": dados.get("cobertura", dados.get("cobertura_roteiro", 0.0)),
                "aprovacao": dados.get("aprovacao", dados.get("taxa_aprovacao", 0.0)),
                "timestamp": dados.get("timestamp", dados.get("data", "")),
                "boletim": dados.get("boletim", dados.get("nome", auditoria_path.parent.name)),
                "status": dados.get("status", "desconhecido"),
            }

            # Extrair data para ordenação
            try:
                if entrada["timestamp"]:
                    entrada["data_dt"] = datetime.fromisoformat(
                        entrada["timestamp"].replace("Z", "+00:00")
                    )
                else:
                    entrada["data_dt"] = datetime.fromtimestamp(
                        auditoria_path.stat().st_mtime
                    )
            except (ValueError, TypeError):
                entrada["data_dt"] = datetime.fromtimestamp(
                    auditoria_path.stat().st_mtime
                )

            historico.append(entrada)
            batches.append(entrada)

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Erro ao ler {auditoria_path}: {e}")

    # Ordenar por data
    historico.sort(key=lambda x: x.get("data_dt", datetime.min))

    # Calcular métricas agregadas
    if historico:
        coberturas = [h["cobertura"] for h in historico if h["cobertura"] > 0]
        aprovacoes = [h["aprovacao"] for h in historico if h["aprovacao"] > 0]

        metricas = {
            "total_boletins": len(historico),
            "cobertura_media": sum(coberturas) / len(coberturas) if coberturas else 0.0,
            "cobertura_min": min(coberturas) if coberturas else 0.0,
            "cobertura_max": max(coberturas) if coberturas else 0.0,
            "aprovacao_media": sum(aprovacoes) / len(aprovacoes) if aprovacoes else 0.0,
            "aprovacao_min": min(aprovacoes) if aprovacoes else 0.0,
            "aprovacao_max": max(aprovacoes) if aprovacoes else 0.0,
            "historico": historico,
            "batches": batches,
            "alertas": _detectar_alertas(historico),
        }
    else:
        metricas = _metricas_vazias()

    logger.info(f"Métricas agregadas: {metricas['total_boletins']} boletins")
    return metricas


def _metricas_vazias() -> dict:
    """Retorna estrutura de métricas vazia."""
    return {
        "total_boletins": 0,
        "cobertura_media": 0.0,
        "cobertura_min": 0.0,
        "cobertura_max": 0.0,
        "aprovacao_media": 0.0,
        "aprovacao_min": 0.0,
        "aprovacao_max": 0.0,
        "historico": [],
        "batches": [],
        "alertas": [],
    }


def _detectar_alertas(historico: list) -> list[dict]:
    """Detecta degradação de qualidade no histórico."""
    alertas = []

    if len(historico) < 2:
        return alertas

    # Verificar queda de cobertura
    for i in range(1, len(historico)):
        cobertura_atual = historico[i]["cobertura"]
        cobertura_anterior = historico[i - 1]["cobertura"]

        if cobertura_anterior > 0:
            queda = cobertura_anterior - cobertura_atual
            if queda >= DEGRADACAO_THRESHOLD:
                alertas.append({
                    "tipo": "degradacao_cobertura",
                    "severidade": "alta" if queda >= 0.20 else "media",
                    "mensagem": f"Queda de cobertura: {cobertura_anterior:.0%} → {cobertura_atual:.0%}",
                    "boletim": historico[i].get("boletim", "desconhecido"),
                })

    # Verificar cobertura abaixo do mínimo
    for h in historico[-5:]:  # últimos 5
        if 0 < h["cobertura"] < COBERTURA_MINIMA:
            alertas.append({
                "tipo": "cobertura_baixa",
                "severidade": "alta",
                "mensagem": f"Cobertura abaixo do mínimo: {h['cobertura']:.0%}",
                "boletim": h.get("boletim", "desconhecido"),
            })

    return alertas


def gerar_grafico_cobertura(historico: list) -> str:
    """
    Gera gráfico de linha temporal como SVG inline (stdlib only, sem matplotlib).

    Args:
        historico: Lista de dicts com 'data_dt' e 'cobertura'.

    Returns:
        String SVG inline.
    """
    if not historico:
        return '<svg width="600" height="200" xmlns="http://www.w3.org/2000/svg"><text x="300" y="100" text-anchor="middle" fill="#666">Sem dados disponíveis</text></svg>'

    # Dimensões
    largura = 600
    altura = 200
    padding = 50
    largura_grafico = largura - 2 * padding
    altura_grafico = altura - 2 * padding

    # Dados
    pontos = [(h.get("data_dt", datetime.min), h.get("cobertura", 0)) for h in historico]
    pontos = [(d, c) for d, c in pontos if c > 0]

    if not pontos:
        return '<svg width="600" height="200" xmlns="http://www.w3.org/2000/svg"><text x="300" y="100" text-anchor="middle" fill="#666">Sem dados de cobertura</text></svg>'

    # Escala
    min_cobertura = min(c for _, c in pontos)
    max_cobertura = max(c for _, c in pontos)
    # Margem na escala
    y_min = max(0, min_cobertura - 0.1)
    y_max = min(1.0, max_cobertura + 0.1)
    y_range = y_max - y_min if y_max > y_min else 1.0

    # Gerar pontos da linha
    svg_pontos = []
    for i, (data, cobertura) in enumerate(pontos):
        x = padding + (i / max(1, len(pontos) - 1)) * largura_grafico
        y = padding + altura_grafico - ((cobertura - y_min) / y_range) * altura_grafico
        svg_pontos.append(f"{x:.1f},{y:.1f}")

    # Linha de referência (COBERTURA_MINIMA)
    y_ref = padding + altura_grafico - ((COBERTURA_MINIMA - y_min) / y_range) * altura_grafico

    # Construir SVG
    svg = f'''<svg viewBox="0 0 {largura} {altaura}" xmlns="http://www.w3.org/2000/svg" class="grafico-cobertura">
  <!-- Fundo -->
  <rect x="0" y="0" width="{largura}" height="{altura}" fill="#fafafa" rx="8"/>

  <!-- Grid horizontal -->
  <line x1="{padding}" y1="{padding}" x2="{padding}" y2="{padding + altura_grafico}" stroke="#e0e0e0" stroke-width="1"/>
  <line x1="{padding}" y1="{padding + altura_grafico}" x2="{largura - padding}" y2="{padding + altura_grafico}" stroke="#e0e0e0" stroke-width="1"/>
  <line x1="{padding}" y1="{padding + altura_grafico / 2}" x2="{largura - padding}" y2="{padding + altura_grafico / 2}" stroke="#eee" stroke-width="1" stroke-dasharray="4"/>

  <!-- Linha de referência (mínimo) -->
  <line x1="{padding}" y1="{y_ref:.1f}" x2="{largura - padding}" y2="{y_ref:.1f}" stroke="#e74c3c" stroke-width="1" stroke-dasharray="6,3" opacity="0.7"/>
  <text x="{largura - padding + 5}" y="{y_ref + 4}" font-size="10" fill="#e74c3c">mín. {COBERTURA_MINIMA:.0%}</text>

  <!-- Linha de cobertura -->
  <polyline points="{' '.join(svg_pontos)}" fill="none" stroke="#2ecc71" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>

  <!-- Pontos -->
'''

    for i, (px, py) in enumerate(svg_pontos):
        x, y = px.split(",")
        cobertura = pontos[i][1]
        svg += f'  <circle cx="{float(x):.1f}" cy="{float(y):.1f}" r="4" fill="#27ae60" stroke="#fff" stroke-width="1.5"/>\n'
        svg += f'  <title>{pontos[i][0].strftime("%Y-%m-%d")}: {cobertura:.1%}</title>\n'

    # Labels Y
    svg += f'  <text x="{padding - 8}" y="{padding + 4}" font-size="10" fill="#666" text-anchor="end">{y_max:.0%}</text>\n'
    svg += f'  <text x="{padding - 8}" y="{padding + altura_grafico + 4}" font-size="10" fill="#666" text-anchor="end">{y_min:.0%}</text>\n'

    # Título
    svg += f'  <text x="{largura / 2}" y="20" font-size="13" font-weight="bold" fill="#333" text-anchor="middle">Cobertura ao longo do tempo</text>\n'

    svg += '</svg>'
    return svg


def gerar_html(metricas: dict) -> str:
    """
    Gera página HTML completa self-contained (CSS inline), responsivo.

    Args:
        metricas: Dict com métricas agregadas.

    Returns:
        String HTML completo.
    """
    historico = metricas.get("historico", [])
    alertas = metricas.get("alertas", [])

    # Gerar gráfico
    grafico_svg = gerar_grafico_cobertura(historico)

    # Tabela de últimos batches
    tabela_rows = ""
    for h in reversed(historico[-10:]):
        cobertura_class = "ok" if h["cobertura"] >= COBERTURA_MINIMA else "baixa"
        tabela_rows += f"""
        <tr>
            <td>{h.get('boletim', 'N/A')}</td>
            <td>{h.get('data_dt', datetime.now()).strftime('%Y-%m-%d %H:%M') if isinstance(h.get('data_dt'), datetime) else 'N/A'}</td>
            <td class="{cobertura_class}">{h['cobertura']:.1%}</td>
            <td>{h['aprovacao']:.1%}</td>
            <td>{h.get('status', '-')}</td>
        </tr>"""

    # Alertas
    alertas_html = ""
    if alertas:
        for alerta in alertas:
            severidade_class = alerta.get("severidade", "media")
            alertas_html += f"""
            <div class="alerta {severidade_class}">
                <strong>⚠ {alerta['tipo'].replace('_', ' ').title()}</strong>
                <p>{alerta['mensagem']} — {alerta.get('boletim', '')}</p>
            </div>"""
    else:
        alertas_html = '<p class="sem-alertas">✓ Nenhum alerta de degradação detectado.</p>'

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DIVISOR — Dashboard de Qualidade</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f6fa;
            color: #333;
            line-height: 1.6;
        }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
        header {{
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 24px;
        }}
        header h1 {{ font-size: 1.5em; margin-bottom: 4px; }}
        header p {{ opacity: 0.8; font-size: 0.9em; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            text-align: center;
        }}
        .card .valor {{ font-size: 2em; font-weight: bold; color: #2ecc71; }}
        .card .valor.baixo {{ color: #e74c3c; }}
        .card .label {{ font-size: 0.85em; color: #666; margin-top: 4px; }}
        .grafico-container {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 24px;
            overflow-x: auto;
        }}
        .grafico-cobertura {{ width: 100%; height: auto; max-height: 250px; }}
        .tabela-container {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 24px;
            overflow-x: auto;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #555; }}
        td.ok {{ color: #27ae60; font-weight: 600; }}
        td.baixa {{ color: #e74c3c; font-weight: 600; }}
        .alertas {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 24px;
        }}
        .alerta {{ padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid; }}
        .alerta.alta {{ background: #fde8e8; border-color: #e74c3c; }}
        .alerta.media {{ background: #fef3cd; border-color: #f39c12; }}
        .sem-alertas {{ color: #27ae60; padding: 12px; }}
        footer {{ text-align: center; color: #999; font-size: 0.8em; padding: 20px; }}
        @media (max-width: 600px) {{
            .cards {{ grid-template-columns: 1fr 1fr; }}
            .card .valor {{ font-size: 1.5em; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 DIVISOR — Dashboard de Qualidade</h1>
            <p>Histórico de cobertura e aprovação dos boletins gerados</p>
        </header>

        <div class="cards">
            <div class="card">
                <div class="valor {'baixo' if metricas['cobertura_media'] < COBERTURA_MINIMA else ''}">
                    {metricas['cobertura_media']:.1%}
                </div>
                <div class="label">Cobertura Média</div>
            </div>
            <div class="card">
                <div class="valor {'baixo' if metricas['aprovacao_media'] < APROVACAO_MINIMA else ''}">
                    {metricas['aprovacao_media']:.1%}
                </div>
                <div class="label">Taxa de Aprovação</div>
            </div>
            <div class="card">
                <div class="valor">{metricas['total_boletins']}</div>
                <div class="label">Total de Boletins</div>
            </div>
            <div class="card">
                <div class="valor {'baixo' if len(alertas) > 0 else ''}">{len(alertas)}</div>
                <div class="label">Alertas Ativos</div>
            </div>
        </div>

        <div class="grafico-container">
            {grafico_svg}
        </div>

        <div class="alertas">
            <h2 style="margin-bottom: 12px;">🚨 Alertas de Degradação</h2>
            {alertas_html}
        </div>

        <div class="tabela-container">
            <h2 style="margin-bottom: 12px;">📋 Últimos Batches</h2>
            <table>
                <thead>
                    <tr>
                        <th>Boletim</th>
                        <th>Data</th>
                        <th>Cobertura</th>
                        <th>Aprovação</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {tabela_rows if tabela_rows else '<tr><td colspan="5" style="text-align:center;color:#999;">Sem dados</td></tr>'}
                </tbody>
            </table>
        </div>

        <footer>
            <p>Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — Pipeline DIVISOR</p>
        </footer>
    </div>
</body>
</html>"""

    return html


def dashboard(pasta_boletins: Path, output_path: Path) -> dict:
    """
    Pipeline completo: agrega métricas e gera HTML.

    Args:
        pasta_boletins: Pasta com boletins e auditoria.json.
        output_path: Caminho do HTML de saída.

    Returns:
        Dict com status e informações.
    """
    pasta_boletins = Path(pasta_boletins)
    output_path = Path(output_path)

    resultado = {
        "status": "pendente",
        "metricas": None,
        "output": None,
        "erros": [],
    }

    try:
        # Agregar métricas
        logger.info(f"Agregando métricas de: {pasta_boletins}")
        metricas = agregar_metricas(pasta_boletins)
        resultado["metricas"] = {
            "total_boletins": metricas["total_boletins"],
            "cobertura_media": metricas["cobertura_media"],
            "aprovacao_media": metricas["aprovacao_media"],
            "alertas": len(metricas["alertas"]),
        }

        # Gerar HTML
        html = gerar_html(metricas)

        # Salvar
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        resultado["status"] = "sucesso"
        resultado["output"] = str(output_path)
        logger.info(f"Dashboard gerado: {output_path}")

    except Exception as e:
        resultado["status"] = "erro"
        resultado["erros"].append(str(e))
        logger.error(f"Erro ao gerar dashboard: {e}")

    return resultado


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Dashboard de métricas DIVISOR")
    parser.add_argument("pasta_boletins", type=Path, help="Pasta de boletins")
    parser.add_argument("--output", type=Path, default=Path("dashboard.html"))

    args = parser.parse_args()

    from shared.logging_config import setup_logging
    setup_logging(level="INFO")

    resultado = dashboard(args.pasta_boletins, args.output)
    print(f"Resultado: {resultado}")
