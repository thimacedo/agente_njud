# coding: utf-8
"""
Plano de alocação do GIRO nas Comarcas.

Gera o plano de programas mmss com mapeamento para pasta de boletins
e persiste em CSV para uso pelo pipeline de processamento.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from .config import DIR_PLANOS
from .utils import gerar_plano, mes_dos_boletins, semanaisoa_das_notícias, terça_do_programa


def gerar_plano_csv(
    ano: int = 2026,
    caminho: Optional[Path] = None,
) -> Path:
    """Gera o CSV de plano do GIRO e o salva em disco.

    Args:
        ano: ano a planejar (default: 2026)
        caminho: caminho opcional do CSV (default: DIR_PLANOS/plano_giro_<ano>.csv)

    Returns:
        Path do CSV gerado
    """
    if caminho is None:
        caminho = DIR_PLANOS / f"plano_giro_{ano}.csv"

    planos = gerar_plano(ano)

    pasta = caminho.parent
    pasta.mkdir(parents=True, exist_ok=True)

    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "mmss",
            "data_terça",
            "seg_notícias",
            "dom_notícias",
            "mes_boletim",
            "n_noticias_previsto",
        ])
        for p in planos:
            writer.writerow([
                p["mmss"],
                p["data_terça"],
                p["seg_notícias"],
                p["dom_notícias"],
                p["mes_boletim"],
                p["n_noticias_previsto"],
            ])

    return caminho


def ler_plano_csv(caminho: Path) -> list[dict]:
    """Lê o CSV de plano e retorna lista de dicts."""
    import csv
    planos = []
    with open(caminho, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            planos.append({
                "mmss": row["mmss"],
                "data_terça": row["data_terça"],
                "seg_notícias": row["seg_notícias"],
                "dom_notícias": row["dom_notícias"],
                "mes_boletim": int(row["mes_boletim"]),
                "n_noticias_previsto": row["n_noticias_previsto"],
            })
    return planos


# ===========================================================================
# MAIN
# ===========================================================================

if __name__ == "__main__":
    import sys

    ano = 2026
    if len(sys.argv) > 1:
        try:
            ano = int(sys.argv[1])
        except ValueError:
            print(f"Ano inválido: {sys.argv[1]}")
            sys.exit(1)

    caminho = gerar_plano_csv(ano)
    print(f"Plano gerado: {caminho}")
    print(f"Programas: {sum(1 for _ in gerar_plano(ano))} linhas")
    print()
    print("Preview (primeiros 8 programas):")
    for p in gerar_plano(ano)[:8]:
        print(
            f"  {p['mmss']} | terça={p['data_terça']} | "
            f"notícias={p['seg_notícias']}→{p['dom_notícias']} | "
            f"boletins-mes={p['mes_boletim']}"
        )
