#!/usr/bin/env python3
"""
Watcher de montagem automática por NJUD.

Monitora estado_por_arquivo/*.json e, assim que TODOS os boletins de
um NJUD atingem OK ou ESGOTADO_ACEITO, dispara montar_jornal().

Uso:
    python monitor_montagem_auto.py <pasta_saida> [--intervalo 30]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from divisor_boletins.log import LogPipeline
from divisor_boletins.montagem import montar_jornal


def _njuds_completos(pasta_estado: Path) -> dict[str, dict]:
    njuds: dict[str, dict] = {}
    for p_estado in pasta_estado.glob("*.json"):
        try:
            d = json.loads(p_estado.read_text(encoding="utf-8"))
        except Exception:
            continue
        njud = d.get("njud", "?")
        status = d.get("status", "PENDENTE")
        njuds.setdefault(njud, {"total": 0, "concluidos": 0})
        njuds[njud]["total"] += 1
        if status in ("OK", "ESGOTADO_ACEITO"):
            njuds[njud]["concluidos"] += 1
    return njuds


def executar(pasta_saida: Path, intervalo: int = 30) -> None:
    pasta_estado = pasta_saida / "estado_por_arquivo"
    pasta_cortes = pasta_saida / "JORNAIS_DIVIDIDOS"
    pasta_jornais = pasta_saida / "JORNAIS_FINAL"
    pasta_jornais.mkdir(parents=True, exist_ok=True)

    logger = LogPipeline(pasta_saida / "_logs")
    montados: set[str] = set()

    print(f"[montagem_auto] Monitorando {pasta_estado} a cada {intervalo}s.")
    while True:
        try:
            njuds = _njuds_completos(pasta_estado)
            prontos = [
                njud
                for njud, info in sorted(njuds.items())
                if info["total"] > 0 and info["concluidos"] == info["total"]
                and njud not in montados
            ]

            for njud in prontos:
                pasta_njud = pasta_cortes / njud
                if not pasta_njud.is_dir():
                    print(f"[montagem_auto] ⚠ cortes de {njud} não encontrados.")
                    continue

                print(f"[montagem_auto] Montando NJUD completo: {njud}")
                try:
                    resultado = montar_jornal(
                        pasta_njud,
                        pasta_jornais,
                        logger,
                        nome_jornal=njud.replace(" ", "_"),
                    )
                    if resultado:
                        montados.add(njud)
                        print(f"[montagem_auto] ✓ {Path(resultado).name}")
                    else:
                        print(f"[montagem_auto] ✖ montagem falhou para {njud}")
                except Exception as e:
                    print(f"[montagem_auto] ✖ erro em {njud}: {e}")
        except KeyboardInterrupt:
            print("\n[montagem_auto] Encerrado pelo operador.")
            raise
        except Exception as e:
            print(f"[montagem_auto] Falha no ciclo: {e}")

        time.sleep(intervalo)


def main() -> None:
    parser = argparse.ArgumentParser(description="Montagem automática por NJUD completo.")
    parser.add_argument("pasta_saida", help="Pasta raiz do pipeline/estado")
    parser.add_argument("--intervalo", type=int, default=30, help="Segundos entre checagens")
    args = parser.parse_args()

    executar(Path(args.pasta_saida), intervalo=args.intervalo)


if __name__ == "__main__":
    main()
