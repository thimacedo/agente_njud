#!/usr/bin/env python3
"""
reprocessar_0303.py — Reprocessa os 6 ERROs de 0303.
O script ignora estados OK/ESGOTADO e apenas reprocessa os falhos.
"""
from __future__ import annotations

import sys, json, logging, gc, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core.processamento.processar_boletim import ConfigPrograma, processar_lote

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("reprocessar_0303")

H_BASE = Path("H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO")
ROOT = Path(__file__).resolve().parent.parent
LOG_BASE = ROOT / "GIRO" / "logs"

def main():
    log.info("=" * 60)
    log.info("  REPROCESSAR 0303 — 6 arquivos com ERRO")
    log.info(f"  Font: {H_BASE}")
    log.info("=" * 60)

    pasta_saida = ROOT / "GIRO" / "output" / "0303"
    pasta_estado = ROOT / "GIRO" / "state" / "0303"
    pasta_log = LOG_BASE / "0303"
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
        data_inicio_coleta="2026-03-13",
        data_fim_coleta="2026-03-18",
    )

    # Listar apenas os erros
    estado_dir = pasta_estado
    erros = []
    for f in sorted(estado_dir.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("status") == "ERRO":
            erros.append((f.name, d))

    log.info(f"Encontrados {len(erros)} ERROs para reprocessar:")
    for nome, d in erros:
        log.info(f"  → {nome}")
        log.info(f"    arquivo: {d.get('arquivo', 'N/A')}")

    if not erros:
        log.info("Nada a fazer — nenhum ERRO encontrado.")
        return 0

    # Recriar configuração para reprocessar
    config.pasta_estado.mkdir(parents=True, exist_ok=True)
    config.pasta_log.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n[processamento] Carregando modelo Whisper ({config.modelo_whisper}, {config.compute_type})...")
    modelo = __import__("core.processamento.processar_boletim", fromlist=["carregar_modelo"]).carregar_modelo()
    print("[processamento] Modelo carregado.")

    resultados = {"total": len(erros), "ok": 0, "esgotado": 0, "erro": 0}

    for idx, (nome, d) in enumerate(erros):
        arquivo = d.get("arquivo", "")
        print(f"\n[{idx+1}/{len(erros)}] {Path(arquivo).name}")

        try:
            from core.processamento.processar_boletim import processar_um_arquivo, LogPipeline
            logger = LogPipeline(pasta_log)
            estado = processar_um_arquivo(arquivo, config, modelo, logger)
            print(f"  -> {estado.status}")
            if estado.status == "OK":
                resultados["ok"] += 1
            elif estado.status == "ESGOTADO":
                resultados["esgotado"] += 1
            else:
                resultados["erro"] += 1
        except Exception as exc:
            print(f"  -> ERRO: {exc}")
            resultados["erro"] += 1

        gc.collect()

    print(f"\n=== CONCLUÍDO (giro/0303) ===")
    print(json.dumps(resultados, indent=2))

    log.info(f"Resultado: {resultados}")
    return 0 if resultados["erro"] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
