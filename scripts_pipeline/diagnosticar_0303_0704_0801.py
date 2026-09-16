#!/usr/bin/env python3
"""
diagnosticar_0303_0704_0801.py — Verifica os ERROs de 0303, identifica faltantes de 0704/0801.
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core.processamento.processar_boletim import ConfigPrograma, listar_tarefas_pendentes

H_BASE = Path("H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO")
ROOT = Path(__file__).resolve().parent.parent

print("=" * 60)
print("  DIAGNÓSTICO: 0303 (ERROs) + 0704/0801 (faltantes)")
print("=" * 60)

# === 0303: listar ERROs ===
print("\n=== 0303 — ARQUIVOS COM ERRO ===")
state_0303 = ROOT / "GIRO" / "state" / "0303"
erros_0303 = []
for f in sorted(state_0303.glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    if d.get("status") == "ERRO":
        erros_0303.append((f.name, d))
        print(f"\n  {f.name}")
        print(f"    erro: {d.get('erro', 'N/A')}")
        print(f"    tentativas: {len(d.get('tentativas', []))}")
        for t in d.get("tentativas", []):
            print(f"      - {t.get('estrategia')}: {t.get('resultado')} @ {t.get('timestamp')}")

print(f"\nTotal ERROs em 0303: {len(erros_0303)}")

# === 0704: verificar faltantes por boletim ===
print("\n=== 0704 — FALTANTES POR BOLETIM ===")
state_0704 = ROOT / "GIRO" / "state" / "0704"
cortés_0704 = list((ROOT / "GIRO" / "output" / "0704" / "cortes").glob("*"))
print(f"Cortes existentes: {len(cortés_0704)} dirs")

by_boletim = {}
for f in state_0704.glob("*.json"):
    d = json.loads(f.read_text(encoding="utf-8"))
    m = __import__("re").search(r"_B(\d+)_", f.stem)
    if m:
        n = int(m.group(1))
        if n not in by_boletim:
            by_boletim[n] = {"CABE": False, "CORP": False, "statuses": []}
        stem = f.stem
        if "_CABECA" in stem:
            by_boletim[n]["CABE"] = True
        elif "_CORPO" in stem:
            by_boletim[n]["CORP"] = True
        by_boletim[n]["statuses"].append(d["status"])

for n in sorted(by_boletim, key=int):
    info = by_boletim[n]
    falta = []
    if not info["CABE"]:
        falta.append("CABEÇA")
    if not info["CORP"]:
        falta.append("CORPO")
    if falta:
        print(f"  B{n:02d}: FALTA {', '.join(falta)} | estados: {info['statuses']}")
    else:
        print(f"  B{n:02d}: OK | {info['statuses']}")

# === 0801: verificar faltantes por boletim ===
print("\n=== 0801 — FALTANTES POR BOLETIM ===")
state_0801 = ROOT / "GIRO" / "state" / "0801"
cortés_0801 = list((ROOT / "GIRO" / "output" / "0801" / "cortes").glob("*"))
print(f"Cortes existentes: {len(cortés_0801)} dirs")

by_boletim_0801 = {}
for f in state_0801.glob("*.json"):
    d = json.loads(f.read_text(encoding="utf-8"))
    m = __import__("re").search(r"_B(\d+)_", f.stem)
    if m:
        n = int(m.group(1))
        if n not in by_boletim_0801:
            by_boletim_0801[n] = {"CABE": False, "CORP": False, "statuses": []}
        stem = f.stem
        if "_CABECA" in stem:
            by_boletim_0801[n]["CABE"] = True
        elif "_CORPO" in stem:
            by_boletim_0801[n]["CORP"] = True
        by_boletim_0801[n]["statuses"].append(d["status"])

for n in sorted(by_boletim_0801, key=int):
    info = by_boletim_0801[n]
    falta = []
    if not info["CABE"]:
        falta.append("CABEÇA")
    if not info["CORP"]:
        falta.append("CORPO")
    if falta:
        print(f"  B{n:02d}: FALTA {', '.join(falta)} | estados: {info['statuses']}")
    else:
        print(f"  B{n:02d}: OK | {info['statuses']}")

# === Responder: quantos faltam para reprocessar ===
print("\n=== RESUMO: O QUE REPROCESSAR ===")
print(f"0303: {len(erros_0303)} ERROs → reprocessar esses arquivos")
print(f"0704: {sum(1 for n in by_boletim if not by_boletim[n]['CABE'] or not by_boletim[n]['CORP'])} boletins com faltante")
print(f"0801: {sum(1 for n in by_boletim_0801 if not by_boletim_0801[n]['CABE'] or not by_boletim_0801[n]['CORP'])} boletins com faltante")
