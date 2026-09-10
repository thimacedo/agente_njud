import shutil, os
from pathlib import Path

BASE = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
OUTPUT = BASE / "data/output/GIRO_COMARCAS"
H_DEST = BASE / "H/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/03_GIRO_NAS_COMARCAS"

H_DEST.mkdir(parents=True, exist_ok=True)
synced = 0
for gnc in OUTPUT.glob("GNC_*.mp3"):
    dest_f = H_DEST / gnc.name
    shutil.copy2(str(gnc), str(dest_f))
    synced += 1
    print(f"  Synced: {gnc.name} ({gnc.stat().st_size / 1024 / 1024:.1f} MB)")

print(f"\nSynced {synced} GNC files to H:")
print(f"  H: destination now has {len(list(H_DEST.glob('GNC_*.mp3')))} GNC files")
