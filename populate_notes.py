import sys
sys.path.insert(0, "src")
from pathlib import Path
import shutil
from collections import defaultdict
from datetime import date
import json

BASE = Path("data/processed/PRODUCAO_2026")
JORNAIS = BASE / "JORNAIS_DIVIDIDOS"
GIRORC = BASE / "GIRO_COMARCAS"

# Load program mapping
from scripts_pipeline.giro.montar_direto import PROGRAMAS

GIRORC.mkdir(parents=True, exist_ok=True)

mapped = 0
for prog, date_str in PROGRAMAS.items():
    mmss = prog
    prog_dir = GIRORC / mmss
    prog_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse date_str to get day/month/year for filename pattern
    d = date.fromisoformat(date_str)
    file_pattern = f"BOLETIM_RADIO_TJRN_{d.day:02d}_{d.month:02d}_{d.year}_B*.mp3"
    
    matching = list(JORNAIS.glob(file_pattern))
    for f in matching:
        dst = prog_dir / f.name
        if not dst.exists():
            shutil.copy2(f, dst)
    
    count = len(list(prog_dir.glob("*.mp3")))
    if count > 0:
        mapped += 1
        print(f"  {prog} ({date_str}): {count} notes")

print(f"\nMapped {mapped} programs with notes")
