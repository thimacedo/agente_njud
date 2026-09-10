import sys
sys.path.insert(0, "src")
from pathlib import Path
import shutil
from datetime import date

BASE = Path("data/processed/PRODUCAO_2026")
JORNAIS = BASE / "JORNAIS_DIVIDIDOS"
GIRORC = BASE / "GIRO_COMARCAS"

from scripts_pipeline.giro.montar_direto import PROGRAMAS

GIRORC.mkdir(parents=True, exist_ok=True)

# Build reverse mapping: source date string -> programs
# JORNAIS files: BOLETIM_RADIO_TJRN_{DD}_{MM}_{YYYY}_B*.mp3
# PROGRAMAS: {code: "YYYY-MM-DD"}

# Group programs by source date
date_to_programs = {}
for prog, date_str in PROGRAMAS.items():
    d = date.fromisoformat(date_str)
    # File naming: DD_MM_YYYY
    file_date_str = f"{d.day:02d}_{d.month:02d}_{d.year}"
    if file_date_str not in date_to_programs:
        date_to_programs[file_date_str] = []
    date_to_programs[file_date_str].append(prog)

print(f"Date groups: {len(date_to_programs)}")

# For each date group, copy matching BOLETIM files
mapped_count = 0
for file_date_str, programs in date_to_programs.items():
    # Find all BOLETIM files matching this date
    matching = list(JORNAIS.glob(f"BOLETIM_RADIO_TJRN_{file_date_str}_B*.mp3"))
    
    for prog in programs:
        prog_dir = GIRORC / prog
        prog_dir.mkdir(parents=True, exist_ok=True)
        
        copied = 0
        for f in matching:
            dst = prog_dir / f.name
            if not dst.exists():
                shutil.copy2(f, dst)
                copied += 1
        
        total = len(list(prog_dir.glob("*.mp3")))
        if total > 0:
            mapped_count += 1
            print(f"  {prog} ({file_date_str}): {total} notes (copied {copied})")

print(f"\nMapped {mapped_count} programs")
