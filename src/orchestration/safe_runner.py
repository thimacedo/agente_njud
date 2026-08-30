#!/usr/bin/env python3
"""
Orquestrador unificado do pipeline de boletins/rádio (fire-and-forget).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from config.settings import settings

PROJECT_ROOT = settings.BASE_DIR
RAW_ROOT = settings.BOLETINS_BRUTOS
PROCESSED_ROOT = Path(settings.BOLETINS_CORTADOS)
OUTPUT_ROOT = Path(settings.DIR_OUTPUT)
LOG_DIR = OUTPUT_ROOT / "_logs"
ASSETS_DIR = settings.BASE_DIR / "assets" / "vinhetas"
PLAN_CSV = Path(settings.BOLETINS_CORTADOS).parent / "plano_alocacao.csv"
NJUDS_POR_MES_CSV = Path(settings.BOLETINS_CORTADOS).parent / "njuds_por_mes.csv"
JOURNAL_NJUDS_CSV = Path(settings.BOLETINS_CORTADOS).parent / "jornal_njuds.csv"

SRC_COPIAR = settings.BASE_DIR / "src" / "sync" / "copy.py"
SRC_PLANEJADOR = settings.BASE_DIR / "src" / "plan" / "allocator.py"
SRC_DIVIDIR = settings.BASE_DIR / "src" / "divisor_boletins"
SRC_AUDITORIA = settings.BASE_DIR / "src" / "audit" / "integrity.py"
SRC_SINCRONIZAR = settings.BASE_DIR / "src" / "sync" / "drive.py"


def ensure_dirs() -> None:
    for p in [RAW_ROOT, PROCESSED_ROOT, OUTPUT_ROOT, LOG_DIR]:
        p.mkdir(parents=True, exist_ok=True)


def check_assets() -> list[str]:
    required = [
        "VHT_ABERTURA_BOLETIM.mp3",
        "VHT_PASSAGEM_BOLETIM.mp3",
        "VHT_ENCERRAMENTO_BOLETIM.mp3",
        "VHT_ABERTURA_NJUD.mp3",
        "EFEITO_PASSAGEM_NJUD.mp3",
        "VHT_ENCERRAMENTO_NJUD.mp3",
        "TRILHA_ESCALADA_NJUD.mp3",
    ]
    missing = [x for x in required if not (ASSETS_DIR / x).exists()]
    return missing


def disk_free_gb(path: Path) -> float:
    try:
        usage = shutil.disk_usage(str(path))
        return usage.free / (1024 ** 3)
    except Exception:
        return -1.0


def run_cmd(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        args,
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
        shell=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def map_months_from_batch(batch: str | None) -> list[str]:
    seq = [
        "01 - JAN - 26", "02 - FEV - 26", "03 - MAR - 26",
        "04 - ABR - 26", "05 - MAI - 26", "06 - JUN - 26",
        "07 - JUL - 26", "08 - AGO - 26",
    ]
    abbr_to_ext = {
        "01": "JANEIRO", "02": "FEVEREIRO", "03": "MARÇO",
        "04": "ABRIL", "05": "MAIO", "06": "JUNHO",
        "07": "JULHO", "08": "AGOSTO",
    }

    if batch is None:
        return [abbr_to_ext[m[:2]] for m in seq]

    compact = batch.replace("-", "")
    if len(compact) == 6:
        start_month = compact[4:6]
        end_month = start_month
    elif len(compact) == 12:
        start_month = compact[4:6]
        end_month = compact[10:12]
    else:
        raise ValueError("Batch inválido. Use None, 'YYYY-MM' ou 'YYYY-MM-YYYY-MM'.")

    try:
        start_idx = next(i for i, m in enumerate(seq) if m.startswith(start_month))
        end_idx = next(i for i, m in enumerate(seq) if m.startswith(end_month))
    except StopIteration:
        raise ValueError("Batch inválido ou fora do intervalo jan-ago/2026.")
    if start_idx > end_idx:
        raise ValueError("Batch inválido: mês inicial maior que final.")
    return [abbr_to_ext[m[:2]] for m in seq[start_idx:end_idx + 1]]


def dry_run_plan(months: list[str]) -> dict:
    summary = {"months": {}, "total_files": 0}
    if not PLAN_CSV.exists() or not NJUDS_POR_MES_CSV.exists():
        return summary
    with open(PLAN_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    wanted = set(months)
    for m in wanted:
        count = sum(1 for r in rows if r.get("mes_destino") == m)
        summary["months"][m] = count
        summary["total_files"] += count
    return summary


def etapa_copiar(apply: bool, months: list[str]) -> bool:
    missing = check_assets()
    if missing:
        print(f"✖ Vinhetas faltando: {missing}")
        return False

    print(f"=== [ORQUESTRADOR] 1. Planejamento/Workspace ({'apply' if apply else 'dry-run'}) ===")

    if not PLAN_CSV.exists():
        print(f"✖ Plano não encontrado: {PLAN_CSV}")
        return False

    with open(PLAN_CSV, newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    wanted = {m.upper() for m in months}
    filtered = [r for r in all_rows if str(r.get("mes_destino", "")).strip().upper() in wanted]
    if not filtered:
        print("✖ Plano filtrado vazio para os meses solicitados.")
        return False

    tmp_plan = OUTPUT_ROOT / f"plano_alocacao_{'_'.join(months).replace(' ','_')}.csv"
    with open(tmp_plan, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(filtered[0].keys()))
        writer.writeheader()
        writer.writerows(filtered)
    print(f"Plano filtrado gerado: {tmp_plan} ({len(filtered)} linhas)")

    json_plan = OUTPUT_ROOT / f"plano_{'_'.join(months).replace(' ','_')}.json"
    workspace = OUTPUT_ROOT / "workspace_temp"
    manifest_path = OUTPUT_ROOT / "workspace_temp_manifest.json"

    cmd = [sys.executable, str(SRC_PLANEJADOR)]
    cmd += ["--plan", str(tmp_plan), "--out-plan", str(json_plan)]
    code, out, err = run_cmd(cmd, cwd=PROJECT_ROOT)
    print(out.strip())
    if err.strip():
        print(err.strip())
    if code != 0:
        print("✖ Falha no planejador JSON")
        return False

    cmd = [sys.executable, str(SRC_PLANEJADOR)]
    cmd += ["--exec-plan", str(json_plan), "--workspace", str(workspace)]
    cmd += ["--apply"] if apply else []
    code, out, err = run_cmd(cmd, cwd=PROJECT_ROOT)
    print(out.strip())
    if err.strip():
        print(err.strip())
    if code != 0:
        print("✖ Falha na cópia seletiva para workspace")
        return False

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        total_itens = len(manifest.get("entradas", []))
    except Exception:
        total_itens = len(filtered)
    print(f"✔ Workspace pronto: {workspace} ({total_itens} itens)")
    return True


def etapa_dividir(apply: bool, months: list[str]) -> bool:
    print("=== [ORQUESTRADOR] 2. Divisão CABEÇA/CORPO ===")
    if not RAW_ROOT.exists():
        print(f"✖ Entrada não existe: {RAW_ROOT}")
        return False

    cmd = [
        sys.executable, "-m", "divisor_boletins", "dividir",
        str(RAW_ROOT), str(PROCESSED_ROOT),
        "--log-dir", str(LOG_DIR),
    ]
    cmd += ["--apply"] if apply else ["--dry-run"]
    print(f"• Processando todos os meses em: {RAW_ROOT}")
    code, out, err = run_cmd(cmd, cwd=SRC_DIVIDIR.parent)
    print(out.strip())
    if err.strip():
        print(err.strip())
    return code == 0


def etapa_auditoria() -> bool:
    print("=== [ORQUESTRADOR] 3. Auditoria de cortes ===")
    if not PROCESSED_ROOT.exists():
        print("✖ Pasta de cortes não existe")
        return False
    relatorio = OUTPUT_ROOT / "relatorio_auditoria.csv"
    cmd = [sys.executable, str(SRC_AUDITORIA), str(PROCESSED_ROOT), str(relatorio)]
    code, out, err = run_cmd(cmd, cwd=PROJECT_ROOT)
    print(out.strip())
    if err.strip():
        print(err.strip())
    if code != 0:
        print("✖ Falha na auditoria")
        return False
    taxa = taxa_corte(relatorio)
    print(f"Taxa de CORTADO: {taxa:.2%}")
    if taxa > 0.10:
        print("ALERTA: taxa de CORTADO > 10%, montagem bloqueada.")
        return False
    return True


def taxa_corte(relatorio: Path) -> float:
    try:
        with open(relatorio, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return 0.0
        cortados = sum(1 for r in rows if str(r.get("classificacao", "")).strip().upper() == "CORTADO")
        return cortados / len(rows)
    except Exception:
        return 0.0


def etapa_montar() -> bool:
    print("=== [ORQUESTRADOR] 4. Montagem dos jornais ===")
    cmd = [
        sys.executable, "-m", "divisor_boletins", "montar",
        str(PROCESSED_ROOT), str(OUTPUT_ROOT),
        "--log-dir", str(LOG_DIR),
    ]
    code, out, err = run_cmd(cmd, cwd=SRC_DIVIDIR.parent)
    print(out.strip())
    if err.strip():
        print(err.strip())
    return code == 0


def etapa_sync() -> None:
    print("=== [ORQUESTRADOR] 5. Sincronização com Drive ===")
    if not SRC_SINCRONIZAR.exists():
        print("⚠ Script de sincronização não encontrado; pulando.")
        return
    code, out, err = run_cmd([sys.executable, str(SRC_SINCRONIZAR)], cwd=PROJECT_ROOT)
    print(out.strip())
    if err.strip():
        print(err.strip())
    if code != 0:
        print("⚠ Sincronização falhou; verifique o Drive/pendências.")


def write_report(start: float, months: list[str], ok: bool) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / "resumo_execucao.txt"
    outputs = sorted([p for p in OUTPUT_ROOT.glob("*.mp3")])
    pendentes = OUTPUT_ROOT / "pendentes_drive.json"
    pendentes_list = []
    if pendentes.exists():
        try:
            pendentes_list = json.loads(pendentes.read_text(encoding="utf-8"))
        except Exception:
            pendentes_list = []
    lines = [
        "RESUMO FINAL",
        "=" * 50,
        f"Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Lote: {months[0] if len(months)==1 else months[0]+' a '+months[-1]}",
        f"Conclusão: {'OK' if ok else 'FALHA'}",
        f"Tempo total: {time.time()-start:.2f}s",
        "",
        "Artefatos gerados:",
        f"  - Jornais: {len(outputs)}",
        "",
        "Pendentes Drive:",
        f"  - {len(pendentes_list)}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Orquestrador do pipeline de boletins/rádio")
    p.add_argument("--batch", default=None, help="Mês (YYYY-MM) ou intervalo (YYYY-MM-YYYY-MM)")
    p.add_argument("--dry-run", action="store_true", default=False, help="Apenas simula")
    p.add_argument("--apply", action="store_true", default=False, help="Executa de fato")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run and not args.apply:
        args.dry_run = True

    ensure_dirs()
    months = map_months_from_batch(args.batch)
    if not months:
        print("✖ Batch inválido ou fora do intervalo jan-ago/2026.")
        return 1

    pre = dry_run_plan(months)
    print(f"Planejado: {pre['total_files']} arquivo(s) para {months}")

    if args.dry_run:
        print("=== MODO DRY-RUN ===")
        etapa_copiar(False, months)
        print("Dry-run finalizado. Rode com --apply para executar.")
        return 0

    start = time.time()
    ok = True
    ok = etapa_copiar(True, months) and ok
    if not ok:
        print("✖ Pipeline abortado na etapa de cópia.")
        write_report(start, months, False)
        return 2

    ok = etapa_dividir(True, months) and ok
    if not ok:
        print("✖ Pipeline abortado na etapa de divisão.")
        write_report(start, months, False)
        return 3

    ok = etapa_auditoria() and ok
    if not ok:
        print("✖ Pipeline abortado pela auditoria.")
        write_report(start, months, False)
        return 4

    ok = etapa_montar() and ok
    if not ok:
        print("✖ Pipeline abortado na montagem.")
        write_report(start, months, False)
        return 5

    etapa_sync()
    path = write_report(start, months, ok)
    print(f"=== Pipeline finalizado. Relatório: {path} ===")
    return 0 if ok else 6


if __name__ == "__main__":
    raise SystemExit(main())
