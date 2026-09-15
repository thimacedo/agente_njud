#!/usr/bin/env python3
"""reprocessar_0802_0803.py — Reprocessa 0802 (apenas B9) + 0803 (B6-B10)."""
from __future__ import annotations

import sys, json, logging, gc, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core.processamento.processar_boletim import ConfigPrograma, processar_lote

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("reprocessar_0802_0803")

H_BASE = Path("H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO")
ROOT = Path(__file__).resolve().parent.parent
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

    tarefas = processar_lote(config)
    log.info(f"Tarefas pendentes: {len(tarefas)}")
    if not tarefas:
        return {"codigo": codigo, "status": "ja_processado", "tarefas": 0}
    log.info(f"Processando {len(tarefas)} tarefas...")
    resultado = processar_lote(config)
    log.info(f"Resultado: {resultado}")
    return {"codigo": codigo, **resultado}

def main():
    log.info("=" * 60)
    log.info("  REPROCESSAMENTO: 0802 (B9) + 0803 (B6-B10)")
    log.info("=" * 60)

    # 0802: B9 já teve 1 ESGOTADO + 30 OK. Faltando B9 completo (3 arquivos: CABEÇA+CORPO+CORTES).
    # O script retoma — listar_tarefas_pendentes ignora OK/ESGOTADO existentes, então só processa os faltantes.
    resultados = []
    
    semanas = [
        ("0802", "2026-08-07", "2026-08-12"),  # B9 terá faltante
        ("0803", "2026-08-14", "2026-08-19"),  # B6-B10 totalmente faltando
    ]
    
    for codigo, inicio, fim in semanas:
        try:
            r = reprocessar(codigo, inicio, fim)
            resultados.append(r)
        except Exception as e:
            log.error(f"ERRO fatal em {codigo}: {e}")
            import traceback
            traceback.print_exc()
            resultados.append({"codigo": codigo, "status": "erro", "erro": str(e)})
        gc.collect()
        time.sleep(3)
    
    log.info(f"\n{'='*60}")
    log.info("  RESUMO")
    log.info(f"{'='*60}")
    for r in resultados:
        log.info(f"  {r['codigo']}: {r.get('status','?')}, ok={r.get('ok',0)}, esgotado={r.get('esgotado',0)}, erro={r.get('erro',0)}")
    
    erros = sum(1 for r in resultados if r.get('status') == 'erro')
    return 1 if erros > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
