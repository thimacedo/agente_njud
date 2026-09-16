#!/usr/bin/env python3
"""
reprocessar_continuar.py — Continua 0704 do ponto onde parou + processa 0801, 0802, 0803.
0704 já tem 7/20 OK; o script pula os OK e continua dos restantes.
As 3 novas semanas (0801/0802/0803) são processadas do zero.
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
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("reprocessar_continuar")

H_BASE = Path("H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO")
ROOT = Path(__file__).resolve().parent.parent

SAIDA_BASE = ROOT / "data" / "processed" / "PRODUCAO_2026"
LOG_BASE = ROOT / "GIRO" / "logs"


def reprocessar(codigo: str, inicio: str, fim: str) -> dict:
    log.info(f"\n{'='*60}")
    log.info(f"  Semana {codigo} ({inicio} → {fim})")
    log.info(f"{'='*60}")

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

    # Conta OK's existentes antes deprocessar
    estado_existente = list(pasta_estado.glob("*.json"))
    ok_existente = sum(
        1 for f in estado_existente
        if json.loads(f.read_text(encoding="utf-8")).get("status") == "OK"
    )
    log.info(f"Estado prévio: {len(estado_existente)} arquivo(s), {ok_existente} OK")

    tarefas = listar_tarefas_pendentes(config)
    log.info(f"Tarefas pendentes de processar: {len(tarefas)}")
    for t in tarefas:
        log.info(f"  → {Path(t['arquivo']).name}")

    if not tarefas:
        log.info("✓ Nada a fazer — todas as tarefas já processadas.")
        return {"codigo": codigo, "status": "concluido", "tarefas_restantes": 0}

    try:
        resultado = processar_lote(config)
        log.info(f"RESULTADO semana {codigo}: {resultado}")
        return {"codigo": codigo, **resultado}
    except Exception as e:
        log.error(f"ERRO fatal na semana {codigo}: {e}")
        import traceback
        traceback.print_exc()
        return {"codigo": codigo, "status": "erro", "erro": str(e)}


def main():
    log.info("=" * 60)
    log.info("  REPROCESSAMENTO CONTÍNUO — 0704 (restante) + 0801 + 0802 + 0803")
    log.info(f"  Font: {H_BASE}")
    log.info("=" * 60)

    semanas = [
        ("0704", "2026-07-17", "2026-07-22"),  # continuar (já tem 7 OK)
        ("0801", "2026-07-31", "2026-08-05"),  # do zero
        ("0802", "2026-08-07", "2026-08-12"),  # do zero
        ("0803", "2026-08-14", "2026-08-19"),  # do zero
    ]

    resultados = []
    for codigo, inicio, fim in semanas:
        r = reprocessar(codigo, inicio, fim)
        resultados.append(r)
        gc.collect()
        time.sleep(5)

    # Resumo final
    log.info(f"\n{'='*60}")
    log.info("  RESUMO FINAL")
    log.info(f"{'='*60}")
    total_ok = sum(r.get("ok", 0) for r in resultados)
    total_esgotado = sum(r.get("esgotado", 0) for r in resultados)
    total_erro = sum(r.get("erro", 0) for r in resultados if r.get("status") == "erro")
    total_concluido = sum(1 for r in resultados if r.get("status") == "concluido")
    total_em_processamento = sum(
        1 for r in resultados if r.get("status") not in ("concluido", "erro")
    )

    log.info(f"Semanas processadas: {len(resultados)}")
    log.info(f"  OK:           {total_ok} novos")
    log.info(f"  ESGOTADO:     {total_esgotado} novos")
    log.info(f"  Concluídas:   {total_concluido}")
    log.info(f"  Erros:        {total_erro}")

    for r in resultados:
        log.info(
            f"  {r['codigo']}: status={r.get('status','?')}, "
            f"ok={r.get('ok',0)}, esgotado={r.get('esgotado',0)}"
        )

    # Salva relatório
    relatorio_path = SAIDA_BASE / "_logs" / "reprocessar_continuar.json"
    relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    relatorio_path.write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    log.info(f"\nRelatório salvo: {relatorio_path}")

    if total_erro > 0:
        log.error("⚠️  Houveram erros no processamento.")
        return 1
    log.info("✓ Todos os processamentos concluídos sem erros.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
