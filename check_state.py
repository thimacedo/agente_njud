import json, os, sys
from pathlib import Path

div = Path('data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS')
pastas = sorted([d for d in div.iterdir() if d.is_dir()])
print(f"Total de pastas NJUD em JORNAIS_DIVIDIDOS: {len(pastas)}")

com_cortes = 0
sem_cortes = 0
for p in pastas:
    arquivos = list(p.glob('*_CABECA.mp3'))
    if arquivos:
        com_cortes += 1
    else:
        sem_cortes += 1

print(f"Com cortes (_CABECA): {com_cortes}")
print(f"Sem cortes: {sem_cortes}")
print()

print("=== NJUDs SEM cortes ===")
for p in pastas:
    arquivos = list(p.glob('*_CABECA.mp3'))
    if not arquivos:
        print(f"  {p.name}")

print()
print("=== Amostra de NJUDs com cortes (primeiros 5) ===")
for p in pastas[:5]:
    ce = list(p.glob('*_CABECA.mp3'))
    co = list(p.glob('*_CORPO.mp3'))
    orig = list(p.glob('*.mp3'))
    orig_sem_corte = [a for a in orig if '_CABECA' not in a.name and '_CORPO' not in a.name]
    print(f"  {p.name}: orig={len(orig_sem_corte)} cabe={len(ce)} corpo={len(co)}")

print()
print("=== Resumo estado_por_arquivo ===")
estado = Path('data/processed/PRODUCAO_2026/estado_por_arquivo')
counts = {}
nj_nao_ok = set()
for f in estado.glob('*.json'):
    d = json.loads(f.read_text())
    s = d.get('status','?')
    counts[s] = counts.get(s,0)+1
    if s not in ('OK','ESGOTADO_ACEITO'):
        nj_nao_ok.add(d.get('njud','?'))

for k,v in sorted(counts.items()):
    print(f"  {k}: {v}")
print(f"Total: {sum(counts.values())}")
print(f"NJUDs com pelo menos 1 arquivo nao-OK: {len(nj_nao_ok)}")
print(f"  NJUDs: {sorted(nj_nao_ok)}")
