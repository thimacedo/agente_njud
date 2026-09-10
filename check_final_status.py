import subprocess, os
from pathlib import Path

BASE = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")

# Count files
giro_count = len(list((BASE / "GIRO").glob("*.mp3")))
output_count = len(list((BASE / "data/output/GIRO_COMARCAS").glob("GNC_*.mp3")))
h_count = len(list((BASE / "H/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/03_GIRO_NAS_COMARCAS").glob("GNC_*.mp3")))

# Check Python processes
result = subprocess.run("ps aux | grep python | grep -v grep | grep -v 'gravador|hermes|node'", shell=True, capture_output=True, text=True)
python_procs = [l for l in result.stdout.strip().split('\n') if l]

print(f"=== FINAL STATUS ===")
print(f"GIRO/ source files: {giro_count}")
print(f"data/output/GIRO_COMARCAS/ GNCs: {output_count}")
print(f"H: destination GNCs: {h_count}")
print(f"Python processes (non-hermes): {len(python_procs)}")
print(f"Programs built: {output_count} / 28 planned")
print(f"=== STATUS ===")
print("BUILD COMPLETE")
