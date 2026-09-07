#!/usr/bin/env python3
import time
from pathlib import Path
from datetime import datetime

from config.settings import settings

ROOT = settings.BASE_DIR
JORNAIS = settings.BOLETINS_BRUTOS
PROCESSED = Path(settings.BOLETINS_CORTADOS)
OUTPUT = Path(settings.DIR_OUTPUT)
LOG = OUTPUT / "_logs" / "monitor_paralelo.txt"
AUDIT_CSV = OUTPUT / "relatorio_auditoria.csv"
AUDIT_JSON = PROCESSED / "AUDIT_cortes.json"


def count_mp3(p: Path):
    return sum(1 for _ in p.rglob("*.mp3")) if p.exists() else 0


def count_cabeca_corpo(p: Path):
    if not p.exists():
        return 0, 0
    cabeca = sum(1 for _ in p.rglob("*_CABECA.mp3"))
    corpo = sum(1 for _ in p.rglob("*_CORPO.mp3"))
    return cabeca, corpo


def audit_summary():
    try:
        if AUDIT_CSV.exists():
            import csv
            with open(AUDIT_CSV, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if not rows:
                return "audit=empty"
            total = len(rows)
            cortados = sum(1 for r in rows if str(r.get("classificacao", "")).strip().upper() == "CORTADO")
            possivel = sum(1 for r in rows if "ALUCINACAO" in str(r.get("classificacao", "")).strip().upper())
            ok = total - cortados - possivel
            return f"audit={total} (OK={ok} CORTADO={cortados} POSSIVEL_ALUCINACAO={possivel})"
        if AUDIT_JSON.exists():
            import json
            data = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
            total = int(data.get("total_arquivos", 0))
            erros = int(data.get("erros", 0))
            processados = int(data.get("processados", 0))
            resultados = data.get("resultados", [])
            if resultados:
                cortados = sum(1 for r in resultados if str(r.get("status", "")).strip().upper() == "CORTADO")
                possivel = sum(1 for r in resultados if str(r.get("status", "")).strip().upper() == "POSSIVEL_ALUCINACAO")
                ok = processados - cortados - possivel
                return f"audit_json={processados}/{total} OK={ok} CORTADO={cortados} POSSIVEL_ALUCINACAO={possivel} erros={erros}"
            return f"audit_json={processados}/{total} erros={erros}"
        return "audit=missing"
    except Exception as e:
        return f"audit=error:{e}"


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    last_j = last_p = last_o = None
    while True:
        j = count_mp3(JORNAIS)
        p = count_mp3(PROCESSED)
        o = count_mp3(OUTPUT)
        cabeca, corpo = count_cabeca_corpo(PROCESSED)
        audit = audit_summary()
        ts = datetime.now().strftime("%H:%M:%S")
        delta_j = f"+{j - last_j}" if last_j is not None else "init"
        delta_p = f"+{p - last_p}" if last_p is not None else "init"
        delta_o = f"+{o - last_o}" if last_o is not None else "init"
        last_j, last_p, last_o = j, p, o
        line = (
            f"[{ts}] "
            f"JORNAIS={j} ({delta_j}) | PROCESSED={p} ({delta_p}) | OUTPUT={o} ({delta_o}) | "
            f"CABECA={cabeca} CORPO={corpo} | {audit}"
        )
        print(line, flush=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        time.sleep(30)

if __name__ == "__main__":
    main()
