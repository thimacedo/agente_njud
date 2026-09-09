#!/usr/bin/env python3
"""
Orquestrador do GIRO — Janeiro 2026.

Lê os JSONs de planejamento de janeiro, verifica quais têm
boletins disponíveis e executa os viáveis usando o executor único
via subprocess (evita problemas de importação de módulos).

Invalida programas sem boletins suficientes e reporta o resultado.

Uso:
    python scripts_pipeline/orquestrador_giro_jan2026.py
"""
from __future__ import annotations

import glob
import json
import logging
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent  # /e/.../DIVISOR
sys.path.insert(0, str(ROOT / "src"))

PLAN_DIR = ROOT / "config" / "planejamento_2026"
BOLETINS_DIR = ROOT / "JORNAIS"
SAIDA_DIR = ROOT / "data" / "processed" / "PRODUCAO_2026"
EXECUTOR_SCRIPT = ROOT / "scripts_pipeline" / "executar_programa.py"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("orquestrador_giro_jan2026")

# -------------------------------------------------------------------
# Dados do mês
# -------------------------------------------------------------------
MES = 1
ANO = 2026
MIN_BOLETINS = 4


def count_boletins(inicio: date, fim: date, diretorio_boletins: Path = BOLETINS_DIR) -> int:
    """Conta arquivos mp3 nos dias da janela (recursivo em JORNAIS/)."""
    total = 0
    for i in range((fim - inicio).days + 1):
        dia = inicio + timedelta(days=i)
        pat = f"**/*_{dia.day:02d}_{dia.month:02d}_{dia.year}_*.mp3"
        total += len(glob.glob(str(diretorio_boletins / pat), recursive=True))
    return total


def load_plan(codigo: str) -> dict:
    """Carrega o JSON de planejamento do programa."""
    path = PLAN_DIR / f"giro_{codigo}.json"
    if not path.exists():
        log.error("JSON não encontrado: %s", path)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    log.info("=== ORQUESTRADOR GIRO JA/2026 INICIADO ===")

    # Descobre todos os planejamentos de janeiro
    jsons = sorted(PLAN_DIR.glob("giro_01*.json"))
    log.info("Encontrados %d planejamento(s) para janeiro", len(jsons))

    resultados: dict[str, list] = {
        "executados": [],
        "invalidados": [],
        "erro": [],
    }

    for j in jsons:
        json_path = j  # Path do JSON
        dado = json.loads(json_path.read_text(encoding="utf-8"))
        codigo = dado["codigo"]
        data_pub = dado["data_exibicao"]
        janela = dado["janela_coleta"]
        params = dado.get("parametros", {})
        minimo = params.get("boletins_minimos", MIN_BOLETINS)

        inicio = date.fromisoformat(janela["inicio"])
        fim = date.fromisoformat(janela["fim"])
        dias = (fim - inicio).days + 1

        log.info("-" * 60)
        log.info("Programa: GIRO %s  |  Exibição: %s", codigo, data_pub)
        log.info("Janela coleta: %s → %s  (%d dias)", janela["inicio"], janela["fim"], dias)

        n_boletins = count_boletins(inicio, fim)
        log.info("Boletins disponíveis na janela: %d  (mínimo: %d)", n_boletins, minimo)

        if n_boletins < minimo:
            log.warning(
                "❌ GIRO %s INVALIDADO — %d boletins < %d mínimos. "
                "Pular este programa.",
                codigo, n_boletins, minimo,
            )
            resultados["invalidados"].append(
                {"codigo": codigo, "motivo": f"boletins insuficientes ({n_boletins}/{minimo})"}
            )
            continue

        # Executa via subprocess (evita importação de módulos)
        log.info("▶ Executando GIRO %s...", codigo)
        try:
            cmd = [
                sys.executable, str(EXECUTOR_SCRIPT),
                str(json_path),
                "--boletins", str(BOLETINS_DIR),
                "--saida", str(SAIDA_DIR),
            ]
            log.info("Comando: %s", " ".join(str(c) for c in cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if result.returncode == 0:
                log.info("✅ GIRO %s finalizado com sucesso (%d boletins encontrados na janela)",
                         codigo, n_boletins)
                resultados["executados"].append(codigo)
            else:
                log.error("❌ GIRO %s falhou (exit %d)", codigo, result.returncode)
                err_log = result.stderr[-500:] if result.stderr else "(sem stderr)"
                resultados["erro"].append({
                    "codigo": codigo,
                    "motivo": f"exit {result.returncode}",
                    "erro": err_log,
                })
        except subprocess.TimeoutExpired:
            log.error("❌ GIRO %s TIMEOUT após 900s", codigo)
            resultados["erro"].append({"codigo": codigo, "motivo": "timeout 900s"})
        except Exception as exc:
            log.exception("Falha crítica ao executar GIRO %s: %s", codigo, exc)
            resultados["erro"].append({"codigo": codigo, "motivo": str(exc)})

    # -------------------------------------------------------------------
    # Resumo final
    # -------------------------------------------------------------------
    log.info("")
    log.info("=" * 60)
    log.info("RESUMO DO ORQUESTRAMENTO — GIRO JANEIRO 2026")
    log.info("=" * 60)
    log.info("Executados : %d", len(resultados["executados"]))
    for c in resultados["executados"]:
        log.info("  ✅ %s", c)
    log.info("Invalidados: %d", len(resultados["invalidados"]))
    for inv in resultados["invalidados"]:
        log.info("  ❌ %s — %s", inv["codigo"], inv["motivo"])
    log.info("Erros      : %d", len(resultados["erro"]))
    for e in resultados["erro"]:
        log.info("  ⚠️  %s — %s", e["codigo"], e["motivo"])
    log.info("=" * 60)
    log.info("Orquestramento de janeiro concluído.")
    log.info("Próximo: verificar montagem dos programas executados.")

    # Salva relatório JSON
    relatorio = {
        "periodo": "janeiro_2026",
        "total_programas": len(jsons),
        "executados": resultados["executados"],
        "invalidados": resultados["invalidados"],
        "erro": resultados["erro"],
        "timestamp": str(date.today()),
    }
    relatorio_path = ROOT / "data" / "processed" / "PRODUCAO_2026" / "orquestrador_jan2026.json"
    relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    relatorio_path.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Relatório salvo em: %s", relatorio_path)


if __name__ == "__main__":
    main()
