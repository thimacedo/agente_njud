#!/usr/bin/env python3
"""
 reprocessar_semanas_giro.py — Reprocessa as 7 semanas GIRO que falharam.
Executa o pipeline para cada semana usando a correção do fallback de data.
"""
from __future__ import annotations

import sys
import json
import logging
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.processamento.processar_boletim import ConfigPrograma, processar_lote

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("reprocessar_semanas")

# Define as 7 semanas problemáticas
SEMANAS = [
    ("0604", "2026-06-19", "2026-06-24"),
    ("0702", "2026-07-03", "2026-07-08"),
    ("0703", "2026-07-10", "2026-07-15"),
    ("0704", "2026-07-17", "2026-07-22"),
    ("0801", "2026-07-31", "2026-08-05"),
    ("0802", "2026-08-07", "2026-08-12"),
    ("0803", "2026-08-14", "2026-08-19"),
]

H_BASE = Path("H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO")
ROOT = Path(__file__).resolve().parent.parent
SAIDA_BASE = ROOT / "data" / "processed" / "PRODUCAO_2026"

def reprocessar_semana(codigo: str, inicio: str, fim: str) -> dict:
    """Reprocessa uma semana específica."""
    log.info(f"=== Processando semana {codigo} ({inicio} → {fim}) ===")

    pasta_saida = ROOT / "GIRO" / "output" / codigo
    pasta_estado = ROOT / "GIRO" / "state" / codigo
    pasta_log = ROOT / "GIRO" / "logs" / codigo

    # Garante que as pastas existem
    for p in [pasta_saida, pasta_estado, pasta_log]:
        p.mkdir(parents=True, exist_ok=True)

    config = ConfigPrograma(
        nome="giro",
        pasta_boletins=H_BASE,
        pasta_saida=pasta_saida,
        pasta_estado=pasta_estado,
        pasta_log=pasta_log,
        modelo_whisper="tiny",
        compute_type="int8",
        roteiro_corte="GIRO_CABEÇA_CORPO",
        minimo_boletins_para_montar=4,
        max_boletins_por_programa=10,
        usar_separacao_stems=False,
        data_inicio_coleta=inicio,
        data_fim_coleta=fim,
    )

    try:
        resultado = processar_lote(config)
        log.info(f"Semana {codigo}: concluída — {resultado}")
        return {"codigo": codigo, "status": "ok", "resultado": resultado}
    except Exception as e:
        log.error(f"Semana {codigo}: ERRO — {e}")
        import traceback
        traceback.print_exc()
        return {"codigo": codigo, "status": "erro", "erro": str(e)}


def main():
    log.info("=== REPROCESSAMENTO DAS 7 SEMANAS GIRO ===")
    log.info(f"Font: {H_BASE}")

    results = []
    for codigo, inicio, fim in SEMANAS:
        r = reprocessar_semana(codigo, inicio, fim)
        results.append(r)
        # Pequeno delay entre semanas para não sobrecarregar
        import time
        time.sleep(2)

    # Resumo final
    log.info("")
    log.info("=== RESUMO FINAL ===")
    ok = sum(1 for r in results if r["status"] == "ok")
    fail = sum(1 for r in results if r["status"] == "erro")
    log.info(f"Total: {len(results)} | OK: {ok} | Falha: {fail}")

    for r in results:
        log.info(f"  {r['codigo']}: {r['status']}")
        if r["status"] == "erro":
            log.info(f"    Erro: {r.get('erro', 'desconhecido')[:200]}")

    # Salva relatório
    relatorio_path = SAIDA_BASE / "_logs" / "reprocessamento_semanas.json"
    relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    relatorio_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    log.info(f"Relatório salvo em: {relatorio_path}")

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
