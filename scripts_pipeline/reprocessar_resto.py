#!/usr/bin/env python3
"""
reprocessar_resto.py — Reprocessa as 4 semanas GIRO restantes (0704, 0801, 0802, 0803).
Usa a correção de data por pasta para contornar o bug de naming dos boletins.
"""
from __future__ import annotations

import sys
import json
import logging
import time
import gc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.processamento.processar_boletim import ConfigPrograma, processar_lote, listar_tarefas_pendentes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("reprocessar_resto")

H_BASE = Path("H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO")
ROOT = Path(__file__).resolve().parent.parent

SAIDA_BASE = ROOT / "data" / "processed" / "PRODUCAO_2026"
LOG_BASE = ROOT / "GIRO" / "logs"

# 4 semanas que ainda estão vazias
SEMANAS = [
    ("0704", "2026-07-17", "2026-07-22"),
    ("0801", "2026-07-31", "2026-08-05"),
    ("0802", "2026-08-07", "2026-08-12"),
    ("0803", "2026-08-14", "2026-08-19"),
]


def reprocessar(codigo: str, inicio: str, fim: str) -> dict:
    log.info(f"=== Processando semana {codigo} ({inicio} → {fim}) ===")

    pasta_saida = ROOT / "GIRO" / "output" / codigo
    pasta_estado = ROOT / "GIRO" / "state" / codigo
    pasta_log = LOG_BASE / codigo

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

    tarefas = listar_tarefas_pendentes(config)
    log.info(f"Tarefas pendentes: {len(tarefas)}")
    for t in tarefas:
        log.info(f"  - {Path(t['arquivo']).name}")

    if not tarefas:
        log.info("Nada a fazer — todas as tarefas já processadas ou fora da janela.")
        return {"codigo": codigo, "status": "no_tasks", "total": 0, "ok": 0, "esgotado": 0, "erro": 0}

    try:
        resultado = processar_lote(config)
        log.info(f"RESULTADO: {resultado}")
        return {"codigo": codigo, **resultado}
    except Exception as e:
        log.error(f"ERRO fatal na semana {codigo}: {e}")
        import traceback
        traceback.print_exc()
        return {"codigo": codigo, "status": "erro", "erro": str(e)}


def main():
    log.info("=== REPROCESSAMENTO DAS 4 SEMANAS GIRO RESTANTES ===")
    log.info(f"Font: {H_BASE}")

    resultados = []
    for codigo, inicio, fim in SEMANAS:
        r = reprocessar(codigo, inicio, fim)
        resultados.append(r)
        gc.collect()
        time.sleep(5)  # Breve pausa entre semanas

    # Resumo
    log.info("")
    log.info("=== RESUMO FINAL ===")
    total_ok = sum(r.get("ok", 0) for r in resultados)
    total_esgotado = sum(r.get("esgotado", 0) for r in resultados)
    total_erro = sum(r.get("erro", 0) for r in resultados if r.get("status") == "erro")
    total_nada = sum(1 for r in resultados if r.get("status") == "no_tasks")

    log.info(f"Total semanas: {len(resultados)}")
    log.info(f"OK: {total_ok} arquivos")
    log.info(f"ESGOTADO: {total_esgotado} arquivos")
    log.info(f"ERRO: {total_erro} semanas")
    log.info(f"NADA (sem tarefas): {total_nada} semanas")

    for r in resultados:
        log.info(f"  {r['codigo']}: {r.get('status', '?')} (ok={r.get('ok',0)}, esgotado={r.get('esgotado',0)})")

    # Salva relatório
    relatorio_path = SAIDA_BASE / "_logs" / "reprocessar_resto.json"
    relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    relatorio_path.write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    log.info(f"Relatório salvo: {relatorio_path}")

    return 0 if total_erro == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
