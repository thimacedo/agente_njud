#!/usr/bin/env python3
"""
reprocessar_0704.py — Reprocessa semana 0704 (2026-07-17 → 2026-07-22).
Executa em background, gera logs, e não falha se já existirem estados.
"""
import sys, logging, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.processamento.processar_boletim import ConfigPrograma, processar_lote, listar_tarefas_pendentes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("reprocessar_0704")

H_BASE = Path("H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO")
ROOT = Path(__file__).resolve().parent.parent

codigo = "0704"
inicio = "2026-07-17"
fim = "2026-07-22"

pasta_saida = ROOT / "GIRO" / "output" / codigo
pasta_estado = ROOT / "GIRO" / "state" / codigo
pasta_log = ROOT / "GIRO" / "logs" / codigo

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

log.info(f"=== Reprocessando semana {codigo} ({inicio} → {fim}) ===")
log.info(f"Font: {H_BASE}")
log.info(f"Saida: {pasta_saida}")

tarefas = listar_tarefas_pendentes(config)
log.info(f"Tarefas pendentes: {len(tarefas)}")
for t in tarefas:
    log.info(f"  - {Path(t['arquivo']).name}")

if not tarefas:
    log.info("Nada a fazer — todas as tarefas já processadas ou fora da janela.")
    sys.exit(0)

resultado = processar_lote(config)
log.info(f"RESULTADO FINAL: {resultado}")

total_ok = resultado.get("ok", 0)
total_esgotado = resultado.get("esgotado", 0)
total_erro = resultado.get("erro", 0)

if total_ok > 0 or total_esgotado > 0:
    log.info(f"Concluida: {total_ok} OK, {total_esgotado} ESGOTADO, {total_erro} ERRO")
    sys.exit(0 if total_erro == 0 else 1)
else:
    log.error("Nenhum arquivo processado com sucesso.")
    sys.exit(1)
